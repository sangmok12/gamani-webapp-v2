from gamani_collector.bulk_collect import _manufacturer_filters, _page_hash


def test_manufacturer_filters_use_server_actions() -> None:
    payload = {
        "iNav": {
            "Nodes": [
                {
                    "Facets": [
                        {
                            "DisplayValue": "현대",
                            "Expression": "Manufacturer.현대.",
                            "Action": "(And.Hidden.N._.(C.CarType.A._.Manufacturer.현대.))",
                            "Metadata": {"Code": ["001"]},
                        },
                        {
                            "DisplayValue": "기아",
                            "Expression": "Manufacturer.기아.",
                            "Action": "(And.Hidden.N._.(C.CarType.A._.Manufacturer.기아.))",
                            "Metadata": {"Code": ["002"]},
                        },
                        {
                            "DisplayValue": "아반떼",
                            "Expression": "ModelGroup.아반떼.",
                            "Action": (
                                "(And.Hidden.N._.(C.CarType.A._.Manufacturer.현대._."
                                "ModelGroup.아반떼.))"
                            ),
                        },
                    ]
                }
            ]
        }
    }

    filters = _manufacturer_filters(payload)

    assert filters["현대"].endswith("Manufacturer.현대.))")
    assert filters["기아"].endswith("Manufacturer.기아.))")
    assert "아반떼" not in filters


def test_page_hash_changes_when_page_order_or_content_changes() -> None:
    original = _page_hash(["100", "200"])

    assert original == _page_hash(["100", "200"])
    assert original != _page_hash(["200", "100"])
    assert original != _page_hash(["100", "300"])
