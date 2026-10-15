from pydantic import BaseModel

from app.models.enums import Language


class FeatureStatus(BaseModel):
    name: str
    available: bool
    mode: str
    detail: str


class ConfigStatus(BaseModel):
    environment: str
    api_version: str
    supported_languages: list[Language]
    max_upload_bytes: int
    allowed_upload_types: list[str]
    report_period_days: list[int]
    features: list[FeatureStatus]
