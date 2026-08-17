import os
from pathlib import Path
import pytest
from backend.app.config.settings import Settings
from backend.app.core.application import create_application

@pytest.fixture(autouse=True)
def clear_settings_cache():
    from backend.app.config.settings import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

def test_settings_loaded_from_project_root():
    """Verify that Settings loads correctly when instantiated from the project root directory."""
    original_cwd = os.getcwd()
    project_root = Path(__file__).resolve().parents[2]
    try:
        os.chdir(str(project_root))
        settings = Settings()
        assert settings.netbox_url == "https://caizh.netbox.com"
        assert settings.netbox_expected_version == "4.6.8"
    finally:
        os.chdir(original_cwd)

def test_settings_loaded_from_backend_directory():
    """Verify that Settings loads correctly when instantiated from the backend subdirectory."""
    original_cwd = os.getcwd()
    backend_dir = Path(__file__).resolve().parents[2] / "backend"
    try:
        os.chdir(str(backend_dir))
        settings = Settings()
        assert settings.netbox_url == "https://caizh.netbox.com"
        assert settings.netbox_expected_version == "4.6.8"
    finally:
        os.chdir(original_cwd)

def test_settings_missing_netbox_url_raises_value_error(monkeypatch):
    """Verify that a missing NETBOX_URL configuration raises an error during app factory boot, without localhost fallback."""
    monkeypatch.setenv("NETBOX_URL", "")
    monkeypatch.setenv("NETBOX_EXPECTED_VERSION", "4.6.8")
    
    with pytest.raises(ValueError) as excinfo:
        create_application()
        
    assert "NETBOX_URL configuration is missing" in str(excinfo.value)

def test_settings_missing_netbox_version_raises_value_error(monkeypatch):
    """Verify that a missing NETBOX_EXPECTED_VERSION raises an error during app factory boot, without default fallback."""
    monkeypatch.setenv("NETBOX_URL", "https://caizh.netbox.com")
    monkeypatch.setenv("NETBOX_EXPECTED_VERSION", "")
    
    with pytest.raises(ValueError) as excinfo:
        create_application()
        
    assert "NETBOX_EXPECTED_VERSION configuration is missing" in str(excinfo.value)
