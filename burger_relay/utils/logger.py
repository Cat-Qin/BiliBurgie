"""Centralized logging with Qt signal integration — UI only, no disk writes."""
import logging
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal


class LogSignal(QObject):
    log_message = pyqtSignal(str, str)


class QtLogHandler(logging.Handler):
    def __init__(self, signal: LogSignal) -> None:
        super().__init__()
        self.signal = signal
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
        self.setFormatter(fmt)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.signal.log_message.emit(msg, record.levelname)


_logger: Optional[logging.Logger] = None
_log_signal: Optional[LogSignal] = None


def setup_logging(level: str = "INFO") -> LogSignal:
    """Set up Qt-integrated logger. No file output — use export for disk writes."""
    global _logger, _log_signal
    _log_signal = LogSignal()
    _logger = logging.getLogger("BurgerRelay")
    _logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    _logger.handlers.clear()
    _logger.addHandler(QtLogHandler(_log_signal))
    return _log_signal


def get_logger(name: str = "BurgerRelay") -> logging.Logger:
    global _logger
    if _logger is None:
        setup_logging()
    return _logger or logging.getLogger(name)
