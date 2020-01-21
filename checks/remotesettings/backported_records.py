"""
The backported collection should contain exactly the same records as the source,
with a maximum lag in seconds. The default max lag is 300, which is the run frequency
of the backport lambda (5 min).

The differences between source and destination are returned.
"""
from typing import Any, Dict
from urllib.parse import parse_qs

from poucave.typings import CheckResult

from .utils import KintoClient, compare_collections, human_diff


EXPOSED_PARAMETERS = ["server", "max_lag_seconds"]


async def run(
    server: str, backports: Dict[str, str], max_lag_seconds: int = 5 * 60
) -> CheckResult:
    client = KintoClient(server_url=server)

    errors = []
    for source, dest in backports.items():
        # If source is filtered, then the check should take it into account.
        filters: Dict[str, Any] = {}
        if "?" in source:
            source, qs = source.split("?")
            filters = parse_qs(qs)
            filters = {k: v[0] if len(v) == 1 else v for k, v in filters.items()}

        source_bid, source_cid = source.split("/")
        dest_bid, dest_cid = dest.split("/")

        source_records = await client.get_records(
            bucket=source_bid, collection=source_cid, **filters
        )
        dest_records = await client.get_records(bucket=dest_bid, collection=dest_cid)
        diff = compare_collections(source_records, dest_records)
        if diff:
            source_timestamp = await client.get_records_timestamp(
                bucket=source_bid, collection=source_cid
            )
            dest_timestamp = await client.get_records_timestamp(
                bucket=dest_bid, collection=dest_cid
            )
            diff_millisecond = abs(int(source_timestamp) - int(dest_timestamp))
            if (diff_millisecond / 1000) > max_lag_seconds:
                missing, differ, extras = diff
                details = human_diff(source, dest, missing, differ, extras)
                errors.append(details)

    return len(errors) == 0, errors
