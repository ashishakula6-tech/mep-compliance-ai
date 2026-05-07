import os
import json
import shutil
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from app.routes import upload, compliance, auth
from app.services.auth_service import init_db


def _seed_sample_reports():
    """Pre-populate uploads/ and sample_outputs/ with demo data on first run."""
    sample_dir = "sample_inputs"
    upload_dir = "uploads"
    reports_dir = "sample_outputs"
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    if not os.path.isdir(sample_dir):
        return

    # Only seed if no reports exist yet
    existing = [f for f in os.listdir(reports_dir) if f.endswith(".json") and f != "example_report.json"]
    if existing:
        return

    from datetime import datetime
    from app.services.file_service import extract_data_from_file
    from app.services.rule_engine import load_rules, check_compliance, compute_risk_score
    from app.services.ai_service import generate_suggestions, generate_summary

    for fname in ["hvac_spec.txt", "electrical_spec.json", "mixed_mep_spec.txt"]:
        src = os.path.join(sample_dir, fname)
        if not os.path.exists(src):
            continue
        dst = os.path.join(upload_dir, fname)
        shutil.copy2(src, dst)

        extracted = extract_data_from_file(dst)
        if not extracted or "_error" in extracted:
            continue
        rules = load_rules()
        violations, compliant_count = check_compliance(extracted, rules)
        risk_score, risk_level = compute_risk_score(violations, compliant_count)
        suggestions = generate_suggestions(violations)
        summary = generate_summary(violations, risk_score, risk_level)

        report = {
            "file": fname,
            "extracted_parameters": extracted,
            "violations": [v.model_dump() for v in violations],
            "suggestions": [s.model_dump() for s in suggestions],
            "risk_score": risk_score,
            "risk_level": risk_level,
            "summary": summary,
            "compliant_count": compliant_count,
            "violation_count": len(violations),
        }
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(reports_dir, f"report_{fname}_{ts}.json")
        with open(out, "w") as f:
            json.dump(report, f, indent=2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_sample_reports()
    yield


app = FastAPI(
    title="MEP AI Compliance System",
    description="Upload MEP drawings or spec files → AI extracts parameters → Rule engine checks compliance → Claude generates fix suggestions.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

app.include_router(upload.router, prefix="/upload", tags=["Upload"])
app.include_router(compliance.router, prefix="/compliance", tags=["Compliance"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
