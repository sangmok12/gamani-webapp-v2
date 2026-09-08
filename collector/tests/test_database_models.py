from gamani_collector.models.database import Base


def test_initial_collection_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "crawl_requests",
        "crawl_runs",
        "insurance_records",
        "option_catalog",
        "vehicle_identifiers",
        "vehicle_listings",
        "vehicle_search_documents",
        "vehicles",
    }
