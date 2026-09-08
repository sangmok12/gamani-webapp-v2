import argparse
import hashlib
import json
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gamani_collector.collect_listings import collect_listings
from gamani_collector.database import create_database_engine
from gamani_collector.http_client import EncarClient, HttpResult
from gamani_collector.logging_config import configure_logging
from gamani_collector.models.database import (
    CrawlRequest,
    CrawlRun,
    InsuranceRecord,
    OptionCatalog,
    Vehicle,
    VehicleIdentifier,
    VehicleListing,
    VehicleSearchDocument,
)
from gamani_collector.models.detail import SafeInsuranceRecord, SafeVehicleDetail
from gamani_collector.rate_limiter import RateLimiter
from gamani_collector.settings import get_settings


def _upsert_vehicle(
    session: Session,
    listing: VehicleListing,
    detail: SafeVehicleDetail,
    now: datetime,
) -> int:
    values = {
        "canonical_source_id": detail.canonical_source_id,
        "vehicle_type": detail.vehicle_type,
        "manufacturer": listing.manufacturer,
        "model_group": listing.model_group,
        "model": listing.model,
        "badge": listing.badge,
        "badge_detail": listing.badge_detail,
        "transmission": listing.transmission,
        "fuel_type": listing.fuel_type,
        "year_month": listing.year_month,
        "form_year": listing.form_year,
        "color": listing.color,
        "option_codes": detail.option_codes(),
        "last_seen_at": now,
    }
    statement = insert(Vehicle).values(**values)
    update_values = {
        key: getattr(statement.excluded, key) for key in values if key != "canonical_source_id"
    }
    vehicle_id = session.scalar(
        statement.on_conflict_do_update(
            index_elements=[Vehicle.canonical_source_id],
            set_=update_values,
        ).returning(Vehicle.id)
    )
    if vehicle_id is None:
        raise RuntimeError("vehicle upsert did not return an id")
    return vehicle_id


def _upsert_identifier(
    session: Session,
    vehicle_id: int,
    detail: SafeVehicleDetail,
    now: datetime,
) -> None:
    statement = insert(VehicleIdentifier).values(
        vehicle_id=vehicle_id,
        vehicle_no=detail.vehicle_no,
        last_verified_at=now,
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[VehicleIdentifier.vehicle_id],
            set_={
                "vehicle_no": statement.excluded.vehicle_no,
                "last_verified_at": statement.excluded.last_verified_at,
            },
        )
    )


def _ensure_option_catalog(session: Session, option_codes: list[str], now: datetime) -> None:
    for code in option_codes:
        statement = insert(OptionCatalog).values(source_code=code, last_seen_at=now)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[OptionCatalog.source_code],
                set_={"last_seen_at": statement.excluded.last_seen_at},
            )
        )


def _insurance_values(record: SafeInsuranceRecord) -> dict[str, object]:
    return record.model_dump()


def _content_hash(values: dict[str, object]) -> str:
    encoded = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _upsert_insurance(
    session: Session,
    vehicle_id: int,
    *,
    status: str,
    record: SafeInsuranceRecord | None,
    error_code: str | None,
    now: datetime,
) -> InsuranceRecord:
    values = _insurance_values(record) if record is not None else {}
    statement = insert(InsuranceRecord).values(
        vehicle_id=vehicle_id,
        status=status,
        **values,
        content_hash=_content_hash(values) if record is not None else None,
        error_code=error_code,
        observed_at=now,
    )
    update_values = {
        column.name: getattr(statement.excluded, column.name)
        for column in InsuranceRecord.__table__.columns
        if column.name != "vehicle_id"
    }
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[InsuranceRecord.vehicle_id],
            set_=update_values,
        )
    )
    return InsuranceRecord(
        vehicle_id=vehicle_id,
        status=status,
        **values,
        content_hash=_content_hash(values) if record is not None else None,
        error_code=error_code,
        observed_at=now,
    )


def _upsert_search_document(
    session: Session,
    listing: VehicleListing,
    vehicle_id: int,
    detail: SafeVehicleDetail,
    insurance: InsuranceRecord,
    now: datetime,
) -> None:
    values = {
        "listing_id": listing.source_listing_id,
        "vehicle_id": vehicle_id,
        "manufacturer": listing.manufacturer,
        "model_group": listing.model_group,
        "model": listing.model,
        "badge": listing.badge,
        "badge_detail": listing.badge_detail,
        "form_year": listing.form_year,
        "mileage_km": listing.mileage_km,
        "price_manwon": listing.price_manwon,
        "fuel_type": listing.fuel_type,
        "transmission": listing.transmission,
        "office_city_state": listing.office_city_state,
        "option_codes": detail.option_codes(),
        "insurance_status": insurance.status,
        "owner_change_count": insurance.owner_change_count,
        "vehicle_no_change_count": insurance.vehicle_no_change_count,
        "government_use_count": insurance.government_use_count,
        "business_use_count": insurance.business_use_count,
        "loan_use_count": insurance.loan_use_count,
        "total_loss_count": insurance.total_loss_count,
        "flood_total_loss_count": insurance.flood_total_loss_count,
        "updated_at": now,
    }
    statement = insert(VehicleSearchDocument).values(**values)
    update_values = {key: getattr(statement.excluded, key) for key in values if key != "listing_id"}
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[VehicleSearchDocument.listing_id],
            set_=update_values,
        )
    )


def _add_request(
    session: Session,
    run_id: int,
    endpoint: str,
    source_id: str,
    result: HttpResult | None,
    status: str,
    error: Exception | None = None,
) -> None:
    http_status = None
    if isinstance(error, httpx.HTTPStatusError):
        http_status = error.response.status_code
    session.add(
        CrawlRequest(
            run_id=run_id,
            endpoint_type=endpoint,
            source_entity_id=source_id,
            http_status=result.status_code if result is not None else http_status,
            attempt_count=result.attempt_count if result is not None else 1,
            elapsed_ms=result.elapsed_ms if result is not None else None,
            result_status=status,
            error_code=type(error).__name__ if error is not None else None,
            error_message=str(error)[:500] if error is not None else None,
        )
    )


def collect_vehicle_data(listing_ids: list[str]) -> dict[str, int]:
    settings = get_settings()
    logger = configure_logging(settings.log_level)
    engine = create_database_engine()
    counters = {
        "requested": len(listing_ids),
        "completed": 0,
        "insurance_available": 0,
        "not_found": 0,
        "failed": 0,
    }

    with Session(engine) as session:
        run = CrawlRun(
            job_type="VEHICLE_DETAILS",
            shard_key="CANARY",
            status="RUNNING",
            expected_count=len(listing_ids),
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with EncarClient(
        rate_limiter=RateLimiter(settings.requests_per_second),
        logger=logger,
    ) as client:
        for listing_id in listing_ids:
            now = datetime.now(UTC)
            with Session(engine) as session:
                listing = session.get(VehicleListing, listing_id)
                if listing is None:
                    counters["failed"] += 1
                    continue

                try:
                    detail_result = client.get_json_result(f"/v1/readside/vehicle/{listing_id}")
                    detail = SafeVehicleDetail.model_validate(detail_result.data)
                    _add_request(session, run_id, "DETAIL", listing_id, detail_result, "SUCCEEDED")
                except httpx.HTTPStatusError as error:
                    not_found = error.response.status_code == 404
                    listing.resolution_status = "NOT_FOUND" if not_found else "RETRY"
                    _add_request(
                        session,
                        run_id,
                        "DETAIL",
                        listing_id,
                        None,
                        "NOT_AVAILABLE" if not_found else "FAILED",
                        error,
                    )
                    session.commit()
                    if not_found:
                        counters["not_found"] += 1
                    else:
                        counters["failed"] += 1
                    continue
                except Exception as error:
                    listing.resolution_status = "RETRY"
                    _add_request(session, run_id, "DETAIL", listing_id, None, "FAILED", error)
                    session.commit()
                    counters["failed"] += 1
                    continue

                vehicle_id = _upsert_vehicle(session, listing, detail, now)
                _upsert_identifier(session, vehicle_id, detail, now)
                _ensure_option_catalog(session, detail.option_codes(), now)
                listing.vehicle_id = vehicle_id
                listing.resolution_status = "RESOLVED"

                insurance_result: HttpResult | None = None
                insurance_error: Exception | None = None
                insurance_model: SafeInsuranceRecord | None = None
                insurance_status = "AVAILABLE"
                try:
                    insurance_result = client.get_json_result(
                        f"/v1/readside/record/vehicle/{detail.canonical_source_id}/open"
                    )
                    insurance_model = SafeInsuranceRecord.model_validate(insurance_result.data)
                    _add_request(
                        session,
                        run_id,
                        "INSURANCE",
                        detail.canonical_source_id,
                        insurance_result,
                        "SUCCEEDED",
                    )
                    counters["insurance_available"] += 1
                except httpx.HTTPStatusError as error:
                    insurance_error = error
                    insurance_status = (
                        "NOT_AVAILABLE" if error.response.status_code == 404 else "FAILED"
                    )
                    if insurance_status == "FAILED":
                        counters["failed"] += 1
                    _add_request(
                        session,
                        run_id,
                        "INSURANCE",
                        detail.canonical_source_id,
                        None,
                        insurance_status,
                        error,
                    )
                except Exception as error:
                    insurance_error = error
                    insurance_status = "FAILED"
                    counters["failed"] += 1
                    _add_request(
                        session,
                        run_id,
                        "INSURANCE",
                        detail.canonical_source_id,
                        None,
                        "FAILED",
                        error,
                    )

                insurance = _upsert_insurance(
                    session,
                    vehicle_id,
                    status=insurance_status,
                    record=insurance_model,
                    error_code=type(insurance_error).__name__ if insurance_error else None,
                    now=now,
                )
                _upsert_search_document(session, listing, vehicle_id, detail, insurance, now)
                session.commit()
                counters["completed"] += 1

    with Session(engine) as session:
        run = session.get(CrawlRun, run_id)
        if run is None:
            raise RuntimeError(f"crawl run {run_id} was not found")
        run.collected_count = counters["completed"]
        request_counts = dict(
            session.execute(
                select(CrawlRequest.result_status, func.count())
                .where(CrawlRequest.run_id == run_id)
                .group_by(CrawlRequest.result_status)
            ).all()
        )
        run.request_count = sum(request_counts.values())
        run.success_count = request_counts.get("SUCCEEDED", 0)
        run.failure_count = request_counts.get("FAILED", 0)
        run.status = "SUCCEEDED" if counters["failed"] == 0 else "FAILED"
        run.finished_at = datetime.now(UTC)
        session.commit()

    return counters


def main() -> None:
    parser = argparse.ArgumentParser(description="목록·상세·보험이력을 안전 필드만 수집합니다.")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100 for canary collection")

    listings = collect_listings(limit=args.limit)
    counters = collect_vehicle_data([listing.source_listing_id for listing in listings])
    print(
        "수집 완료: "
        f"요청 {counters['requested']}대, 상세 완료 {counters['completed']}대, "
        f"보험이력 {counters['insurance_available']}대, "
        f"종료 광고 {counters['not_found']}대, 실패 {counters['failed']}대"
    )


if __name__ == "__main__":
    main()
