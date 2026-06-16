import httpx
import pytest
import respx

from advisor.sources import SourceHttpError, SourceParseError
from advisor.sources.nrel_pvwatts import estimate_production


@respx.mock
async def test_estimate_production_success():
    respx.get("https://developer.nrel.gov/api/pvwatts/v8.json").mock(
        return_value=httpx.Response(
            200,
            json={
                "outputs": {
                    "ac_annual": 9123.4,
                    "capacity_factor": 17.5,
                    "solrad_annual": 5.6,
                },
                "errors": [],
                "warnings": [],
            },
        )
    )
    result = await estimate_production(
        api_key="fake", lat=33.7, lon=-117.8, system_capacity_kw=6.0
    )
    assert result.ac_annual_kwh == 9123.4
    assert result.capacity_factor == 17.5
    assert result.system_capacity_kw == 6.0


@respx.mock
async def test_estimate_production_http_error():
    respx.get("https://developer.nrel.gov/api/pvwatts/v8.json").mock(
        return_value=httpx.Response(403, text="forbidden")
    )
    with pytest.raises(SourceHttpError):
        await estimate_production(
            api_key="fake", lat=33.7, lon=-117.8, system_capacity_kw=6.0
        )


@respx.mock
async def test_estimate_production_api_errors():
    respx.get("https://developer.nrel.gov/api/pvwatts/v8.json").mock(
        return_value=httpx.Response(
            200,
            json={"outputs": {}, "errors": ["invalid lat/lon"]},
        )
    )
    with pytest.raises(SourceParseError):
        await estimate_production(
            api_key="fake", lat=999, lon=999, system_capacity_kw=6.0
        )
