
import logging
logger = logging.getLogger(__name__) 

def uvicorn_log_level() -> str | None:
    """Return the right string (or None) for uvicorn.log_level."""
    root = logging.getLogger()
    if root.manager.disable >= logging.CRITICAL:
        return None                      # logging globally disabled

    name = logging.getLevelName(root.getEffectiveLevel()).lower()
    return name if name in {"critical","error","warning","info","debug","trace"} else "warning"