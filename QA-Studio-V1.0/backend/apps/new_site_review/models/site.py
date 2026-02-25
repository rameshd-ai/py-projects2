"""Model for a site in New Site Review."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class SiteType(str, Enum):
    EXTERNAL = "External"
    MILESTONE = "Milestone"


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class Site:
    id: UUID
    name: str
    live_url: str
    site_type: SiteType
    last_scan_at: datetime | None = None
    scan_status: str = ScanStatus.PENDING.value
    ga4_results: dict | None = None
    export_download_url: str | None = None

    def __init__(
        self,
        name: str,
        live_url: str,
        site_type: SiteType = SiteType.EXTERNAL,
        id: UUID | None = None,
        last_scan_at: datetime | None = None,
        scan_status: str | None = None,
        ga4_results: dict | None = None,
        export_download_url: str | None = None,
    ):
        self.id = id or uuid4()
        self.name = name
        self.live_url = live_url
        self.site_type = site_type
        self.last_scan_at = last_scan_at
        self.scan_status = scan_status or ScanStatus.PENDING.value
        self.ga4_results = ga4_results
        self.export_download_url = export_download_url
