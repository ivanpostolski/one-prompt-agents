import logging
import pytest # It's good practice to use pytest for fixtures and runners if available

from src.one_prompt_agents.utils import uvicorn_log_level

# Helper to save and restore logging level
class LogLevelContext:
    def __init__(self, level):
        self.level = level
        self.original_level = None

    def __enter__(self):
        self.original_level = logging.getLogger().getEffectiveLevel()
        logging.getLogger().setLevel(self.level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.getLogger().setLevel(self.original_level)

class LogDisabledContext:
    def __init__(self, disable_level):
        self.disable_level = disable_level
        self.original_disable_level = logging.root.manager.disable

    def __enter__(self):
        logging.disable(self.disable_level)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.disable(self.original_disable_level)


def test_uvicorn_log_level_debug():
    original_level = logging.getLogger().getEffectiveLevel()
    try:
        logging.getLogger().setLevel(logging.DEBUG)
        assert uvicorn_log_level() == "debug"
    finally:
        logging.getLogger().setLevel(original_level)

def test_uvicorn_log_level_info():
    original_level = logging.getLogger().getEffectiveLevel()
    try:
        logging.getLogger().setLevel(logging.INFO)
        assert uvicorn_log_level() == "info"
    finally:
        logging.getLogger().setLevel(original_level)

def test_uvicorn_log_level_warning():
    original_level = logging.getLogger().getEffectiveLevel()
    try:
        logging.getLogger().setLevel(logging.WARNING)
        assert uvicorn_log_level() == "warning"
    finally:
        logging.getLogger().setLevel(original_level)

def test_uvicorn_log_level_error():
    original_level = logging.getLogger().getEffectiveLevel()
    try:
        logging.getLogger().setLevel(logging.ERROR)
        assert uvicorn_log_level() == "error"
    finally:
        logging.getLogger().setLevel(original_level)

def test_uvicorn_log_level_critical():
    original_level = logging.getLogger().getEffectiveLevel()
    try:
        logging.getLogger().setLevel(logging.CRITICAL)
        assert uvicorn_log_level() == "critical"
    finally:
        logging.getLogger().setLevel(original_level)

def test_uvicorn_log_level_disabled():
    original_disable_level = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL) # Disable all levels up to CRITICAL
        assert uvicorn_log_level() is None
    finally:
        logging.disable(original_disable_level) # Reset to original disable level

def test_uvicorn_log_level_custom_level_defaults_to_warning():
    original_level = logging.getLogger().getEffectiveLevel()
    custom_level = 15  # Between DEBUG and INFO
    try:
        logging.getLogger().setLevel(custom_level)
        assert uvicorn_log_level() == "warning" # Per Uvicorn's typical default for unknown levels
    finally:
        logging.getLogger().setLevel(original_level)
