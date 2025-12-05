from pydantic import BaseModel
from typing import Optional, Dict

class BuildRequest(BaseModel):
    prompt: str
    clarification_answer: Optional[str] = None
    global_spec: Optional[str] = None

class BuildResponse(BaseModel):
    status: str
    details: Optional[Dict] = None