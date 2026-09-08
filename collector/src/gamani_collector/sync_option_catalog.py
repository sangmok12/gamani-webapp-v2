import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gamani_collector.database import create_database_engine
from gamani_collector.models.database import OptionCatalog

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = PROJECT_ROOT / "docs/research/samples/options-catalog-2026-09-07.json"


def sync_option_catalog(path: Path = CATALOG_PATH) -> int:
    entries = json.loads(path.read_text(encoding="utf-8"))
    now = datetime.now(UTC)
    engine = create_database_engine()

    with Session(engine) as session:
        for entry in entries:
            statement = insert(OptionCatalog).values(
                source_code=str(entry["code"]),
                name=entry.get("name"),
                category_code=entry.get("categoryCode"),
                category_name=entry.get("category"),
                display_order=int(entry["ordering"]) if entry.get("ordering") is not None else None,
                last_seen_at=now,
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[OptionCatalog.source_code],
                    set_={
                        "name": statement.excluded.name,
                        "category_code": statement.excluded.category_code,
                        "category_name": statement.excluded.category_name,
                        "display_order": statement.excluded.display_order,
                        "last_seen_at": statement.excluded.last_seen_at,
                    },
                )
            )
        session.commit()
    return len(entries)


def main() -> None:
    count = sync_option_catalog()
    print(f"옵션 메타데이터 {count}건 동기화 완료")


if __name__ == "__main__":
    main()
