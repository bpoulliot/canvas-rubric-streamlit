import time
import threading


class RateLimiter:
    def __init__(self, calls_per_second=8):
        self.interval = 1.0 / calls_per_second
        self.lock = threading.Lock()
        self.last_call = 0.0

    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_call = time.time()


global_rate_limiter = RateLimiter(8)
