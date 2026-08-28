-- Small deterministic fixture used by CI integration tests.
INSERT INTO public.airports (iata, airport_id, city, country) VALUES
    ('RUH', 10001, 'Riyadh', 'Saudi Arabia'),
    ('JED', 10002, 'Jeddah', 'Saudi Arabia'),
    ('DXB', 20001, 'Dubai', 'United Arab Emirates')
ON CONFLICT (iata) DO NOTHING;

INSERT INTO bronze.flights (
    FlightDate,
    Operating_Airline,
    Tail_Number,
    Flight_Number_Operating_Airline,
    OriginAirportID,
    Origin,
    OriginCityName,
    DestAirportID,
    Dest,
    DestCityName,
    DepDelay,
    DepDel15,
    ArrDelay,
    ArrDel15,
    Cancelled,
    Diverted,
    Distance,
    DistanceGroup,
    CarrierDelay,
    WeatherDelay,
    NASDelay,
    SecurityDelay,
    LateAircraftDelay
)
SELECT
    DATE '2024-01-01' + (n - 1),
    CASE (n % 3) WHEN 0 THEN 'SV' WHEN 1 THEN 'RX' ELSE 'EK' END,
    'HZ' || LPAD(n::text, 5, '0'),
    1000 + n,
    CASE WHEN n % 2 = 0 THEN 10001 ELSE 10002 END,
    CASE WHEN n % 2 = 0 THEN 'RUH' ELSE 'JED' END,
    CASE WHEN n % 2 = 0 THEN 'Riyadh' ELSE 'Jeddah' END,
    20001,
    'DXB',
    'Dubai',
    CASE WHEN n % 4 = 0 THEN 30.0 ELSE 5.0 END,
    n % 4 = 0,
    CASE WHEN n % 4 = 0 THEN 25.0 ELSE 2.0 END,
    n % 4 = 0,
    FALSE,
    FALSE,
    CASE WHEN n % 2 = 0 THEN 545.0 ELSE 1055.0 END,
    3,
    CASE WHEN n % 4 = 0 THEN 10.0 ELSE 0.0 END,
    0.0,
    CASE WHEN n % 4 = 0 THEN 5.0 ELSE 0.0 END,
    0.0,
    CASE WHEN n % 4 = 0 THEN 10.0 ELSE 0.0 END
FROM generate_series(1, 24) AS n;
