import pickle
import os
from sklearn.ensemble import IsolationForest as SKLearnIF
from .base import BaseDetector

MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/isolation_forest.pkl')

class IsolationForestDetector(BaseDetector):
    def __init__(self):
        super().__init__('isolation_forest')
        cfg = self.config['isolation_forest']
        self.train_size = cfg['train_size']
        self.buffer = []
        self.model = SKLearnIF(
            contamination=cfg['contamination'],
            random_state=cfg['random_state'],
            n_estimators=cfg['n_estimators']
        )
        self._load_model()

    def _load_model(self):
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, 'rb') as f:
                self.model = pickle.load(f)
            self.is_trained = True
            print("Isolation Forest загружен из файла.")

    def _save_model(self):
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        with open(MODEL_PATH, 'wb') as f:
            pickle.dump(self.model, f)

    def train(self, data: list) -> None:
        self.model.fit(data)
        self.is_trained = True
        self._save_model()
        print("Isolation Forest обучен и сохранён.")

    def update_buffer(self, features: list) -> None:
        if not self.is_trained:
            self.buffer.append(features)
            if len(self.buffer) >= self.train_size:
                self.train(self.buffer)

    def detect(self, features: list) -> bool:
        if not self.is_trained:
            return False
        pred = self.model.predict([features])
        return pred[0] == -1
