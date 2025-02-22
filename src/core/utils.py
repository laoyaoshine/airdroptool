import random
import time
import asyncio
from .tools import log, handle_error

def random_delay(min_delay: float = 1, max_delay: float = 5) -> float:
    """随机延迟模拟人类行为（同步）"""
    try:
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
        return delay
    except Exception as e:
        handle_error(e, "Random delay")

async def async_random_delay(min_delay: float = 1, max_delay: float = 5) -> float:
    """异步随机延迟模拟人类行为"""
    try:
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
        return delay
    except Exception as e:
        handle_error(e, "Async random delay")