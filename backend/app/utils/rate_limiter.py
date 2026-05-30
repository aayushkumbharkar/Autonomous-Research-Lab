import time
import asyncio
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # Maps client IP -> {"tokens": float, "last_updated": float}
        self.buckets: dict[str, dict[str, float]] = {}

    def _get_bucket(self, ip: str, rate: float, capacity: float) -> dict[str, float]:
        """Retrieve or create the token bucket for the given IP address, replenishing tokens."""
        now = time.time()
        if ip not in self.buckets:
            self.buckets[ip] = {"tokens": capacity, "last_updated": now}
        else:
            elapsed = now - self.buckets[ip]["last_updated"]
            replenished = elapsed * rate
            self.buckets[ip]["tokens"] = min(capacity, self.buckets[ip]["tokens"] + replenished)
            self.buckets[ip]["last_updated"] = now
        return self.buckets[ip]

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()

        # Only apply rate limiting to standard /api endpoints, excluding /api/health
        if (
            not settings.rate_limit_enabled 
            or not request.url.path.startswith("/api")
            or request.url.path == "/api/health"
        ):
            return await call_next(request)

        # Retrieve client IP
        ip = request.client.host if request.client else "unknown"

        # Calculate replenish rate (tokens per second) and bucket capacity
        rate = settings.rate_limit_requests_per_minute / 60.0
        capacity = float(settings.rate_limit_burst)

        # Get bucket and apply token replenishment
        bucket = self._get_bucket(ip, rate, capacity)

        # 1. Throttling (Bottleneck control): Slow down the response if tokens are running low
        threshold = capacity * (1.0 - settings.throttle_threshold_ratio)
        if bucket["tokens"] < threshold:
            logger.info("rate_limiter_throttling", ip=ip, tokens=round(bucket["tokens"], 2))
            await asyncio.sleep(settings.throttle_delay_seconds)

        # 2. Block the request if there are no tokens left (tokens < 1.0)
        if bucket["tokens"] < 1.0:
            logger.warning("rate_limiter_blocked", ip=ip)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "detail": "Too many requests. Please slow down and try again later."
                }
            )

        # Consume 1 token and proceed with the request lifecycle
        bucket["tokens"] -= 1.0
        return await call_next(request)
