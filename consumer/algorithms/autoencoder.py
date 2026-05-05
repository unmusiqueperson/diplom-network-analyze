import torch
import torch.nn as nn
import numpy as np
import os
from .base import BaseDetector

MODEL_PATH = os.path.join(os.path.dirname(__file__), '../models/autoencoder.pt')

class AutoencoderNet(nn.Module):
    def __init__(self, input_dim=5):
        super(AutoencoderNet, self).__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16), nn.ReLU(),
            nn.Linear(16, 8), nn.ReLU(),
            nn.Linear(8, 3)
        )
        self.decoder = nn.Sequential(
            nn.Linear(3, 8), nn.ReLU(),
            nn.Linear(8, 16), nn.ReLU(),
            nn.Linear(16, input_dim)
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


class AutoencoderDetector(BaseDetector):
    def __init__(self):
        super().__init__('autoencoder')
        cfg = self.config['autoencoder']
        self.input_dim = cfg['input_dim']
        self.epochs = cfg['epochs']
        self.lr = cfg['learning_rate']
        self.train_size = cfg['train_size']
        self.threshold_percentile = cfg['threshold_percentile']
        self.threshold = None
        self.buffer = []
        self.model = AutoencoderNet(self.input_dim)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        self.criterion = nn.MSELoss()
        # Скользящая нормализация
        self.running_mean = None
        self.running_std = None
        self._load_model()

    def _load_model(self):
        if os.path.exists(MODEL_PATH):
            checkpoint = torch.load(MODEL_PATH)
            self.model.load_state_dict(checkpoint['model_state'])
            self.threshold = checkpoint['threshold']
            self.running_mean = checkpoint['running_mean']
            self.running_std = checkpoint['running_std']
            self.is_trained = True
            print("Autoencoder загружен из файла.")

    def _save_model(self):
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        torch.save({
            'model_state': self.model.state_dict(),
            'threshold': self.threshold,
            'running_mean': self.running_mean,
            'running_std': self.running_std
        }, MODEL_PATH)

    def _normalize(self, X):
        X = np.array(X, dtype=np.float32)
        if self.running_mean is None:
            self.running_mean = X.mean(axis=0)
            self.running_std = X.std(axis=0)
        self.running_std[self.running_std == 0] = 1
        return (X - self.running_mean) / self.running_std

    def train(self, data: list) -> None:
        X = self._normalize(data)
        X_tensor = torch.FloatTensor(X)
        self.model.train()
        for epoch in range(self.epochs):
            self.optimizer.zero_grad()
            output = self.model(X_tensor)
            loss = self.criterion(output, X_tensor)
            loss.backward()
            self.optimizer.step()
        self.model.eval()
        with torch.no_grad():
            output = self.model(X_tensor)
            errors = torch.mean((output - X_tensor) ** 2, dim=1).numpy()
        self.threshold = float(np.percentile(errors, self.threshold_percentile))
        self.is_trained = True
        self._save_model()
        print(f"Autoencoder обучен. Порог: {self.threshold:.6f}")

    def update_buffer(self, features: list) -> None:
        if not self.is_trained:
            self.buffer.append(features)
            if len(self.buffer) >= self.train_size:
                self.train(self.buffer)

    def detect(self, features: list) -> bool:
        if not self.is_trained:
            return False
        x = self._normalize([features])[0]
        x_tensor = torch.FloatTensor(x).unsqueeze(0)
        self.model.eval()
        with torch.no_grad():
            output = self.model(x_tensor)
            error = torch.mean((output - x_tensor) ** 2).item()
        return error > self.threshold
