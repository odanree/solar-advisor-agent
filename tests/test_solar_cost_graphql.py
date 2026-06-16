import httpx
import pytest
import respx

from advisor.sources import SourceHttpError, SourceParseError
from advisor.sources.solar_cost_graphql import fetch_cost_bands


@respx.mock
async def test_fetch_cost_bands_success():
    url = "https://example.test/graphql/"
    respx.post(url).mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "costBands": {
                        "totalCount": 1,
                        "edges": [
                            {
                                "node": {
                                    "id": "1",
                                    "systemSizeRange": "5-8 kW",
                                    "panelTier": "standard",
                                    "location": "California",
                                    "installerType": "local",
                                    "p25": 2.95,
                                    "p50": 3.35,
                                    "p75": 3.75,
                                    "p90": 4.20,
                                    "sampleSize": 120,
                                }
                            }
                        ],
                    }
                }
            },
        )
    )
    bands = await fetch_cost_bands(url=url, location="California")
    assert len(bands) == 1
    assert bands[0].system_size_range == "5-8 kW"
    assert bands[0].p50 == 3.35


@respx.mock
async def test_fetch_cost_bands_http_error():
    url = "https://example.test/graphql/"
    respx.post(url).mock(return_value=httpx.Response(500, text="server boom"))
    with pytest.raises(SourceHttpError) as exc:
        await fetch_cost_bands(url=url)
    assert exc.value.status == 500


@respx.mock
async def test_fetch_cost_bands_graphql_errors():
    url = "https://example.test/graphql/"
    respx.post(url).mock(
        return_value=httpx.Response(200, json={"errors": [{"message": "bad filter"}]})
    )
    with pytest.raises(SourceParseError):
        await fetch_cost_bands(url=url)
