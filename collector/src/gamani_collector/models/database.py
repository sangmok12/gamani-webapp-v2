from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED')",
            name="crawl_runs_status_check",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    shard_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    expected_count: Mapped[int | None] = mapped_column(Integer)
    collected_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(Text)
    failure_message: Mapped[str | None] = mapped_column(Text)


class CrawlRequest(Base):
    __tablename__ = "crawl_requests"
    __table_args__ = (
        CheckConstraint(
            "result_status IN ('SUCCEEDED', 'NOT_AVAILABLE', 'RETRY', 'FAILED')",
            name="crawl_requests_result_status_check",
        ),
        Index("crawl_requests_run_idx", "run_id", "result_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crawl_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    endpoint_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_entity_id: Mapped[str | None] = mapped_column(Text)
    page_offset: Mapped[int | None] = mapped_column(Integer)
    requested_size: Mapped[int | None] = mapped_column(Integer)
    http_status: Mapped[int | None] = mapped_column(Integer)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    result_status: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class VehicleListing(Base):
    __tablename__ = "vehicle_listings"
    __table_args__ = (
        Index("vehicle_listings_active_idx", "manufacturer", "model", "price_manwon"),
    )

    source_listing_id: Mapped[str] = mapped_column(Text, primary_key=True)
    vehicle_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("vehicles.id"),
    )
    resolution_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="UNRESOLVED",
    )
    service_copy_car: Mapped[str | None] = mapped_column(Text)
    manufacturer: Mapped[str | None] = mapped_column(Text)
    model_group: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    badge: Mapped[str | None] = mapped_column(Text)
    badge_detail: Mapped[str | None] = mapped_column(Text)
    transmission: Mapped[str | None] = mapped_column(Text)
    fuel_type: Mapped[str | None] = mapped_column(Text)
    year_month: Mapped[str | None] = mapped_column(Text)
    form_year: Mapped[int | None] = mapped_column(Integer)
    mileage_km: Mapped[int | None] = mapped_column(Integer)
    price_manwon: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(Text)
    office_city_state: Mapped[str | None] = mapped_column(Text)
    condition_codes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    service_marks: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (Index("vehicles_category_idx", "manufacturer", "model_group", "model"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    canonical_source_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    vehicle_type: Mapped[str | None] = mapped_column(Text)
    manufacturer: Mapped[str | None] = mapped_column(Text)
    model_group: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    badge: Mapped[str | None] = mapped_column(Text)
    badge_detail: Mapped[str | None] = mapped_column(Text)
    transmission: Mapped[str | None] = mapped_column(Text)
    fuel_type: Mapped[str | None] = mapped_column(Text)
    year_month: Mapped[str | None] = mapped_column(Text)
    form_year: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(Text)
    option_codes: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class VehicleIdentifier(Base):
    __tablename__ = "vehicle_identifiers"

    vehicle_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    vehicle_no: Mapped[str] = mapped_column(Text, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class OptionCatalog(Base):
    __tablename__ = "option_catalog"

    source_code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    category_code: Mapped[str | None] = mapped_column(Text)
    category_name: Mapped[str | None] = mapped_column(Text)
    display_order: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class InsuranceRecord(Base):
    __tablename__ = "insurance_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('AVAILABLE', 'NOT_AVAILABLE', 'FAILED')",
            name="insurance_records_status_check",
        ),
        Index("insurance_records_owner_idx", "owner_change_count"),
        Index("insurance_records_usage_idx", "business_use_count", "loan_use_count"),
    )

    vehicle_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    open_data: Mapped[bool | None] = mapped_column(Boolean)
    usage_code: Mapped[str | None] = mapped_column(Text)
    owner_change_count: Mapped[int | None] = mapped_column(Integer)
    vehicle_no_change_count: Mapped[int | None] = mapped_column(Integer)
    government_use_count: Mapped[int | None] = mapped_column(Integer)
    business_use_count: Mapped[int | None] = mapped_column(Integer)
    loan_use_count: Mapped[int | None] = mapped_column(Integer)
    my_accident_count: Mapped[int | None] = mapped_column(Integer)
    my_accident_cost_won: Mapped[int | None] = mapped_column(BigInteger)
    other_accident_count: Mapped[int | None] = mapped_column(Integer)
    other_accident_cost_won: Mapped[int | None] = mapped_column(BigInteger)
    robbery_count: Mapped[int | None] = mapped_column(Integer)
    total_loss_count: Mapped[int | None] = mapped_column(Integer)
    flood_total_loss_count: Mapped[int | None] = mapped_column(Integer)
    flood_partial_loss_count: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class VehicleSearchDocument(Base):
    __tablename__ = "vehicle_search_documents"
    __table_args__ = (
        Index(
            "vehicle_search_category_price_idx",
            "manufacturer",
            "model_group",
            "model",
            "price_manwon",
        ),
        Index("vehicle_search_year_mileage_idx", "form_year", "mileage_km"),
        Index("vehicle_search_owner_idx", "owner_change_count"),
        Index("vehicle_search_usage_idx", "business_use_count", "loan_use_count"),
        Index("vehicle_search_options_gin_idx", "option_codes", postgresql_using="gin"),
    )

    listing_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("vehicle_listings.source_listing_id", ondelete="CASCADE"),
        primary_key=True,
    )
    vehicle_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
    )
    manufacturer: Mapped[str | None] = mapped_column(Text)
    model_group: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    badge: Mapped[str | None] = mapped_column(Text)
    badge_detail: Mapped[str | None] = mapped_column(Text)
    form_year: Mapped[int | None] = mapped_column(Integer)
    mileage_km: Mapped[int | None] = mapped_column(Integer)
    price_manwon: Mapped[int | None] = mapped_column(Integer)
    fuel_type: Mapped[str | None] = mapped_column(Text)
    transmission: Mapped[str | None] = mapped_column(Text)
    office_city_state: Mapped[str | None] = mapped_column(Text)
    option_codes: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    insurance_status: Mapped[str] = mapped_column(Text, nullable=False)
    owner_change_count: Mapped[int | None] = mapped_column(Integer)
    vehicle_no_change_count: Mapped[int | None] = mapped_column(Integer)
    government_use_count: Mapped[int | None] = mapped_column(Integer)
    business_use_count: Mapped[int | None] = mapped_column(Integer)
    loan_use_count: Mapped[int | None] = mapped_column(Integer)
    total_loss_count: Mapped[int | None] = mapped_column(Integer)
    flood_total_loss_count: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
