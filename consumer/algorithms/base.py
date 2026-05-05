from abc import ABC, abstractmethod
import yaml
import os

# Загружаем конфиг
CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../config/algorithms.yml')

def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f)

class BaseDetector(ABC):
    """Базовый класс для всех алгоритмов обнаружения аномалий"""

    def __init__(self, name: str):
        self.name = name
        self.is_trained = False
        self.config = load_config()
        self.weight = self.config.get(name, {}).get('weight', 0.25)

    @abstractmethod
    def train(self, data: list) -> None:
        """Обучение модели на нормальных данных"""
        pass

    @abstractmethod
    def detect(self, features: list) -> bool:
        """Возвращает True если событие аномальное"""
        pass

    def is_ready(self) -> bool:
        """Готов ли алгоритм к работе"""
        return self.is_trained

    def __repr__(self):
        return f"{self.name}(trained={self.is_trained}, weight={self.weight})"
