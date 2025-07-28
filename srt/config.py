import logging
from datetime import timedelta
from pathlib import Path


MIN_COMMIT_COUNT_KAFKA = 5
STORAGE_TIME_REQUIREMENTS = timedelta(days=3) # время хранения требований
STORAGE_TIME_RESUME = timedelta(hours=1) # время хранения резюме
LOGIN_BLOCK_TIME = timedelta(seconds=300)  # Период блокировки
ALLOWED_EXTENSIONS = {'.txt', '.docx', '.pdf'} # поддерживаемые форматы файлов
MAX_CHAR_REQUIREMENTS = 5000
MAX_CHAR_RESUME = 15000

# данные для ключей Kafka
KEY_NEW_REQUEST = 'new_request'
KEY_NEW_RESUME = 'new_resume'
KEY_NEW_REQUIREMENTS = 'new_requirements'

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