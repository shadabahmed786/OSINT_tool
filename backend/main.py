import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import sqlite3
import yaml
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.breach.hibp_pwned_passwords import check_password_exposure_kanonymity
from backend.correlation.scoring import compute_rule_confidence
from backend.db.models import DatabaseManager
from backend.enumeration.base import Hit
from backend.models_runtime.model_manager import ModelManager
from backend.case.graph import generate_case_graph

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
STATIC_DIR = Path(__file__).resolve().parent.parent / "app" / "static"
with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file)

for env_var in config["guardrails"]["banned_api_keys"]:
    if os.environ.get(env_var):
        raise SystemExit(f"GUARDRAIL CRITICAL FAILURE: Cloud API Key detected in environment ({env_var}). System halted.")


def detect_selector_type(target: str) -> str:
    target_clean = target.strip()
    if "@" in target_clean and "." in target_clean:
        return "email"
    digits_only = "".join(ch for ch in target_clean if ch.isdigit())
    if (target_clean.startswith("+") or digits_only.isdigit()) and len(digits_only) >= 7:
        return "phone"
    if " " in target_clean:
        return "name"
    return "username"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db._init_db()
    yield


app = FastAPI(title="Local OSINT Platform", lifespan=lifespan)
db = DatabaseManager()
model_manager = ModelManager(ollama_url=config["ai"]["ollama_base_url"])


@app.post("/investigations/new")
async def create_investigation(selector: str, selector_type: str):
    investigation_id = str(uuid.uuid4())
    retention_days = int(config["retention"]["default_days"])
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO investigations (id, initial_selector, initial_selector_type, retention_days) VALUES (?, ?, ?, ?)",
            (investigation_id, selector, selector_type, retention_days),
        )
        cursor.execute(
            "INSERT INTO selectors (investigation_id, selector_value, selector_type, approved) VALUES (?, ?, ?, 1)",
            (investigation_id, selector, selector_type),
        )
        conn.commit()

    db.log_evidence(investigation_id, "investigation_created", {"selector": selector, "type": selector_type})
    return {"investigation_id": investigation_id, "id": investigation_id, "target": selector, "selector_type": selector_type, "retention_days": retention_days}


@app.get("/investigations/{investigation_id}")
async def get_investigation(investigation_id: str):
    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        inv = conn.cursor().execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,)).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Investigation not found")
        selectors = conn.cursor().execute("SELECT * FROM selectors WHERE investigation_id = ?", (investigation_id,)).fetchall()
        findings = conn.cursor().execute("SELECT * FROM hits WHERE investigation_id = ? ORDER BY confidence_score DESC", (investigation_id,)).fetchall()
        logs = conn.cursor().execute("SELECT * FROM evidence_log WHERE investigation_id = ? ORDER BY id ASC", (investigation_id,)).fetchall()
    return {
        **dict(inv),
        "selectors": [dict(row) for row in selectors],
        "findings": [dict(row) for row in findings],
        "evidence_log": [dict(row) for row in logs],
    }


@app.get("/api/investigations/{investigation_id}")
async def api_get_investigation(investigation_id: str):
    return await get_investigation(investigation_id)


@app.post("/investigations/{inv_id}/run")
async def run_enumeration(inv_id: str, background_tasks: BackgroundTasks):
    try:
        with db.get_connection() as conn:
            selector_row = conn.cursor().execute(
                "SELECT selector_value, selector_type FROM selectors WHERE investigation_id = ? AND approved = 1",
                (inv_id,),
            ).fetchone()

        if not selector_row:
            raise HTTPException(status_code=400, detail="No approved selector found to pivot on.")

        selector, selector_type = selector_row["selector_value"], selector_row["selector_type"]
        hits: list[Hit] = []

        if selector_type == "email":
            from backend.enumeration.holehe_adapter import HoleheAdapter
            adapter = HoleheAdapter(db)
            hits = await adapter.run(selector, inv_id)
        elif selector_type == "username":
            from backend.enumeration.sherlock_adapter import SherlockAdapter
            adapter = SherlockAdapter(db)
            hits = await adapter.run(selector, inv_id)
        elif selector_type == "phone":
            from backend.enumeration.phoneinfoga_adapter import PhoneInfogaAdapter
            adapter = PhoneInfogaAdapter(db)
            hits = await adapter.run(selector, inv_id)
        elif selector_type == "domain":
            from backend.enumeration.theharvester_adapter import TheHarvesterAdapter
            adapter = TheHarvesterAdapter(db)
            hits = await adapter.run(selector, inv_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported selector type: {selector_type}")

        with db.get_connection() as conn:
            cursor = conn.cursor()
            for hit in hits:
                tier, score = compute_rule_confidence(hit, len(hits), False)
                cursor.execute(
                    """INSERT INTO hits (investigation_id, platform, source_tool, account_status, confidence_tier, confidence_score) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (inv_id, hit.platform, hit.source_tool, hit.account_status, tier.upper(), score),
                )
            conn.commit()

        db.update_investigation_status(inv_id, "completed", f"Enumeration finished with {len(hits)} hit(s).")
        return {"status": "complete", "hits_found": len(hits)}
    except Exception as exc:
        if isinstance(exc, HTTPException):
            db.update_investigation_status(inv_id, "failed", exc.detail)
            raise

        db.update_investigation_status(inv_id, "failed", str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/investigations/{inv_id}/run")
async def api_run_enumeration(inv_id: str, background_tasks: BackgroundTasks):
    return await run_enumeration(inv_id, background_tasks)


@app.post("/investigations/{inv_id}/approve-selector/{selector_id}")
async def approve_selector(inv_id: str, selector_id: int):
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE selectors SET approved = 1 WHERE id = ? AND investigation_id = ?", (selector_id, inv_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Selector not found")
        conn.commit()
    db.log_evidence(inv_id, "selector_approved", {"selector_id": selector_id})
    return {"status": "approved"}


@app.post("/api/investigations/{inv_id}/approve-selector/{selector_id}")
async def api_approve_selector(inv_id: str, selector_id: int):
    return await approve_selector(inv_id, selector_id)


@app.get("/investigations/{inv_id}/pending-selectors")
async def pending_selectors(inv_id: str):
    with db.get_connection() as conn:
        rows = conn.cursor().execute(
            "SELECT * FROM selectors WHERE investigation_id = ? AND approved = 0 ORDER BY id ASC",
            (inv_id,),
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/investigations/{inv_id}/pending-selectors")
async def api_pending_selectors(inv_id: str):
    return await pending_selectors(inv_id)


@app.get("/investigations/{inv_id}/graph")
async def get_graph(inv_id: str):
    return generate_case_graph(db.get_connection(), inv_id)


@app.get("/api/investigations/{inv_id}/graph")
async def api_get_graph(inv_id: str):
    return await get_graph(inv_id)


@app.get("/api/export/{investigation_id}")
async def api_export_report(investigation_id: str):
    with db.get_connection() as conn:
        inv = conn.cursor().execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,)).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Investigation not found")
        findings = conn.cursor().execute(
            "SELECT * FROM hits WHERE investigation_id = ? ORDER BY confidence_score DESC",
            (investigation_id,),
        ).fetchall()
        evidence_log = conn.cursor().execute(
            "SELECT * FROM evidence_log WHERE investigation_id = ? ORDER BY id ASC",
            (investigation_id,),
        ).fetchall()

    target = inv["initial_selector"]
    selector_type = inv["initial_selector_type"]
    created_at = inv["created_at"]
    high_cnt = sum(1 for finding in findings if finding["confidence_tier"] == "HIGH")
    overall = "HIGH" if high_cnt > 0 else ("MEDIUM" if findings else "LOW")

    md_lines = [
        "# OSINT Investigation Report",
        f"**Target:** `{target}` ({selector_type})  ",
        f"**Date:** {created_at}  ",
        f"**Overall Confidence:** **{overall}**  ",
        f"**Total Findings:** {len(findings)}",
        "",
        "## Discovered Accounts & Findings",
        "| Platform | Display Name / Status | Confidence | URL |",
        "|---|---|---|---|",
    ]

    for finding in findings:
        platform = finding["platform"] or "Unknown"
        display_name = finding["display_name"] or finding["matched_selector"] or "N/A"
        tier = finding["confidence_tier"] or "LOW"
        score = finding["confidence_score"] or 0.0
        profile_url = finding["profile_url"] or "N/A"
        md_lines.append(f"| {platform} | {display_name} | **{tier}** ({score}%) | [{profile_url}]({profile_url}) |")

    md_lines.extend([
        "",
        "## Evidence & Audit Log",
        "| Timestamp | Event | Details |",
        "|---|---|---|",
    ])

    for entry in evidence_log:
        md_lines.append(f"| {entry['timestamp']} | `{entry['action']}` | {entry['detail']} |")

    report_md = "\n".join(md_lines)
    return Response(
        content=report_md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=OSINT_Report_{investigation_id[:8]}.md"},
    )


@app.post("/investigations/{inv_id}/ai-summary")
async def generate_ai_summary(inv_id: str):
    with db.get_connection() as conn:
        inv = conn.cursor().execute("SELECT * FROM investigations WHERE id = ?", (inv_id,)).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Investigation not found")
        findings = conn.cursor().execute("SELECT * FROM hits WHERE investigation_id = ?", (inv_id,)).fetchall()

    target = inv["initial_selector"]
    selector_type = inv["initial_selector_type"]
    high_findings = [dict(row) for row in findings if row["confidence_tier"] == "HIGH"]
    med_findings = [dict(row) for row in findings if row["confidence_tier"] == "MEDIUM"]

    prompt = f"You are an expert OSINT analyst. Write a concise executive summary report for an investigation on selector '{target}' ({selector_type})."
    summary_text = ""
    engine_used = "Local OSINT Heuristic AI Engine"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{config['ai']['ollama_base_url']}/api/generate",
                json={"model": config["ai"]["text_llm_model"], "prompt": prompt, "stream": False},
            )
            if response.status_code == 200:
                summary_text = response.json().get("response", "").strip()
                engine_used = f"Ollama Local Model ({config['ai']['text_llm_model']})"
    except Exception:
        pass

    if not summary_text:
        summary_text = (
            f"### Executive Summary for `{target}` ({selector_type.upper()})\n"
            f"**Assessment:** Target selector yielded **{len(findings)} platform match(es)**.\n"
            f"**High Confidence Matches:** {len(high_findings)}\n"
            f"**Moderate Confidence Matches:** {len(med_findings)}"
        )

    return {"investigation_id": inv_id, "target": target, "engine": engine_used, "summary": summary_text}


@app.post("/api/check-password-hash")
async def check_password(input_data: dict):
    return await check_password_exposure_kanonymity(input_data["password"])


@app.post("/api/investigate")
async def api_investigate(input_data: dict, background_tasks: BackgroundTasks):
    target = input_data.get("target", "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="Target selector cannot be empty")
    selector_type = input_data.get("selector_type") or detect_selector_type(target)
    retention_days = int(input_data.get("retention_days", config["retention"]["default_days"]))
    investigation_id = str(uuid.uuid4())
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO investigations (id, initial_selector, initial_selector_type, retention_days) VALUES (?, ?, ?, ?)",
            (investigation_id, target, selector_type, retention_days),
        )
        cursor.execute(
            "INSERT INTO selectors (investigation_id, selector_value, selector_type, approved) VALUES (?, ?, ?, 1)",
            (investigation_id, target, selector_type),
        )
        conn.commit()
    db.log_evidence(investigation_id, "investigation_created", {"selector": target, "type": selector_type})
    investigation = {"investigation_id": investigation_id, "id": investigation_id, "target": target, "selector_type": selector_type, "retention_days": retention_days, "status": "running"}
    background_tasks.add_task(run_enumeration, investigation["investigation_id"], background_tasks)
    return investigation


@app.get("/api/investigations")
async def api_list_investigations():
    with db.get_connection() as conn:
        rows = conn.cursor().execute("SELECT * FROM investigations ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=False), name="static")
