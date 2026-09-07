from gamani_collector.models.listing import EncarListItem, EncarListResponse


def test_list_response_keeps_only_allowlisted_fields() -> None:
    payload = {
        "Count": 1,
        "SearchResults": [
            {
                "Id": "12345",
                "ServiceCopyCar": "ORIGINAL",
                "Manufacturer": "현대",
                "ModelGroup": "그랜저",
                "Model": "그랜저 (GN7)",
                "Badge": "가솔린 2.5",
                "Year": 202401.0,
                "FormYear": "2024",
                "Mileage": 12000.0,
                "Price": 3500.0,
                "Color": "검정색",
                "OfficeCityState": "서울",
                "Condition": ["Record"],
                "ServiceMark": ["EncarDiagnosisP0"],
                "vehicleNo": "12가3456",
                "vin": "SECRET-VIN",
                "contact": {"phone": "010-0000-0000"},
            }
        ],
        "UnapprovedTopLevelField": "ignored",
    }

    response = EncarListResponse.model_validate(payload)
    summary = response.search_results[0].to_summary().model_dump()

    assert summary["source_listing_id"] == "12345"
    assert summary["year_month"] == "202401"
    assert summary["form_year"] == 2024
    assert summary["mileage_km"] == 12000
    assert summary["price_manwon"] == 3500
    assert "vehicleNo" not in summary
    assert "vin" not in summary
    assert "contact" not in summary


def test_list_item_requires_source_listing_id() -> None:
    assert EncarListItem.model_fields["source_listing_id"].is_required()
