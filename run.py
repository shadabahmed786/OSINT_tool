import uvicorn
import logging
from backend.db.models import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run")

if __name__ == "__main__":
    logger.info("Initializing OSINT Platform Database...")
    db = DatabaseManager()
    logger.info("Starting server on http://localhost:8000")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

