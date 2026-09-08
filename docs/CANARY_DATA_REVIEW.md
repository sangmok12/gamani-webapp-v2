# Canary 수집 데이터 확인 방법

## DBeaver에서 볼 테이블

| 테이블 | 확인할 내용 |
|---|---|
| `vehicles` | 현재 판매 매물의 차량번호·기본정보·가격·옵션·보험이력 전체 |
| `option_catalog` | 옵션 코드와 한글 옵션명·분류 메타데이터 |
| `crawl_runs`, `crawl_requests` | 수집 실행과 개별 API 요청 성공·실패 기록 |

차량별 옵션은 `vehicles.option_codes` 배열에 저장한다. 엔카 응답의 기본·선택·튜닝 구분은
합치고 중복 코드는 제거한다.

`NULL`은 0회가 아니라 조회 불가 또는 원본 미제공을 뜻한다. 보험 조건을 검색할 때는 반드시
`insurance_status = 'AVAILABLE'`을 함께 사용한다.

## 차량번호와 핵심 검색 데이터 보기

```sql
SELECT
    source_listing_id,
    vehicle_no,
    manufacturer,
    model,
    form_year,
    mileage_km,
    first_price_manwon,
    current_price_manwon,
    current_price_manwon - first_price_manwon AS price_change_manwon,
    owner_change_count,
    business_use_count,
    loan_use_count,
    cardinality(option_codes) AS option_count
FROM vehicles
ORDER BY last_collected_at DESC;
```

## 소유주 변경 1회 이하, 영업·대여 이력 없는 차량

```sql
SELECT
    source_listing_id,
    vehicle_no,
    manufacturer,
    model,
    form_year,
    mileage_km,
    current_price_manwon,
    owner_change_count
FROM vehicles
WHERE insurance_status = 'AVAILABLE'
  AND owner_change_count <= 1
  AND business_use_count = 0
  AND loan_use_count = 0
ORDER BY current_price_manwon;
```

## 특정 옵션을 모두 가진 차량

```sql
SELECT source_listing_id, manufacturer, model, current_price_manwon, option_codes
FROM vehicles
WHERE option_codes @> ARRAY['001', '005']::text[]
ORDER BY current_price_manwon;
```
