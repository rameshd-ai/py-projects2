"""GA4 integration settings (OAuth only)."""
from dataclasses import dataclass


@dataclass
class GA4Settings:
    ga4_property_id: str

    def is_configured(self) -> bool:
        return bool((self.ga4_property_id or "").strip())
