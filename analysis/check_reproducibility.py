"""
analysis/check_reproducibility.py
Запускает metrics.py дважды и сравнивает результаты.
Выход 0 = детерминировано, выход 1 = расхождение.
"""

import subprocess
import sys
import json
import os

SCRIPT = os.path.join(os.path.dirname(__file__), "metrics.py")


def run_once() -> dict:
    """Запустить metrics.py и вернуть итоговую таблицу как dict."""
    result = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Ошибка запуска metrics.py:")
        print(result.stderr)
        sys.exit(1)

    # Парсим строки summary table: пропускаем заголовок, разделители
    rows = {}
    in_table = False
    for line in result.stdout.splitlines():
        if "SUMMARY TABLE" in line:
            in_table = True
            continue
        if not in_table:
            continue
        parts = line.split()
        # Валидная строка данных: имя модели + 4 числа
        if len(parts) >= 5:
            try:
                name = " ".join(parts[:-4])
                p, r, f1, acc = map(float, parts[-4:])
                rows[name] = {"P": p, "R": r, "F1": f1, "Acc": acc}
            except ValueError:
                continue
    return rows


def main():
    print("Запуск 1...")
    run1 = run_once()
    print(f"  Получено строк: {len(run1)}")

    print("Запуск 2...")
    run2 = run_once()
    print(f"  Получено строк: {len(run2)}")

    if run1.keys() != run2.keys():
        print(f"FAIL: разные наборы моделей: {run1.keys()} vs {run2.keys()}")
        sys.exit(1)

    mismatches = []
    for name in run1:
        for metric in ["P", "R", "F1", "Acc"]:
            v1 = run1[name][metric]
            v2 = run2[name][metric]
            if abs(v1 - v2) > 1e-6:
                mismatches.append(
                    f"  {name} | {metric}: {v1} vs {v2}"
                )

    if mismatches:
        print("\nFAIL: обнаружены расхождения:")
        for m in mismatches:
            print(m)
        sys.exit(1)
    else:
        print("\nOK: оба прогона дали идентичные результаты.")
        print("Зафиксированные гарантии детерминизма:")
        print("  random_state=42 (train_test_split, IsolationForest)")
        print("  torch.manual_seed(42) (Autoencoder)")
        print("  Единый SELECT-снимок из ClickHouse (dataset_snapshot)")
        sys.exit(0)


if __name__ == "__main__":
    main()
