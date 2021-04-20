"""
Recipes available on the server should match the recipes clients are reporting
Uptake Telemetry about.

The list of recipes for which no event was received is returned. The min/max
timestamps give the datetime range of the obtained dataset.
"""
import logging
from collections import defaultdict
from typing import Dict, List

from poucave.typings import CheckResult
from poucave.utils import fetch_json

from .uptake_error_rate import fetch_normandy_uptake


EXPOSED_PARAMETERS = ["server", "lag_margin", "channels"]

NORMANDY_URL = "{server}/api/v1/recipe/signed/?enabled=1"

RFC_3339 = "%Y-%m-%dT%H:%M:%S.%fZ"


logger = logging.getLogger(__name__)


async def run(
    server: str, lag_margin: int = 600, channels: List[str] = [], period_hours: int = 6
) -> CheckResult:
    rows = await fetch_normandy_uptake(channels=channels, period_hours=period_hours)

    min_timestamp = min(r["min_timestamp"] for r in rows)
    max_timestamp = max(r["max_timestamp"] for r in rows)

    count_by_id: Dict[int, int] = defaultdict(int)
    for row in rows:
        try:
            rid = int(row["source"].split("/")[-1])
        except ValueError:
            # The query also returns action and runner uptake.
            continue
        count_by_id[rid] += row["total"]

    # Recipes from source of truth.
    normandy_url = NORMANDY_URL.format(server=server)
    normandy_recipes = await fetch_json(normandy_url)

    reported_recipes_ids = set(count_by_id.keys())

    normandy_recipes_ids = set(r["recipe"]["id"] for r in normandy_recipes)
    missing = normandy_recipes_ids - reported_recipes_ids

    data = {
        "min_timestamp": min_timestamp.isoformat(),
        "max_timestamp": max_timestamp.isoformat(),
        "missing": sorted(missing),
    }
    return len(missing) == 0, data
