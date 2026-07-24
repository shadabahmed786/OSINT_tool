import uvicorn
import logging
import asyncio
from app.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run")

if __name__ == "__main__":
    logger.info("Initializing OSINT Platform Database...")
    asyncio.run(init_db())
    logger.info("Starting server on http://localhost:8000")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
