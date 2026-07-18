"""Logger construction — stdout only; the platform owns log collection."""

import logging
import sys


def logger_create() -> logging.Logger:
    logger = logging.getLogger("api")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
