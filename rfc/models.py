from dataclasses import dataclass, field
from typing import Any


@dataclass
class Dashboard:
    managed_company_ids: list[str] = field(default_factory=list)


@dataclass
class Company:
    id: str
    name: str
    domains: list[str] = field(default_factory=list)
    compliance_status: str = field(default_factory=str)


@dataclass
class Task:
    id: str
    company_id: str
    prompt: str
    models: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)


@dataclass
class IOM:
    id: str
    name: str
    linked_canary_type_ids: list[str] = field(default_factory=list)


@dataclass
class CanaryType:
    id: str
    name: str


@dataclass
class CanaryInstance:
    id: str
    canary_type_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
