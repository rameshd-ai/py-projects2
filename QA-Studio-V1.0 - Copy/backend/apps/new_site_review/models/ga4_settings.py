"""GA4 integration settings."""
from dataclasses import dataclass
from enum import Enum


class CredentialsType(str, Enum):
    OAUTH = "OAuth"
    SERVICE_ACCOUNT = "Service Account"


@dataclass
class GA4Settings:
    ga4_property_id: str
    credentials_type: CredentialsType
    service_account_json: str | None  # base64 or raw JSON string for storage

    def is_configured(self) -> bool:
        if not (self.ga4_property_id or "").strip():
            return False
        if self.credentials_type == CredentialsType.SERVICE_ACCOUNT:
            return bool(self.service_account_json and self.service_account_json.strip())
        return True
