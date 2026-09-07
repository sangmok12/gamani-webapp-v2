from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ListingSummary(BaseModel):
    """Allowlisted listing fields safe for the service database."""

    source_listing_id: str
    service_copy_car: str | None
    manufacturer: str | None
    model_group: str | None
    model: str | None
    badge: str | None
    badge_detail: str | None
    transmission: str | None
    fuel_type: str | None
    year_month: str | None
    form_year: int | None
    mileage_km: int | None
    price_manwon: int | None
    color: str | None
    office_city_state: str | None
    condition_codes: list[str]
    service_marks: list[str]


class EncarListItem(BaseModel):
    """Only the source fields explicitly accepted from an Encar list item."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    source_listing_id: str = Field(alias="Id")
    service_copy_car: str | None = Field(default=None, alias="ServiceCopyCar")
    manufacturer: str | None = Field(default=None, alias="Manufacturer")
    model_group: str | None = Field(default=None, alias="ModelGroup")
    model: str | None = Field(default=None, alias="Model")
    badge: str | None = Field(default=None, alias="Badge")
    badge_detail: str | None = Field(default=None, alias="BadgeDetail")
    transmission: str | None = Field(default=None, alias="Transmission")
    fuel_type: str | None = Field(default=None, alias="FuelType")
    year_month: str | None = Field(default=None, alias="Year")
    form_year: int | None = Field(default=None, alias="FormYear")
    mileage_km: int | None = Field(default=None, alias="Mileage")
    price_manwon: int | None = Field(default=None, alias="Price")
    color: str | None = Field(default=None, alias="Color")
    office_city_state: str | None = Field(default=None, alias="OfficeCityState")
    condition_codes: list[str] = Field(default_factory=list, alias="Condition")
    service_marks: list[str] = Field(default_factory=list, alias="ServiceMark")

    @field_validator("year_month", mode="before")
    @classmethod
    def normalize_year_month(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value).split(".", maxsplit=1)[0]

    def to_summary(self) -> ListingSummary:
        return ListingSummary(**self.model_dump())


class EncarListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    total_count: int = Field(alias="Count")
    search_results: list[EncarListItem] = Field(alias="SearchResults")
