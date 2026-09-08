from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gamani_collector.database import create_database_engine
from gamani_collector.http_client import EncarClient
from gamani_collector.logging_config import configure_logging
from gamani_collector.models.database import CrawlRequest, CrawlRun, Vehicle
from gamani_collector.models.listing import EncarListResponse
from gamani_collector.rate_limiter import RateLimiter
from gamani_collector.settings import get_settings

LIST_PATH = "/search/car/list/mobile"
LIST_QUERY = "(And.Hidden.N._.CarType.A.)"


@dataclass(frozen=True)
class ListingPage:
    vehicles: list[Vehicle]
    total_count: int


def collect_listing_page(
    *,
    limit: int,
    offset: int = 0,
    query: str = LIST_QUERY,
    shard_key: str = "ALL",
) -> ListingPage:
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if offset < 0:
        raise ValueError("offset must not be negative")

    settings = get_settings()
    logger = configure_logging(settings.log_level)
    engine = create_database_engine()

    with Session(engine) as session:
        run = CrawlRun(job_type="LISTINGS", shard_key=shard_key, status="RUNNING")
        session.add(run)
        session.commit()
        run_id = run.id

    try:
        with EncarClient(
            rate_limiter=RateLimiter(settings.requests_per_second),
            logger=logger,
        ) as client:
            result = client.get_json_result(
                LIST_PATH,
                params={
                    "count": "true",
                    "q": query,
                    "sr": f"|MobileModifiedDate|{offset}|{limit}",
                    "cursor": "",
                },
            )

        response = EncarListResponse.model_validate(result.data)
        summaries = [item.to_summary().model_dump() for item in response.search_results]
        now = datetime.now(UTC)

        with Session(engine) as session:
            for summary in summaries:
                price = summary.pop("price_manwon")
                statement = insert(Vehicle).values(
                    **summary,
                    first_price_manwon=price,
                    current_price_manwon=price,
                    insurance_status="PENDING",
                )
                update_values = {
                    key: getattr(statement.excluded, key)
                    for key in summary
                    if key != "source_listing_id"
                }
                update_values["current_price_manwon"] = statement.excluded.current_price_manwon
                update_values["last_collected_at"] = now
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[Vehicle.source_listing_id],
                        set_=update_values,
                    )
                )

            session.add(
                CrawlRequest(
                    run_id=run_id,
                    endpoint_type="LIST",
                    page_offset=offset,
                    requested_size=limit,
                    http_status=result.status_code,
                    attempt_count=result.attempt_count,
                    elapsed_ms=result.elapsed_ms,
                    result_status="SUCCEEDED",
                )
            )
            run = session.get(CrawlRun, run_id)
            if run is None:
                raise RuntimeError(f"crawl run {run_id} was not found")
            run.status = "SUCCEEDED"
            run.expected_count = response.total_count
            run.collected_count = len(summaries)
            run.request_count = result.attempt_count
            run.success_count = 1
            run.finished_at = now
            session.commit()

            listing_ids = [summary["source_listing_id"] for summary in summaries]
            vehicles = list(
                session.query(Vehicle).filter(Vehicle.source_listing_id.in_(listing_ids))
            )
            by_id = {vehicle.source_listing_id: vehicle for vehicle in vehicles}
            return ListingPage(
                vehicles=[by_id[listing_id] for listing_id in listing_ids],
                total_count=response.total_count,
            )
    except Exception as error:
        with Session(engine) as session:
            run = session.get(CrawlRun, run_id)
            if run is not None:
                run.status = "FAILED"
                run.failure_code = type(error).__name__
                run.failure_message = str(error)[:500]
                run.finished_at = datetime.now(UTC)
                session.commit()
        raise


def collect_listings(limit: int = 3) -> list[Vehicle]:
    return collect_listing_page(limit=limit).vehicles


def main() -> None:
    listings = collect_listings(limit=3)
    print("\n수집된 실제 매물")
    print("-" * 90)
    for listing in listings:
        print(
            f"{listing.source_listing_id} | {listing.manufacturer} | {listing.model} | "
            f"{listing.form_year}년 | {listing.mileage_km:,}km | "
            f"{listing.current_price_manwon:,}만원"
        )


if __name__ == "__main__":
    main()
