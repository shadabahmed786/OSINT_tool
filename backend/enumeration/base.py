from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Hit:
    platform: str
    source_tool: str
    profile_picture_path: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    region: Optional[str] = None
    last_active_date: Optional[str] = None
    account_status: str = "live"
    screenshot_path: Optional[str] = None
    confidence_tier: str = "medium"
    confidence_score: float = 0.5


class EnumerationAdapter(ABC):
    selector_type: str

    @abstractmethod
    async def run(self, selector: str, investigation_id: str) -> list[Hit]:
        pass
