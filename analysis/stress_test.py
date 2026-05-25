"""
analysis/stress_test.py — Anomaly Rate Stress Test
Experiment: model stability under distribution shift (1% / 5% / 10% anomaly rate)
Protocol: same pipeline as metrics.py, 70/30 split, random_state=42
Only resampling changes — no model architecture changes.
"""

import os
import sys
import numpy as np
from clickhouse_driver import Client
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

ANOMALY_RATES = [0.01, 0.05, 0.10]
RANDOM_STATE  = 42

# ──────────────────────────────────────────────
# 1. LOAD SNAPSHOT
# ──────────────────────────────────────────────

def load_snapshot():
    ch = Client(
        host=os.getenv('CLICKHOUSE_HOST', 'localhost'),
        port=int(os.getenv('CLICKHOUSE_PORT', 9000)),
        user=os.getenv('CLICKHOUSE_USER', 'default'),
        password=os.getenv('CLICKHOUSE_PASSWORD', 'diplom123'),
    )
    rows = ch.execute("""
        SELECT bytes, packets, duration, src_port, dst_port, is_anomaly
        FROM network_events
        ORDER BY timestamp
    """)
    if len(rows) < 100:
        print(f"Insufficient data: {len(rows)} events.")
        sys.exit(1)
    X = np.array([[r[0], r[1], r[2], r[3], r[4]] for r in rows], dtype=np.float32)
    y = np.array([r[5] for r in rows], dtype=np.int32)
    return X, y


# ──────────────────────────────────────────────
# 2. RESAMPLE TO TARGET ANOMALY RATE
# ──────────────────────────────────────────────

def resample_to_rate(X, y, target_rate, random_state=42):
    """
    Resample dataset to achieve target anomaly rate.
    Keeps all anomalies, downsamples normals (or upsamples if needed).
    Uses random_state for reproducibility.
    """
    rng = np.random.RandomState(random_state)

    idx_anomaly = np.where(y == 1)[0]
    idx_normal  = np.where(y == 0)[0]

    n_anomaly = len(idx_anomaly)

    # n_anomaly / (n_anomaly + n_normal) = target_rate
    # n_normal = n_anomaly * (1 - target_rate) / target_rate
    n_normal_target = int(n_anomaly * (1 - target_rate) / target_rate)

    if n_normal_target > len(idx_normal):
        # Upsample normals with replacement
        idx_normal_sampled = rng.choice(idx_normal, size=n_normal_target, replace=True)
    else:
        # Downsample normals without replacement
        idx_normal_sampled = rng.choice(idx_normal, size=n_normal_target, replace=False)

    idx_all = np.concatenate([idx_anomaly, idx_normal_sampled])
    rng.shuffle(idx_all)

    return X[idx_all], y[idx_all]


# ──────────────────────────────────────────────
# 3. METRICS
# ──────────────────────────────────────────────

def calc_metrics(y_true, y_pred, name):
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy  = (tp + tn) / len(y_true)
    return {
        'name': name,
        'precision': round(precision, 3),
        'recall':    round(recall, 3),
        'f1':        round(f1, 3),
        'accuracy':  round(accuracy, 3),
        'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
    }


# ──────────────────────────────────────────────
# 4. DETECTORS (identical to metrics.py)
# ──────────────────────────────────────────────

def run_zscore(X_train, X_test, threshold=3.0, window=100):
    buf = deque(list(X_train[-window:, 0]), maxlen=window)
    preds = []
    for val in X_test[:, 0]:
        if len(buf) < 10:
            preds.append(0)
        else:
            mean, std = np.mean(buf), np.std(buf)
            z = abs((val - mean) / std) if std > 0 else 0.0
            preds.append(1 if z > threshold else 0)
        buf.append(val)
    return np.array(preds, dtype=np.int32)


def run_moving_avg(X_train, X_test, multiplier=5.0, window=100):
    buf = deque(list(X_train[-window:, 0]), maxlen=window)
    preds = []
    for val in X_test[:, 0]:
        if len(buf) < 10:
            preds.append(0)
        else:
            mean = np.mean(buf)
            preds.append(1 if val > mean * multiplier else 0)
        buf.append(val)
    return np.array(preds, dtype=np.int32)


def run_isolation_forest(X_train, X_test, contamination=0.05):
    model = IsolationForest(
        contamination=contamination,
        random_state=RANDOM_STATE,
        n_estimators=100,
    )
    model.fit(X_train)
    return (model.predict(X_test) == -1).astype(np.int32)


def run_autoencoder(X_train, X_test, epochs=50, threshold_percentile=95):
    import torch
    import torch.nn as nn

    mean, std = X_train.mean(axis=0), X_train.std(axis=0)
    std[std == 0] = 1.0
    X_tr = torch.FloatTensor((X_train - mean) / std)
    X_te = torch.FloatTensor((X_test  - mean) / std)

    class AE(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc = nn.Sequential(
                nn.Linear(5, 16), nn.ReLU(),
                nn.Linear(16, 8), nn.ReLU(),
                nn.Linear(8, 3),
            )
            self.dec = nn.Sequential(
                nn.Linear(3, 8),  nn.ReLU(),
                nn.Linear(8, 16), nn.ReLU(),
                nn.Linear(16, 5),
            )
        def forward(self, x):
            return self.dec(self.enc(x))

    torch.manual_seed(RANDOM_STATE)
    model = AE()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()
    model.train()
    for _ in range(epochs):
        optimizer.zero_grad()
        loss = criterion(model(X_tr), X_tr)
        loss.backward()
        optimizer.step()
    model.eval()
    with torch.no_grad():
        tr_errs   = torch.mean((model(X_tr) - X_tr) ** 2, dim=1).numpy()
        threshold = float(np.percentile(tr_errs, threshold_percentile))
        te_errs   = torch.mean((model(X_te) - X_te) ** 2, dim=1).numpy()
    return (te_errs > threshold).astype(np.int32)


def run_baseline(X_train, X_test, percentile=95):
    threshold = float(np.percentile(X_train[:, 0], percentile))
    return (X_test[:, 0] > threshold).astype(np.int32)


def run_ensemble(vote_matrix, min_votes):
    return (vote_matrix.sum(axis=1) >= min_votes).astype(np.int32)


# ──────────────────────────────────────────────
# 5. SINGLE RATE RUN
# ──────────────────────────────────────────────

def run_for_rate(X, y, target_rate):
    X_r, y_r = resample_to_rate(X, y, target_rate, random_state=RANDOM_STATE)

    actual_rate = y_r.mean()
    print(f"\n  Dataset size : {len(X_r)} | "
          f"Anomalies: {y_r.sum()} ({actual_rate*100:.1f}%)")

    X_train, X_test, y_train, y_test = train_test_split(
        X_r, y_r,
        test_size=0.30,
        random_state=RANDOM_STATE,
        stratify=y_r,
    )
    print(f"  Train: {len(X_train)} | Test: {len(X_test)} | "
          f"Test anomalies: {y_test.sum()}")

    # Run all detectors
    preds_z   = run_zscore(X_train, X_test)
    preds_ma  = run_moving_avg(X_train, X_test)
    preds_iso = run_isolation_forest(X_train, X_test)
    preds_ae  = run_autoencoder(X_train, X_test)
    preds_bl  = run_baseline(X_train, X_test)

    vote_matrix = np.column_stack([preds_z, preds_ma, preds_iso, preds_ae])

    results = {
        'Moving Average':      calc_metrics(y_test, preds_ma,  "Moving Average"),
        'Baseline (p95)':      calc_metrics(y_test, preds_bl,  "Baseline (p95)"),
        'Ensemble (votes>=2)': calc_metrics(y_test, run_ensemble(vote_matrix, 2), "Ensemble (votes>=2)"),
        'Ensemble (votes>=3)': calc_metrics(y_test, run_ensemble(vote_matrix, 3), "Ensemble (votes>=3)"),
    }
    return results


# ──────────────────────────────────────────────
# 6. PRINT TABLES
# ──────────────────────────────────────────────

def print_rate_table(rate_label, results):
    print(f"\n  {'Model':<26} {'P':>6} {'R':>6} {'F1':>6} {'Acc':>7}")
    print(f"  {'-'*50}")
    for r in results.values():
        print(f"  {r['name']:<26} "
              f"{r['precision']:>6.3f} "
              f"{r['recall']:>6.3f} "
              f"{r['f1']:>6.3f} "
              f"{r['accuracy']:>7.3f}")


def print_final_table(all_results):
    models = ['Moving Average', 'Baseline (p95)', 'Ensemble (votes>=2)', 'Ensemble (votes>=3)']
    rates  = [0.01, 0.05, 0.10]

    print(f"\n{'='*72}")
    print(f"{'STRESS TEST — FINAL COMPARISON TABLE':^72}")
    print(f"{'='*72}")
    print(f"{'anomaly_rate':<14} {'model':<26} {'precision':>9} {'recall':>7} {'f1':>7}")
    print(f"{'-'*72}")

    for rate in rates:
        rate_label = f"{int(rate*100)}%"
        for model in models:
            r = all_results[rate][model]
            print(f"{rate_label:<14} {r['name']:<26} "
                  f"{r['precision']:>9.3f} "
                  f"{r['recall']:>7.3f} "
                  f"{r['f1']:>7.3f}")
        print(f"{'-'*72}")

    print(f"{'='*72}")


# ──────────────────────────────────────────────
# 7. MAIN
# ──────────────────────────────────────────────

def main():
    print("Loading dataset snapshot from ClickHouse...")
    X, y = load_snapshot()
    print(f"Snapshot: {len(X)} events | "
          f"Anomalies: {y.sum()} ({y.mean()*100:.1f}%)")

    all_results = {}

    for rate in ANOMALY_RATES:
        rate_label = f"{int(rate*100)}%"
        print(f"\n{'='*54}")
        print(f"  ANOMALY RATE = {rate_label}")
        print(f"{'='*54}")
        results = run_for_rate(X, y, rate)
        all_results[rate] = results
        print_rate_table(rate_label, results)

    print_final_table(all_results)


if __name__ == '__main__':
    main()
