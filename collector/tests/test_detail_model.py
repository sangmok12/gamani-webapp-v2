from gamani_collector.models.detail import SafeInsuranceRecord, SafeVehicleDetail


def test_vehicle_detail_keeps_only_safe_fields_and_normalizes_vehicle_number() -> None:
    detail = SafeVehicleDetail.model_validate(
        {
            "vehicleId": 1234,
            "vehicleNo": "12가 3456",
            "vehicleType": "CAR",
            "vin": "must-not-be-kept",
            "contact": {"phone": "must-not-be-kept"},
            "photos": [{"path": "must-not-be-kept"}],
            "options": {
                "standard": ["001", "002"],
                "choice": ["002", "100"],
                "tuning": None,
            },
        }
    )

    assert detail.canonical_source_id == "1234"
    assert detail.vehicle_no == "12가3456"
    assert detail.option_codes() == ["001", "002", "100"]
    assert "vin" not in detail.model_dump()
    assert "contact" not in detail.model_dump()
    assert "photos" not in detail.model_dump()


def test_insurance_record_keeps_search_fields_without_vehicle_number() -> None:
    record = SafeInsuranceRecord.model_validate(
        {
            "openData": True,
            "use": "2",
            "ownerChangeCnt": 2,
            "carNoChangeCnt": 1,
            "government": 0,
            "business": 1,
            "loan": 0,
            "myAccidentCnt": 3,
            "myAccidentCost": 1_500_000,
            "carNo": "must-not-be-kept",
            "ownerChanges": [{"date": "must-not-be-kept"}],
        }
    )

    assert record.owner_change_count == 2
    assert record.business_use_count == 1
    assert record.my_accident_cost_won == 1_500_000
    assert "carNo" not in record.model_dump()
    assert "ownerChanges" not in record.model_dump()
