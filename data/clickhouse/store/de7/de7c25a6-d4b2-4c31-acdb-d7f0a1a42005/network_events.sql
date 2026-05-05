ATTACH TABLE _ UUID 'fcec34a7-6db5-4b6b-8b46-d135c0a39a70'
(
    `timestamp` DateTime,
    `src_ip` String,
    `dst_ip` String,
    `src_port` UInt16,
    `dst_port` UInt16,
    `protocol` String,
    `bytes` UInt64,
    `packets` UInt32,
    `duration` Float32,
    `is_anomaly` UInt8
)
ENGINE = MergeTree
ORDER BY timestamp
SETTINGS index_granularity = 8192
