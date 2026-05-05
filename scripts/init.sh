#!/bin/bash
echo "Инициализация проекта..."

# Ждём пока ClickHouse запустится
echo "Ожидаем ClickHouse..."
until docker exec diplom-clickhouse-1 clickhouse-client \
    --user default --password diploma123 \
    --query "SELECT 1" > /dev/null 2>&1; do
    sleep 2
done
echo "ClickHouse готов."

# Создаём таблицы
echo "Создаём таблицы..."
docker exec diplom-clickhouse-1 clickhouse-client \
    --user default --password diploma123 \
    --query "CREATE TABLE IF NOT EXISTS network_events (
    timestamp DateTime, src_ip String, dst_ip String,
    src_port UInt16, dst_port UInt16, protocol String,
    bytes UInt64, packets UInt32, duration Float32, is_anomaly UInt8
) ENGINE = MergeTree() ORDER BY timestamp TTL timestamp + INTERVAL 90 DAY"

docker exec diplom-clickhouse-1 clickhouse-client \
    --user default --password diploma123 \
    --query "CREATE TABLE IF NOT EXISTS anomaly_results (
    timestamp DateTime, src_ip String, dst_ip String, bytes UInt64,
    anomaly_type String, z_score UInt8, moving_avg UInt8,
    iso_forest UInt8, autoencoder UInt8, ensemble UInt8, is_real UInt8
) ENGINE = MergeTree() ORDER BY timestamp TTL timestamp + INTERVAL 90 DAY"

# Создаём материализованные представления
echo "Создаём представления..."
docker exec diplom-clickhouse-1 clickhouse-client \
    --user default --password diploma123 \
    --query "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_stats_by_ip
ENGINE = SummingMergeTree() ORDER BY (src_ip, hour)
AS SELECT src_ip, toStartOfHour(timestamp) AS hour,
count() AS events, sum(is_anomaly) AS anomalies,
sum(bytes) AS total_bytes, avg(bytes) AS avg_bytes
FROM network_events GROUP BY src_ip, hour"

docker exec diplom-clickhouse-1 clickhouse-client \
    --user default --password diploma123 \
    --query "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_stats_by_minute
ENGINE = SummingMergeTree() ORDER BY minute
AS SELECT toStartOfMinute(timestamp) AS minute,
count() AS events, sum(is_anomaly) AS anomalies,
avg(bytes) AS avg_bytes, max(bytes) AS max_bytes
FROM network_events GROUP BY minute"

echo "Готово! База данных инициализирована."
