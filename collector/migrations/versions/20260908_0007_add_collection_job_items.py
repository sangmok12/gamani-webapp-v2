"""Track unique listings processed by each collection job."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0007"
down_revision: str | None = "20260908_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_job_items",
        sa.Column(
            "job_id",
            sa.BigInteger(),
            sa.ForeignKey("collection_jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_listing_id", sa.Text(), primary_key=True),
        sa.Column("discovered_offset", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), server_default="PENDING", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COMPLETED', 'NOT_FOUND', 'FAILED')",
            name="collection_job_items_status_check",
        ),
        comment="수집 작업마다 중복 없이 발견하고 처리한 판매 매물을 기록하는 테이블",
    )
    op.create_index(
        "collection_job_items_status_idx",
        "collection_job_items",
        ["job_id", "status"],
    )
    comments = {
        "job_id": "전체 수집 작업 식별자",
        "source_listing_id": "엔카 판매 매물 식별자",
        "discovered_offset": "이 매물을 처음 발견한 목록 위치",
        "status": "PENDING, COMPLETED, NOT_FOUND, FAILED 중 처리 상태",
        "updated_at": "마지막 상태 변경 일시",
    }
    for column, description in comments.items():
        escaped = description.replace("'", "''")
        op.execute(
            f'COMMENT ON COLUMN collection_job_items."{column}" IS \'{escaped}\''
        )


def downgrade() -> None:
    op.drop_index("collection_job_items_status_idx", table_name="collection_job_items")
    op.drop_table("collection_job_items")
