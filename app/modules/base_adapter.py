from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class Hit(BaseModel):
    platform: str
    matched_selector: str
    matched_selector_id: Optional[int] = None
    profile_picture_path: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    region: Optional[str] = None
    last_active_date: Optional[str] = None
    account_status: str = "live"  # live | dead | archived
    source_tool: str = "enumeration_adapter"
    screenshot_path: Optional[str] = None
    confidence_tier: str = "LOW"  # HIGH | MEDIUM | LOW
    confidence_score: float = 0.0
    profile_url: Optional[str] = None
    rarity_weight: float = 1.0
    raw_data: Dict[str, Any] = Field(default_factory=dict)

class EnumerationAdapter(ABC):
    """
    Abstract Base Class for all OSINT Enumeration Adapters (§2).
    Every enumeration module must implement this contract.
    """
    @property
    @abstractmethod
    def selector_type(self) -> str:
        """The primary selector type supported: 'email' | 'username' | 'phone' | 'domain'"""
        pass

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Name of the source tool / adapter"""
        pass

    @abstractmethod
    async def run(self, selector: str, investigation_id: str) -> List[Hit]:
        """
        Executes enumeration for given selector and investigation_id.
        MUST NOT raise on partial failures — log to evidence audit log and skip individual platform failures.
        Returns a list of normalized Hit objects.
        """
        pass
