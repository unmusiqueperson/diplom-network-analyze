from prometheus_client import Counter, Histogram, start_http_server

events_processed_total = Counter(
    'events_processed_total',
    'Total number of Kafka events processed'
)

anomalies_detected_total = Counter(
    'anomalies_detected_total',
    'Total anomalies detected by ensemble',
    ['anomaly_type']
)

processing_latency_seconds = Histogram(
    'processing_latency_seconds',
    'Time to process a single Kafka event',
    buckets=[.001, .005, .01, .025, .05, .1, .25, .5, 1.0]
)

drift_events_total = Counter(
    'drift_events_total',
    'Number of data drift events detected'
)

processing_errors_total = Counter(
    'processing_errors_total',
    'Number of errors during event processing'
)

def start_metrics_server(port: int = 8001):
    start_http_server(port)
