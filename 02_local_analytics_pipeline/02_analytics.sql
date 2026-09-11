-- Aggregate analytics tables

DROP TABLE IF EXISTS chicago_taxi.daily_metrics;
CREATE TABLE chicago_taxi.daily_metrics AS
SELECT
    trip_date,
    COUNT(*) AS trip_count,
    SUM(total_amount) AS total_revenue,
    AVG(fare) AS avg_fare,
    AVG(trip_miles) AS avg_trip_miles,
    AVG(trip_seconds) AS avg_trip_seconds,
    SUM(CASE WHEN is_weekend THEN 1 ELSE 0 END) AS weekend_trips,
    SUM(CASE WHEN NOT is_weekend THEN 1 ELSE 0 END) AS weekday_trips
FROM chicago_taxi.trips_clean
GROUP BY trip_date
ORDER BY trip_date;

DROP TABLE IF EXISTS chicago_taxi.hourly_demand;
CREATE TABLE chicago_taxi.hourly_demand AS
SELECT
    trip_date,
    hour_of_day,
    COUNT(*) AS trip_count,
    SUM(total_amount) AS total_revenue,
    AVG(fare) AS avg_fare
FROM chicago_taxi.trips_clean
GROUP BY trip_date, hour_of_day
ORDER BY trip_date, hour_of_day;

DROP TABLE IF EXISTS chicago_taxi.zone_performance;
CREATE TABLE chicago_taxi.zone_performance AS
SELECT
    pickup_community_area,
    COUNT(*) AS trip_count,
    SUM(total_amount) AS total_revenue,
    AVG(fare) AS avg_fare,
    AVG(trip_miles) AS avg_trip_miles
FROM chicago_taxi.trips_clean
WHERE pickup_community_area IS NOT NULL
GROUP BY pickup_community_area
ORDER BY trip_count DESC;
