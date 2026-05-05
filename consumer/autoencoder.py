import torch
import torch.nn as nn
import numpy as np

class Autoencoder(nn.Module):
    def __init__(self, input_dim=5):
        super(Autoencoder, self).__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.ReLU(),
            nn.Linear(16, 8),
            nn.ReLU(),
            nn.Linear(8, 3)
        )
        self.decoder = nn.Sequential(
            nn.Linear(3, 8),
            nn.ReLU(),
            nn.Linear(8, 16),
            nn.ReLU(),
            nn.Linear(16, input_dim)
        )

    def forward(self, x):
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded


class AnomalyDetectorAE:
    def __init__(self, input_dim=5, threshold_percentile=95):
        self.model = Autoencoder(input_dim)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()
        self.threshold = None
        self.threshold_percentile = threshold_percentile
        self.is_trained = False
        self.scaler_min = None
        self.scaler_max = None

    def normalize(self, X):
        if self.scaler_min is None:
            self.scaler_min = X.min(axis=0)
            self.scaler_max = X.max(axis=0)
        denom = self.scaler_max - self.scaler_min
        denom[denom == 0] = 1
        return (X - self.scaler_min) / denom

    def train(self, X, epochs=50):
        X = self.normalize(np.array(X, dtype=np.float32))
        X_tensor = torch.FloatTensor(X)
        self.model.train()
        for epoch in range(epochs):
            self.optimizer.zero_grad()
            output = self.model(X_tensor)
            loss = self.criterion(output, X_tensor)
            loss.backward()
            self.optimizer.step()

        # Считаем пороговое значение ошибки восстановления
        self.model.eval()
        with torch.no_grad():
            output = self.model(X_tensor)
            errors = torch.mean((output - X_tensor) ** 2, dim=1).numpy()
        self.threshold = np.percentile(errors, self.threshold_percentile)
        self.is_trained = True
        print(f"Autoencoder обучен. Порог ошибки: {self.threshold:.6f}")

    def detect(self, features):
        if not self.is_trained:
            return False
        x = np.array(features, dtype=np.float32)
        x = self.normalize(x)
        x_tensor = torch.FloatTensor(x).unsqueeze(0)
        self.model.eval()
        with torch.no_grad():
            output = self.model(x_tensor)
            error = torch.mean((output - x_tensor) ** 2).item()
        return error > self.threshold
