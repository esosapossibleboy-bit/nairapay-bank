import time

class RateLimiter:
    def __init__(self, max_requests: int = 20, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}

    def allow_request(self, key: str) -> bool:
        now = time.time()
        timestamps = self.requests.get(key, [])
        timestamps = [t for t in timestamps if now - t < self.window_seconds]
        if len(timestamps) >= self.max_requests:
            self.requests[key] = timestamps
            return False
        timestamps.append(now)
        self.requests[key] = timestamps
        return True
