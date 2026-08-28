from gulf_live import OpenSkyGulfClient, market_for_position, nearest_gateway


def test_nearest_gateway_assigns_riyadh_market():
    airport, details, distance = nearest_gateway(24.96, 46.70)
    assert airport == "RUH"
    assert details["country"] == "Saudi Arabia"
    assert distance < 2


def test_market_boundaries_exclude_neighboring_countries():
    assert market_for_position(24.71, 46.68) == "Saudi Arabia"
    assert market_for_position(25.20, 55.27) == "United Arab Emirates"
    assert market_for_position(32.08, 34.78) is None


def test_normalize_keeps_only_airborne_positioned_aircraft():
    airborne = [
        "abc123", "SVA123 ", "Saudi Arabia", 1, 2, 46.7, 24.96,
        10000, False, 240, 90, 0, None, 10100, "7000", False, 0,
    ]
    grounded = [
        "def456", "UAE456 ", "United Arab Emirates", 1, 2, 55.36, 25.25,
        0, True, 0, 0, 0, None, 0, None, False, 0,
    ]
    records = list(OpenSkyGulfClient.normalize([airborne, grounded], 1_700_000_000))
    assert len(records) == 1
    assert records[0]["callsign"] == "SVA123"
    assert records[0]["market_country"] == "Saudi Arabia"
    assert records[0]["nearest_airport"] == "RUH"
    assert records[0]["is_live"] is True
