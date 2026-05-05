-- Основная таблица сетевых событий с TTL 90 дней
CREATE TABLE IF NOT EXISTS network_events (
    timestamp    DateTime,
    src_ip       String,
    dst_ip       String,
    src_port     UInt16,
    dst_port     UInt16,
    protocol     String,
    bytes        UInt64,
    packets      UInt32,
    duration     Float32,
    is_anomaly   UInt8
) ENGINE = MergeTree()
ORDER BY timestamp
TTL timestamp + INTERVAL 90 DAY;

-- Таблица для хранения результатов алгоритмов
CREATE TABLE IF NOT EXISTS anomaly_results (
    timestamp     DateTime,
    src_ip        String,
    dst_ip        String,
    bytes         UInt64,
    anomaly_type  String,
    z_score       UInt8,
    moving_avg    UInt8,
    iso_forest    UInt8,
    autoencoder   UInt8,
    ensemble      UInt8,
    is_real       UInt8
) ENGINE = MergeTree()
ORDER BY timestamp
TTL timestamp + INTERVAL 90 DAY;
