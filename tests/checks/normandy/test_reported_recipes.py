from checks.normandy.reported_recipes import NORMANDY_URL, run
from tests.utils import patch_async


NORMANDY_SERVER = "http://normandy"
MODULE = "checks.normandy.reported_recipes"

FAKE_ROWS = [
    {
        "status": "success",
        "source": "normandy/recipe/123",
        "total": 20000,
        "min_timestamp": "2019-09-16T02:36:12.348",
        "max_timestamp": "2019-09-16T06:24:58.741",
    },
    {
        "status": "backoff",
        "source": "normandy/recipe/456",
        "total": 15000,
        "min_timestamp": "2019-09-16T03:36:12.348",
        "max_timestamp": "2019-09-16T05:24:58.741",
    },
    {
        "status": "apply_error",
        "source": "normandy/recipe/123",
        "total": 5000,
        "min_timestamp": "2019-09-16T01:36:12.348",
        "max_timestamp": "2019-09-16T07:24:58.741",
    },
    {
        "status": "custom_2_error",
        "source": "normandy/recipe/111",
        "total": 999,
        "min_timestamp": "2019-09-16T03:36:12.348",
        "max_timestamp": "2019-09-16T05:24:58.741",
    },
]


async def test_positive(mock_aioresponses):
    mock_aioresponses.get(
        NORMANDY_URL.format(server=NORMANDY_SERVER),
        payload=[{"recipe": {"id": 123}}, {"recipe": {"id": 456}}],
    )

    with patch_async(f"{MODULE}.fetch_redash", return_value=FAKE_ROWS):
        status, data = await run(server=NORMANDY_SERVER, api_key="")

    assert status is True
    assert data == {
        "missing": [],
        "extras": [],
        "min_timestamp": "2019-09-16T01:36:12.348",
        "max_timestamp": "2019-09-16T07:24:58.741",
    }


async def test_negative(mock_aioresponses):
    mock_aioresponses.get(
        NORMANDY_URL.format(server=NORMANDY_SERVER),
        payload=[
            {"recipe": {"id": 123}},
            {"recipe": {"id": 456}},
            {"recipe": {"id": 789}},
        ],
    )

    with patch_async(f"{MODULE}.fetch_redash", return_value=FAKE_ROWS):
        status, data = await run(server=NORMANDY_SERVER, api_key="")

    assert status is False
    assert data == {
        "missing": [789],
        "extras": [],
        "min_timestamp": "2019-09-16T01:36:12.348",
        "max_timestamp": "2019-09-16T07:24:58.741",
    }


async def test_negative_min_events(mock_aioresponses):
    mock_aioresponses.get(
        NORMANDY_URL.format(server=NORMANDY_SERVER),
        payload=[{"recipe": {"id": 123}}, {"recipe": {"id": 456}}],
    )

    with patch_async(f"{MODULE}.fetch_redash", return_value=FAKE_ROWS):
        status, data = await run(
            server=NORMANDY_SERVER, api_key="", min_total_events=100
        )

    assert status is False
    assert data == {
        "missing": [],
        "extras": [111],
        "min_timestamp": "2019-09-16T01:36:12.348",
        "max_timestamp": "2019-09-16T07:24:58.741",
    }
