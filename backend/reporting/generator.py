from backend.models_runtime.model_manager import ModelManager

REPORT_TEMPLATE = """
# OSINT Investigation Report
**Investigation ID:** {{ investigation_id }}
**Initial Selector:** {{ initial_selector }} ({{ selector_type }})
**Date Generated:** {{ timestamp }}

---

## Executive Summary
{{ summary_text }}

---

## Discovered Accounts & Findings
| Platform | Source Tool | Status | Confidence Tier | Score |
|----------|-------------|--------|-----------------|-------|
{% for hit in hits %}
| {{ hit.platform }} | {{ hit.source_tool }} | {{ hit.account_status }} | **{{ hit.confidence_tier | upper }}** | {{ hit.confidence_score }} |
{% endfor %}

---

## Evidence Audit Log
{% for log in logs %}
- **[{{ log.timestamp }}]** `{{ log.action }}`: {{ log.detail }}
{% endfor %}
"""


async def generate_pdf_report(investigation_id: str, initial_selector: str, selector_type: str, hits: list[dict], logs: list[dict], model_manager: ModelManager) -> str:
    import httpx

    try:
        import jinja2
    except Exception:
        jinja2 = None

    try:
        from markdown import markdown
    except Exception:
        def markdown(value: str, extensions=None):
            return value

    try:
        from weasyprint import HTML
    except Exception:
        HTML = None

    await model_manager.load("llama3.1:8b")
    prompt = f"Synthesize these findings into an objective, factual executive summary for an OSINT report:\nSelector: {initial_selector}\nHits: {hits}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{model_manager.ollama_url}/api/generate",
            json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
        )
        summary_text = response.json().get("response", "Summary generation unavailable.")

    await model_manager.unload("llama3.1:8b")

    if jinja2 is None:
        rendered_md = REPORT_TEMPLATE
    else:
        template = jinja2.Template(REPORT_TEMPLATE)
        rendered_md = template.render(
            investigation_id=investigation_id,
            initial_selector=initial_selector,
            selector_type=selector_type,
            hits=hits,
            logs=logs,
            summary_text=summary_text,
            timestamp="",
        )
    html_content = markdown(rendered_md, extensions=["tables"])
    pdf_path = f"./data/evidence/{investigation_id}/report.pdf"
    if HTML is not None:
        HTML(string=html_content).write_pdf(pdf_path)
    else:
        with open(pdf_path, "w", encoding="utf-8") as report_file:
            report_file.write(rendered_md)
    return pdf_path
