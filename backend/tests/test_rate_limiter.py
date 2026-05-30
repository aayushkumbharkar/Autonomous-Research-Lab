import pytest
import time
import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.utils.rate_limiter import RateLimitMiddleware
from app.config import get_settings

def test_rate_limiter_and_throttling():
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/api/test")
    def test_endpoint():
        return {"status": "ok"}

    @app.get("/api/health")
    def health_endpoint():
        return {"status": "healthy"}

    @app.get("/other")
    def other_endpoint():
        return {"status": "other"}

    client = TestClient(app)
    settings = get_settings()

    # Save original settings
    original_enabled = settings.rate_limit_enabled
    original_rpm = settings.rate_limit_requests_per_minute
    original_burst = settings.rate_limit_burst
    original_ratio = settings.throttle_threshold_ratio
    original_delay = settings.throttle_delay_seconds

    try:
        # Configure small, deterministic limits for testing
        settings.rate_limit_enabled = True
        settings.rate_limit_requests_per_minute = 60  # 1 token per second
        settings.rate_limit_burst = 3.0
        settings.throttle_threshold_ratio = 0.5  # Throttles when tokens < 1.5 (after 2 requests)
        settings.throttle_delay_seconds = 0.5

        # 1. Non-API endpoints and health checks are NOT rate-limited
        for _ in range(5):
            res = client.get("/other")
            assert res.status_code == 200
            res = client.get("/api/health")
            assert res.status_code == 200

        # 2. First request to /api/test should succeed immediately without throttle
        t0 = time.time()
        res = client.get("/api/test")
        t1 = time.time()
        assert res.status_code == 200
        assert (t1 - t0) < 0.3

        # 3. Second request to /api/test should succeed immediately without throttle
        t0 = time.time()
        res = client.get("/api/test")
        t1 = time.time()
        assert res.status_code == 200
        assert (t1 - t0) < 0.3

        # 4. Third request should trigger throttling (tokens < threshold of 1.5)
        t0 = time.time()
        res = client.get("/api/test")
        t1 = time.time()
        assert res.status_code == 200
        assert (t1 - t0) >= 0.4  # Artificially delayed by ~0.5s

        # 5. Fourth request should exceed rate limits and return 429
        res = client.get("/api/test")
        assert res.status_code == 429
        assert res.json()["error"] == "Too Many Requests"

    finally:
        # Restore original settings
        settings.rate_limit_enabled = original_enabled
        settings.rate_limit_requests_per_minute = original_rpm
        settings.rate_limit_burst = original_burst
        settings.throttle_threshold_ratio = original_ratio
        settings.throttle_delay_seconds = original_delay
