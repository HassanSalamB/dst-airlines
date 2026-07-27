-- Small deterministic fixture used by CI integration tests.
INSERT INTO public.airports (iata, airport_id, city, country) VALUES
    ('ATL', 10397, 'Atlanta, GA', 'United States'),
    ('JFK', 12478, 'New York, NY', 'United States'),
    ('LAX', 12892, 'Los Angeles, CA', 'United States')
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
    CASE (n % 3) WHEN 0 THEN 'AA' WHEN 1 THEN 'DL' ELSE 'UA' END,
    'N' || LPAD(n::text, 5, '0'),
    1000 + n,
    CASE WHEN n % 2 = 0 THEN 10397 ELSE 12478 END,
    CASE WHEN n % 2 = 0 THEN 'ATL' ELSE 'JFK' END,
    CASE WHEN n % 2 = 0 THEN 'Atlanta, GA' ELSE 'New York, NY' END,
    12892,
    'LAX',
    'Los Angeles, CA',
    CASE WHEN n % 4 = 0 THEN 30.0 ELSE 5.0 END,
    n % 4 = 0,
    CASE WHEN n % 4 = 0 THEN 25.0 ELSE 2.0 END,
    n % 4 = 0,
    FALSE,
    FALSE,
    CASE WHEN n % 2 = 0 THEN 1946.0 ELSE 2475.0 END,
    8,
    CASE WHEN n % 4 = 0 THEN 10.0 ELSE 0.0 END,
    0.0,
    CASE WHEN n % 4 = 0 THEN 5.0 ELSE 0.0 END,
    0.0,
    CASE WHEN n % 4 = 0 THEN 10.0 ELSE 0.0 END
FROM generate_series(1, 24) AS n;
