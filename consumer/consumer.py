import json
import numpy as np
from datetime import datetime
from kafka import KafkaConsumer
from clickhouse_driver import Client
from sklearn.ensemble import IsolationForest
from collections import deque
from autoencoder import AnomalyDetectorAE

# Подключение к ClickHouse
ch = Client(host='localhost', port=9000, user='default', password='diploma123')

# Подключение к Kafka
consumer = KafkaConsumer(
    'network-events',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    auto_offset_reset='latest',
    group_id='anomaly-detector-v2'
)

# Буфер для Z-score и скользящего среднего
WINDOW_SIZE = 100
bytes_window = deque(maxlen=WINDOW_SIZE)

# Isolation Forest
if_model = IsolationForest(contamination=0.05, random_state=42)
if_buffer = []
if_trained = False

# Autoencoder
ae_model = AnomalyDetectorAE(input_dim=5)
ae_buffer = []
ae_trained = False

# Адаптивные пороги (пересчитываются каждые 500 событий)
adaptive_buffer = []
adaptive_threshold_bytes = None
event_count = 0

def zscore_detect(value, window):
    if len(window) < 10:
        return False
    mean = np.mean(window)
    std = np.std(window)
    if std == 0:
        return False
    z = abs((value - mean) / std)
    return z > 3.0

def moving_avg_detect(value, window):
    if len(window) < 10:
        return False
    mean = np.mean(window)
    threshold = mean * 5
    return value > threshold

def isolation_forest_detect(features):
    global if_trained
    if not if_trained:
        return False
    pred = if_model.predict([features])
    return pred[0] == -1

def classify_anomaly(event):
    """Классификация типа аномалии по признакам события"""
    bytes_val = event['bytes']
    packets = event['packets']
    duration = event['duration']
    dst_port = event['dst_port']
    dst_ip = event['dst_ip']

    # DDoS — огромный объём, много пакетов, короткая сессия
    if bytes_val > 100000 and packets > 500 and duration < 0.1:
        return 'ddos'

    # Port scan — маленький объём, мало пакетов, нестандартный порт
    if bytes_val < 200 and packets <= 3 and dst_port < 1024:
        return 'portscan'

    # Data leak — большой объём, внешний IP (не из 10.x или 192.168.x)
    if bytes_val > 50000 and not (dst_ip.startswith('10.') or dst_ip.startswith('192.168.')):
        return 'data_leak'

    # BGP аномалия — специфичный порт 179
    if dst_port == 179 or event.get('protocol') == 'BGP':
        return 'bgp_anomaly'

    return 'unknown'

def update_adaptive_threshold(buffer):
    """Пересчёт адаптивного порога на основе последних событий"""
    if len(buffer) < 100:
        return None
    values = [e['bytes'] for e in buffer]
    mean = np.mean(values)
    std = np.std(values)
    return mean + 4 * std

print("Консьюмер v2 запущен. Анализируем события...")

for message in consumer:
    event = message.value
    event_count += 1

    ts = datetime.fromisoformat(event['timestamp'])
    bytes_val = event['bytes']
    features = [
        event['bytes'],
        event['packets'],
        event['duration'],
        event['src_port'],
        event['dst_port']
    ]

    # Обучение Isolation Forest
    if not if_trained:
        if_buffer.append(features)
        if len(if_buffer) >= 200:
            if_model.fit(if_buffer)
            if_trained = True
            print("Isolation Forest обучен!")

    # Обучение Autoencoder
    if not ae_trained:
        ae_buffer.append(features)
        if len(ae_buffer) >= 300:
            ae_model.train(ae_buffer, epochs=50)
            ae_trained = True

    # Обновление адаптивного порога каждые 500 событий
    adaptive_buffer.append(event)
    if len(adaptive_buffer) > 500:
        adaptive_buffer.pop(0)
    if event_count % 500 == 0:
        adaptive_threshold_bytes = update_adaptive_threshold(adaptive_buffer)
        print(f"Адаптивный порог обновлён: {adaptive_threshold_bytes:.0f} байт")

    # Четыре алгоритма
    z   = 1 if zscore_detect(bytes_val, bytes_window) else 0
    ma  = 1 if moving_avg_detect(bytes_val, bytes_window) else 0
    iso = 1 if isolation_forest_detect(features) else 0
    ae  = 1 if ae_model.detect(features) else 0
    adp = 1 if (adaptive_threshold_bytes and bytes_val > adaptive_threshold_bytes) else 0
    real = event['is_anomaly']

    bytes_window.append(bytes_val)

    # Классификация если хоть один алгоритм сработал
    anomaly_type = 'normal'
    if z or ma or iso or ae or adp:
        anomaly_type = classify_anomaly(event)

    # Запись в ClickHouse
    ch.execute(
        'INSERT INTO network_events VALUES',
        [(ts, event['src_ip'], event['dst_ip'],
          event['src_port'], event['dst_port'],
          event['protocol'], event['bytes'],
          event['packets'], event['duration'], real)]
    )

    if z or ma or iso or ae or adp:
        print(f"[{anomaly_type.upper()}] {ts} | Z:{z} MA:{ma} ISO:{iso} AE:{ae} ADP:{adp} REAL:{real} | bytes:{bytes_val}")
