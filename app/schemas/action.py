from pydantic import BaseModel, Field
from typing import Dict, Optional


class ActionRequest(BaseModel):
    action_type: str = Field(
        ...,
        min_length=1,
        description="Type of action to execute (required)"
    )
    
    params: Dict = Field(
        default={},
        description="Parameters for the action"
    )
    
    user_id: int = Field(
        ...,
        ge=1,
        description="User ID (required, must be positive)"
    )


class ActionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None