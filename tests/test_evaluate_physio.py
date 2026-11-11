import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_exercise_reference import reference_from_intervals  # noqa: E402
from evaluate_physio import (  # noqa: E402
    blocks_of,
    count_errors,
    covered_reps,
    metrics,
    pooled,
    wilson,
)


def test_reference_from_intervals_many_videos():
    t = np.linspace(0, 2 * np.pi, 40)
    s1 = {"knee": 120 + 40 * np.cos(t)}
    s2 = {"knee": 110 + 30 * np.cos(t)}
    ref = reference_from_intervals("squat", [s1, s2], [[(0, 39)], [(0, 39)]], 10.0)
    assert ref["n_reps"] == 2 and len(ref["mean_curves"]["knee"]) == 50
    assert abs(ref["rom"]["knee"] - 70) < 1  # média de 80 e 60


def test_reference_without_reps_fails():
    try:
        reference_from_intervals("squat", [{"knee": np.zeros(5)}], [[]], 10.0)
    except ValueError:
        return
    raise AssertionError("esperava ValueError")


def test_wilson_bounds():
    lo, hi = wilson(5, 10)
    assert 0.23 < lo < 0.5 < hi < 0.77
    assert wilson(0, 0) == (0.0, 1.0)


def test_covered_reps_includes_consolidated():
    f = [{"type": "physio_low_rom", "rep": 2, "payload": {}},
         {"type": "physio_asymmetry", "rep": None, "payload": {"reps": [1, 3]}},
         {"type": "other", "rep": 9, "payload": {}}]
    assert covered_reps(f) == {1, 2, 3}


def _row(label, flagged, subject=1, key=("v", "front"), n=(2, 2)):
    return {"label": label, "flagged": flagged, "subject": subject, "rep_key": key,
            "n_annot": n[0], "n_detected": n[1], "orientation": key[1]}


def test_metrics_precision_recall():
    rows = [_row("incorrect", True), _row("incorrect", False), _row("correct", True),
            _row("correct", False), _row("correct", False)]
    m = metrics(rows)
    assert (m["tp"], m["fp"]) == (1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5
    assert abs(m["false_alarm_rate"] - 1 / 3) < 1e-9


def test_count_errors_per_block():
    rows = [_row("correct", False, key=("a", "front"), n=(10, 8)),
            _row("correct", False, key=("a", "front"), n=(10, 8)),
            _row("correct", False, key=("b", "half-profile"), n=(4, 4))]
    c = count_errors(rows)
    assert len(c["blocks"]) == 2 and c["mae"] == 1.0


def test_pooled_sums_parts():
    part = {"tp": 2, "fp": 1, "n_incorrect": 4, "n_correct": 6}
    p = pooled({"calibracao": part, "validacao": part})
    assert (p["tp"], p["fp"], p["n_incorrect"], p["n_correct"]) == (4, 2, 8, 12)
    assert abs(p["precision"] - 4 / 6) < 1e-9 and p["recall"] == 0.5


def test_blocks_group_by_orientation_and_split():
    def r(i, ori, split="calibracao", cam=18):
        return {"video": "v", "camera": cam, "subject": 1, "split": split, "orientation": ori,
                "rep_start_s": float(i), "rep_end_s": i + 0.9, "label": "correct"}
    rows = [r(0, "front"), r(1, "front"), r(2, "half-profile"), r(3, "front", "reservado"),
            r(4, "front", cam=17)]
    b = blocks_of(rows, 18, {"calibracao"})
    assert [(x["orientation"], len(x["reps"])) for x in b] == [("front", 2), ("half-profile", 1)]
    assert b[0]["t0"] == -1.0 and abs(b[0]["t1"] - 2.9) < 1e-9
