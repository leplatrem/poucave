"""
The HTML content of the page that lists blocked addons and plugins should
match the source of truth.

The list of missing or extras entries is returned, along with the XML and
source timestamps.
"""
import asyncio
import logging
import re
import xml.etree.ElementTree

import aiohttp
from bs4 import BeautifulSoup

from poucave import config
from poucave.typings import CheckResult
from .utils import KintoClient


EXPOSED_PARAMETERS = ["remotesettings_server", "blocked_pages"]
BLOCKLIST_URL_PATH = "/blocklist/3/{ec8030f7-c20a-464f-9b0e-13a3a9e97384}/46.0/"

logger = logging.getLogger(__name__)


def chunker(seq, size):
    return (seq[pos : pos + size] for pos in range(0, len(seq), size))  # noqa


async def fetch_text(session, url):
    async with session.get(url) as response:
        return await response.text()


async def fetch_status(session, url):
    try:
        logger.debug(f"Fetch status of {url}")
        async with session.head(url) as response:
            return response.status
    except aiohttp.ClientError:
        return None


async def run(remotesettings_server: str, blocked_pages: str) -> CheckResult:
    xml_url = remotesettings_server + BLOCKLIST_URL_PATH

    async with aiohttp.ClientSession() as session:
        # Read blocked page index to obtain the links.
        blocked_index = await fetch_text(session, blocked_pages)
        soup = BeautifulSoup(blocked_index, features="html.parser")
        urls = []
        for link in soup.find_all("a", href=re.compile(".html$")):
            urls.append(link["href"])

        # Make sure no link is broken.
        missing = []
        for chunk in chunker(urls, config.REQUESTS_MAX_PARALLEL):
            futures = [fetch_status(session, f"{blocked_pages}/{url}") for url in chunk]
            results = await asyncio.gather(*futures)
            urls_statuses = zip(chunk, results)
            missing.extend([url for url, status in urls_statuses if status != 200])

        # Compare list of blocked ids with the source of truth.
        client = KintoClient(server_url=remotesettings_server, bucket="blocklists")
        records_ids = [
            r.get("blockID", r["id"])
            for r in await client.get_records(collection="plugins")
            + await client.get_records(collection="addons")
        ]
        blocked_ids = [url.rsplit(".", 1)[0] for url in urls]
        extras_ids = set(blocked_ids) - set(records_ids)
        missing_ids = set(records_ids) - set(blocked_ids)

        """
        <?xml version="1.0" encoding="UTF-8"?>
        <blocklist xmlns="http://www.mozilla.org/2006/addons-blocklist" lastupdate="1568816392824">
        ...
        """
        timestamp = await client.get_records_timestamp(
            bucket="monitor", collection="changes"
        )
        xml_content = await fetch_text(session, xml_url)
        root = xml.etree.ElementTree.fromstring(xml_content)
        xml_timestamp = root.attrib["lastupdate"]

    success = (
        len(missing) == 0
        and len(missing_ids) == 0
        and len(extras_ids) == 0
        and timestamp == xml_timestamp
    )
    data = {
        "xml-update": xml_timestamp,
        "timestamp": timestamp,
        "broken-links": missing,
        "missing": list(missing_ids),
        "extras": list(extras_ids),
    }
    return success, data
