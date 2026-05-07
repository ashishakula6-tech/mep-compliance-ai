import json
from app.models.schemas import Violation


def load_rules() -> list[dict]:
    with open("app/data/rules.json") as f:
        return json.load(f)


def check_compliance(extracted_data: dict, rules: list[dict]) -> tuple[list[Violation], int]:
    violations = []
    checked = 0

    for rule in rules:
        param = rule["parameter"]
        if param not in extracted_data:
            continue

        value = float(extracted_data[param])
        min_val = rule.get("min_value")
        max_val = rule.get("max_value")
        checked += 1

        failed = False
        if min_val is not None and value < min_val:
            failed = True
        if max_val is not None and value > max_val:
            failed = True

        if failed:
            violations.append(Violation(
                rule_id=rule["id"],
                category=rule["category"],
                rule=rule["rule"],
                parameter=param,
                required_min=min_val,
                required_max=max_val,
                found=value,
                unit=rule["unit"],
                severity=rule["severity"],
                code_reference=rule["code_reference"],
            ))

    compliant = checked - len(violations)
    return violations, compliant


def compute_risk_score(violations: list[Violation], compliant_count: int) -> tuple[int, str]:
    if not violations and compliant_count == 0:
        return 100, "UNKNOWN"

    severity_weights = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 8, "LOW": 3}
    deduction = sum(severity_weights.get(v.severity, 5) for v in violations)
    score = max(0, 100 - deduction)

    if score >= 90:
        level = "LOW RISK"
    elif score >= 70:
        level = "MEDIUM RISK"
    elif score >= 50:
        level = "HIGH RISK"
    else:
        level = "CRITICAL RISK"

    return score, level
