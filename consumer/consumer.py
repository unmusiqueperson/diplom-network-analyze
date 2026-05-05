import json
import numpy as np
from datetime import datetime
from kafka import KafkaConsumer
from clickhouse_driver import Client
from sklearn.ensemble import IsolationForest
from collections import deque

# Подключение к ClickHouse
ch = Client(host="localhost", port=9000, user="default", password="diploma123")

# Подключение к Kafka
consumer = KafkaConsumer(
    'network-events',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    auto_offset_reset='earliest',
    group_id='anomaly-detector'
)

# Буфер для скользящего среднего и Z-score
WINDOW_SIZE = 100
bytes_window = deque(maxlen=WINDOW_SIZE)

# Isolation Forest — обучаем на первых 200 событиях
if_model = IsolationForest(contamination=0.05, random_state=42)
if_buffer = []
if_trained = False

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

print("Консьюмер запущен. Анализируем события...")

for message in consumer:
    event = message.value

    ts = datetime.fromisoformat(event['timestamp'])
    bytes_val = event['bytes']
    features = [event['bytes'], event['packets'], event['duration'], event['src_port'], event['dst_port']]

    # Обучаем Isolation Forest когда накопили 200 событий
    if not if_trained:
        if_buffer.append(features)
        if len(if_buffer) >= 200:
            if_model.fit(if_buffer)
            if_trained = True
            print("Isolation Forest обучен!")

    # Три алгоритма
    z = 1 if zscore_detect(bytes_val, bytes_window) else 0
    ma = 1 if moving_avg_detect(bytes_val, bytes_window) else 0
    iso = 1 if isolation_forest_detect(features) else 0
    real = event['is_anomaly']

    bytes_window.append(bytes_val)

    # Пишем в ClickHouse
    ch.execute(
        'INSERT INTO network_events VALUES',
        [(ts, event['src_ip'], event['dst_ip'],
          event['src_port'], event['dst_port'],
          event['protocol'], event['bytes'],
          event['packets'], event['duration'], real)]
    )

    if z or ma or iso:
        print(f"[ОБНАРУЖЕНО] {ts} | Z:{z} MA:{ma} ISO:{iso} REAL:{real} | bytes:{bytes_val}")
