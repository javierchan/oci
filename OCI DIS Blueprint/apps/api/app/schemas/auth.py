"""Strict contracts for local sessions and read-only external API tokens."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.api_token_scopes import ALL_API_TOKEN_SCOPES


class LoginRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=4096)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    current_password: str = Field(min_length=1, max_length=4096)
    new_password: str = Field(min_length=12, max_length=4096)


class AuthUserResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    username: Optional[str]
    email: str
    display_name: str
    role: Literal["Admin", "Architect", "Analyst", "Viewer"]
    providers: list[Literal["local", "oci_iam"]]
    project_count: int


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    user: AuthUserResponse
    authentication_method: Literal["session", "api_token"]
    expires_at: Optional[datetime]


class ApiTokenCreateRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    expires_in_days: int = Field(default=90, ge=1, le=365)
    project_ids: Optional[list[str]] = Field(default=None, max_length=100)
    scopes: list[str] = Field(min_length=1, max_length=len(ALL_API_TOKEN_SCOPES))

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("project_ids")
    @classmethod
    def unique_project_ids(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        return list(dict.fromkeys(value))

    @field_validator("scopes")
    @classmethod
    def governed_scopes(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(item.strip() for item in value))
        invalid = set(normalized) - ALL_API_TOKEN_SCOPES
        if invalid:
            raise ValueError("unsupported API token scopes: " + ", ".join(sorted(invalid)))
        return normalized


class ApiTokenResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    name: str
    token_prefix: str
    scopes: list[str]
    project_ids: Optional[list[str]]
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]
    created_at: datetime


class ApiTokenCreatedResponse(ApiTokenResponse):
    token: str


class ApiTokenListResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    tokens: list[ApiTokenResponse]


class ApiTokenScopeResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    code: str
    label: str
    description: str


class ApiTokenScopeListResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    scopes: list[ApiTokenScopeResponse]
