from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class ConnectionStatus(str, Enum):
    pending = "pending"
    sent = "sent"
    accepted = "accepted"
    failed = "failed"


class SearchConfig(BaseModel):
    """Configuration for LinkedIn job search"""
    job_titles: List[str] = Field(default_factory=list, description="Job titles to search for")
    description_keywords: List[str] = Field(default_factory=list, description="Keywords to search for in job descriptions")
    locations: List[str] = Field(default_factory=list, description="Locations to filter by")
    company_sizes: List[str] = Field(default_factory=list, description="Company size filters")
    posted_within_days: int = Field(default=7, description="Jobs posted within X days")


class MessageTemplate(BaseModel):
    """Template for connection messages"""
    template: str = Field(..., description="Message template with placeholders")
    examples: List[str] = Field(default_factory=list, description="Example messages")


class Executive(BaseModel):
    """Represents a LinkedIn executive/lead"""
    name: str
    title: str
    company: str
    linkedin_url: str
    company_job_title: Optional[str] = None  # The job they're hiring for
    profile_summary: Optional[str] = None


class ConnectionRequest(BaseModel):
    """A connection request to be sent"""
    executive: Executive
    custom_message: str
    status: ConnectionStatus = ConnectionStatus.pending
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None


class CRMLeadPayload(BaseModel):
    """Payload for CRM lead creation"""
    name: str
    stageId: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    priority: Priority = Priority.medium
    value: Optional[str] = None
    source: str = "LinkedIn Sales Robot"
    nextSteps: Optional[str] = None
    notes: Optional[str] = None


class BotConfig(BaseModel):
    """Full bot configuration"""
    search_config: SearchConfig
    message_template: MessageTemplate
    crm_stage_id: str
    delay_between_connections: int = Field(default=30, description="Seconds between connections")
    max_connections_per_session: int = Field(default=20, description="Max connections per run")


class BotStatus(BaseModel):
    """Current bot status"""
    is_running: bool = False
    current_action: str = "Idle"
    connections_sent: int = 0
    connections_failed: int = 0
    leads_created: int = 0
    current_executive: Optional[Executive] = None
    log_messages: List[str] = Field(default_factory=list)

