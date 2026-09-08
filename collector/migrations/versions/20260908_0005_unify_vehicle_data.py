"""Unify current listing, identifier, insurance, and search data."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260908_0005"
down_revision: str | None = "20260908_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vehicles_unified",
        sa.Column("source_listing_id", sa.Text(), primary_key=True),
        sa.Column("vehicle_no", sa.Text()),
        sa.Column("vehicle_type", sa.Text()),
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
        sa.Column("first_price_manwon", sa.Integer()),
        sa.Column("current_price_manwon", sa.Integer()),
        sa.Column("color", sa.Text()),
        sa.Column("office_city_state", sa.Text()),
        sa.Column("condition_codes", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("service_marks", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column(
            "option_codes", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("insurance_status", sa.Text(), server_default="PENDING", nullable=False),
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
        sa.Column("insurance_content_hash", sa.Text()),
        sa.Column("insurance_error_code", sa.Text()),
        sa.Column("insurance_observed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "first_collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "insurance_status IN ('PENDING', 'AVAILABLE', 'NOT_AVAILABLE', 'FAILED')",
            name="vehicles_unified_insurance_status_check",
        ),
        comment="현재 엔카 판매목록의 차량 검색 정보를 한 행에 통합한 테이블",
    )
    op.execute(
        """
        INSERT INTO vehicles_unified (
            source_listing_id, vehicle_no, vehicle_type, service_copy_car,
            manufacturer, model_group, model, badge, badge_detail,
            transmission, fuel_type, year_month, form_year, mileage_km,
            first_price_manwon, current_price_manwon, color, office_city_state,
            condition_codes, service_marks, option_codes, insurance_status,
            open_data, usage_code, owner_change_count, vehicle_no_change_count,
            government_use_count, business_use_count, loan_use_count,
            my_accident_count, my_accident_cost_won, other_accident_count,
            other_accident_cost_won, robbery_count, total_loss_count,
            flood_total_loss_count, flood_partial_loss_count,
            insurance_content_hash, insurance_error_code, insurance_observed_at,
            first_collected_at, last_collected_at
        )
        SELECT
            l.source_listing_id, vi.vehicle_no, v.vehicle_type, l.service_copy_car,
            l.manufacturer, l.model_group, l.model, l.badge, l.badge_detail,
            l.transmission, l.fuel_type, l.year_month, l.form_year, l.mileage_km,
            l.price_manwon, l.price_manwon, l.color, l.office_city_state,
            l.condition_codes, l.service_marks, v.option_codes,
            COALESCE(i.status, 'PENDING'), i.open_data, i.usage_code,
            i.owner_change_count, i.vehicle_no_change_count, i.government_use_count,
            i.business_use_count, i.loan_use_count, i.my_accident_count,
            i.my_accident_cost_won, i.other_accident_count, i.other_accident_cost_won,
            i.robbery_count, i.total_loss_count, i.flood_total_loss_count,
            i.flood_partial_loss_count, i.content_hash, i.error_code, i.observed_at,
            l.first_seen_at, l.last_seen_at
        FROM vehicle_listings l
        JOIN vehicles v ON v.id = l.vehicle_id
        LEFT JOIN vehicle_identifiers vi ON vi.vehicle_id = v.id
        LEFT JOIN insurance_records i ON i.vehicle_id = v.id
        WHERE l.resolution_status = 'RESOLVED'
        """
    )
    op.drop_table("vehicle_search_documents")
    op.drop_table("insurance_records")
    op.drop_table("vehicle_identifiers")
    op.drop_table("vehicle_listings")
    op.drop_table("vehicles")
    op.rename_table("vehicles_unified", "vehicles")
    op.execute(
        "ALTER TABLE vehicles RENAME CONSTRAINT vehicles_unified_insurance_status_check "
        "TO vehicles_insurance_status_check"
    )
    op.create_index(
        "vehicles_category_price_idx",
        "vehicles",
        ["manufacturer", "model_group", "model", "current_price_manwon"],
    )
    op.create_index("vehicles_year_mileage_idx", "vehicles", ["form_year", "mileage_km"])
    op.create_index("vehicles_owner_idx", "vehicles", ["owner_change_count"])
    op.create_index(
        "vehicles_usage_idx", "vehicles", ["business_use_count", "loan_use_count"]
    )
    op.create_index(
        "vehicles_options_gin_idx", "vehicles", ["option_codes"], postgresql_using="gin"
    )
    _add_comments()


def _add_comments() -> None:
    comments = {
        "source_listing_id": "엔카 현재 판매목록에 표시되는 매물 식별자",
        "vehicle_no": "공백을 제거해 정규화한 차량번호",
        "vehicle_type": "차량 유형 코드",
        "service_copy_car": "엔카 원본·재등록 표시값",
        "manufacturer": "제조사 이름",
        "model_group": "모델 그룹 이름",
        "model": "세대가 포함된 상세 모델 이름",
        "badge": "엔진·트림 등이 포함된 등급 이름",
        "badge_detail": "추가 세부 등급 이름",
        "transmission": "변속기 표시값",
        "fuel_type": "연료 표시값",
        "year_month": "차량 연식 기준 연월 YYYYMM",
        "form_year": "차량 연식 연도",
        "mileage_km": "누적 주행거리, km",
        "first_price_manwon": "가마니연구소가 이 매물을 처음 확인한 가격, 만원",
        "current_price_manwon": "가장 최근에 확인한 가격, 만원",
        "color": "외장 색상 이름",
        "office_city_state": "판매 지역 시·도",
        "condition_codes": "보험·성능 정보 제공 여부 코드",
        "service_marks": "엔카 진단 등 서비스 표시 코드",
        "option_codes": "그룹 구분 없이 합치고 중복 제거한 옵션 코드 배열",
        "insurance_status": "보험이력 조회 상태",
        "open_data": "보험이력 공개 여부",
        "usage_code": "보험이력의 차량 용도 코드",
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
        "insurance_content_hash": "허용한 보험 요약값의 변경 감지 해시",
        "insurance_error_code": "보험이력 조회 실패 유형",
        "insurance_observed_at": "보험이력을 마지막으로 확인한 일시",
        "first_collected_at": "판매 매물을 처음 수집한 일시",
        "last_collected_at": "판매 매물을 마지막으로 갱신한 일시",
    }
    for column, description in comments.items():
        escaped = description.replace("'", "''")
        op.execute(f'COMMENT ON COLUMN vehicles."{column}" IS \'{escaped}\'')


def downgrade() -> None:
    raise NotImplementedError("The unified vehicle migration is intentionally irreversible")
