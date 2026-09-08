import argparse
import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from gamani_collector.collect_listings import LIST_QUERY, collect_listing_page
from gamani_collector.collect_vehicle_data import collect_vehicle_data
from gamani_collector.database import create_database_engine
from gamani_collector.http_client import EncarClient
from gamani_collector.models.database import CollectionJob, CollectionJobItem, Vehicle

PAGE_SIZE = 500
LOCK_NAME = "gamani-bulk-collector"


def _manufacturer_filters(payload: dict[str, Any]) -> dict[str, str]:
    filters: dict[str, str] = {}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            action = value.get("Action")
            expression = value.get("Expression")
            name = value.get("DisplayValue")
            if (
                isinstance(action, str)
                and isinstance(expression, str)
                and expression.startswith("Manufacturer.")
                and isinstance(name, str)
            ):
                filters[name] = action
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload.get("iNav", {}))
    return filters


def fetch_manufacturer_filters() -> dict[str, str]:
    with EncarClient() as client:
        payload = client.get_json(
            "/search/car/list/mobile",
            params={
                "count": "true",
                "q": LIST_QUERY,
                "sr": "|MobileModifiedDate|0|1",
                "inav": "|Metadata|Sort",
                "cursor": "",
            },
        )
    filters = _manufacturer_filters(payload)
    if not filters:
        raise RuntimeError("manufacturer metadata was not found")
    return filters


def _create_job(
    session: Session,
    *,
    mode: str,
    manufacturer: str | None,
    query: str,
    page_size: int,
    max_vehicles: int | None,
) -> CollectionJob:
    job = CollectionJob(
        mode=mode,
        manufacturer=manufacturer,
        query_expression=query,
        page_size=page_size,
        max_vehicles=max_vehicles,
        status="RUNNING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _resume_job(session: Session) -> CollectionJob:
    job = session.scalar(
        select(CollectionJob)
        .where(CollectionJob.status.in_(["RUNNING", "FAILED"]))
        .order_by(CollectionJob.id.desc())
        .limit(1)
    )
    if job is None:
        raise RuntimeError("이어갈 수집 작업이 없습니다")
    job.status = "RUNNING"
    job.error_message = None
    job.finished_at = None
    session.commit()
    return job


def _page_hash(listing_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(listing_ids).encode()).hexdigest()


def _pending_unique_ids(
    session: Session, job_id: int, listing_ids: list[str], offset: int
) -> list[str]:
    for listing_id in listing_ids:
        session.execute(
            insert(CollectionJobItem)
            .values(
                job_id=job_id,
                source_listing_id=listing_id,
                discovered_offset=offset,
            )
            .on_conflict_do_nothing()
        )
    session.commit()
    return list(
        session.scalars(
            select(CollectionJobItem.source_listing_id).where(
                CollectionJobItem.job_id == job_id,
                CollectionJobItem.source_listing_id.in_(listing_ids),
                CollectionJobItem.status.in_(["PENDING", "FAILED"]),
            )
        )
    )


def _finish_items(session: Session, job_id: int, listing_ids: list[str]) -> int:
    vehicles = {
        vehicle.source_listing_id: vehicle
        for vehicle in session.scalars(
            select(Vehicle).where(Vehicle.source_listing_id.in_(listing_ids))
        )
    }
    for item in session.scalars(
        select(CollectionJobItem).where(
            CollectionJobItem.job_id == job_id,
            CollectionJobItem.source_listing_id.in_(listing_ids),
        )
    ):
        vehicle = vehicles.get(item.source_listing_id)
        if vehicle is None:
            item.status = "NOT_FOUND"
        elif vehicle.insurance_status in ("PENDING", "FAILED"):
            item.status = "FAILED"
        else:
            item.status = "COMPLETED"
        item.updated_at = datetime.now(UTC)
    session.commit()
    return session.scalar(
        select(func.count()).select_from(CollectionJobItem).where(
            CollectionJobItem.job_id == job_id,
            CollectionJobItem.status.in_(["COMPLETED", "NOT_FOUND"]),
        )
    ) or 0


def _mark_failed(engine: Engine, job_id: int, error: BaseException) -> None:
    with Session(engine) as session:
        job = session.get(CollectionJob, job_id)
        if job is not None:
            job.status = "FAILED"
            job.error_message = f"{type(error).__name__}: {error}"[:500]
            job.finished_at = datetime.now(UTC)
            session.commit()


def run_collection(
    *,
    limit: int | None = None,
    manufacturer: str | None = None,
    resume: bool = False,
    page_size: int = PAGE_SIZE,
) -> CollectionJob:
    if not 1 <= page_size <= PAGE_SIZE:
        raise ValueError("page_size must be between 1 and 500")
    if limit is not None and not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    engine = create_database_engine()
    with engine.connect() as lock_connection:
        locked = lock_connection.scalar(
            text("SELECT pg_try_advisory_lock(hashtext(:name))"), {"name": LOCK_NAME}
        )
        if not locked:
            raise RuntimeError("다른 전체 수집 작업이 이미 실행 중입니다")

        with Session(engine) as job_session:
            if resume:
                job = _resume_job(job_session)
            elif manufacturer is not None:
                filters = fetch_manufacturer_filters()
                if manufacturer not in filters:
                    choices = ", ".join(sorted(filters))
                    raise ValueError(
                        f"알 수 없는 제조사입니다: {manufacturer}. 선택 가능: {choices}"
                    )
                job = _create_job(
                    job_session,
                    mode="MANUFACTURER",
                    manufacturer=manufacturer,
                    query=filters[manufacturer],
                    page_size=page_size,
                    max_vehicles=None,
                )
            elif limit is not None:
                job = _create_job(
                    job_session,
                    mode="LIMIT",
                    manufacturer=None,
                    query=LIST_QUERY,
                    page_size=page_size,
                    max_vehicles=limit,
                )
            else:
                raise ValueError("limit, manufacturer, resume 중 하나가 필요합니다")
            job_id = job.id
        try:
            while True:
                with Session(engine) as session:
                    current = session.get(CollectionJob, job_id)
                    if current is None:
                        raise RuntimeError(f"collection job {job_id} was not found")
                    target = current.expected_count
                    if current.max_vehicles is not None:
                        target = (
                            current.max_vehicles
                            if target is None
                            else min(target, current.max_vehicles)
                        )
                    limit_reached = (
                        current.max_vehicles is not None
                        and current.processed_count >= current.max_vehicles
                    )
                    manufacturer_exhausted = (
                        current.max_vehicles is None
                        and target is not None
                        and current.next_offset >= target
                    )
                    if limit_reached or manufacturer_exhausted:
                        current.status = "SUCCEEDED"
                        current.finished_at = datetime.now(UTC)
                        session.commit()
                        session.refresh(current)
                        return current
                    request_size = current.page_size
                    if current.max_vehicles is not None:
                        request_size = min(
                            request_size,
                            current.max_vehicles - current.processed_count,
                        )
                    elif target is not None:
                        request_size = min(request_size, target - current.next_offset)
                    offset = current.next_offset
                    query = current.query_expression
                    shard_key = current.manufacturer or "LIMIT"
                    previous_hash = current.last_page_hash

                page = collect_listing_page(
                    limit=request_size,
                    offset=offset,
                    query=query,
                    shard_key=shard_key,
                )
                listing_ids = [vehicle.source_listing_id for vehicle in page.vehicles]
                if not listing_ids:
                    if offset == 0:
                        raise RuntimeError("첫 목록 페이지가 0건이라 안전하게 중단했습니다")
                    with Session(engine) as session:
                        current = session.get(CollectionJob, job_id)
                        if current is None:
                            raise RuntimeError(f"collection job {job_id} was not found")
                        current.status = "SUCCEEDED"
                        current.finished_at = datetime.now(UTC)
                        session.commit()
                        session.refresh(current)
                        return current

                current_hash = _page_hash(listing_ids)
                if current_hash == previous_hash:
                    raise RuntimeError(f"목록 페이지가 반복되어 offset {offset}에서 중단했습니다")

                with Session(engine) as session:
                    pending_ids = _pending_unique_ids(session, job_id, listing_ids, offset)

                if pending_ids:
                    collect_vehicle_data(pending_ids)

                with Session(engine) as session:
                    processed_count = _finish_items(session, job_id, pending_ids)
                    current = session.get(CollectionJob, job_id)
                    if current is None:
                        raise RuntimeError(f"collection job {job_id} was not found")
                    if current.expected_count is None:
                        current.expected_count = page.total_count
                    current.next_offset += len(listing_ids)
                    current.processed_count = processed_count
                    current.last_page_hash = current_hash
                    session.commit()
                    failed_count = session.scalar(
                        select(func.count()).select_from(CollectionJobItem).where(
                            CollectionJobItem.job_id == job_id,
                            CollectionJobItem.status == "FAILED",
                        )
                    ) or 0
                    print(
                        f"작업 {job_id}: {current.processed_count}대 처리, "
                        f"다음 offset {current.next_offset}, 예상 전체 {page.total_count}대"
                    )
                    if failed_count:
                        raise RuntimeError(
                            f"offset {offset} 상세 수집에서 {failed_count}대가 실패했습니다"
                        )
        except (Exception, KeyboardInterrupt) as error:
            _mark_failed(engine, job_id, error)
            raise
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(hashtext(:name))"), {"name": LOCK_NAME}
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="500대 시험 또는 제조사별 수집을 실행합니다.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--limit", type=int, help="최대 500대 시험 수집")
    group.add_argument("--manufacturer", help="엔카 메타데이터의 제조사 이름")
    group.add_argument("--resume", action="store_true", help="마지막 중단 작업 이어서 실행")
    group.add_argument(
        "--list-manufacturers", action="store_true", help="선택 가능한 제조사 이름 출력"
    )
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    args = parser.parse_args()

    if args.list_manufacturers:
        for name in sorted(fetch_manufacturer_filters()):
            print(name)
        return

    job = run_collection(
        limit=args.limit,
        manufacturer=args.manufacturer,
        resume=args.resume,
        page_size=args.page_size,
    )
    print(f"수집 작업 {job.id} 완료: {job.processed_count}대")


if __name__ == "__main__":
    main()
