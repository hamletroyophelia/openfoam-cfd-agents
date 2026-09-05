"""Scoped evidence reuse. Dependencies contain revision ids, never agent verdicts."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    schema_version: Literal[2] = 2
    kind: Literal['declared', 'contract', 'runtime', 'numerical', 'physical', 'presentation']
    dependencies: dict[str, str] = Field(min_length=1)
    artifacts: list[str] = Field(min_length=1)


def reusable_evidence(record: EvidenceRecord, current_revisions: dict[str, str]) -> bool:
    """Missing or changed dependencies invalidate reuse; historical evidence is retained."""
    return all(value and current_revisions.get(key) == value for key, value in record.dependencies.items())


class ApprovalScope(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    case_revision: str = Field(min_length=1)
    rules_revision: str = Field(min_length=1)
    resource_budget_revision: str = Field(min_length=1)
    action: str = Field(min_length=1)


def approval_applies(approved: ApprovalScope, proposed: ApprovalScope) -> bool:
    return approved == proposed
