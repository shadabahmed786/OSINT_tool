import logging

import httpx

logger = logging.getLogger("ModelManager")


class ModelManager:
    """Keeps only one heavy Ollama model resident at a time."""

    def __init__(self, ollama_url: str = "http://localhost:11434") -> None:
        self.ollama_url = ollama_url
        self.current_heavy_model: str | None = None

    async def load(self, model_name: str) -> None:
        if self.current_heavy_model == model_name:
            return
        if self.current_heavy_model:
            await self.unload(self.current_heavy_model)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/generate",
                json={"model": model_name, "keep_alive": "10m"},
            )
            if response.status_code != 200:
                raise RuntimeError(f"Failed to load model {model_name}: {response.text}")
            self.current_heavy_model = model_name

    async def unload(self, model_name: str) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"{self.ollama_url}/api/generate",
                json={"model": model_name, "keep_alive": 0},
            )
        if self.current_heavy_model == model_name:
            self.current_heavy_model = None
