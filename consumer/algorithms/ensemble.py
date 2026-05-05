from .base import BaseDetector, load_config

class EnsembleDetector:
    """Взвешенное голосование всех четырёх алгоритмов"""

    def __init__(self, detectors: list):
        self.detectors = detectors
        self.config = load_config()
        self.min_votes = self.config['ensemble']['min_votes']
        self.use_weights = self.config['ensemble']['use_weights']

    def detect(self, features: list) -> tuple:
        """
        Возвращает (is_anomaly, score, votes)
        score — взвешенная сумма голосов от 0 до 1
        votes — словарь с результатами каждого алгоритма
        """
        votes = {}
        weighted_score = 0.0
        total_weight = 0.0
        vote_count = 0

        for detector in self.detectors:
            if not detector.is_ready():
                votes[detector.name] = 0
                continue
            result = 1 if detector.detect(features) else 0
            votes[detector.name] = result
            if self.use_weights:
                weighted_score += result * detector.weight
                total_weight += detector.weight
            else:
                weighted_score += result
                total_weight += 1
            vote_count += result

        score = weighted_score / total_weight if total_weight > 0 else 0.0
        is_anomaly = vote_count >= self.min_votes

        return is_anomaly, round(score, 3), votes

    def ready_count(self) -> int:
        return sum(1 for d in self.detectors if d.is_ready())
