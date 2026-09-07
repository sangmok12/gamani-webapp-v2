# 엔카 API 분석과 가마니연구소 V2 수집·DB 설계

> 조사 기준일: 2026-09-07  
> 목적: 약 20만 대의 전체 매물을 최초 수집하고, 이후에는 중복 호출을 최소화하면서 변경·신규·판매 종료 상태를 갱신할 수 있는 V2 기반 설계

## 1. 결론부터

V2는 다음 구조로 시작하는 것이 안전하다.

1. 차량을 제조사별 테이블로 나누지 않고 `vehicles` 한 테이블에 저장한다.
2. 수집 작업만 제조사·차종 등의 작은 구간으로 나누어 시간대별로 실행한다.
3. 목록의 `Id`와 실제 차량의 ID를 분리한다. 재등록 매물은 두 값이 다를 수 있다.
4. 목록 → 차량 상세 → 보험 이력/성능 기록/진단 순서로 호출한다.
5. 옵션은 쉼표 문자열이나 100여 개의 boolean 컬럼이 아니라 `option_catalog`와 `vehicle_options`로 저장한다.
6. 검색 성능이 필요하면 정규화된 원본을 유지하면서 별도의 검색용 projection에 옵션 코드 배열과 GIN 인덱스를 둔다.
7. 첫 수집과 일일 갱신을 분리한다. 일일 갱신은 목록 값의 fingerprint, 신규 광고 ID, 재등록 alias, 주기적 심층 재검사를 조합한다.
8. 응답 0건, 응답 구조 변경, 페이지 누락을 정상적인 판매 종료로 처리하지 않는다. 해당 수집 구간 전체를 중단하고 기존 데이터를 보존한다.
9. 전체 상세 응답에는 차량번호, VIN, 판매자 전화번호·주소 등이 들어온다. 수집 과정에서 필요한 값만 골라 저장하고 공개 API에는 절대 내보내지 않는다.

가장 중요한 발견은 **목록의 `Id`가 항상 실제 차량의 canonical ID는 아니라는 것**이다. 실제 표본에서 목록 ID `41464910`은 `DUPLICATION`이었고, 상세 조회 결과 실제 차량 ID는 `41460716`이었다. 보험·성능·진단 API는 전자 ID로 404, 후자 ID로 200을 반환했다.

따라서 `목록 ID 하나를 차량 PK로 사용`하면 일부 차량의 부가 정보가 유실된다.

---

## 2. 조사 범위와 정확도 표시

### 직접 확인한 내용

- V1의 실제 엔카 호출 코드와 파싱 로직
- 전체 목록 API와 V1 필터 목록 API의 요청/응답
- 차량 상세 API의 축약 응답과 전체 응답
- 재등록 광고 ID에서 canonical 차량 ID로의 변환
- 보험 이력 API
- 성능·상태 점검 API
- 엔카 진단 API
- 목록 메타데이터에 포함된 옵션 코드 62개와 4개 분류
- 응답의 null, 배열, 중첩 객체, 금액·날짜 형식

### 아직 확정하지 않은 내용

- 엔카가 공식적으로 허용하는 최대 호출 속도와 일일 호출량
- `cursor` 파라미터의 실제 페이징 동작
- 모든 제조사·상용차·특수차에서의 필드 변형
- 모든 차량에서 보험 API의 `vehicleNo`가 생략 가능한지 여부
- `include`에 `CATEGORY`, `OPTIONS`, `PHOTOS` 같은 값을 지정할 수 있는지 여부
- 엔카 내부 API의 이용 조건과 자동 수집 허용 범위

확인되지 않은 항목은 DB의 핵심 전제로 사용하지 않는다. 수집기 시작 시 canary 표본으로 검증하고, 실패해도 기존 데이터를 손상하지 않도록 만든다.

---

## 3. 현재 V1의 동작

V1의 핵심 수집 코드는 `VehicleCollector.js`에 있다.

### V1 호출 순서

1. 시트 X2~X14에 저장된 차종·가격·주행거리·연료·색상·옵션 조건으로 `q` 문자열 생성
2. 목록 API를 500건 단위로 반복 호출
3. 목록 `Id`가 cache에 있으면 기존 검수 결과 재사용
4. checked에 없는 ID만 보험 이력 API 호출
5. 소유자 변경, 관용·영업·대여 이력 조건으로 필터링
6. 통과 차량을 본 시트와 cache에 저장
7. checked에 조회한 ID를 누적

### V1에서 재사용할 좋은 원칙

- 이미 확인한 차량을 `checked`로 구분
- 통과 차량을 `cache`에서 재사용
- 목록 Count 0이면 메인·cache·공개 시트를 갱신하지 않고 중단
- 한 번에 500건씩 페이지 분리
- 로그에 시작/종료/호출 수/성공 여부 기록

### V2에서 고쳐야 할 위험

V1은 목록의 `car.Id`로 바로 보험 API를 호출한다. 재등록된 `DUPLICATION` ID는 보험 API에서 404가 될 수 있다. 더 큰 문제는 그 ID가 checked에 먼저 들어가면 이후에도 다시 확인하지 않을 가능성이 있다는 점이다.

V2에서는 다음 순서를 강제한다.

```text
목록 listing_id
    ↓ 차량 상세 조회
canonical_vehicle_id 확인
    ↓ alias 저장
보험 / 성능 / 진단 조회
```

개별 부가 API가 실패한 차량은 `확인 완료`가 아니라 `재시도 필요` 상태로 저장해야 한다.

---

## 4. 확인한 API 목록

공통 도메인은 `https://api.encar.com`이다. 모두 GET 요청으로 확인했다.

| 목적 | 경로 | 확인 상태 | 주요 역할 |
|---|---|---:|---|
| 차량 목록 | `/search/car/list/mobile` | 확인 | 현재 광고 목록, 가격·주행거리·모델, 검색 메타데이터 |
| 차량 상세 | `/v1/readside/vehicle/{id}` | 확인 | canonical ID, 분류, 사양, 옵션, 사진, 광고 상태 |
| 축약 상세 | `/v1/readside/vehicle/{id}?include=MANAGE,SPEC,CONDITION,ADVERTISEMENT` | 확인 | 변경 시각, 기본 사양, 부가 데이터 보유 여부, canonical ID |
| 보험 이력 | `/v1/readside/record/vehicle/{canonicalId}/open` | 확인 | 소유자·번호 변경, 용도 이력, 사고 이력·비용 |
| 성능 점검 | `/v1/readside/inspection/vehicle/{canonicalId}` | 확인 | 성능기록부, 교환·판금 부위, 계통별 상태 |
| 엔카 진단 | `/v1/readside/diagnosis/vehicle/{canonicalId}` | 확인 | 진단 결과와 부위별 판정 |

이 경로들은 엔카가 외부 개발자용으로 공개한 공식 API라는 뜻이 아니다. 웹 서비스가 현재 사용하는 내부 read API를 관찰한 결과다. 경로와 응답은 예고 없이 바뀔 수 있다.

---

## 5. 목록 API

### 요청

```http
GET /search/car/list/mobile
  ?count=true
  &q=(And.Hidden.N._.CarType.A.)
  &sr=|MobileModifiedDate|0|500
  &inav=|Metadata|Sort
  &cursor=
```

| 파라미터 | 의미 | 설계상 주의 |
|---|---|---|
| `count` | 전체 결과 수 포함 | 첫 페이지에서만 신뢰하고 페이지 누적 수와 대조 |
| `q` | 엔카 검색식 | 문자열을 직접 이어 붙이지 말고 전용 builder와 escaping 사용 |
| `sr` | 정렬, offset, 요청 수 | `정렬\|offset\|size` 성격. 현재 V1은 500 단위 |
| `inav` | 검색 facet·메타데이터 | 매우 큰 응답이므로 매 페이지 받을 필요 없음 |
| `cursor` | 커서 자리 | 빈 값으로 동작 확인. 실제 커서 페이징은 미확정 |

관찰 시점에 `(And.Hidden.N._.CarType.A.)`의 Count는 **206,996대**였다. 이는 2026-09-07 당시의 순간값이며 계속 변한다.

V1의 현장 관찰상 한 요청의 안전한 최대 크기는 500건이다. 현재 수집기는 `page_size=500`을 상한으로 두되, 서버가 더 적게 반환하면 실제 반환 건수만큼 offset을 이동해야 한다.

### 목록 `SearchResults` 필드

| 필드 | 관찰 형식 | 저장 제안 |
|---|---|---|
| `Id` | 문자열 | `source_listing_id TEXT` |
| `ServiceCopyCar` | `ORIGINAL` / `DUPLICATION` | 광고 alias 판별용 |
| `Manufacturer` | 문자열 | 표시명. 상세의 코드와 함께 저장 |
| `ModelGroup`, `Model` | 문자열 | 상세 분류 코드와 함께 저장 |
| `Badge`, `BadgeDetail` | 문자열/null | 등급·세부등급 |
| `Transmission`, `FuelType` | 문자열 | 표시값. 추후 코드 테이블 병행 |
| `Year` | 숫자 `YYYYMM.0` | 문자열 `CHAR(6)`으로 정규화 |
| `FormYear` | 문자열 `YYYY` | `SMALLINT` 가능 |
| `Mileage` | 숫자 | `INTEGER`, km |
| `Price` | 숫자 | `INTEGER`, **만원 단위** |
| `Color`, `SeatColor` | 문자열 | 표시명 |
| `ColorExpression`, `SeatColorExpression` | 색상 표현 문자열 | 필요 시 UI 색상으로 별도 파싱 |
| `OfficeCityState` | 문자열 | 지역 |
| `Condition` | 문자열 배열 | 보험·성능·이력 제공 여부 힌트 |
| `ServiceMark`, `Trust`, `AdType`, `BuyType`, `Separation` | 문자열 배열 | JSONB 또는 보조 테이블 |
| `Photo`, `Photos` | 문자열/객체 배열 | 사진 테이블 또는 대표 사진만 |
| `SellType` | 문자열 | 판매 형태 |
| `ServiceCopyCar` | 문자열 | 원본/재등록 구분 |

### `iNav` 메타데이터

`iNav.Nodes`에는 제조사 → 모델 그룹 → 모델 → 등급의 계층과 검색 facet이 들어 있다.

공통적으로 관찰한 키는 다음과 같다.

- `Name`, `DisplayName`
- `Value`, `DisplayValue`
- `Action`, `Expression`
- `Count`
- `Facets`
- `Metadata.Code`, `Ordering`, 영문명, 최소·최대 가격 등

응답 크기가 크므로 다음처럼 운영한다.

- 매 목록 페이지: `inav`를 생략할 수 있는지 canary로 확인 후 가능하면 생략
- 메타데이터 동기화 작업: 하루 1회 또는 변경 감지 시에만 별도 호출
- 옵션·차종 코드 카탈로그: 관찰 시각과 함께 versioned upsert

---

## 6. 광고 ID와 실제 차량 ID

### 확인된 사례

목록에는 같은 차량이 다음 두 행으로 존재했다.

| 목록 ID | `ServiceCopyCar` | 가격/주행거리 | 상세 조회 결과 |
|---|---|---|---|
| `41460716` | `ORIGINAL` | 동일 | canonical `vehicleId=41460716` |
| `41464910` | `DUPLICATION` | 동일 | canonical `vehicleId=41460716`, `manage.dummy=true` |

부가 API 결과:

- `/record/vehicle/41464910/open` → 404
- `/inspection/vehicle/41464910` → 404
- `/diagnosis/vehicle/41464910` → 404
- 같은 요청을 `41460716`으로 호출 → 200

### DB 규칙

- `vehicles.canonical_source_id`: 실제 차량 ID
- `vehicle_listings.source_listing_id`: 목록에 노출된 광고 ID
- 한 차량은 여러 광고 ID를 가질 수 있다.
- `vehicle_listings.vehicle_id`가 내부 `vehicles.id`를 참조한다.
- 상세 조회가 404이면 즉시 삭제하지 않고 `UNRESOLVED`로 재시도한다.

상세 응답에서 `manage.dummy`, `manage.dummyVehicleId`, `manage.reRegistered`를 함께 저장하면 재등록 관계를 추적할 수 있다.

---

## 7. 차량 상세 API

### 축약 상세

```http
GET /v1/readside/vehicle/{listingId}
  ?include=MANAGE,SPEC,CONDITION,ADVERTISEMENT
```

관찰한 주요 값:

- `vehicleId`, `vehicleNo`, `vin`, `vehicleType`
- `manage.registDateTime`, `firstAdvertisedDateTime`, `modifyDateTime`
- `manage.dummy`, `dummyVehicleId`, `reRegistered`
- `manage.subscribeCount`, `viewCount`, `webReserved`
- `advertisement.price`, `status`, `trust`, 서비스 표시, 진단 여부
- `spec.mileage`, `displacement`, `transmissionName`, `fuelCd`, `fuelName`
- `spec.colorName`, `seatCount`, `tradeType`, `bodyName`
- `condition.accident.recordView`, `resumeView`
- `condition.inspection.formats`
- `condition.seizingCount`, `pledgeCount`

축약 호출은 canonical ID 확인과 변경 시각 확인에 적합하다.

### 전체 상세

```http
GET /v1/readside/vehicle/{canonicalId}
```

축약 상세 외에 다음 하위 객체가 포함됐다.

#### `category`

- 제조사·모델 그룹·모델·등급·세부등급의 코드/한글명/영문명
- `yearMonth`, `formYear`
- `domestic`, `importType`
- `originPrice`
- `jatoVehicleId`
- 차체·변속기 보증 개월/거리

#### `options`

- `type`
- `standard`: 기본 옵션 코드 배열
- `choice`: 선택 옵션 코드 배열
- `tuning`: 튜닝 옵션 코드 배열
- `etc`: 기타 옵션 코드 배열

#### `photos`

- `code`, `path`, `type`, `updateDateTime`, `desc`
- type 표본: `OUTER`, `INNER`, `OPTION`

#### 그 밖의 객체

- `contact`: 판매자/딜러 연락 정보
- `partnership`: 제휴·딜러·센터 관련 정보
- `contents.text`: 판매자가 작성한 긴 설명
- `view`: 화면 표시용 값

### 개인정보 최소화

전체 상세에는 다음 정보가 실제로 포함됐다.

- 차량번호
- VIN
- 판매자 전화번호
- 판매자 주소와 사용자 ID
- 판매자 설명 안의 연락처·계좌 등 자유 입력 정보

권장 방식:

1. 수집 프로세스 메모리에서 필요한 공개 필드만 추출한다.
2. `contact`, 원문 `contents.text`, 차량번호, VIN은 일반 서비스 DB에 저장하지 않는다.
3. 중복 판별상 VIN이 꼭 필요하다면 원문 대신 keyed hash/HMAC를 별도 제한 테이블에 저장한다.
4. 원본 응답 보관이 필요하면 암호화된 제한 저장소에 짧은 보존 기간을 두고 공개 API와 분리한다.

---

## 8. 옵션 구조

2026-09-07 목록 메타데이터에서 옵션 코드 **62개**, 분류 **4개**를 확인했다.

| 분류 코드 | 분류명 | 옵션 수 |
|---|---|---:|
| `01` | 외관/내장 | 17 |
| `02` | 안전 | 15 |
| `03` | 편의/멀티미디어 | 18 |
| `04` | 시트 | 12 |

전체 매핑은 `samples/options-catalog-2026-09-07.json`에 저장했다.

### 권장 저장 방식

```text
option_catalog
  source_code  name  category_code  category_name

vehicle_options
  vehicle_id  source_code  source_group  active
```

`source_group`은 `standard`, `choice`, `tuning`, `etc`를 구분한다.

### 왜 쉼표 문자열이 아닌가

- `LIKE '%001%'` 검색은 오탐과 느린 전체 탐색을 만들 수 있다.
- 옵션 이름 변경 시 모든 차량 문자열을 수정해야 한다.
- 옵션 3개를 모두 만족하는 차량 검색이 복잡해진다.
- 외래키와 중복 방지가 불가능하다.

### 왜 옵션별 boolean 컬럼도 아닌가

- 새 옵션이 추가될 때마다 테이블 변경이 필요하다.
- 대부분 false인 넓은 테이블이 된다.
- `standard/choice/tuning` 구분과 관찰 이력을 담기 어렵다.

검색이 많아지면 권위 데이터는 정규화 테이블에 유지하고, 다음 검색 projection을 추가한다.

```sql
option_codes text[]
```

여기에 GIN 인덱스를 두면 `선루프 + 어라운드 뷰 + 통풍시트` 같은 다중 옵션 검색을 빠르게 처리할 수 있다.

---

## 9. 보험 이력 API

```http
GET /v1/readside/record/vehicle/{canonicalId}/open
```

표본에서는 `?vehicleNo=` 없이도 같은 응답을 받았다. 그러나 한 차량 표본의 결과이므로 모든 차량에서 생략 가능하다고 확정하지 않는다.

### 주요 필드

| 묶음 | 필드 예시 |
|---|---|
| 공개 상태 | `openData` |
| 기본 | `regDate`, `firstDate`, `year`, `maker`, `model`, `fuel`, `use`, `displacement` |
| 변경 횟수 | `ownerChangeCnt`, `carNoChangeCnt` |
| 용도 이력 | `government`, `business`, `loan` |
| 사고 집계 | `myAccidentCnt`, `myAccidentCost`, `otherAccidentCnt`, `otherAccidentCost`, `accidentCnt` |
| 특수 이력 | `robberCnt`, `totalLossCnt`, `floodTotalLossCnt`, `floodPartLossCnt`와 날짜 |
| 변경 내역 | `carInfoChanges`, `ownerChanges`, `carInfoUse1s`, `carInfoUse2s` |
| 미가입 | `notJoinDate1` ~ `notJoinDate5` |
| 사고 상세 | `accidents[]`의 `type`, `date`, `insuranceBenefit`, `partCost`, `laborCost`, `paintingCost` |

보험 금액은 원 단위 정수로 보인다. 실제 표본에서 `insuranceBenefit`이 음수인 항목도 있었으므로 unsigned 타입이나 `CHECK (amount >= 0)`을 사용하면 안 된다.

날짜는 필드별로 문자열 형식이 다를 수 있으므로 수집 원문과 파싱 결과를 분리하고, 파싱 실패 시 null과 오류 코드를 남긴다.

---

## 10. 성능 점검 API

```http
GET /v1/readside/inspection/vehicle/{canonicalId}
```

### 상위 구조

- `vehicleId`
- `formats`
- `master`
- `price`
- `inners`
- `outers`
- `images`
- `etcs`
- `directManagement`
- `inspectionSource`

### `master.detail`에서 관찰한 내용

- 기록 번호, 최초 등록일, 유효 기간, 주행거리
- VIN, 변속기, 원동기 형식, 배출가스 관련 문자열
- 튜닝 여부·종류
- 사고·단순 수리 여부
- 용도 변경, 색상 변경
- 리콜 여부와 이행 여부
- 검사자·고지자·코멘트
- 침수, 엔진·변속기 상태 등

원본 필드에 `accdient`처럼 오탈자도 존재하므로 원문 키를 코드에서 임의로 고치지 않는다. 내부 모델로 변환할 때만 `accident` 같은 정상 이름을 사용한다.

### `inners`와 `outers`

- `inners`: 엔진, 변속기, 조향, 제동, 전기, 연료 누출 등의 계통별 중첩 점검 항목
- `outers`: 외판 부위 코드와 교환·판금 등 상태
- 공통적으로 코드, 제목, 상태 코드/제목, 설명, 하위 항목이 섞여 있다.

모든 점검 항목을 `vehicles` 컬럼으로 펼치지 않는다.

- 자주 검색하는 요약: `inspections`
- 계통별 결과: `inspection_items`
- 외판 부위: `inspection_body_panels`
- 전체 구조 보존: PII를 제거한 `raw_snapshots.payload_redacted`

---

## 11. 엔카 진단 API

```http
GET /v1/readside/diagnosis/vehicle/{canonicalId}
```

상위 필드:

- `vehicleId`
- `diagnosisDate`, `realDiagnosisDate`
- `diagnosisNo`, `ordNo`
- `centerCode`, `reservationCenterName`
- `items[]`

`items[]`에는 `code`, `name`, `result`, `resultCode`가 있다. 차체 부위의 `NORMAL`, `REPLACEMENT` 같은 결과와 자유 서술 코멘트가 함께 올 수 있다. 자유 서술에는 개인정보가 섞일 수 있으므로 공개 데이터로 바로 저장하지 않는다.

---

## 12. null·배열·타입 처리 규칙

Python 모델과 DB에서 다음 규칙을 사용한다.

1. `null`, 누락, 빈 배열, 빈 문자열을 서로 다른 상태로 취급한다.
2. 외부 ID는 숫자로 보여도 우선 문자열로 수집한다.
3. `Year=202008.0`은 숫자 연산으로 다루지 않고 `202008` 문자열로 정규화한다.
4. 목록 `Price`는 만원, 보험 비용은 원이므로 컬럼명에 단위를 붙인다.
5. 배열 순서가 업무 의미를 가진다고 가정하지 않는다.
6. 알 수 없는 코드가 오면 거부하지 말고 코드 카탈로그에 `UNKNOWN` 상태로 먼저 넣는다.
7. 소스 필드가 새로 생겨도 파서 전체가 실패하지 않도록 허용하되 schema drift 로그를 남긴다.
8. 필수 식별 필드가 사라지면 그 페이지 전체를 격리한다.

권장 Python 도구:

- `httpx.AsyncClient`: 연결 재사용, timeout, 동시성 제어
- `pydantic`: 관찰 모델과 정규화 모델 분리
- `SQLAlchemy 2.x` + PostgreSQL driver
- Alembic: 스키마 변경 이력
- 구조화 로그: run_id, shard, page, endpoint, status, elapsed_ms

---

## 13. 권장 PostgreSQL 구조

실행 가능한 초안은 `postgresql-schema.sql`에 분리했다.

```text
vehicles 1 ─── N vehicle_listings
   │                 │
   │                 └── N vehicle_price_history
   ├── N vehicle_options N ─── 1 option_catalog
   ├── N insurance_records ─── N insurance_accidents
   ├── N inspections ───────── N inspection_items
   │                      └──── N inspection_body_panels
   ├── N diagnoses ─────────── N diagnosis_items
   └── N vehicle_photos

crawl_runs ─── N crawl_requests
vehicles/listings ─── N raw_snapshots
```

### 핵심 원칙

- 내부 PK와 엔카 ID를 분리
- 차량과 광고를 분리
- 현재값과 이력을 분리
- 검색용 정형 데이터와 감사용 원문 snapshot을 분리
- 개인정보를 일반 서비스 테이블에서 분리
- `updated_at` 하나로 신규/변경/판매 종료를 모두 추측하지 않음

---

## 14. 최초 전체 수집 전략

2026-09-07 관찰 Count 206,996을 기준으로 목록만 500개씩 받으면 약 414페이지다. 문제는 목록이 아니라 차량별 상세 호출 수다.

차량 한 대당 무조건 네 API를 호출하면 최대 약 82만 회가 된다. 따라서 단계별로 나눈다.

### 1단계: 목록 인덱스 확보

- 제조사 또는 충분히 작은 facet으로 shard 분리
- 각 shard의 첫 응답에서 Count 기록
- 500건씩 수집
- `source_listing_id` 기준 upsert
- 목록 fingerprint 저장
- 모든 페이지가 완전할 때만 shard를 성공 처리

### 2단계: canonical ID 해석

- 아직 해석되지 않은 listing만 상세 호출
- 원본/중복 광고 관계 저장
- 한 canonical 차량로 합치기

### 3단계: 필요한 부가 API

- `Condition`에 `Record`가 있는 차량만 보험 이력 후보
- `Condition`에 `Inspection`이 있는 차량만 성능 점검 후보
- `ServiceMark` 또는 상세의 진단 표시가 있는 차량만 진단 후보
- 404는 `NOT_AVAILABLE` 또는 `NOT_FOUND`로 기록하고 제한적으로 재시도

### 4단계: 검증

- shard Count와 고유 listing 수 비교
- alias 해석 전/후 차량 수 비교
- null 비율과 404 비율을 제조사별로 확인
- 옵션 코드 미등록 건수 확인
- 가격·주행거리·연식 범위 이상치 확인

### 동시성

처음부터 높은 병렬도를 사용하지 않는다.

- 동시성 1~2로 canary
- 응답 시간·429·5xx 비율 측정
- 지수 backoff + jitter
- `Retry-After`가 있으면 우선 적용
- 성공률이 안정적일 때만 작은 폭으로 증가
- 제조사별 작업 사이에 DB advisory lock을 사용해 중복 실행 방지

엔카의 공식 호출 제한을 확인하지 못했으므로 특정 초당 호출 수를 안전하다고 단정하지 않는다.

---

## 15. 일일 갱신 전략: checked/cache의 V2 버전

V1의 checked/cache 아이디어는 유지하되 DB 상태로 바꾼다.

| V1 | V2 |
|---|---|
| checked 시트 | `vehicle_listings.first_seen_at`, `last_seen_at`, 수집 상태 |
| cache 시트 | 정규화 테이블의 현재값 + endpoint별 snapshot hash |
| Log 시트 | `crawl_runs`, `crawl_requests` |

### 매일 수행

1. 목록 전체 또는 제조사 shard를 다시 읽는다.
2. `last_seen_at` 갱신
3. 새 listing ID는 상세 조회 queue에 추가
4. 목록 fingerprint가 바뀐 차량은 변경 queue에 추가
5. 재등록 광고는 상세에서 canonical 차량과 연결
6. 그날 보이지 않은 광고는 즉시 삭제하지 않고 `missing_streak` 증가
7. 여러 번 연속 누락되거나 상세 상태가 종료일 때만 inactive 처리
8. 활성 차량을 제조사별로 분산해 주기적 심층 재조회

### 목록 fingerprint 후보

- listing ID
- 가격
- 주행거리
- 모델/등급
- 연식
- 색상
- `Condition`, `ServiceMark`, `Trust`
- 대표 사진 경로

목록 응답에는 상세의 `manage.modifyDateTime`이 노출되지 않았다. 따라서 목록 fingerprint만으로 모든 상세 변경을 알 수는 없다. 신규·목록 변경 기반 조회에 더해 활성 차량을 분할해 주기적으로 재검사해야 한다.

---

## 16. 실패 안전장치

### shard 전체를 중단해야 하는 경우

- 원래 차량이 존재하는 shard에서 Count 0
- `SearchResults` 누락 또는 필수 키 `Id` 누락
- 첫 페이지 Count보다 누적 고유 ID가 비정상적으로 적음
- 같은 페이지가 반복됨
- JSON 파싱 실패가 기준치를 넘음
- 인증/차단으로 추정되는 동일 응답 반복

이때는 기존 차량을 inactive로 바꾸거나 삭제하지 않는다.

### 개별 차량만 실패 처리하는 경우

- 상세/보험/성능/진단 404
- 특정 차량 JSON의 선택 필드 파싱 실패
- 일시적 429/5xx

개별 실패는 endpoint별 상태와 다음 재시각을 기록한다. `record 404`를 이유로 차량 자체를 버리면 안 된다.

### 완료 조건

한 shard가 성공하려면 최소한 다음을 만족해야 한다.

- 모든 목록 페이지 200 및 JSON 정상
- 고유 listing 수가 기대 범위와 일치
- 마지막 페이지 종료 조건이 명확
- DB transaction 또는 staging merge 성공
- run summary 기록 완료

대량 upsert는 staging table에 먼저 적재하고 검증 후 본 테이블에 merge한다.

---

## 17. 검색 API 설계

프론트엔드가 제조사별 테이블을 직접 선택하게 하지 않는다. 하나의 검색 API가 조건을 받는다.

```http
GET /api/vehicles
  ?manufacturer=현대
  &model=그랜저
  &price_max=3500
  &mileage_max=80000
  &option=087
  &option=090
  &sort=price_asc
  &cursor=...
```

기본 인덱스 후보:

- 활성 광고 + 제조사/모델 + 가격
- 활성 광고 + 연식 + 주행거리
- canonical ID, listing ID unique
- `vehicle_options(source_code, vehicle_id)`
- 검색 projection의 `option_codes` GIN

사용자가 많아진 뒤에 실제 slow query를 보고 인덱스를 추가한다. 모든 컬럼에 미리 인덱스를 만들면 수집 upsert 비용과 저장 공간이 커진다.

---

## 18. 구현 순서

1. V2 저장소 생성과 Python 실행 환경 구성
2. HTTP client, retry, rate limiter, 구조화 로그 구현
3. 목록 응답 Pydantic 모델과 1개 shard 수집
4. PostgreSQL의 run/listing/vehicle 최소 테이블 구성
5. 상세 호출과 canonical ID alias 연결
6. 옵션 카탈로그·차량 옵션 저장
7. 보험 이력 저장
8. 성능·진단 저장
9. 500~1,000대 canary 수집 후 null·404·중복 통계 검토
10. 한 제조사 전체 수집
11. 재시작·실패 복구 테스트
12. 전체 최초 수집
13. 일일 갱신과 판매 종료 판정
14. Spring Boot 검색 API와 React 연결

20만 대 전체 수집은 9~11단계가 통과하기 전에는 실행하지 않는다.

---

## 19. 다음 구현 전에 필요한 canary 검증

아래 항목은 설계를 뒤집는 문제가 아니라, 수집기에서 흡수해야 할 변형 확인이다.

- 국산/수입/화물/승합/전기차 각 10대의 전체 상세 비교
- ORIGINAL과 DUPLICATION의 alias 비율
- 상세 404가 된 listing의 재조회 결과
- 보험 `vehicleNo` 생략 성공률
- `include` 조합으로 개인정보 하위 객체를 제외하면서 category/options/photos만 받는 방법
- 목록 `inav` 생략 가능 여부
- `cursor` 기반 안정적 페이징 가능 여부
- 500건 요청에서 실제 반환 수와 중복률
- 429가 발생하기 전이 아니라, 충분히 낮은 속도에서의 장시간 안정성

이 검증 결과는 API adapter 설정과 테스트 fixture에 반영한다. DB의 차량/광고 분리, 옵션 정규화, 원문·정형 분리 구조는 그대로 유지할 수 있다.

---

## 20. 이번 조사에서 남긴 안전 표본

- `samples/list-response-summary-2026-09-07.json`
  - V1과 같은 BMW 필터의 목록 20건
  - 사진·딜러 정보 등을 제외한 필드만 저장
- `samples/options-catalog-2026-09-07.json`
  - 목록 메타데이터에서 추출한 옵션 62개
  - 코드, 이름, 분류, 정렬 순서

원본 전체 상세 응답은 차량번호·VIN·연락처·주소가 포함되어 저장소에 남기지 않았다. 이후 자동 fixture 생성기도 동일하게 redaction 후 저장해야 한다.
