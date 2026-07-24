from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Any, Optional

class SelectorInput(BaseModel):
    target: str = Field(..., description="Target selector (email, username, phone, or name)")
    selector_type: Optional[str] = Field(None, description="Optional override: email, username, phone, name")

class FindingSchema(BaseModel):
    platform: str
    matched_selector: str
    display_name: Optional[str] = None
    profile_url: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    status: str = "active"  # active, dead, possible
    confidence_tier: str = "LOW"  # HIGH, MEDIUM, LOW
    confidence_score: float = 0.0
    rarity_weight: float = 1.0
    screenshot_path: Optional[str] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)

class PasswordCheckInput(BaseModel):
    password: str = Field(..., description="Plain password or hash to check against HIBP k-anonymity database")

class InvestigationResponse(BaseModel):
    id: str
    target: str
    selector_type: str
    status: str
    summary: Optional[str] = None
    findings: List[FindingSchema] = Field(default_factory=list)
    evidence_log: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
