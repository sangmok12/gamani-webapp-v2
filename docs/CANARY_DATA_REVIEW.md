# Canary 수집 데이터 확인 방법

## DBeaver에서 볼 테이블

| 테이블 | 확인할 내용 |
|---|---|
| `vehicle_listings` | 엔카 광고 ID, 가격, 주행거리, 현재 실제 차량 연결 상태 |
| `vehicles` | 재등록 광고를 합친 실제 차량과 기본 제원 |
| `vehicle_identifiers` | 구매 확인에 사용하는 현재 차량번호 |
| `option_catalog` | 옵션 코드와 한글 옵션명·분류 메타데이터 |
| `insurance_records` | 소유주 변경, 번호 변경, 관용·영업·대여·사고 이력 |
| `vehicle_search_documents` | 사용자 검색 API가 읽을 평탄화된 데이터 |
| `crawl_runs`, `crawl_requests` | 수집 실행과 개별 API 요청 성공·실패 기록 |

차량별 옵션은 `vehicles.option_codes`와 `vehicle_search_documents.option_codes` 배열에 저장한다.
엔카 응답의 기본·선택·튜닝 구분은 합치고 중복 코드는 제거한다.

`NULL`은 0회가 아니라 조회 불가 또는 원본 미제공을 뜻한다. 보험 조건을 검색할 때는 반드시
`insurance_status = 'AVAILABLE'`을 함께 사용한다.

## 차량번호와 핵심 검색 데이터를 함께 보기

```sql
SELECT
    s.listing_id,
    v.canonical_source_id,
    vi.vehicle_no,
    s.manufacturer,
    s.model,
    s.form_year,
    s.mileage_km,
    s.price_manwon,
    s.owner_change_count,
    s.business_use_count,
    s.loan_use_count,
    cardinality(s.option_codes) AS option_count
FROM vehicle_search_documents s
JOIN vehicles v ON v.id = s.vehicle_id
JOIN vehicle_identifiers vi ON vi.vehicle_id = v.id
ORDER BY s.updated_at DESC;
```

## 소유주 변경 1회 이하, 영업·대여 이력 없는 차량

```sql
SELECT
    s.listing_id,
    vi.vehicle_no,
    s.manufacturer,
    s.model,
    s.form_year,
    s.mileage_km,
    s.price_manwon,
    s.owner_change_count
FROM vehicle_search_documents s
JOIN vehicle_identifiers vi ON vi.vehicle_id = s.vehicle_id
WHERE s.insurance_status = 'AVAILABLE'
  AND s.owner_change_count <= 1
  AND s.business_use_count = 0
  AND s.loan_use_count = 0
ORDER BY s.price_manwon;
```

## 특정 옵션을 모두 가진 차량

아래의 옵션 코드는 예시이며, 옵션 카탈로그 동기화가 완료되면 화면에서는 한글 이름을 코드로
변환해 조회한다.

```sql
SELECT listing_id, manufacturer, model, price_manwon, option_codes
FROM vehicle_search_documents
WHERE option_codes @> ARRAY['001', '005']::text[]
ORDER BY price_manwon;
```
