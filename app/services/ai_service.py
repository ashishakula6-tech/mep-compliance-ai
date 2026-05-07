import os
from app.models.schemas import Violation, Suggestion

_EXPLANATIONS = {
    "HVAC-001": lambda v: (
        f"Duct clearance of {v.found}mm violates ASHRAE 90.1 §6.4.3, which mandates a minimum {v.required_min}mm clearance "
        f"to ensure safe maintenance access, adequate insulation space, and compliance with fire egress requirements. "
        f"The duct must be rerouted or the obstruction removed to achieve at least {v.required_min}mm of unobstructed clearance on all sides. "
        f"Verify the fix with a site measurement and submit an as-built drawing showing the revised clearance dimension signed by a licensed MEP engineer."
    ),
    "HVAC-002": lambda v: (
        f"Supply air temperature of {v.found}°C is outside the ASHRAE 55-2020 thermal comfort band of {v.required_min}–{v.required_max}°C. "
        f"Temperatures outside this range cause occupant discomfort, increased complaints, and potential HVAC system inefficiency. "
        f"Recalibrate the AHU discharge air temperature setpoint to maintain between {v.required_min}°C and {v.required_max}°C under all load conditions. "
        f"Confirm the fix by running a TAB (Test, Adjust, Balance) report at full and part-load conditions across all zones."
    ),
    "HVAC-003": lambda v: (
        f"Fresh air rate of {v.found}% is below the ASHRAE 62.1 §6.2 minimum of {v.required_min}% for occupied commercial spaces, "
        f"creating indoor air quality risks including elevated CO₂, volatile organic compounds, and potential health code violations. "
        f"The outdoor air intake damper must be re-sized or its actuator recalibrated to deliver at least {v.required_min}% outside air at design conditions. "
        f"Verification requires a TAB report confirming the outdoor air fraction at both full-load and minimum ventilation operating modes."
    ),
    "ELEC-001": lambda v: (
        f"Electrical panel working clearance of {v.found}mm fails NEC 110.26(A), which requires a minimum {v.required_min}mm clear working space "
        f"in front of all electrical equipment to allow safe operation, maintenance, and emergency shutoff without obstruction. "
        f"Relocate the panel or remove encroaching structures to achieve the full {v.required_min}mm clear depth, width, and height as specified. "
        f"A licensed electrician must certify the corrected clearance on the as-built electrical drawings before final inspection."
    ),
    "ELEC-002": lambda v: (
        f"Cable tray fill of {v.found}% exceeds the NEC 392.22 maximum of {v.required_max}%, which exists to prevent overheating, "
        f"cable damage from weight, and difficulty pulling or replacing individual conductors during maintenance. "
        f"Redistribute cables to adjacent trays or install additional tray sections to bring fill below {v.required_max}% across all spans. "
        f"Document the corrected fill calculations per NEC 392.22(A) and submit to the engineer of record for approval."
    ),
    "ELEC-003": lambda v: (
        f"Conduit diameter of {v.found}mm is below the NEC 358.22 minimum of {v.required_min}mm for the specified circuit conductors, "
        f"which risks conductor damage during pull-in, excessive heat buildup, and code non-compliance on final inspection. "
        f"Replace the undersized conduit with a minimum {v.required_min}mm diameter conduit and verify fill ratios comply with NEC Chapter 9, Table 1. "
        f"An electrical inspector must sign off on the conduit sizing before energisation of the circuit."
    ),
    "PLMB-001": lambda v: (
        f"Drain pipe slope of {v.found}mm/m is insufficient — IPC §704.1 requires a minimum {v.required_min}mm/m to ensure self-cleaning velocity "
        f"and prevent solids accumulation, blockages, and sewer gas backup into occupied spaces. "
        f"Re-pitch the affected drain run to achieve at least {v.required_min}mm/m fall, which may require lowering invert levels or re-routing to a lower connection point. "
        f"Confirm with a camera inspection of the completed drain to verify continuous grade and absence of low spots."
    ),
    "PLMB-002": lambda v: (
        f"Hot water supply temperature of {v.found}°C is below the IPC §501.1 minimum of {v.required_min}°C, "
        f"creating a serious Legionella bacterial growth risk in the system — the bacteria thrive between 20°C and 50°C. "
        f"Raise the water heater setpoint to at least {v.required_min}°C and verify thermostatic mixing valves are set correctly at point-of-use fixtures. "
        f"Conduct a full Legionella risk assessment and water temperature log before the system is commissioned for occupancy."
    ),
    "PLMB-003": lambda v: (
        f"Cold water pressure of {v.found}kPa is outside the IPC §604.3 acceptable range of {v.required_min}–{v.required_max}kPa, "
        f"which affects fixture performance, pipe joint integrity, and water hammer risk throughout the distribution system. "
        f"{'Install a pressure-reducing valve (PRV) upstream to limit pressure to below ' + str(v.required_max) + 'kPa.' if v.found > (v.required_max or 0) else 'Install a pressure-boosting pump to raise supply pressure above ' + str(v.required_min) + 'kPa.'} "
        f"Verify with a calibrated gauge at the most remote and most proximate fixtures to confirm compliant pressure across all demand conditions."
    ),
    "FIRE-001": lambda v: (
        f"Sprinkler head spacing of {v.found}m exceeds the NFPA 13 §8.6.2 maximum of {v.required_max}m, "
        f"leaving coverage gaps that would allow a fire to grow beyond the design basis before activation — a life-safety critical violation. "
        f"Additional sprinkler heads must be installed to reduce spacing to no more than {v.required_max}m in all directions per the coverage area design. "
        f"The revised layout must be approved by a licensed fire protection engineer and the authority having jurisdiction (AHJ) before any ceiling work is closed."
    ),
    "FIRE-002": lambda v: (
        f"Fire suppression system pipe pressure of {v.found}kPa is below the NFPA 13 §7.1.1 minimum of {v.required_min}kPa, "
        f"meaning the system cannot deliver the required flow rate at the design sprinkler demand — a critical life-safety deficiency. "
        f"The fire pump must be upsized, re-impellerred, or the supply connection upgraded to guarantee at least {v.required_min}kPa at the hydraulically most remote head. "
        f"A full hydraulic calculation report must be submitted to the AHJ and a flow test witnessed by the fire marshal before system acceptance."
    ),
}

_SUMMARIES = {
    "LOW RISK": lambda vcount, vlist: (
        f"This MEP system is in strong compliance with {vcount} minor issue{'s' if vcount>1 else ''} identified. "
        f"The {'violations are' if vcount>1 else 'violation is'} low-severity and can be addressed during routine commissioning. "
        f"No immediate action is required before construction can proceed."
    ),
    "MEDIUM RISK": lambda vcount, vlist: (
        f"The MEP system has {vcount} compliance violation{'s' if vcount>1 else ''} requiring attention before occupancy sign-off. "
        f"Priority item: {vlist[0].rule} ({vlist[0].category}) — {vlist[0].severity} severity. "
        f"Coordinate remediation with the relevant subcontractors and re-submit for compliance review."
    ),
    "HIGH RISK": lambda vcount, vlist: (
        f"ATTENTION: {vcount} significant compliance violations detected. "
        f"The most critical issue is {vlist[0].rule} ({vlist[0].code_reference}) which must be resolved before proceeding. "
        f"Halt affected work scope and issue an RFI to the engineer of record immediately."
    ),
    "CRITICAL RISK": lambda vcount, vlist: (
        f"STOP WORK ADVISORY: {vcount} violations including {len([v for v in vlist if v.severity=='CRITICAL'])} CRITICAL life-safety issues. "
        f"Immediate remediation required on {vlist[0].rule}. "
        f"Do not commission or occupy until all violations are resolved and re-inspected by the authority having jurisdiction."
    ),
}


def _get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def generate_suggestions(violations: list[Violation], project_context: str = "") -> list[Suggestion]:
    client = _get_client()
    suggestions = []
    for v in violations:
        explanation = _get_explanation(client, v, project_context)
        fix = _build_fix_text(v)
        suggestions.append(Suggestion(
            rule_id=v.rule_id,
            issue=v.rule,
            suggestion=fix,
            ai_explanation=explanation,
        ))
    return suggestions


def _build_fix_text(v: Violation) -> str:
    parts = []
    if v.required_min is not None and v.found < v.required_min:
        parts.append(f"Increase {v.parameter.replace('_', ' ')} from {v.found}{v.unit} to at least {v.required_min}{v.unit}")
    if v.required_max is not None and v.found > v.required_max:
        parts.append(f"Reduce {v.parameter.replace('_', ' ')} from {v.found}{v.unit} to no more than {v.required_max}{v.unit}")
    return ". ".join(parts) + f". Reference: {v.code_reference}"


def _get_explanation(client, v: Violation, project_context: str) -> str:
    if client:
        prompt = (
            f"You are a licensed MEP compliance engineer. Explain this violation clearly and provide a practical fix.\n\n"
            f"Rule: {v.rule}\nCode Reference: {v.code_reference}\nCategory: {v.category}\n"
            f"Found value: {v.found} {v.unit}\n"
            f"Required minimum: {v.required_min} {v.unit if v.required_min else 'N/A'}\n"
            f"Required maximum: {v.required_max} {v.unit if v.required_max else 'N/A'}\n"
            f"Severity: {v.severity}\n\n"
            "In 3-4 sentences: (1) why this matters for safety/code, "
            "(2) exactly what needs to change, (3) how to verify the fix."
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    fn = _EXPLANATIONS.get(v.rule_id)
    if fn:
        return fn(v)
    parts = []
    if v.required_min and v.found < v.required_min:
        parts.append(f"the value of {v.found}{v.unit} is below the minimum required {v.required_min}{v.unit} per {v.code_reference}")
    if v.required_max and v.found > v.required_max:
        parts.append(f"the value of {v.found}{v.unit} exceeds the maximum allowed {v.required_max}{v.unit} per {v.code_reference}")
    return (
        f"This {v.category} violation ({v.rule}) is flagged because {' and '.join(parts)}. "
        f"Immediate remediation is required to achieve code compliance. "
        f"Engage the relevant subcontractor and re-submit for inspection after the correction is made."
    )


def generate_summary(violations: list[Violation], risk_score: int, risk_level: str, client=None) -> str:
    if not violations:
        return "All checked parameters are fully compliant with applicable MEP codes. No corrective action required. The system is ready for commissioning sign-off."

    c = client or _get_client()
    if c:
        prompt = (
            f"Summarize this MEP compliance report in 2-3 sentences for a project manager:\n"
            f"Violations ({len(violations)}): {[v.rule for v in violations]}\n"
            f"Risk score: {risk_score}/100 ({risk_level})\n"
            f"Most critical: {violations[0].rule}"
        )
        response = c.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    level_key = next((k for k in _SUMMARIES if k in risk_level), "MEDIUM RISK")
    return _SUMMARIES[level_key](len(violations), violations)
