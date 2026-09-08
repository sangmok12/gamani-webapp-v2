# 가마니연구소 V2

가마니연구소 V2는 중고차 매물 데이터를 안정적으로 수집·정규화하고, 이후 검색 API와 사용자 화면으로 확장하기 위한 프로젝트다.

V1/V1.5의 Google Apps Script와 Google Sheets 중심 구조에서 얻은 업무 규칙은 유지하되, V2의 데이터 기반은 Python 수집기와 PostgreSQL로 새로 구성한다.

## 현재 단계

현재는 **목록·상세·보험이력 canary 수집을 검증한 단계**다.

- V1.5에서 조사한 엔카 API 자료 인수인계 완료
- PostgreSQL 스키마 초안 인수인계 완료
- 개인정보가 제거된 응답 표본 인수인계 완료
- V2 개발 순서와 완료 기준 문서화 완료
- 프로젝트 전용 Python 3.14 환경 구성
- Python 수집기 최소 패키지 구성
- PostgreSQL 18.6 Docker Compose 구성
- 환경설정 로딩과 DB 연결 확인 코드 구성
- 엔카 실제 목록·상세·보험이력 호출과 PostgreSQL 저장 검증
- 판매 매물 ID 기준의 통합 차량 테이블과 옵션 메타데이터 구성
- 차량번호 외 VIN·연락처·주소·사진·판매자 설명은 저장하지 않는 허용목록 적용

현재 전체 수집 전 20대 canary로 데이터 연결과 검색 필드를 확인했다.

## 목표 구조

```text
gamani-webapp-v2/
├── collector/              # Python 수집기
├── api/                    # 추후 Spring Boot 검색 API
├── frontend/               # 추후 React 사용자 화면
├── docs/
│   ├── START_HERE.md       # 가장 먼저 읽을 문서
│   ├── ROADMAP.md          # 단계별 구현 계획과 완료 기준
│   ├── DECISIONS.md        # 확정된 기술·데이터 결정
│   └── research/           # V1.5에서 인수인계한 조사 자료
├── compose.yaml            # PostgreSQL 로컬 실행 설정
├── .env.example            # 환경변수 예시
└── README.md
```

## 로컬 실행

이 저장소에는 Mac의 시스템 Python과 분리된 Python 3.14 환경을 사용한다.

```bash
cd /Users/user/Desktop/gamani-labs/gamani-webapp-v2/collector
../.tools/uv sync
../.tools/uv run pytest
../.tools/uv run ruff check .
```

Docker Desktop을 실행한 다음 PostgreSQL을 시작한다.

```bash
cd /Users/user/Desktop/gamani-labs/gamani-webapp-v2
docker compose up -d postgres
docker compose ps
```

상태가 `healthy`가 되면 연결을 확인한다.

```bash
cd collector
../.tools/uv run gamani-db-check
```

실제 목록·상세·보험이력을 소량 수집한다. canary 단계에서는 최대 100대로 제한한다.

```bash
cd collector
../.tools/uv run gamani-collect-canary --limit 20
```

종료할 때는 다음 명령을 사용한다. 데이터가 담긴 Docker volume은 유지된다.

```bash
docker compose stop
```

## 문서 읽는 순서

1. [V2 시작 안내](docs/START_HERE.md)
2. [단계별 로드맵](docs/ROADMAP.md)
3. [확정된 결정사항](docs/DECISIONS.md)
4. [엔카 API 분석](docs/research/encar-api-analysis.md)
5. [PostgreSQL 스키마 초안](docs/research/postgresql-schema.sql)

## 개발 원칙

- V1과 V1.5는 정상 동작하는 참고 원본으로 보존한다.
- 한 번에 전체 시스템을 만들지 않고, 작은 기능 단위로 구현·확인·커밋한다.
- 확인된 사실과 추정 또는 미검증 항목을 문서에서 구분한다.
- 외부 API 응답 0건이나 구조 변경을 판매 종료로 간주하지 않는다.
- 차량번호, VIN, 연락처, 주소 같은 개인정보는 일반 서비스 DB에 저장하지 않는다.
- 약 20만 대 전체 수집은 canary 검증과 실패 복구 테스트가 끝난 뒤에만 실행한다.
