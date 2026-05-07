from pydantic import BaseModel
from typing import Optional, Any


class Violation(BaseModel):
    rule_id: str
    category: str
    rule: str
    parameter: str
    required_min: Optional[float]
    required_max: Optional[float]
    found: float
    unit: str
    severity: str
    code_reference: str


class Suggestion(BaseModel):
    rule_id: str
    issue: str
    suggestion: str
    ai_explanation: Optional[str] = None


class ComplianceReport(BaseModel):
    file: str
    extracted_parameters: dict[str, Any]
    violations: list[Violation]
    suggestions: list[Suggestion]
    risk_score: int
    risk_level: str
    summary: str
    compliant_count: int
    violation_count: int
