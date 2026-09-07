from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
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
    started_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    finished_at: Mapped[datetime | None]
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
    requested_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


class VehicleListing(Base):
    __tablename__ = "vehicle_listings"
    __table_args__ = (
        Index("vehicle_listings_active_idx", "manufacturer", "model", "price_manwon"),
    )

    source_listing_id: Mapped[str] = mapped_column(Text, primary_key=True)
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
    first_seen_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    last_seen_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
