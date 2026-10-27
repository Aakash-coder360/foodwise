import logging
from pathlib import Path

log_path = Path("foodwise.log")
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FoodWise")