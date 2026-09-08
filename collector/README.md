# Gamani Collector

가마니연구소 V2의 Python 데이터 수집기다.

목록·상세·보험이력에서 허용한 검색 필드만 골라 PostgreSQL에 저장한다.

```bash
../.tools/uv run gamani-collect-canary --limit 20
```

canary 실행은 최대 100대까지 허용한다. 차량번호는 통합 `vehicles` 테이블에 저장하고 VIN,
판매자 연락처, 주소, 사진, 판매자 설명은 저장하지 않는다.

옵션은 그룹을 구분하지 않은 코드 배열로 차량에 저장하고, 코드와 한글 이름은 카탈로그에서
한 번만 관리한다.

```bash
../.tools/uv run gamani-sync-option-catalog
```

## 500대 시험 및 제조사별 수집

```bash
../.tools/uv run gamani-collect --limit 500
../.tools/uv run gamani-collect --list-manufacturers
../.tools/uv run gamani-collect --manufacturer 현대
../.tools/uv run gamani-collect --resume
```

`collection_jobs`에는 진행 위치와 결과를, `collection_job_items`에는 작업별 고유 판매 ID와
처리 상태를 기록한다. 따라서 실행 도중 목록 순서가 바뀌어 같은 차량이 다시 등장해도 한 번만
집계하며, 중단되면 `--resume`으로 마지막 작업을 이어갈 수 있다.

Mac이 잠들면 Docker와 수집도 사실상 멈추므로 장시간 수집은 다음처럼 실행한다.

```bash
caffeinate -dimsu ../.tools/uv run gamani-collect --limit 500
```
