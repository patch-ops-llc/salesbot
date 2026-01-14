import httpx
from typing import Optional
from .models import CRMLeadPayload, Executive


class CRMClient:
    """Client for interacting with the PatchOps CRM API"""
    
    BASE_URL = "https://work.patchops.io"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    async def create_lead(self, payload: CRMLeadPayload) -> dict:
        """Create a new lead in the CRM"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/api/leads",
                json=payload.model_dump(exclude_none=True),
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def create_lead_from_executive(
        self,
        executive: Executive,
        stage_id: str,
        custom_message: str,
        priority: str = "medium"
    ) -> dict:
        """Create a CRM lead from an executive profile"""
        notes = f"""LinkedIn Profile: {executive.linkedin_url}
Title: {executive.title}
Hiring for: {executive.company_job_title or 'N/A'}

Connection Message Sent:
{custom_message}

Profile Summary:
{executive.profile_summary or 'N/A'}"""

        payload = CRMLeadPayload(
            name=executive.name,
            stageId=stage_id,
            company=executive.company,
            priority=priority,
            source="LinkedIn Sales Robot",
            nextSteps="Follow up on LinkedIn connection acceptance",
            notes=notes
        )
        
        return await self.create_lead(payload)

