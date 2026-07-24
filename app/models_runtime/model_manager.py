import httpx
import logging
from typing import Optional
from app.config import OLLAMA_HOST, DEFAULT_TEXT_MODEL, DEFAULT_VISION_MODEL

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Ensures only ONE heavyweight local model (Text LLM or VLM) is resident in VRAM at a time (§5).
    Unloads the active model before loading another heavy model to run safely within 16GB VRAM @ 150W.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance.current_heavy_model: Optional[str] = None
        return cls._instance

    async def ensure_model_loaded(self, target_model: str) -> bool:
        """Loads target_model into Ollama memory, unloading any other active heavy model first."""
        if self.current_heavy_model == target_model:
            return True

        if self.current_heavy_model is not None and self.current_heavy_model != target_model:
            await self.unload_model(self.current_heavy_model)

        logger.info("Loading local model '%s' into VRAM via Ollama...", target_model)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Pre-warm model in Ollama by sending a blank generate request
                resp = await client.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json={"model": target_model, "prompt": "", "keep_alive": "10m"}
                )
                if resp.status_code == 200:
                    self.current_heavy_model = target_model
                    logger.info("Successfully loaded '%s' into VRAM.", target_model)
                    return True
                else:
                    logger.warning("Failed to load model '%s'. HTTP %d", target_model, resp.status_code)
                    return False
        except Exception as e:
            logger.warning("Ollama pre-warm error for model '%s': %s", target_model, e)
            return False

    async def unload_model(self, model_name: str) -> bool:
        """Unloads model_name from VRAM by setting keep_alive to 0."""
        logger.info("Unloading model '%s' from VRAM...", model_name)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{OLLAMA_HOST}/api/generate",
                    json={"model": model_name, "prompt": "", "keep_alive": "0s"}
                )
            if self.current_heavy_model == model_name:
                self.current_heavy_model = None
            return True
        except Exception as e:
            logger.warning("Error unloading model '%s': %s", model_name, e)
            return False

# Global singleton instance
model_manager = ModelManager()
