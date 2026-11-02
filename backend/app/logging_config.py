import copy
import logging
import os
import sys

LEVEL_COLORS = {
    logging.DEBUG: "\033[90m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;37;41m",
}
RESET = "\033[0m"


class ColorLevelFormatter(logging.Formatter):
    def __init__(self, *, use_color: bool):
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        colored_record = copy.copy(record)
        if self.use_color:
            color = LEVEL_COLORS.get(colored_record.levelno, "")
            if color:
                colored_record.levelname = f"{color}{colored_record.levelname}{RESET}"
        return super().format(colored_record)


def configure_logging() -> None:
    use_color = os.getenv("LOG_COLOR", "true").lower() in {"1", "true", "yes", "on"}
    use_color = use_color and "NO_COLOR" not in os.environ
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ColorLevelFormatter(use_color=use_color))
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        handlers=[handler],
        force=True,
    )


configure_logging()
logger = logging.getLogger("document_chatbot")
