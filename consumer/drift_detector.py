import numpy as np
import logging
from collections import deque

logger = logging.getLogger(__name__)

class DriftDetector:
    """
    Обнаружение дрейфа данных методом сравнения скользящих окон.
    Если распределение трафика изменилось — сигнализирует о необходимости
    переобучения моделей.
    """

    def __init__(self, window_size=500, threshold=0.3):
        self.window_size = window_size
        self.threshold = threshold
        self.reference_window = deque(maxlen=window_size)
        self.current_window = deque(maxlen=window_size)
        self.drift_count = 0
        self.is_reference_set = False

    def add(self, features: list) -> bool:
        """
        Добавить событие. Возвращает True если обнаружен дрейф.
        """
        bytes_val = features[0]
        self.current_window.append(bytes_val)

        # Первые window_size событий — эталонное окно
        if not self.is_reference_set:
            self.reference_window.append(bytes_val)
            if len(self.reference_window) >= self.window_size:
                self.is_reference_set = True
                logger.info("Эталонное окно установлено.")
            return False

        # Сравниваем текущее окно с эталонным
        if len(self.current_window) >= self.window_size:
            drift = self._detect_drift()
            if drift:
                self.drift_count += 1
                logger.warning(
                    f"Обнаружен дрейф данных #{self.drift_count}. "
                    f"Рекомендуется переобучение моделей."
                )
                # Обновляем эталонное окно
                self.reference_window = deque(
                    self.current_window, maxlen=self.window_size
                )
                return True
        return False

    def _detect_drift(self) -> bool:
        """Сравнение распределений через нормированное расстояние средних"""
        ref = np.array(self.reference_window)
        cur = np.array(self.current_window)

        ref_mean = np.mean(ref)
        cur_mean = np.mean(cur)
        ref_std  = np.std(ref) + 1e-9

        distance = abs(cur_mean - ref_mean) / ref_std
        logger.debug(f"Дрейф-метрика: {distance:.3f} (порог: {self.threshold})")
        return distance > self.threshold
