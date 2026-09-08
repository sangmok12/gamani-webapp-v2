import json

from gamani_collector.sync_option_catalog import CATALOG_PATH


def test_safe_option_catalog_has_unique_codes_and_names() -> None:
    entries = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    codes = [str(entry["code"]) for entry in entries]

    assert len(entries) > 0
    assert len(codes) == len(set(codes))
    assert all(entry.get("name") for entry in entries)
