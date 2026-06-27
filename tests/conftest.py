import pytest


@pytest.fixture(autouse=True)
def reset_settings_cache():
    """Clear the settings LRU cache before/after each test to pick up env var changes."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
