import json
import os
import sys
from dotenv import load_dotenv

# Загружаем .env
load_dotenv(os.path.join(os.path.dirname(__file__), '../.env'))

from logger import setup_logger
from classifier import AnomalyClassifier
from batch_writer import BatchWriter
from drift_detector import DriftDetector
from algorithms import (
    ZScoreDetector, MovingAvgDetector,
    IsolationForestDetector, AutoencoderDetector,
    EnsembleDetector
)
from kafka import KafkaConsumer

logger = setup_logger('consumer')

# Подключение к Kafka
consumer = KafkaConsumer(
    os.getenv('KAFKA_TOPIC', 'network-events'),
    bootstrap_servers=os.getenv('KAFKA_BROKER', 'localhost:9092'),
    value_deserializer=lambda v: json.loads(v.decode('utf-8')),
    auto_offset_reset='latest',
    group_id='anomaly-detector-v3'
)

# Инициализация компонентов
writer = BatchWriter(
    host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
    port=int(os.getenv('CLICKHOUSE_PORT', 9000)),
    user=os.getenv('CLICKHOUSE_USER', 'default'),
    password=os.getenv('CLICKHOUSE_PASSWORD', 'diplom123'),
)

classifier  = AnomalyClassifier()
drift       = DriftDetector(window_size=500, threshold=0.3)

# Алгоритмы
zscore   = ZScoreDetector()
mov_avg  = MovingAvgDetector()
iso      = IsolationForestDetector()
ae       = AutoencoderDetector()
ensemble = EnsembleDetector([zscore, mov_avg, iso, ae])

logger.info("Консьюмер v3 запущен.")
logger.info(f"Алгоритмы: {ensemble.detectors}")

for message in consumer:
    try:
        event = message.value
        features = [
            event['bytes'], event['packets'], event['duration'],
            event['src_port'], event['dst_port']
        ]

        # Обновляем буферы алгоритмов которые требуют обучения
        iso.update_buffer(features)
        ae.update_buffer(features)

        # Проверяем дрейф данных
        drift_detected = drift.add(features)
        if drift_detected:
            logger.warning("Дрейф данных! Рекомендуется переобучение.")

        # Ensemble голосование
        is_anomaly, score, votes = ensemble.detect(features)

        # Классификация типа аномалии
        anomaly_type = 'normal'
        if is_anomaly:
            anomaly_type = classifier.classify(event)

        # Результат для записи
        anomaly_result = {
            'anomaly_type': anomaly_type,
            'zscore':      votes.get('zscore', 0),
            'moving_avg':  votes.get('moving_average', 0),
            'iso_forest':  votes.get('isolation_forest', 0),
            'autoencoder': votes.get('autoencoder', 0),
            'ensemble':    1 if is_anomaly else 0,
        }

        # Батчевая запись
        writer.add(event, anomaly_result if is_anomaly else None)

        if is_anomaly:
            logger.info(
                f"[{anomaly_type.upper()}] score={score} | "
                f"Z:{votes.get('zscore',0)} "
                f"MA:{votes.get('moving_average',0)} "
                f"ISO:{votes.get('isolation_forest',0)} "
                f"AE:{votes.get('autoencoder',0)} | "
                f"bytes:{event['bytes']} | "
                f"src:{event['src_ip']} -> dst:{event['dst_ip']}"
            )

    except Exception as e:
        logger.error(f"Ошибка обработки события: {e}")
        continue
