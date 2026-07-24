import base64

from backend.models_runtime.model_manager import ModelManager


def run_tesseract_ocr(image_path: str) -> tuple[str, float]:
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(image_path)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        text = " ".join(word for word in data["text"] if word.strip())
        confidences = [int(conf) for conf in data["conf"] if conf != "-1"]
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return text, average_confidence / 100.0
    except Exception:
        return "", 0.0


async def run_vlm_fallback_ocr(image_path: str, model_manager: ModelManager) -> str:
    await model_manager.load("qwen2.5-vl:7b")
    import httpx

    with open(image_path, "rb") as image_file:
        img_b64 = base64.b64encode(image_file.read()).decode("utf-8")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{model_manager.ollama_url}/api/generate",
            json={
                "model": "qwen2.5-vl:7b",
                "prompt": "Perform OCR on this image. Extract all readable text, names, bios, and timestamps verbatim.",
                "images": [img_b64],
                "stream": False,
            },
        )
        result = response.json().get("response", "")

    await model_manager.unload("qwen2.5-vl:7b")
    return result
