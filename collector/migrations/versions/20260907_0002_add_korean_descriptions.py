"""Add Korean descriptions to every table and column."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260907_0002"
down_revision: str | Sequence[str] | None = "20260907_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLE_COMMENTS = {
    "alembic_version": "현재 적용된 데이터베이스 구조 변경 버전을 관리하는 Alembic 내부 테이블",
    "crawl_runs": "수집 작업 한 번의 시작부터 종료까지 전체 실행 결과를 기록하는 테이블",
    "crawl_requests": "수집 작업 중 실행한 개별 API 요청 결과를 기록하는 테이블",
    "vehicle_listings": "엔카 목록 API에서 수집한 현재 광고 매물 정보를 저장하는 테이블",
}

COLUMN_COMMENTS = {
    "alembic_version": {
        "version_num": "현재 데이터베이스에 마지막으로 적용된 Alembic migration 버전",
    },
    "crawl_runs": {
        "id": "수집 실행을 구분하는 내부 자동 증가 식별자",
        "job_type": "LISTINGS 등 실행한 수집 작업의 종류",
        "shard_key": "제조사나 차종 등 분할 수집 구간을 구분하는 값",
        "status": "RUNNING, SUCCEEDED, FAILED, ABORTED 중 현재 실행 상태",
        "expected_count": "API가 알려준 해당 수집 구간의 전체 예상 매물 수",
        "collected_count": "이번 실행에서 검증하고 저장한 매물 수",
        "request_count": "이번 실행에서 실제로 시도한 API 요청 횟수",
        "success_count": "성공으로 처리한 API 요청 수",
        "failure_count": "실패로 처리한 API 요청 수",
        "started_at": "수집 실행을 시작한 일시",
        "finished_at": "수집 실행이 성공 또는 실패로 종료된 일시",
        "failure_code": "수집 실패 유형을 구분하기 위한 오류 코드",
        "failure_message": "수집 실패 원인을 확인하기 위한 제한된 오류 설명",
    },
    "crawl_requests": {
        "id": "개별 API 요청 기록을 구분하는 내부 자동 증가 식별자",
        "run_id": "이 요청이 속한 수집 실행의 crawl_runs.id",
        "endpoint_type": "LIST, DETAIL, RECORD 등 호출한 API의 업무 유형",
        "source_entity_id": "요청 대상이 된 엔카 광고 또는 차량 식별자",
        "page_offset": "목록 API에서 요청을 시작한 순번",
        "requested_size": "목록 API에서 요청한 매물 개수",
        "http_status": "API가 반환한 HTTP 상태 코드",
        "attempt_count": "재시도를 포함해 실제 요청을 시도한 횟수",
        "elapsed_ms": "마지막 API 요청부터 응답까지 걸린 밀리초",
        "result_status": "SUCCEEDED, NOT_AVAILABLE, RETRY, FAILED 중 요청 처리 결과",
        "error_code": "요청 실패 유형을 구분하기 위한 오류 코드",
        "error_message": "요청 실패 원인을 확인하기 위한 제한된 오류 설명",
        "requested_at": "API 요청 결과를 기록한 일시",
    },
    "vehicle_listings": {
        "source_listing_id": "엔카 목록에 노출된 광고 식별자",
        "service_copy_car": "ORIGINAL 또는 DUPLICATION 등 원본·재등록 광고 구분",
        "manufacturer": "차량 제조사 이름",
        "model_group": "그랜저, 쏘렌토 등 모델 그룹 이름",
        "model": "세대가 포함된 상세 모델 이름",
        "badge": "엔진과 트림 등이 포함된 차량 등급 이름",
        "badge_detail": "차량 등급의 추가 세부 명칭",
        "transmission": "오토, 수동 등 변속기 표시값",
        "fuel_type": "가솔린, 디젤, 전기 등 연료 표시값",
        "year_month": "차량 연식 기준 연월을 YYYYMM 형식으로 저장한 값",
        "form_year": "차량의 연식 연도",
        "mileage_km": "현재 누적 주행거리, 단위 km",
        "price_manwon": "현재 판매가격, 단위 만원",
        "color": "차량 외장 색상 이름",
        "office_city_state": "매물이 등록된 시·도 지역",
        "condition_codes": "보험 이력·성능점검 등 제공 정보 종류 코드 목록",
        "service_marks": "엔카 진단 등 적용된 서비스 표시 코드 목록",
        "first_seen_at": "가마니연구소가 이 광고를 처음 발견한 일시",
        "last_seen_at": "가마니연구소가 이 광고를 마지막으로 확인한 일시",
    },
}


def _escape(value: str) -> str:
    return value.replace("'", "''")


def upgrade() -> None:
    for table_name, comment in TABLE_COMMENTS.items():
        op.execute(f"COMMENT ON TABLE {table_name} IS '{_escape(comment)}'")

    for table_name, columns in COLUMN_COMMENTS.items():
        for column_name, comment in columns.items():
            op.execute(
                f"COMMENT ON COLUMN {table_name}.{column_name} IS '{_escape(comment)}'"
            )


def downgrade() -> None:
    for table_name, columns in COLUMN_COMMENTS.items():
        for column_name in columns:
            op.execute(f"COMMENT ON COLUMN {table_name}.{column_name} IS NULL")

    for table_name in TABLE_COMMENTS:
        op.execute(f"COMMENT ON TABLE {table_name} IS NULL")
