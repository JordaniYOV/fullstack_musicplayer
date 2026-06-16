from datetime import time
from limits import parse, storage, strategies
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

class RateLimiter: 
    def __init__(self): 
        self._store = storage.RedisStorage()
        self._limiter = strategies.MovingWindowRateLimiter(self._store)
        self._limits = {
            "/": parse("5/min")
        }

    def get_rule(self, path):
        if path in self._limits:
            return self._limits[path]
        
        for prefix, limit in self._limits.items(): 
            if prefix.endswith("/") and path.startswith(prefix): 
                return limit
            
        return parse("60/min")

    def allow_request(self, key, rule):
        """Return (is allowed? (bool), sec to restart)"""
        if rule is None:
            return True, 0
    
        allowed = self._limiter.hit(rule, key)

        if allowed:
            return True, 0
        
        stats = self._limiter.get_window_stats(rule, key)
        retry_after = int(stats.reset_time - time.time())
        return False, max(retry_after, 1)

class LimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app): 
        super.__init__(app)
        self.rate_limiter = RateLimiter()
    
    def make_key(self, request: Request)

    async def dispatch(self, request: Request, call_next):
        rule = self.rate_limiter.get_rule(request.url.path)
        key = self.make_key(request)

        allowed, retry_after = self.rate_limiter.allow_request(key=key, rule=rule)

        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(rule.amount) if rule else "0",
                    "X-RateLimit-Remaining": "0",
                },
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after_seconds": retry_after,
                }
            )
        
        response = await call_next(request)
        if rule:
            stats = self.rate_limiter.limiter.get_window_stats(rule, key)
            response.headers["X-RateLimit-Limit"] = str(rule.amount)
            response.headers["X-RateLimit-Remaining"] = str(stats.remaining_count)
        
        return response
