import time
import redis.asyncio as aioredis
from fastapi import Request, HTTPException
from app.core.config import settings

# Plan tier limits: requests per minute
PLAN_LIMITS = {
    "free": 20,
    "pro": 100,
    "enterprise": 500,
}

redis_client: aioredis.Redis = None

async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return redis_client

async def rate_limit_middleware(request: Request, call_next):
    # Skip rate limiting for non-API routes
    if not request.url.path.startswith("/api"):
        return await call_next(request)

    redis = await get_redis()

    # Identify user: use JWT subject or fallback to IP
    user_id = getattr(request.state, "user_id", None) or request.client.host
    plan = getattr(request.state, "plan", "free")

    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    window = 60  # 1 minute window

    key = f"rate_limit:{user_id}"
    # use nanosecond resolution so very fast repeated requests are counted separately
    now = time.time_ns()
    window_ns = window * 1_000_000_000
    window_start = now - window_ns

    pipe = redis.pipeline()
    # Queue commands in the pipeline (don't await here)
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, window)
    results = await pipe.execute()

    current_count = results[1]  # count before adding current request

    remaining = max(0, limit - current_count - 1)
    reset_time = now + window

    if current_count >= limit:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded. Max {limit} requests/minute for '{plan}' plan.",
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_time),
                "Retry-After": str(window),
            },
        )

    response = await call_next(request)

    # Attach rate limit headers to every response
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(reset_time)

    return response