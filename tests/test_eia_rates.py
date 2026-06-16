import httpx
import pytest
import respx

from advisor.sources import SourceParseError
from advisor.sources.eia_rates import get_residential_rate


@respx.mock
async def test_get_rate_success():
    respx.get("https://api.eia.gov/v2/electricity/retail-sales/data/").mock(
        return_value=httpx.Response(
            200,
            json={
                "response": {
                    "data": [
                        {
                            "period": "2026-04",
                            "stateid": "CA",
                            "sectorid": "RES",
                            "price": 31.42,
                        }
                    ]
                }
            },
        )
    )
    rate = await get_residential_rate(api_key="fake", state="California")
    assert rate.state_code == "CA"
    assert rate.price_cents_per_kwh == 31.42
    assert rate.period == "2026-04"


async def test_unknown_state_raises():
    with pytest.raises(SourceParseError):
        await get_residential_rate(api_key="fake", state="Atlantis")


@respx.mock
async def test_empty_data_raises():
    respx.get("https://api.eia.gov/v2/electricity/retail-sales/data/").mock(
        return_value=httpx.Response(200, json={"response": {"data": []}})
    )
    with pytest.raises(SourceParseError):
        await get_residential_rate(api_key="fake", state="California")
