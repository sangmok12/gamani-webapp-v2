"""Add resumable collection job checkpoints."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0006"
down_revision: str | None = "20260908_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collection_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("manufacturer", sa.Text()),
        sa.Column("query_expression", sa.Text(), nullable=False),
        sa.Column("page_size", sa.Integer(), nullable=False),
        sa.Column("max_vehicles", sa.Integer()),
        sa.Column("expected_count", sa.Integer()),
        sa.Column("next_offset", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_page_hash", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
        sa.CheckConstraint(
            "status IN ('RUNNING', 'SUCCEEDED', 'FAILED')",
            name="collection_jobs_status_check",
        ),
        comment="500대 또는 제조사별 장시간 수집의 중단 재개 지점을 기록하는 테이블",
    )
    comments = {
        "id": "전체 수집 작업 식별자",
        "mode": "LIMIT 또는 MANUFACTURER 수집 방식",
        "manufacturer": "제조사별 수집일 때 선택한 제조사 이름",
        "query_expression": "엔카 메타데이터에서 확인한 검색 표현식",
        "page_size": "한 번에 목록에서 요청하는 차량 수",
        "max_vehicles": "시험 수집의 최대 차량 수",
        "expected_count": "엔카 목록 API가 알려준 검색 조건 전체 건수",
        "next_offset": "다음에 시작할 목록 위치",
        "processed_count": "상세 처리를 시도한 누적 차량 수",
        "last_page_hash": "동일 페이지 반복을 감지하기 위한 직전 목록 해시",
        "status": "RUNNING, SUCCEEDED, FAILED 중 작업 상태",
        "started_at": "작업 시작 일시",
        "finished_at": "작업 종료 일시",
        "error_message": "실패 원인을 확인하기 위한 제한된 오류 설명",
    }
    for column, description in comments.items():
        escaped = description.replace("'", "''")
        op.execute(f'COMMENT ON COLUMN collection_jobs."{column}" IS \'{escaped}\'')


def downgrade() -> None:
    op.drop_table("collection_jobs")
