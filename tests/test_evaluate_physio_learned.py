import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import evaluate_physio_learned as el  # noqa: E402
import train_physio_model as tp  # noqa: E402


def test_rules_with_and_without_new_findings():
    cfg = {"dtw_max": 20, "incomplete_rom_min_deg": 40.0, "trunk_min_expected_deg": 6.0}
    old = el.without_new(cfg, "squat")
    assert "incomplete_rom_min_deg" not in old and old["dtw_max"] == 20
    assert el.with_new(cfg, "squat")["trunk_min_expected_deg"] == 6.0


def _scored(flag, y):
    return el.scored(np.array(y), np.array(flag, float), np.array(flag), ["a", "a", "b", "b"])


def test_render_lists_methods_and_winner():
    y = [1, 0, 1, 0]
    m = tp.binary_metrics(np.array(y), np.array([1, 0, 1, 1]))
    model = {"auc": 0.8, "auc_ci": (0.6, 0.9), "metrics": m, "hyper": {"C": 1.0}}
    cv = {"exercises": {"squat": {"why": "2 corretas e 2 incorretas fora do reservado",
                                  "subjects": ["a", "b"], "rules": model, "flag_all": m,
                                  "models": {"logistic": model}, "winner": "logistic"}},
          "skipped": {"trunk_rotation": "28 corretas e 5 incorretas fora do reservado"},
          "new_findings": {"trunk_rotation": {"thresholds": {"rotation_ratio_range_min": 0.09},
                                              "check": {"rotation_ratio_range_min": {
                                                  "corretas": [5, 41], "alvo": [1, 2]}}}}}
    rows = {"regras": _scored([1, 0, 1, 1], y), "logistic": _scored([1, 0, 1, 0], y)}
    res = {"squat": {"subjects": ["a", "b"], "n_incorrect": 2, "n_correct": 2, "rows": rows},
           "trunk_rotation": {"rows": {"regras": _scored([1, 1, 1, 1], y)},
                              "new_findings": {"physio_rotation_low": {"corretas": [0, 2]}}},
           "hide_face": {"rows": {}}, "lateral_stretch": {"rows": {}}}
    md = el.render(cv, res)
    assert "Vencedor na validação cruzada: **Regressão logística**" in md
    assert "Sem dados para aprender" in md and "`rotation_ratio_range_min`" in md
    assert "## Leitura" in md
