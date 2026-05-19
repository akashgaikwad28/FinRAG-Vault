from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class RoleBase(BaseModel):
    name: str = Field(..., max_length=50, description="The name of the role, e.g. Admin, Financial Analyst", examples=["Financial Analyst"])
    description: str | None = Field(None, max_length=255, description="A description of what permissions this role grants", examples=["Analyze company reports and upload document metadata"])


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = Field(None, max_length=50, examples=["Lead Analyst"])
    description: str | None = Field(None, max_length=255)


class RoleResponse(RoleBase):
    id: uuid.UUID = Field(..., description="Unique Role UUID identifier")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
