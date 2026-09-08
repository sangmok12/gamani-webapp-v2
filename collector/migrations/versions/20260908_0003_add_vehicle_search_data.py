"""Add vehicle, identifier, option, insurance, and search data."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0003"
down_revision: str | None = "20260907_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("canonical_source_id", sa.Text(), nullable=False),
        sa.Column("vehicle_type", sa.Text()),
        sa.Column("manufacturer", sa.Text()),
        sa.Column("model_group", sa.Text()),
        sa.Column("model", sa.Text()),
        sa.Column("badge", sa.Text()),
        sa.Column("badge_detail", sa.Text()),
        sa.Column("transmission", sa.Text()),
        sa.Column("fuel_type", sa.Text()),
        sa.Column("year_month", sa.Text()),
        sa.Column("form_year", sa.Integer()),
        sa.Column("color", sa.Text()),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_source_id"),
        comment="광고 재등록과 무관하게 실제 차량 한 대를 관리하는 테이블",
    )
    op.create_index("vehicles_category_idx", "vehicles", ["manufacturer", "model_group", "model"])
    op.add_column("vehicle_listings", sa.Column("vehicle_id", sa.BigInteger()))
    op.add_column(
        "vehicle_listings",
        sa.Column("resolution_status", sa.Text(), server_default="UNRESOLVED", nullable=False),
    )
    op.create_foreign_key(
        "vehicle_listings_vehicle_id_fkey",
        "vehicle_listings",
        "vehicles",
        ["vehicle_id"],
        ["id"],
    )

    op.create_table(
        "vehicle_identifiers",
        sa.Column("vehicle_id", sa.BigInteger(), nullable=False),
        sa.Column("vehicle_no", sa.Text(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_verified_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vehicle_id"),
        comment="구매 확인에 필요한 차량번호를 일반 차량 정보와 분리해 저장하는 제한 데이터",
    )
    op.create_table(
        "vehicle_options",
        sa.Column("vehicle_id", sa.BigInteger(), nullable=False),
        sa.Column("source_code", sa.Text(), nullable=False),
        sa.Column("source_group", sa.Text(), nullable=False),
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
        comment="차량별 기본·선택·튜닝·기타 옵션 코드를 저장하는 테이블",
    )
    op.create_table(
        "insurance_records",
        sa.Column("vehicle_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("open_data", sa.Boolean()),
        sa.Column("usage_code", sa.Text()),
        sa.Column("owner_change_count", sa.Integer()),
        sa.Column("vehicle_no_change_count", sa.Integer()),
        sa.Column("government_use_count", sa.Integer()),
        sa.Column("business_use_count", sa.Integer()),
        sa.Column("loan_use_count", sa.Integer()),
        sa.Column("my_accident_count", sa.Integer()),
        sa.Column("my_accident_cost_won", sa.BigInteger()),
        sa.Column("other_accident_count", sa.Integer()),
        sa.Column("other_accident_cost_won", sa.BigInteger()),
        sa.Column("robbery_count", sa.Integer()),
        sa.Column("total_loss_count", sa.Integer()),
        sa.Column("flood_total_loss_count", sa.Integer()),
        sa.Column("flood_partial_loss_count", sa.Integer()),
        sa.Column("content_hash", sa.Text()),
        sa.Column("error_code", sa.Text()),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('AVAILABLE', 'NOT_AVAILABLE', 'FAILED')",
            name="insurance_records_status_check",
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vehicle_id"),
        comment="차량별 최신 보험·소유주 변경·용도·사고 이력 요약",
    )
    op.create_index("insurance_records_owner_idx", "insurance_records", ["owner_change_count"])
    op.create_index(
        "insurance_records_usage_idx",
        "insurance_records",
        ["business_use_count", "loan_use_count"],
    )
    op.create_table(
        "vehicle_search_documents",
        sa.Column("listing_id", sa.Text(), nullable=False),
        sa.Column("vehicle_id", sa.BigInteger(), nullable=False),
        sa.Column("manufacturer", sa.Text()),
        sa.Column("model_group", sa.Text()),
        sa.Column("model", sa.Text()),
        sa.Column("badge", sa.Text()),
        sa.Column("badge_detail", sa.Text()),
        sa.Column("form_year", sa.Integer()),
        sa.Column("mileage_km", sa.Integer()),
        sa.Column("price_manwon", sa.Integer()),
        sa.Column("fuel_type", sa.Text()),
        sa.Column("transmission", sa.Text()),
        sa.Column("office_city_state", sa.Text()),
        sa.Column("option_codes", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("insurance_status", sa.Text(), nullable=False),
        sa.Column("owner_change_count", sa.Integer()),
        sa.Column("vehicle_no_change_count", sa.Integer()),
        sa.Column("government_use_count", sa.Integer()),
        sa.Column("business_use_count", sa.Integer()),
        sa.Column("loan_use_count", sa.Integer()),
        sa.Column("total_loss_count", sa.Integer()),
        sa.Column("flood_total_loss_count", sa.Integer()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["vehicle_listings.source_listing_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("listing_id"),
        comment="사용자 검색을 빠르고 단순하게 제공하기 위한 차량별 검색 전용 데이터",
    )
    op.create_index(
        "vehicle_search_category_price_idx",
        "vehicle_search_documents",
        ["manufacturer", "model_group", "model", "price_manwon"],
    )
    op.create_index(
        "vehicle_search_year_mileage_idx",
        "vehicle_search_documents",
        ["form_year", "mileage_km"],
    )
    op.create_index("vehicle_search_owner_idx", "vehicle_search_documents", ["owner_change_count"])
    op.create_index(
        "vehicle_search_usage_idx",
        "vehicle_search_documents",
        ["business_use_count", "loan_use_count"],
    )
    op.create_index(
        "vehicle_search_options_gin_idx",
        "vehicle_search_documents",
        ["option_codes"],
        postgresql_using="gin",
    )
    _add_comments()


def _add_comments() -> None:
    comments = {
        "vehicles": {
            "id": "가마니연구소 내부 실제 차량 식별자",
            "canonical_source_id": "엔카 상세 API가 반환한 실제 차량 식별자",
            "vehicle_type": "승용차 등 차량 유형 코드",
            "manufacturer": "제조사 이름",
            "model_group": "모델 그룹 이름",
            "model": "세대가 포함된 상세 모델 이름",
            "badge": "엔진·트림 등이 포함된 등급 이름",
            "badge_detail": "추가 세부 등급 이름",
            "transmission": "변속기 표시값",
            "fuel_type": "연료 표시값",
            "year_month": "차량 연식 기준 연월 YYYYMM",
            "form_year": "차량 연식 연도",
            "color": "외장 색상 이름",
            "first_seen_at": "실제 차량을 처음 발견한 일시",
            "last_seen_at": "실제 차량을 마지막으로 확인한 일시",
        },
        "vehicle_identifiers": {
            "vehicle_id": "가마니연구소 내부 실제 차량 식별자",
            "vehicle_no": "공백을 제거해 정규화한 현재 차량번호",
            "first_seen_at": "차량번호를 처음 확인한 일시",
            "last_verified_at": "차량번호를 마지막으로 확인한 일시",
        },
        "vehicle_options": {
            "vehicle_id": "가마니연구소 내부 실제 차량 식별자",
            "source_code": "엔카가 제공한 옵션 코드",
            "source_group": "기본·선택·튜닝·기타 옵션 구분",
            "first_seen_at": "해당 옵션을 처음 확인한 일시",
            "last_seen_at": "해당 옵션을 마지막으로 확인한 일시",
        },
        "insurance_records": {
            "vehicle_id": "가마니연구소 내부 실제 차량 식별자",
            "status": "보험이력 조회 상태",
            "open_data": "보험이력 데이터 공개 여부",
            "usage_code": "보험이력에 표시된 차량 용도 코드",
            "owner_change_count": "소유주 변경 횟수",
            "vehicle_no_change_count": "차량번호 변경 횟수",
            "government_use_count": "관용 사용 이력 횟수",
            "business_use_count": "영업용 사용 이력 횟수",
            "loan_use_count": "대여용 사용 이력 횟수",
            "my_accident_count": "내 차 피해 보험사고 횟수",
            "my_accident_cost_won": "내 차 피해 보험처리 금액, 원",
            "other_accident_count": "상대 차 피해 보험사고 횟수",
            "other_accident_cost_won": "상대 차 피해 보험처리 금액, 원",
            "robbery_count": "도난 이력 횟수",
            "total_loss_count": "전손 이력 횟수",
            "flood_total_loss_count": "침수 전손 이력 횟수",
            "flood_partial_loss_count": "침수 분손 이력 횟수",
            "content_hash": "허용한 보험 요약값의 변경 감지 해시",
            "error_code": "조회 실패 시 오류 분류 코드",
            "observed_at": "보험이력을 확인한 일시",
        },
        "vehicle_search_documents": {
            "listing_id": "현재 검색 결과가 가리키는 엔카 광고 식별자",
            "vehicle_id": "가마니연구소 내부 실제 차량 식별자",
            "manufacturer": "제조사 이름",
            "model_group": "모델 그룹 이름",
            "model": "상세 모델 이름",
            "badge": "차량 등급 이름",
            "badge_detail": "추가 세부 등급 이름",
            "form_year": "차량 연식 연도",
            "mileage_km": "누적 주행거리, km",
            "price_manwon": "현재 판매가격, 만원",
            "fuel_type": "연료 표시값",
            "transmission": "변속기 표시값",
            "office_city_state": "광고 등록 시·도 지역",
            "option_codes": "차량에 적용된 전체 옵션 코드 배열",
            "insurance_status": "보험이력 조회 상태",
            "owner_change_count": "소유주 변경 횟수",
            "vehicle_no_change_count": "차량번호 변경 횟수",
            "government_use_count": "관용 사용 이력 횟수",
            "business_use_count": "영업용 사용 이력 횟수",
            "loan_use_count": "대여용 사용 이력 횟수",
            "total_loss_count": "전손 이력 횟수",
            "flood_total_loss_count": "침수 전손 이력 횟수",
            "updated_at": "검색 데이터 마지막 갱신 일시",
        },
    }
    op.execute(
        sa.text("COMMENT ON COLUMN vehicle_listings.vehicle_id IS '연결된 내부 실제 차량 식별자'")
    )
    op.execute(
        sa.text(
            "COMMENT ON COLUMN vehicle_listings.resolution_status "
            "IS '광고 ID의 실제 차량 연결 상태'"
        )
    )
    for table, columns in comments.items():
        for column, description in columns.items():
            escaped = description.replace("'", "''")
            op.execute(f'COMMENT ON COLUMN "{table}"."{column}" IS \'{escaped}\'')


def downgrade() -> None:
    op.drop_table("vehicle_search_documents")
    op.drop_table("insurance_records")
    op.drop_table("vehicle_options")
    op.drop_table("vehicle_identifiers")
    op.drop_constraint("vehicle_listings_vehicle_id_fkey", "vehicle_listings", type_="foreignkey")
    op.drop_column("vehicle_listings", "resolution_status")
    op.drop_column("vehicle_listings", "vehicle_id")
    op.drop_table("vehicles")
