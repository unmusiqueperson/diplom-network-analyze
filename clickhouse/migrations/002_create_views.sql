-- Материализованное представление: статистика по IP за час
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_stats_by_ip
ENGINE = SummingMergeTree()
ORDER BY (src_ip, hour)
AS SELECT
    src_ip,
    toStartOfHour(timestamp) AS hour,
    count()          AS events,
    sum(is_anomaly)  AS anomalies,
    sum(bytes)       AS total_bytes,
    avg(bytes)       AS avg_bytes
FROM network_events
GROUP BY src_ip, hour;

-- Материализованное представление: статистика по минутам
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_stats_by_minute
ENGINE = SummingMergeTree()
ORDER BY minute
AS SELECT
    toStartOfMinute(timestamp) AS minute,
    count()         AS events,
    sum(is_anomaly) AS anomalies,
    avg(bytes)      AS avg_bytes,
    max(bytes)      AS max_bytes
FROM network_events
GROUP BY minute;
