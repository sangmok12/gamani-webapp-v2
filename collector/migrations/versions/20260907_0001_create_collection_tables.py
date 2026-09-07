"""Create initial collection tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("shard_key", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("expected_count", sa.Integer()),
        sa.Column("collected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.Text()),
        sa.Column("failure_message", sa.Text()),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'ABORTED')",
            name="crawl_runs_status_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "crawl_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("endpoint_type", sa.Text(), nullable=False),
        sa.Column("source_entity_id", sa.Text()),
        sa.Column("page_offset", sa.Integer()),
        sa.Column("requested_size", sa.Integer()),
        sa.Column("http_status", sa.Integer()),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("elapsed_ms", sa.Integer()),
        sa.Column("result_status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "result_status IN ('SUCCEEDED', 'NOT_AVAILABLE', 'RETRY', 'FAILED')",
            name="crawl_requests_result_status_check",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["crawl_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("crawl_requests_run_idx", "crawl_requests", ["run_id", "result_status"])
    op.create_table(
        "vehicle_listings",
        sa.Column("source_listing_id", sa.Text(), nullable=False),
        sa.Column("service_copy_car", sa.Text()),
        sa.Column("manufacturer", sa.Text()),
        sa.Column("model_group", sa.Text()),
        sa.Column("model", sa.Text()),
        sa.Column("badge", sa.Text()),
        sa.Column("badge_detail", sa.Text()),
        sa.Column("transmission", sa.Text()),
        sa.Column("fuel_type", sa.Text()),
        sa.Column("year_month", sa.Text()),
        sa.Column("form_year", sa.Integer()),
        sa.Column("mileage_km", sa.Integer()),
        sa.Column("price_manwon", sa.Integer()),
        sa.Column("color", sa.Text()),
        sa.Column("office_city_state", sa.Text()),
        sa.Column(
            "condition_codes",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "service_marks",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("source_listing_id"),
    )
    op.create_index(
        "vehicle_listings_active_idx",
        "vehicle_listings",
        ["manufacturer", "model", "price_manwon"],
    )


def downgrade() -> None:
    op.drop_index("vehicle_listings_active_idx", table_name="vehicle_listings")
    op.drop_table("vehicle_listings")
    op.drop_index("crawl_requests_run_idx", table_name="crawl_requests")
    op.drop_table("crawl_requests")
    op.drop_table("crawl_runs")
