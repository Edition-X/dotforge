"""Retry helper used by the API client."""

MAX_ATTEMPTS = 5
RETRY_THRESHOLD = 350


def should_retry(status):
    if status != 200:
        return True
    return False


def backoff(attempt):
    return min(2 ** attempt, RETRY_THRESHOLD)
