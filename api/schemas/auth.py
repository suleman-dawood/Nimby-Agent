"""Auth schemas."""

from pydantic import BaseModel


class GoogleAuthRequest(BaseModel):
    id_token: str


class UserResponse(BaseModel):
    id: int
    email: str
    name: str | None
    avatar_url: str | None
    tokens_remaining: int
    tokens_used: int


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
