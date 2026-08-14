"""Admin user, role, local identity, and project-membership contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ApiTimestamp


AppRole = Literal["Admin", "Architect", "Analyst", "Viewer"]
ProjectRole = Literal["Owner", "Contributor", "Viewer"]


def _normalized_identity(value: str) -> str:
    normalized = value.strip().casefold()
    if not normalized or any(character.isspace() for character in normalized):
        raise ValueError("must be a non-blank value without whitespace")
    return normalized


class UserProjectMembershipInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    project_role: Literal["Contributor", "Viewer"] = "Contributor"


class UserProjectMembershipResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    project_id: str
    project_name: str
    project_role: ProjectRole


class ManagedUserCreateRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    username: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=255)
    role: AppRole
    password: str = Field(min_length=12, max_length=4096)
    memberships: list[UserProjectMembershipInput] = Field(default_factory=list, max_length=100)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return _normalized_identity(value)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if "@" not in normalized:
            raise ValueError("must be a valid email address")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class ManagedUserPatchRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    expected_updated_at: ApiTimestamp
    username: Optional[str] = Field(default=None, min_length=1, max_length=255)
    email: Optional[str] = Field(default=None, min_length=3, max_length=320)
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[AppRole] = None
    is_active: Optional[bool] = None
    reset_password: Optional[str] = Field(default=None, min_length=12, max_length=4096)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: Optional[str]) -> Optional[str]:
        return _normalized_identity(value) if value is not None else None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().casefold()
        if "@" not in normalized:
            raise ValueError("must be a valid email address")
        return normalized

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class UserMembershipReplaceRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    expected_updated_at: ApiTimestamp
    memberships: list[UserProjectMembershipInput] = Field(default_factory=list, max_length=100)


class ManagedUserResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    id: str
    username: Optional[str]
    email: str
    display_name: str
    role: AppRole
    is_active: bool
    providers: list[Literal["local", "oci_iam"]]
    memberships: list[UserProjectMembershipResponse]
    last_authenticated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class ManagedUserListResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    users: list[ManagedUserResponse]
    total: int
