from pydantic import BaseModel,EmailStr
from typing import Literal



class InviteInfoSchema(BaseModel):
    email: EmailStr
    department_id: str
    invite_code: str

class DingTAlkTokenInfoSchema(BaseModel):
    access_token: str
    refresh_token: str
    user_id: str

from schemas.agent_schema import AgentCandidateSchema
class TaskInfoSchema(BaseModel):
    task_id: str
    status: Literal["pending","done","failed"]
    result: AgentCandidateSchema | None = None
    error: str | None = None