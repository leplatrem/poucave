"""
Signatures should be refreshed periodically, keeping their age under a maximum of hours.

The list of collections whose age is over the maximum allowed is returned.
"""
import asyncio
from datetime import datetime, timezone

from poucave.typings import CheckResult

from .utils import KintoClient as Client, fetch_signed_resources


URL_PARAMETERS = ["max_age"]
EXPOSED_PARAMETERS = ["max_age"]


def utcnow():
    # Tiny wrapper, used for mocking in tests.
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def get_signature_age_hours(client, bucket, collection):
    data = client.get_collection(bucket=bucket, id=collection)["data"]
    signature_date = data.get("last_signature_date")
    if signature_date is None:
        age = None
    else:
        dt = datetime.fromisoformat(signature_date)
        delta = utcnow() - dt
        age = int(delta.days * 24 + delta.seconds / 3600)
    return age


async def run(server: str, auth: str, max_age: int) -> CheckResult:
    client = Client(server_url=server, auth=auth)

    source_collections = [
        (r["source"]["bucket"], r["source"]["collection"])
        for r in fetch_signed_resources(server, auth)
    ]

    loop = asyncio.get_event_loop()
    futures = [
        loop.run_in_executor(None, get_signature_age_hours, client, bid, cid)
        for (bid, cid) in source_collections
    ]
    results = await asyncio.gather(*futures)

    ages = {
        f"{bid}/{cid}": age
        for ((bid, cid), age) in zip(source_collections, results)
        if age is None or age > max_age
    }
    all_good = len(ages) == 0
    return all_good, ages
