from advisor.sources.dsire import lookup_incentives


async def test_lookup_returns_federal_for_any_state():
    incentives = await lookup_incentives("Texas")
    assert any(i.scope == "federal" for i in incentives)
    fed = next(i for i in incentives if i.scope == "federal")
    assert fed.value_pct == 30.0


async def test_lookup_adds_state_incentives_when_known():
    ca = await lookup_incentives("California")
    state_ones = [i for i in ca if i.scope == "state"]
    assert len(state_ones) >= 1


async def test_lookup_unknown_state_returns_federal_only():
    nv = await lookup_incentives("Nevada")
    assert len(nv) == 1
    assert nv[0].scope == "federal"
