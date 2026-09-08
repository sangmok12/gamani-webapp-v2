# Gamani Collector

가마니연구소 V2의 Python 데이터 수집기다.

목록·상세·보험이력에서 허용한 검색 필드만 골라 PostgreSQL에 저장한다.

```bash
../.tools/uv run gamani-collect-canary --limit 20
```

canary 실행은 최대 100대까지 허용한다. 차량번호는 별도 테이블에 저장하고 VIN, 판매자 연락처,
주소, 사진, 판매자 설명은 저장하지 않는다.

옵션은 그룹을 구분하지 않은 코드 배열로 차량에 저장하고, 코드와 한글 이름은 카탈로그에서
한 번만 관리한다.

```bash
../.tools/uv run gamani-sync-option-catalog
```
