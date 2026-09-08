"""Replace per-option rows with arrays and an option catalog."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0004"
down_revision: str | None = "20260908_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vehicles",
        sa.Column(
            "option_codes",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
            comment="기본·선택·튜닝 구분 없이 합치고 중복 제거한 옵션 코드 배열",
        ),
    )
    op.execute(
        """
        UPDATE vehicles v
        SET option_codes = options.codes
        FROM (
            SELECT vehicle_id, array_agg(DISTINCT source_code ORDER BY source_code) AS codes
            FROM vehicle_options
            GROUP BY vehicle_id
        ) AS options
        WHERE options.vehicle_id = v.id
        """
    )
    op.create_table(
        "option_catalog",
        sa.Column("source_code", sa.Text(), nullable=False, comment="엔카가 제공한 옵션 코드"),
        sa.Column("name", sa.Text(), comment="사용자에게 표시할 한글 옵션 이름"),
        sa.Column("category_code", sa.Text(), comment="옵션 분류 코드"),
        sa.Column("category_name", sa.Text(), comment="안전·편의 등 옵션 분류 이름"),
        sa.Column("display_order", sa.Integer(), comment="분류 안에서의 표시 순서"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="옵션 코드를 처음 발견한 일시",
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="옵션 코드를 마지막으로 확인한 일시",
        ),
        sa.PrimaryKeyConstraint("source_code"),
        comment="옵션 코드와 한글 이름을 한 번만 관리하는 메타데이터 테이블",
    )
    op.execute(
        """
        INSERT INTO option_catalog (source_code)
        SELECT DISTINCT unnest(option_codes)
        FROM vehicles
        ON CONFLICT (source_code) DO NOTHING
        """
    )
    op.drop_table("vehicle_options")


def downgrade() -> None:
    op.create_table(
        "vehicle_options",
        sa.Column("vehicle_id", sa.BigInteger(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("source_group", sa.Text(), nullable=False, server_default="unknown"),
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
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vehicle_id", "source_code", "source_group"),
    )
    op.execute(
        """
        INSERT INTO vehicle_options (vehicle_id, source_code, source_group)
        SELECT id, unnest(option_codes), 'unknown'
        FROM vehicles
        """
    )
    op.drop_table("option_catalog")
    op.drop_column("vehicles", "option_codes")
