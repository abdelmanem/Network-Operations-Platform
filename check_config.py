#!/usr/bin/env python3
"""Check runtime configuration."""

from backend.app.config.settings import get_settings

s = get_settings()
print(f"NetBox URL: {s.netbox_base_url}")
print(f"NetBox Token: {'SET' if s.netbox_token else 'NOT SET'}")
print(f"Database URL: {s.database_url}")
print(f"Redis URL: {s.redis_url}")
print(f"Cache TTL: {s.cache_default_ttl_seconds}s")
print(f"Log Level: {s.log_level}")
print(f"App Env: {s.app_env}")
