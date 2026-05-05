import numpy as np
from collections import deque
from .base import BaseDetector, load_config

class ZScoreDetector(BaseDetector):
    def __init__(self):
        super().__init__('zscore')
        cfg = self.config['zscore']
        self.window_size = cfg['window_size']
        self.threshold = cfg['threshold']
        self.window = deque(maxlen=self.window_size)
        self.is_trained = True  # Z-score не требует обучения

    def train(self, data: list) -> None:
        for item in data:
            self.window.append(item[0])  # bytes
        self.is_trained = True

    def detect(self, features: list) -> bool:
        bytes_val = features[0]
        if len(self.window) < 10:
            self.window.append(bytes_val)
            return False
        mean = np.mean(self.window)
        std = np.std(self.window)
        self.window.append(bytes_val)
        if std == 0:
            return False
        z = abs((bytes_val - mean) / std)
        return z > self.threshold
