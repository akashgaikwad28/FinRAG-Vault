from pydantic import BaseModel, EmailStr, Field
from typing import Any, Dict, List, Optional
import uuid


class LoginRequest(BaseModel):
    email: str = Field(..., description="Login email address", examples=["admin@finragvault.com"])
    password: str = Field(..., description="Plaintext account password", examples=["AdminPassword123!"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100, examples=["client_acme"])
    email: EmailStr = Field(..., examples=["client_acme@finragvault.com"])
    password: str = Field(..., min_length=8, max_length=128, examples=["ClientPassword123!"])
    company_name: Optional[str] = Field(None, max_length=100, description="Crucial for Client role isolation", examples=["Acme Corp"])


class Token(BaseModel):
    access_token: str = Field(..., description="Cryptographically signed access token string")
    token_type: str = Field("bearer", description="The token validation protocol")


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[uuid.UUID] = None


# Enterprise standard response envelopes
class ValidationErrorDetail(BaseModel):
    field: str = Field(..., description="Path of the invalid field parameter")
    message: str = Field(..., description="Detailed description of the validation failure")


class StandardResponse(BaseModel):
    success: bool = Field(True, description="Indicates if the request succeeded")
    message: str = Field(..., description="Action completion message detail")
    data: Optional[Any] = Field(None, description="Response payload structure")


class StandardErrorResponse(BaseModel):
    success: bool = Field(False, description="Indicates if the request failed")
    message: str = Field(..., description="High-level description of the system exception")
    errors: Optional[List[ValidationErrorDetail]] = Field(None, description="Granular schema or validation error list")
