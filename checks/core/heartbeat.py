"""
URL should return a 200 response.

The remote response is returned.
"""
import os

import aiohttp

from poucave.typings import CheckResult


EXPOSED_PARAMETERS = ["url"]


REQUESTS_TIMEOUT_SECONDS = int(os.getenv("REQUESTS_TIMEOUT_SECONDS", 5))


async def run(url: str, timeout: int = REQUESTS_TIMEOUT_SECONDS) -> CheckResult:
    timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.get(url) as response:
                status = response.status == 200
                return status, await response.json()
        except aiohttp.client_exceptions.ClientError as e:
            return False, str(e)
