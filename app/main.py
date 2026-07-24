import uuid
import re
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from pathlib import Path

from app.config import BASE_DIR
from app.database import (
    init_db, create_investigation, update_investigation_status,
    add_finding, log_evidence, get_investigation, list_investigations
)
from app.models import SelectorInput, PasswordCheckInput
from app.modules.email_checker import EmailChecker
from app.modules.username_checker import UsernameChecker
from app.modules.phone_checker import PhoneChecker
from app.modules.hibp_checker import check_password_exposure
from app.modules.scoring_engine import score_and_rank_findings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("osint_app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await init_db()
    logger.info("OSINT Investigation Platform Backend initialized.")
    yield
    # Shutdown logic

app = FastAPI(
    title="OSINT Investigation Platform",
    description="Local-First OSINT Pivot Engine & Evidence Logger",
    version="0.1.0",
    lifespan=lifespan
)

# Detect selector type automatically if user didn't specify
def detect_selector_type(target: str) -> str:
    target_clean = target.strip()
    if "@" in target_clean and "." in target_clean:
        return "email"
    digits_only = re.sub(r"\D", "", target_clean)
    if (target_clean.startswith("+") or digits_only.isdigit()) and len(digits_only) >= 7:
        return "phone"
    if " " in target_clean:
        return "name"
    return "username"

# Asynchronous background task runner for investigations
async def run_investigation_task(investigation_id: str, target: str, selector_type: str):
    logger.info("Executing background investigation %s for %s (%s)", investigation_id, target, selector_type)
    
    raw_findings = []

    try:
        if selector_type == "email":
            checker = EmailChecker()
            raw_findings = await checker.check(target, selector_type)
        elif selector_type == "username":
            checker = UsernameChecker()
            raw_findings = await checker.check(target, selector_type)
        elif selector_type == "phone":
            checker = PhoneChecker()
            raw_findings = await checker.check(target, selector_type)
        else:
            # Fallback check username module for general names/selectors
            checker = UsernameChecker()
            raw_findings = await checker.check(target, "username")

        # Score and rank findings
        scored = score_and_rank_findings(raw_findings)

        # Save findings to database
        for hit in scored:
            await add_finding(investigation_id, hit)

        summary_msg = f"Completed check for '{target}'. Discovered {len(scored)} hit(s)."
        await update_investigation_status(investigation_id, "completed", summary_msg)
        await log_evidence(investigation_id, "investigation_completed", summary_msg)

    except Exception as e:
        logger.error("Investigation failed: %s", e)
        await update_investigation_status(investigation_id, "failed", str(e))
        await log_evidence(investigation_id, "error", f"Investigation failed: {e}")

@app.post("/api/investigate")
async def start_investigation(input_data: SelectorInput, background_tasks: BackgroundTasks):
    target = input_data.target.strip()
    if not target:
        raise HTTPException(status_code=400, detail="Target selector cannot be empty")

    selector_type = input_data.selector_type or detect_selector_type(target)
    investigation_id = str(uuid.uuid4())

    await create_investigation(investigation_id, target, selector_type)

    # Run investigation asynchronously
    background_tasks.add_task(run_investigation_task, investigation_id, target, selector_type)

    return {
        "id": investigation_id,
        "target": target,
        "selector_type": selector_type,
        "status": "running"
    }

@app.get("/api/investigations")
async def fetch_investigations():
    return await list_investigations()

@app.get("/api/investigations/{investigation_id}")
async def fetch_investigation_detail(investigation_id: str):
    inv = await get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv

@app.post("/api/check-password-hash")
async def check_password(input_data: PasswordCheckInput):
    return await check_password_exposure(input_data.password)

@app.get("/api/export/{investigation_id}")
async def export_report(investigation_id: str, format: str = "markdown"):
    inv = await get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    target = inv.get("initial_selector") or inv.get("target", "Target")
    selector_type = inv.get("initial_selector_type") or inv.get("selector_type", "selector")
    created_at = inv.get("created_at", "")
    findings = inv.get("findings", [])
    evidence_log = inv.get("evidence_log", [])

    # Calculate overall confidence
    high_cnt = sum(1 for f in findings if f.get("confidence_tier") == "HIGH")
    overall = "HIGH" if high_cnt > 0 else ("MEDIUM" if len(findings) > 0 else "LOW")

    md_lines = [
        f"# OSINT Investigation Report",
        f"**Target:** `{target}` ({selector_type})  ",
        f"**Date:** {created_at}  ",
        f"**Overall Confidence:** **{overall}**  ",
        f"**Total Findings:** {len(findings)}",
        "",
        "## Discovered Accounts & Findings",
        "| Platform | Display Name / Status | Confidence | URL |",
        "|---|---|---|---|",
    ]

    for f in findings:
        plat = f.get("platform", "Unknown")
        name = f.get("display_name") or f.get("matched_selector")
        tier = f.get("confidence_tier", "LOW")
        score = f.get("confidence_score", 0.0)
        url = f.get("profile_url") or "N/A"
        md_lines.append(f"| {plat} | {name} | **{tier}** ({score}%) | [{url}]({url}) |")

    md_lines.extend([
        "",
        "## Evidence & Audit Log",
        "| Timestamp | Event | Details |",
        "|---|---|---|",
    ])

    for log in evidence_log:
        ts = log.get("timestamp", "")
        evt = log.get("event_type", "")
        dt = log.get("details", "")
        md_lines.append(f"| {ts} | `{evt}` | {dt} |")

    report_md = "\n".join(md_lines)

    if format == "html":
        html_content = f"<html><head><title>OSINT Report - {target}</title><style>body{{font-family:sans-serif;padding:30px;line-height:1.6;background:#0d1117;color:#c9d1d9;}}table{{border-collapse:collapse;width:100%;}}th,td{{border:1px solid #30363d;padding:8px 12px;}}th{{background:#161b22;}}a{{color:#58a6ff;}}</style></head><body><pre>{report_md}</pre></body></html>"
        return HTMLResponse(content=html_content)

    return Response(content=report_md, media_type="text/markdown", headers={"Content-Disposition": f"attachment; filename=OSINT_Report_{investigation_id[:8]}.md"})

@app.post("/api/investigations/{investigation_id}/ai-summary")
async def generate_ai_summary(investigation_id: str):
    inv = await get_investigation(investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    target = inv.get("initial_selector") or inv.get("target", "Target")
    selector_type = inv.get("initial_selector_type") or inv.get("selector_type", "selector")
    findings = inv.get("findings", [])

    high_findings = [f for f in findings if f.get("confidence_tier") == "HIGH"]
    med_findings = [f for f in findings if f.get("confidence_tier") == "MEDIUM"]

    # Try calling local Ollama instance if available
    from app.config import OLLAMA_HOST, DEFAULT_TEXT_MODEL
    import httpx

    prompt = f"""You are an expert OSINT analyst. Write a concise executive summary report for an investigation on selector '{target}' ({selector_type}).
Discovered {len(findings)} total accounts across platforms:
High Confidence: {len(high_findings)}
Medium Confidence: {len(med_findings)}

Top Findings:
"""
    for f in findings[:8]:
        prompt += f"- Platform: {f.get('platform')}, Display Name: {f.get('display_name')}, Confidence: {f.get('confidence_tier')} ({f.get('confidence_score')}%)\n"

    prompt += "\nSummarize key insights, digital footprint, potential pivot targets, and recommended next steps."

    summary_text = ""
    engine_used = "Local OSINT Heuristic AI Engine"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={"model": DEFAULT_TEXT_MODEL, "prompt": prompt, "stream": False}
            )
            if resp.status_code == 200:
                summary_text = resp.json().get("response", "").strip()
                engine_used = f"Ollama Local Model ({DEFAULT_TEXT_MODEL})"
    except Exception:
        pass

    if not summary_text:
        # Fallback to local structured intelligence synthesis engine
        lines = [
            f"### Executive Summary for `{target}` ({selector_type.upper()})",
            f"**Assessment:** Target selector yielded **{len(findings)} platform match(es)**.",
        ]
        if high_findings:
            high_names = ", ".join(f.get("platform") for f in high_findings)
            lines.append(f"**High Confidence Matches:** Verified footprint identified on **{high_names}**. Cross-platform alias matching indicates strong identity correlation.")
        elif med_findings:
            med_names = ", ".join(f.get("platform") for f in med_findings)
            lines.append(f"**Moderate Confidence Matches:** Footprint identified on **{med_names}**. Recommended further verification.")
        else:
            lines.append("**Low Signal / No High-Confidence Hits:** Discovered profile matches are low confidence or common aliases.")

        lines.extend([
            "",
            "**Recommended Actionable Pivot Steps:**",
            f"1. Cross-reference discovered username `{target}` against domain registries and code repositories.",
            "2. Execute reverse profile image hash checks on pulled avatars.",
            "3. Export full Markdown evidence log for official case archiving."
        ])
        summary_text = "\n".join(lines)

    return {
        "investigation_id": investigation_id,
        "target": target,
        "engine": engine_used,
        "summary": summary_text
    }

@app.get("/api/investigations/{investigation_id}/pending-selectors")
async def fetch_pending_selectors(investigation_id: str):
    from app.database import get_pending_selectors
    return await get_pending_selectors(investigation_id)

@app.post("/api/investigations/{investigation_id}/approve-selector/{selector_id}")
async def approve_discovered_selector(investigation_id: str, selector_id: int):
    from app.database import approve_selector
    success = await approve_selector(selector_id)
    if not success:
        raise HTTPException(status_code=404, detail="Selector not found")
    return {"status": "approved", "selector_id": selector_id}

@app.post("/api/admin/cleanup-expired")
async def run_data_retention_cleanup():
    from app.database import cleanup_expired_investigations
    count = await cleanup_expired_investigations()
    return {"status": "success", "purged_investigations": count}

# Serve static web frontend
static_path = BASE_DIR / "app" / "static"
static_path.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
