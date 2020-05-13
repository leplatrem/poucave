"""
The percentage of reported errors in Uptake Telemetry should be under the specified
maximum. Error rate is computed for each period of 10min.

For each source whose error rate is above the maximum, the total number of events
for each status is returned. The min/max timestamps give the datetime range of the
dataset obtained from https://sql.telemetry.mozilla.org/queries/67605/
"""
from collections import defaultdict
from typing import Dict, List, Tuple

from poucave.typings import CheckResult
from poucave.utils import fetch_redash


EXPOSED_PARAMETERS = [
    "max_error_percentage",
    "min_total_events",
    "ignore_status",
    "ignore_versions",
]

REDASH_QUERY_ID = 67605


def sort_dict_desc(d, key):
    return dict(sorted(d.items(), key=key, reverse=True))


def parse_ignore_status(ign):
    source, status, version = "*", ign, "*"
    if "@" in ign:
        status, version = ign.split("@")
    if "/" in status or "-" in status:
        source = status
        status = "*"
    if ":" in source:
        source, status = source.split(":")
    return (source, status, version)


async def run(
    api_key: str,
    max_error_percentage: float,
    min_total_events: int = 1000,
    sources: List[str] = [],
    channels: List[str] = [],
    ignore_status: List[str] = [],
    ignore_versions: List[int] = [],
) -> CheckResult:
    # Fetch latest results from Redash JSON API.
    rows = await fetch_redash(REDASH_QUERY_ID, api_key)

    min_timestamp = min(r["min_timestamp"] for r in rows)
    max_timestamp = max(r["max_timestamp"] for r in rows)

    # Uptake events can be ignored by status, by version, or by status on a
    # specific version (eg. ``parse_error@68``)
    ignored_statuses = []
    for ign in ignore_status:
        ignored_statuses.append(parse_ignore_status(ign))
    ignored_statuses.extend([("*", "*", str(version)) for version in ignore_versions])

    # We will store reported events by period, by source,
    # by version, and by status.
    # {
    #   ('2020-01-17T07:50:00', '2020-01-17T08:00:00'): {
    #     'settings-sync': {
    #       '71': {
    #         'success': 4699,
    #         'sync_error': 39
    #       },
    #       ...
    #     },
    #     ...
    #   }
    # }
    periods: Dict[Tuple[str, str], Dict] = {}
    for row in rows:
        # Filter by channel if parameter is specified.
        if channels and row["channel"].lower() not in channels:
            continue

        period: Tuple[str, str] = (row["min_timestamp"], row["max_timestamp"])
        if period not in periods:
            by_source: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
                lambda: defaultdict(dict)
            )
            periods[period] = by_source

        if len(sources) == 0 or row["source"] in sources:
            periods[period][row["source"]][row["version"]][row["status"]] = row["total"]

    error_rates: Dict[str, Dict] = {}
    min_rate = None
    max_rate = None
    for (min_period, max_period), by_source in periods.items():
        # Compute error rate by period.
        # This allows us to prevent error rate to be "spread" over the overall datetime
        # range of events (eg. a spike of errors during 10min over 2H).
        for source, all_versions in by_source.items():
            total_statuses = 0
            # Store total by status (which are not ignored).
            statuses: Dict[str, int] = defaultdict(int)
            ignored: Dict[str, int] = defaultdict(int)

            for version, all_statuses in all_versions.items():
                for status, total in all_statuses.items():
                    total_statuses += total
                    # Should we ignore this status, version, status@version?
                    is_ignored = (
                        (source, status, version) in ignored_statuses
                        or (source, status, "*") in ignored_statuses
                        or ("*", status, version) in ignored_statuses
                        or (source, "*", version) in ignored_statuses
                        or ("*", status, "*") in ignored_statuses
                        or ("*", "*", version) in ignored_statuses
                        # We don't support (source, *, *) in `ignore_status` param.
                    )
                    if is_ignored:
                        ignored[status] += total
                    else:
                        statuses[status] += total

            # Ignore uptake Telemetry of a certain source if the total of collected
            # events is too small.
            if total_statuses < min_total_events:
                continue

            total_errors = sum(
                total for status, total in statuses.items() if status.endswith("_error")
            )
            error_rate = round(total_errors * 100 / total_statuses, 2)

            min_rate = error_rate if min_rate is None else min(min_rate, error_rate)
            max_rate = error_rate if max_rate is None else max(max_rate, error_rate)

            # If error rate for this period is below threshold, or lower than one reported
            # in another period, then we ignore it.
            other_period_rate = error_rates.get(source, {"error_rate": 0.0})[
                "error_rate"
            ]
            if error_rate < max_error_percentage or error_rate < other_period_rate:
                continue

            error_rates[source] = {
                "error_rate": error_rate,
                "statuses": sort_dict_desc(statuses, key=lambda item: item[1]),
                "ignored": sort_dict_desc(ignored, key=lambda item: item[1]),
                "min_timestamp": min_period,
                "max_timestamp": max_period,
            }

        sort_by_rate = sort_dict_desc(
            error_rates, key=lambda item: item[1]["error_rate"]
        )

    data = {
        "sources": sort_by_rate,
        "min_rate": min_rate,
        "max_rate": max_rate,
        "min_timestamp": min_timestamp,
        "max_timestamp": max_timestamp,
    }
    """
    {
      "sources": {
        "main/public-suffix-list": {
          "error_rate": 6.12,
          "statuses": {
            "up_to_date": 369628,
            "apply_error": 24563,
            "sync_error": 175,
            "success": 150,
            "custom_1_error": 52,
            "sign_retry_error": 5
          },
          "ignored": {
            "network_error": 10476
          },
          "min_timestamp": "2020-01-17T08:10:00",
          "max_timestamp": "2020-01-17T08:20:00",
        },
        ...
      },
      "min_rate": 2.1,
      "max_rate": 6.12,
      "min_timestamp": "2020-01-17T08:00:00",
      "max_timestamp": "2020-01-17T10:00:00"
    }
    """
    return len(sort_by_rate) == 0, data
