from loguru import logger
import sys

logger.remove()

logger.add(sys.stderr, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>", level="INFO")
logger.add("logs/{time}.log", format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", level="DEBUG")
