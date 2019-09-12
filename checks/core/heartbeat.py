"""
URL should return a 200 response.
"""
import aiohttp


EXPOSED_PARAMETERS = ["url"]


async def run(query, url):
    # TODO: controlled timeout
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                status = response.status == 200
                return status, await response.json()
        except aiohttp.client_exceptions.ClientError as e:
            return False, str(e)
