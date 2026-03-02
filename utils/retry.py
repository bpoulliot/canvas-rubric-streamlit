import time
import random
from functools import wraps


def retry(max_attempts=5, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except ValueError:
                    # Do NOT retry validation or 404 errors
                    raise
                except Exception:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    sleep = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(sleep)
        return wrapper
    return decorator
