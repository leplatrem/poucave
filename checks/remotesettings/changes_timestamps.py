"""
Timestamps of entries in monitoring endpoint should match collection timestamp.

For each collection the change `entry` timestamp is returned along with the
`collection` timestamp. The `datetime` is the human-readable version.
"""
import asyncio
from datetime import datetime

from .utils import KintoClient as Client


def get_timestamp(client, bucket, collection, timestamp):
    return client.get_records_timestamp(
        bucket=bucket, collection=collection, _expected=timestamp
    )


async def run(query, server):
    loop = asyncio.get_event_loop()

    client = Client(server_url=server, bucket="monitor", collection="changes")
    entries = client.get_records()
    futures = [
        loop.run_in_executor(
            None,
            get_timestamp,
            client,
            entry["bucket"],
            entry["collection"],
            entry["last_modified"],
        )
        for entry in entries
    ]
    results = await asyncio.gather(*futures)

    datetimes = []
    for (entry, collection_timestamp) in zip(entries, results):
        entry_timestamp = entry["last_modified"]
        collection_timestamp = int(collection_timestamp)
        dt = datetime.utcfromtimestamp(collection_timestamp / 1000).isoformat()
        datetimes.append(
            {
                "id": "{bucket}/{collection}".format(**entry),
                "collection": collection_timestamp,
                "entry": entry_timestamp,
                "datetime": dt,
            }
        )

    all_good = all([r["entry"] == r["collection"] for r in datetimes])
    return all_good, datetimes
