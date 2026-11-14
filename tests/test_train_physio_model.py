import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import train_physio_model as tp  # noqa: E402

pytest.importorskip("sklearn")


def _folds(sep: float, n_subj: int = 5, n: int = 20, seed: int = 0):
    """Dobras sintéticas: incorretas deslocadas de `sep` na primeira medida."""
    rng = np.random.default_rng(seed)
    data = []
    for s in range(n_subj):
        y = np.array([0] * (n // 2) + [1] * (n // 2))
        X = rng.normal(size=(n, 4))
        X[:, 0] += sep * y
        data.append((str(s), X, y))
    fs = []
    for s, X, y in data:
        tr = [(X2, y2) for s2, X2, y2 in data if s2 != s]
        fs.append({"subject": s, "Xtr": np.vstack([a for a, _ in tr]),
                   "ytr": np.concatenate([b for _, b in tr]), "Xte": X, "yte": y})
    return fs


def test_supervised_and_unsupervised_separate_easy_data():
    fs = _folds(sep=4.0)
    lg = tp.cv_model("logistic", {"C": 1.0}, fs)
    assert lg["auc"] > 0.95 and lg["metrics"]["f1"] > 0.9
    mh = tp.cv_model("mahalanobis", {}, fs)
    assert mh["auc"] > 0.9 and mh["meets_fa"] and mh["metrics"]["false_alarm"] <= 0.2
    assert tp.wins(lg, bar=0.67)


def test_noise_does_not_win():
    fs = _folds(sep=0.0)
    lg = tp.cv_model("logistic", {"C": 1.0}, fs)
    assert lg["auc_ci"][0] < 0.5 or not tp.wins(lg, bar=0.67)


def test_binary_metrics_and_flag_all():
    y = np.array([1, 1, 0, 0, 0])
    m = tp.binary_metrics(y, np.array([1, 0, 1, 0, 0]))
    assert (m["tp"], m["fp"]) == (1, 1) and m["precision"] == 0.5 and m["recall"] == 0.5
    assert abs(m["false_alarm"] - 1 / 3) < 1e-9
    fa = tp.flag_all(y)
    assert fa["recall"] == 1.0 and abs(fa["precision"] - 0.4) < 1e-9


def test_auc_ci_by_subject_resamples_whole_subjects():
    y = np.array([0, 1] * 6)
    s = y.astype(float)
    lo, hi = tp.auc_ci_by_subject(y, s, [str(k // 4) for k in range(12)], n_boot=200)
    assert lo == hi == 1.0


def test_wins_requires_false_alarm_ceiling():
    r = {"metrics": {"f1": 0.9}, "meets_fa": False, "auc_ci": (0.8, 0.9)}
    assert not tp.wins(r, bar=0.5)
