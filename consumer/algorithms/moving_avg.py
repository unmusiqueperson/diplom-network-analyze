import numpy as np
from collections import deque
from .base import BaseDetector, load_config

class MovingAvgDetector(BaseDetector):
    def __init__(self):
        super().__init__('moving_average')
        cfg = self.config['moving_average']
        self.window_size = cfg['window_size']
        self.multiplier = cfg['multiplier']
        self.window = deque(maxlen=self.window_size)
        self.is_trained = True

    def train(self, data: list) -> None:
        for item in data:
            self.window.append(item[0])
        self.is_trained = True

    def detect(self, features: list) -> bool:
        bytes_val = features[0]
        if len(self.window) < 10:
            self.window.append(bytes_val)
            return False
        mean = np.mean(self.window)
        self.window.append(bytes_val)
        return bytes_val > mean * self.multiplier
