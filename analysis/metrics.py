from clickhouse_driver import Client
import numpy as np

ch = Client(host='localhost', port=9000, user='default', password='diplom123')

print("Считаем метрики из ClickHouse...")
print("Ждём накопления данных...\n")

# Получаем все события
rows = ch.execute('''
    SELECT bytes, packets, duration, src_port, dst_port, is_anomaly
    FROM network_events
    ORDER BY timestamp
''')

if len(rows) < 100:
    print(f"Мало данных: {len(rows)} событий. Нужно минимум 100.")
    exit()

print(f"Загружено событий: {len(rows)}")

# Разбиваем на признаки и метки
X = np.array([[r[0], r[1], r[2], r[3], r[4]] for r in rows], dtype=np.float32)
y_true = np.array([r[5] for r in rows])

print(f"Реальных аномалий: {y_true.sum()} ({y_true.mean()*100:.1f}%)\n")

def calc_metrics(y_true, y_pred, name):
    tp = ((y_pred == 1) & (y_true == 1)).sum()
    fp = ((y_pred == 1) & (y_true == 0)).sum()
    fn = ((y_pred == 0) & (y_true == 1)).sum()
    tn = ((y_pred == 0) & (y_true == 0)).sum()

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy  = (tp + tn) / len(y_true)

    print(f"{'='*40}")
    print(f"Алгоритм: {name}")
    print(f"  Precision : {precision:.3f}")
    print(f"  Recall    : {recall:.3f}")
    print(f"  F1-score  : {f1:.3f}")
    print(f"  Accuracy  : {accuracy:.3f}")
    print(f"  TP:{tp} FP:{fp} FN:{fn} TN:{tn}")
    return precision, recall, f1

# Z-score
mean_b = np.mean(X[:, 0])
std_b  = np.std(X[:, 0])
z_pred = (np.abs((X[:, 0] - mean_b) / (std_b + 1e-9)) > 3.0).astype(int)
calc_metrics(y_true, z_pred, "Z-score")

# Скользящее среднее
ma_pred = np.zeros(len(X), dtype=int)
window = []
for i, row in enumerate(X):
    if len(window) >= 10:
        mean_w = np.mean(window[-100:])
        if row[0] > mean_w * 5:
            ma_pred[i] = 1
    window.append(row[0])
calc_metrics(y_true, ma_pred, "Скользящее среднее")

# Isolation Forest
from sklearn.ensemble import IsolationForest
iso = IsolationForest(contamination=0.05, random_state=42)
iso.fit(X)
iso_pred = (iso.predict(X) == -1).astype(int)
calc_metrics(y_true, iso_pred, "Isolation Forest")

# Autoencoder
import torch
import torch.nn as nn
import sys
sys.path.insert(0, '/Users/unmusiqueperson/Documents/Projects/diplom/consumer')
from autoencoder import AnomalyDetectorAE

ae = AnomalyDetectorAE(input_dim=5)
train_size = int(len(X) * 0.7)
ae.train(X[:train_size].tolist(), epochs=50)
ae_pred = np.array([1 if ae.detect(x.tolist()) else 0 for x in X])
calc_metrics(y_true, ae_pred, "Autoencoder")

print(f"\n{'='*40}")
print("Готово!")
