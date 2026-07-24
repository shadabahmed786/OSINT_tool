import logging
from pathlib import Path
from typing import Optional, Dict, Any
from app.config import BASE_DIR

logger = logging.getLogger(__name__)

def extract_text_tesseract(image_path: str) -> Dict[str, Any]:
    """
    Primary fast, cheap CPU-bound OCR extractor using pytesseract (§4).
    Returns dict: {"text": str, "char_count": int, "confidence": float, "success": bool}
    """
    full_path = BASE_DIR / "data" / image_path if not Path(image_path).is_absolute() else Path(image_path)
    if not full_path.exists():
        return {"text": "", "char_count": 0, "confidence": 0.0, "success": False}

    try:
        import pytesseract
        from PIL import Image

        with Image.open(full_path) as img:
            ocr_text = pytesseract.image_to_string(img).strip()
            char_cnt = len(ocr_text)
            
            # Simple heuristic confidence based on extracted alphanumeric characters
            alpha_cnt = sum(1 for c in ocr_text if c.isalnum())
            conf = (alpha_cnt / char_cnt) * 100.0 if char_cnt > 0 else 0.0

            return {
                "text": ocr_text,
                "char_count": char_cnt,
                "confidence": conf,
                "success": char_cnt >= 10
            }
    except Exception as e:
        logger.info("Tesseract OCR unavailable or failed for %s: %s", image_path, e)
        return {"text": "", "char_count": 0, "confidence": 0.0, "success": False}
