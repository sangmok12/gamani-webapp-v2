import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SafeVehicleDetail(BaseModel):
    """상세 응답에서 서비스 DB에 저장하도록 허용한 필드만 받는다."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    canonical_source_id: str = Field(alias="vehicleId")
    vehicle_no: str = Field(alias="vehicleNo")
    vehicle_type: str | None = Field(default=None, alias="vehicleType")
    options: dict[str, object] = Field(default_factory=dict)

    @field_validator("canonical_source_id", mode="before")
    @classmethod
    def normalize_source_id(cls, value: object) -> str:
        return str(value)

    @field_validator("vehicle_no")
    @classmethod
    def normalize_vehicle_no(cls, value: str) -> str:
        normalized = re.sub(r"\s+", "", value)
        if not normalized:
            raise ValueError("vehicleNo must not be empty")
        return normalized

    def option_groups(self) -> dict[str, list[str]]:
        groups: dict[str, list[str]] = {}
        for group in ("standard", "choice", "tuning", "etc"):
            value = self.options.get(group, [])
            groups[group] = [str(code) for code in value] if isinstance(value, list) else []
        return groups

    def option_codes(self) -> list[str]:
        return sorted({code for codes in self.option_groups().values() for code in codes})


class SafeInsuranceRecord(BaseModel):
    """보험 응답에서 검색에 필요한 비개인 필드만 받는다."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    open_data: bool | None = Field(default=None, alias="openData")
    usage_code: str | None = Field(default=None, alias="use")
    owner_change_count: int | None = Field(default=None, alias="ownerChangeCnt")
    vehicle_no_change_count: int | None = Field(default=None, alias="carNoChangeCnt")
    government_use_count: int | None = Field(default=None, alias="government")
    business_use_count: int | None = Field(default=None, alias="business")
    loan_use_count: int | None = Field(default=None, alias="loan")
    my_accident_count: int | None = Field(default=None, alias="myAccidentCnt")
    my_accident_cost_won: int | None = Field(default=None, alias="myAccidentCost")
    other_accident_count: int | None = Field(default=None, alias="otherAccidentCnt")
    other_accident_cost_won: int | None = Field(default=None, alias="otherAccidentCost")
    robbery_count: int | None = Field(default=None, alias="robberCnt")
    total_loss_count: int | None = Field(default=None, alias="totalLossCnt")
    flood_total_loss_count: int | None = Field(default=None, alias="floodTotalLossCnt")
    flood_partial_loss_count: int | None = Field(default=None, alias="floodPartLossCnt")
