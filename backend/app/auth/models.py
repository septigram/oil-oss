"""認証ドメインモデル。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Role(StrEnum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class CurrentUser(BaseModel):
    user_id: str
    employee_id: str
    display_name: str
    login_name: str
    roles: list[Role]

    def has_any_role(self, *roles: Role) -> bool:
        role_set = set(self.roles)
        return any(r in role_set for r in roles)


class LoginRequest(BaseModel):
    login_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class UserSummaryResponse(BaseModel):
    user_id: str
    employee_id: str
    display_name: str
    roles: list[str]


class UserListItem(BaseModel):
    user_id: str
    employee_id: str
    employee_name: str
    login_name: str
    is_active: bool
    roles: list[str]
    row_version: int


class UserCreateRequest(BaseModel):
    employee_id: str
    login_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)
    roles: list[Role] = Field(default_factory=lambda: [Role.OPERATOR])


class UserUpdateRequest(BaseModel):
    row_version: int
    is_active: bool | None = None
    password: str | None = None


class UserRolesUpdateRequest(BaseModel):
    row_version: int
    roles: list[Role]
