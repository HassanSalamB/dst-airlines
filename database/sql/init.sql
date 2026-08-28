-- init.sql — runs automatically when PostgreSQL container starts
-- Creates schemas and tables for DST Airlines

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- Bronze: raw flights
CREATE TABLE IF NOT EXISTS bronze.flights (
    flight_id                       SERIAL PRIMARY KEY,
    FlightDate                      DATE NOT NULL,
    Operating_Airline               VARCHAR(20) NOT NULL,
    Tail_Number                     VARCHAR(20),
    Flight_Number_Operating_Airline INT,
    OriginAirportID                 INT,
    Origin                          VARCHAR(10) NOT NULL,
    OriginCityName                  VARCHAR(100),
    DestAirportID                   INT,
    Dest                            VARCHAR(10) NOT NULL,
    DestCityName                    VARCHAR(100),
    DepDelay                        FLOAT,
    DepDel15                        BOOLEAN,
    ArrDelay                        FLOAT,
    ArrDel15                        BOOLEAN,
    Cancelled                       BOOLEAN DEFAULT FALSE,
    Diverted                        BOOLEAN DEFAULT FALSE,
    Distance                        FLOAT,
    DistanceGroup                   INT,
    CarrierDelay                    FLOAT,
    WeatherDelay                    FLOAT,
    NASDelay                        FLOAT,
    SecurityDelay                   FLOAT,
    LateAircraftDelay               FLOAT,
    ingested_at                     TIMESTAMP DEFAULT NOW()
);

-- Bronze: weather
CREATE TABLE IF NOT EXISTS bronze.weather (
    weather_id        SERIAL PRIMARY KEY,
    location_name     VARCHAR(100) NOT NULL,
    weather_date      DATE NOT NULL,
    temp              FLOAT,
    temp_min_c        FLOAT,
    temp_max_c        FLOAT,
    relative_humidity FLOAT,
    precipitation_mm  FLOAT,
    snow_mm           FLOAT,
    wind_speed_kmh    FLOAT,
    pressure_hpa      FLOAT,
    cloud_cover       FLOAT,
    ingested_at       TIMESTAMP DEFAULT NOW()
);

-- Reference: airports
CREATE TABLE IF NOT EXISTS public.airports (
    iata       VARCHAR(10) PRIMARY KEY,
    airport_id INT,
    city       VARCHAR(100),
    country    VARCHAR(100) NOT NULL
);

-- Reference: airlines
CREATE TABLE IF NOT EXISTS public.airlines (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100)
);

-- Saudi Arabia and UAE portfolio carriers
INSERT INTO public.airlines (code, name) VALUES
    ('RX',  'Riyadh Air'),
    ('SV',  'Saudia'),
    ('XY',  'flynas'),
    ('EK',  'Emirates'),
    ('EY',  'Etihad Airways'),
    ('FZ',  'flydubai'),
    ('G9',  'Air Arabia')
ON CONFLICT (code) DO NOTHING;

-- Silver view: flights + weather joined
CREATE OR REPLACE VIEW silver.flights_weather AS
SELECT
    f.flight_id,
    f.FlightDate,
    f.Operating_Airline,
    f.Origin,
    f.OriginCityName,
    f.Dest,
    f.DestCityName,
    f.Distance,
    f.DistanceGroup,
    f.DepDelay,
    f.DepDel15,
    f.Diverted,
    f.CarrierDelay,
    f.WeatherDelay,
    f.NASDelay,
    wo.temp             AS temp_origin,
    wo.wind_speed_kmh   AS wind_origin,
    wo.precipitation_mm AS precip_origin,
    wd.temp             AS temp_dest,
    wd.wind_speed_kmh   AS wind_dest
FROM bronze.flights f
LEFT JOIN bronze.weather wo
    ON f.FlightDate = wo.weather_date
    AND f.OriginCityName = wo.location_name
LEFT JOIN bronze.weather wd
    ON f.FlightDate = wd.weather_date
    AND f.DestCityName = wd.location_name;

-- Gold view: ML-ready aggregates
CREATE OR REPLACE VIEW gold.delay_summary AS
SELECT
    Operating_Airline,
    Origin,
    Dest,
    COUNT(*)                                                        AS total_flights,
    ROUND(AVG(DepDelay)::numeric, 2)                               AS avg_dep_delay,
    ROUND(AVG(Distance)::numeric, 0)                               AS avg_distance,
    SUM(CASE WHEN DepDel15 = TRUE THEN 1 ELSE 0 END)              AS delayed_count,
    ROUND(AVG(CASE WHEN DepDel15 = TRUE THEN 1.0 ELSE 0.0 END) * 100, 2) AS delay_rate_pct,
    ROUND(AVG(CarrierDelay)::numeric, 2)                           AS avg_carrier_delay,
    ROUND(AVG(WeatherDelay)::numeric, 2)                           AS avg_weather_delay,
    ROUND(AVG(NASDelay)::numeric, 2)                               AS avg_nas_delay
FROM bronze.flights
WHERE Cancelled = FALSE OR Cancelled IS NULL
GROUP BY Operating_Airline, Origin, Dest;
