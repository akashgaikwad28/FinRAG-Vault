from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import uuid
from typing import List, Optional
from app.schemas.role import RoleResponse


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, description="Unique username identifier", examples=["jane_analyst"])
    email: EmailStr = Field(..., description="Unique email address", examples=["jane.doe@finragvault.com"])
    company_name: Optional[str] = Field(None, max_length=100, description="The company name, crucial for Client role isolation", examples=["Acme Corp"])


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="Plaintext security password", examples=["AnalystPassword123!"])


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    email: Optional[EmailStr] = Field(None)
    company_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = Field(None)
    roles: Optional[List[str]] = Field(None, description="List of role names to assign to the user")


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    roles: List[RoleResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True
