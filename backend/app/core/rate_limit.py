import time

from redis.asyncio import Redis


RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


async def check_rate_limit(
    redis: Redis, *, key: str, limit: int, window_seconds: int
) -> tuple[bool, int, int]:
    bucket = int(time.time() // window_seconds)
    redis_key = f"apiforge:ratelimit:{key}:{bucket}"
    current = int(await redis.eval(RATE_LIMIT_SCRIPT, 1, redis_key, window_seconds))
    remaining = max(0, limit - current)
    retry_after = window_seconds - (int(time.time()) % window_seconds)
    return current <= limit, remaining, retry_after
