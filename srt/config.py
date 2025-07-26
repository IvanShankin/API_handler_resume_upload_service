import logging
from datetime import timedelta
from pathlib import Path


MIN_COMMIT_COUNT_KAFKA = 5
LOGIN_BLOCK_TIME = timedelta(seconds=300)  # Период блокировки

LOG_DIR = Path("../logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "auth_service.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)