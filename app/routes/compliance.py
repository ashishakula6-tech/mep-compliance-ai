import os
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.file_service import extract_data_from_file
from app.services.rule_engine import load_rules, check_compliance, compute_risk_score
from app.services.ai_service import generate_suggestions, generate_summary
from app.models.schemas import ComplianceReport

router = APIRouter()
UPLOAD_DIR = "uploads"
REPORTS_DIR = "sample_outputs"
os.makedirs(REPORTS_DIR, exist_ok=True)


@router.get("/report", summary="Run compliance check on an uploaded file")
def generate_report(
    filename: str = Query(..., description="Name of uploaded file"),
    save_report: bool = Query(True, description="Save JSON report to sample_outputs/"),
):
    file_path = os.path.join(UPLOAD_DIR, filename)
    source = "manual" if filename == "manual_entry.json" else "file"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found. Upload it first via POST /upload")

    extracted = extract_data_from_file(file_path)

    if not extracted or "_error" in extracted:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Could not extract MEP parameters from file",
                "error": extracted.get("_error", "No recognisable parameters found"),
                "hint": "Use a .txt or .json file. See sample_inputs/ for examples.",
            }
        )

    rules = load_rules()
    violations, compliant_count = check_compliance(extracted, rules)
    risk_score, risk_level = compute_risk_score(violations, compliant_count)
    suggestions = generate_suggestions(violations)
    summary = generate_summary(violations, risk_score, risk_level)

    report = ComplianceReport(
        file=filename,
        extracted_parameters=extracted,
        violations=violations,
        suggestions=suggestions,
        risk_score=risk_score,
        risk_level=risk_level,
        summary=summary,
        compliant_count=compliant_count,
        violation_count=len(violations),
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_id = f"{filename}_{ts}"
    out_path = os.path.join(REPORTS_DIR, f"report_{report_id}.json")
    payload = {**report.model_dump(), "source": source, "report_id": report_id, "timestamp": ts}
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    return {**payload, "report_saved_to": out_path}


@router.get("/reports", summary="List all past compliance reports")
def list_reports():
    reports = []
    for f in sorted(os.listdir(REPORTS_DIR), reverse=True):
        if not f.endswith(".json") or f == "example_report.json":
            continue
        path = os.path.join(REPORTS_DIR, f)
        try:
            with open(path) as fh:
                data = json.load(fh)
            viols = data.get("violations", [])
            sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
            for v in viols:
                s = v.get("severity", "LOW")
                if s in sev_counts:
                    sev_counts[s] += 1
            reports.append({
                "report_id": f.replace("report_", "").replace(".json", ""),
                "filename": f,
                "file": data.get("file", ""),
                "source": data.get("source", "file"),
                "risk_score": data.get("risk_score"),
                "risk_level": data.get("risk_level"),
                "violation_count": data.get("violation_count", 0),
                "compliant_count": data.get("compliant_count", 0),
                "severity_counts": sev_counts,
                "violations": viols,
                "suggestions": data.get("suggestions", []),
                "extracted_parameters": data.get("extracted_parameters", {}),
                "summary": data.get("summary", ""),
                "path": path,
            })
        except Exception:
            continue
    return {"reports": reports, "count": len(reports)}


@router.get("/reports/{report_id}", summary="Get a specific past report")
def get_report(report_id: str):
    path = os.path.join(REPORTS_DIR, f"report_{report_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report not found")
    with open(path) as f:
        return json.load(f)


@router.get("/rules", summary="List all loaded compliance rules")
def list_rules(category: str = Query(None)):
    rules = load_rules()
    if category:
        rules = [r for r in rules if r["category"].lower() == category.lower()]
    return {"rules": rules, "count": len(rules)}


@router.get("/parameters", summary="List all extractable MEP parameters")
def list_parameters():
    from app.services.file_service import PARAMETER_PATTERNS
    return {
        "extractable_parameters": list(PARAMETER_PATTERNS.keys()),
        "tip": "Include these parameter names and values in your uploaded spec files"
    }
