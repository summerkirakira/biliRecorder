from loguru import logger


logger.add("logs/{time}.log", rotation="5MB", encoding="utf-8", enqueue=True, compression="zip", retention="10 days")
