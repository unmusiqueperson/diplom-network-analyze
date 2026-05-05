import signal
import logging
from clickhouse_driver import Client
from datetime import datetime

logger = logging.getLogger(__name__)

class BatchWriter:
    """Батчевая запись событий в ClickHouse с back-pressure и graceful shutdown"""

    def __init__(self, host, port, user, password, batch_size=100, max_buffer=1000):
        self.client = Client(host=host, port=port, user=user, password=password)
        self.batch_size = batch_size
        self.max_buffer = max_buffer
        self.buffer = []
        self.anomaly_buffer = []
        self._register_shutdown()

    def _register_shutdown(self):
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        logger.info("Получен сигнал завершения. Сбрасываем буфер...")
        self.flush()
        logger.info(f"Буфер сброшен. Завершение работы.")
        exit(0)

    def add(self, event: dict, anomaly_result: dict = None):
        """Добавить событие в буфер"""
        # Back-pressure: если буфер переполнен — сбрасываем немедленно
        if len(self.buffer) >= self.max_buffer:
            logger.warning(f"Буфер переполнен ({self.max_buffer}). Принудительный сброс.")
            self.flush()

        ts = datetime.fromisoformat(event['timestamp'])
        self.buffer.append((
            ts,
            event['src_ip'], event['dst_ip'],
            event['src_port'], event['dst_port'],
            event['protocol'], event['bytes'],
            event['packets'], event['duration'],
            event['is_anomaly']
        ))

        if anomaly_result:
            self.anomaly_buffer.append((
                ts,
                event['src_ip'], event['dst_ip'],
                event['bytes'],
                anomaly_result.get('anomaly_type', 'normal'),
                anomaly_result.get('zscore', 0),
                anomaly_result.get('moving_avg', 0),
                anomaly_result.get('iso_forest', 0),
                anomaly_result.get('autoencoder', 0),
                anomaly_result.get('ensemble', 0),
                event['is_anomaly']
            ))

        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        """Сбросить буфер в ClickHouse"""
        if self.buffer:
            try:
                self.client.execute('INSERT INTO network_events VALUES', self.buffer)
                logger.info(f"Записано {len(self.buffer)} событий в ClickHouse.")
                self.buffer = []
            except Exception as e:
                logger.error(f"Ошибка записи в ClickHouse: {e}")

        if self.anomaly_buffer:
            try:
                self.client.execute('INSERT INTO anomaly_results VALUES', self.anomaly_buffer)
                logger.info(f"Записано {len(self.anomaly_buffer)} аномалий в anomaly_results.")
                self.anomaly_buffer = []
            except Exception as e:
                logger.error(f"Ошибка записи аномалий: {e}")
