import base64
import httpx
import logging
from pathlib import Path
from typing import Dict, Any
from app.config import BASE_DIR, OLLAMA_HOST, DEFAULT_VISION_MODEL
from app.models_runtime.model_manager import model_manager

logger = logging.getLogger(__name__)

async def extract_text_vlm_fallback(image_path: str) -> Dict[str, Any]:
    """
    Fallback VLM (Qwen2.5-VL 7B) OCR & Layout understanding engine (§4).
    Invoked when Tesseract output is empty or low confidence.
    Enforces sequential model loading via model_manager (§5).
    """
    full_path = BASE_DIR / "data" / image_path if not Path(image_path).is_absolute() else Path(image_path)
    if not full_path.exists():
        return {"text": "", "engine": "Qwen2.5-VL 7B", "success": False}

    # Ensure Vision model is loaded in VRAM (unloading text model if resident)
    loaded = await model_manager.ensure_model_loaded(DEFAULT_VISION_MODEL)
    if not loaded:
        logger.warning("VLM model '%s' could not be loaded into VRAM.", DEFAULT_VISION_MODEL)
        return {"text": "", "engine": "VLM (Unavailable)", "success": False}

    try:
        with open(full_path, "rb") as f:
            b64_img = base64.b64encode(f.read()).decode("utf-8")

        prompt = "Read and transcribe all visible text, profile bio, username, and key information from this webpage screenshot accurately."

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": DEFAULT_VISION_MODEL,
                    "prompt": prompt,
                    "images": [b64_img],
                    "stream": False
                }
            )

            if resp.status_code == 200:
                text_out = resp.json().get("response", "").strip()
                return {
                    "text": text_out,
                    "engine": f"Local VLM ({DEFAULT_VISION_MODEL})",
                    "success": len(text_out) > 0
                }
    except Exception as e:
        logger.warning("VLM Fallback OCR error for %s: %s", image_path, e)

    return {"text": "", "engine": "Qwen2.5-VL 7B", "success": False}
