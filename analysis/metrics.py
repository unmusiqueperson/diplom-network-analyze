"""
analysis/metrics.py — Unified Experiment Runner
Ablation study: individual algorithms vs ensemble configurations
Protocol: 70/30 hold-out split, random_state=42, single ClickHouse snapshot
"""

import os
import sys
import numpy as np
from clickhouse_driver import Client
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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

def calc_metrics(y_true, y_pred, name):
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy  = (tp + tn) / len(y_true)
    return {'name': name, 'precision': round(precision, 3), 'recall': round(recall, 3),
            'f1': round(f1, 3), 'accuracy': round(accuracy, 3),
            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn}

def print_result(r):
    print(f"{'='*42}")
    print(f"Detector : {r['name']}")
    print(f"  Precision : {r['precision']:.3f}")
    print(f"  Recall    : {r['recall']:.3f}")
    print(f"  F1-score  : {r['f1']:.3f}")
    print(f"  Accuracy  : {r['accuracy']:.3f}")
    print(f"  TP:{r['tp']}  FP:{r['fp']}  FN:{r['fn']}  TN:{r['tn']}")

def print_summary(results):
    print(f"\n{'='*54}")
    print(f"{'SUMMARY TABLE':^54}")
    print(f"{'='*54}")
    print(f"{'Detector':<26} {'P':>6} {'R':>6} {'F1':>6} {'Acc':>7}")
    print("-" * 54)
    for r in results:
        print(f"{r['name']:<26} {r['precision']:>6.3f} {r['recall']:>6.3f} {r['f1']:>6.3f} {r['accuracy']:>7.3f}")
    print("=" * 54)

def run_zscore(X_train, X_test, threshold=3.0, window=100):
    from collections import deque
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
    from collections import deque
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
    model = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
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
            self.enc = nn.Sequential(nn.Linear(5,16), nn.ReLU(), nn.Linear(16,8), nn.ReLU(), nn.Linear(8,3))
            self.dec = nn.Sequential(nn.Linear(3,8),  nn.ReLU(), nn.Linear(8,16), nn.ReLU(), nn.Linear(16,5))
        def forward(self, x): return self.dec(self.enc(x))
    torch.manual_seed(42)
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
        tr_errs = torch.mean((model(X_tr) - X_tr) ** 2, dim=1).numpy()
        threshold = float(np.percentile(tr_errs, threshold_percentile))
        print(f"  Autoencoder threshold: {threshold:.6f}")
        te_errs = torch.mean((model(X_te) - X_te) ** 2, dim=1).numpy()
    return (te_errs > threshold).astype(np.int32)

def run_baseline(X_train, X_test, percentile=95):
    threshold = float(np.percentile(X_train[:, 0], percentile))
    print(f"  Baseline threshold (p{percentile}): {threshold:.1f} bytes")
    return (X_test[:, 0] > threshold).astype(np.int32)

def run_ensemble(vote_matrix, min_votes):
    return (vote_matrix.sum(axis=1) >= min_votes).astype(np.int32)

def main():
    print("Loading dataset snapshot from ClickHouse...")
    X, y = load_snapshot()
    print(f"Total events  : {len(X)}")
    print(f"Anomalies     : {y.sum()} ({y.mean()*100:.1f}%)")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y)
    print(f"Train: {len(X_train)} | Test: {len(X_test)}")
    print(f"Test anomalies: {y_test.sum()} ({y_test.mean()*100:.1f}%)\n")

    results = []

    print("[1/9] Z-score")
    preds_z = run_zscore(X_train, X_test)
    r = calc_metrics(y_test, preds_z, "Z-score"); print_result(r); results.append(r)

    print("[2/9] Moving Average")
    preds_ma = run_moving_avg(X_train, X_test)
    r = calc_metrics(y_test, preds_ma, "Moving Average"); print_result(r); results.append(r)

    print("[3/9] Isolation Forest")
    preds_iso = run_isolation_forest(X_train, X_test)
    r = calc_metrics(y_test, preds_iso, "Isolation Forest"); print_result(r); results.append(r)

    print("[4/9] Autoencoder")
    preds_ae = run_autoencoder(X_train, X_test)
    r = calc_metrics(y_test, preds_ae, "Autoencoder"); print_result(r); results.append(r)

    print("[5/9] Baseline (p95)")
    preds_bl = run_baseline(X_train, X_test)
    r = calc_metrics(y_test, preds_bl, "Baseline (p95)"); print_result(r); results.append(r)

    vote_matrix = np.column_stack([preds_z, preds_ma, preds_iso, preds_ae])
    for min_v in [1, 2, 3, 4]:
        label = f"Ensemble (votes>={min_v})"
        print(f"[{5+min_v}/9] {label}")
        preds_ens = run_ensemble(vote_matrix, min_votes=min_v)
        r = calc_metrics(y_test, preds_ens, label); print_result(r); results.append(r)

    print_summary(results)

if __name__ == '__main__':
    main()
