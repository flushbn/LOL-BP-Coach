"""Global exception hook for crash logging."""
import sys, traceback, datetime
from pathlib import Path

_CRASH_LOG: Path = None

def init_crash_log(log_path=None):
    global _CRASH_LOG
    if log_path is None:
        base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent
        log_dir = base / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _CRASH_LOG = log_dir / "crash.log"
    else:
        _CRASH_LOG = Path(log_path)
        _CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)

    def _global_excepthook(exc_type, exc_value, exc_tb):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        msg = f"=== {timestamp} ===\n{tb}\n"
        try:
            with open(_CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(msg)
        except:
            pass
        # Still show the error
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _global_excepthook

def log_message(msg: str):
    """Log a non-fatal message."""
    if _CRASH_LOG:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(_CRASH_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {msg}\n")
        except:
            pass

