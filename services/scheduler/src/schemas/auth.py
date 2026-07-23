from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EffectiveRole = Literal["admin", "supervisor", "operator", "field_team"]
CANONICAL_EFFECTIVE_ROLES = frozenset({"admin", "supervisor", "operator", "field_team"})


class EffectivePrincipalProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    subject: str = Field(min_length=1)
    effective_roles: list[EffectiveRole] = Field(min_length=1, max_length=4)

    @field_validator("effective_roles")
    @classmethod
    def require_sorted_unique_roles(
        cls, value: list[EffectiveRole]
    ) -> list[EffectiveRole]:
        if value != sorted(set(value)):
            raise ValueError("effective roles must be sorted and unique")
        return value
