from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status


class BearerTokenAuth:
    def __init__(self, token: str | None) -> None:
        self.token = token

    async def __call__(
        self, authorization: str | None = Header(default=None)
    ) -> None:
        if self.token is None:
            return
        scheme, _, supplied = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(
            supplied, self.token
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bearer token",
            )

