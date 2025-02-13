"""Rate limiting functionality"""
import time
from contextlib import contextmanager

class RequestRateLimiter:
    def __init__(self, delay: float):
        self.delay = delay
        self.last_request_time = 0

    @contextmanager
    def limit_rate(self):
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        try:
            yield
        finally:
            self.last_request_time = time.time()