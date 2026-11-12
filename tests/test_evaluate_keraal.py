"""Testes das funções puras de scripts/evaluate_keraal.py (sem depender do download)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evaluate_keraal import judge, overlaps, pick, prf, wilson  # noqa: E402

CFG = {"errors": {"Error1": "physio_low_rom", "Error2": None}}


def finding(type_, t0, t1):
    return {"type": type_, "t_start": t0, "t_end": t1}


def rec(evaluation, errors=()):
    return {"evaluation": evaluation, "errors": list(errors)}


def test_overlaps_tolerance():
    err = {"t0": 10.0, "t1": 12.0}
    assert overlaps(finding("x", 13.5, 15.0), err)
    assert not overlaps(finding("x", 14.5, 15.0), err)


def test_judge_named_and_timed():
    r = rec("Incorrect", [{"type": "Error1", "t0": 5.0, "t1": 8.0}])
    j = judge(r, [finding("physio_low_rom", 6.0, 7.0)], CFG)
    assert j["flagged"] and j["named"] and j["timed"] and not j["not_visible"]
    j = judge(r, [finding("physio_low_rom", 20.0, 21.0)], CFG)
    assert j["named"] and not j["timed"]
    j = judge(r, [finding("physio_asymmetry", 6.0, 7.0)], CFG)
    assert not j["named"]


def test_judge_error_not_visible_in_2d():
    r = rec("Incorrect", [{"type": "Error2", "t0": 5.0, "t1": 8.0}])
    j = judge(r, [], CFG)
    assert not j["flagged"] and j["not_visible"] and j["named"] is None


def test_prf_and_pick():
    rows = [
        {"evaluation": "Incorrect", "j": {"flagged": True}},
        {"evaluation": "Incorrect", "j": {"flagged": False}},
        {"evaluation": "Correct", "j": {"flagged": True}},
        {"evaluation": "Correct", "j": {"flagged": False}},
        {"evaluation": "Incomplete", "j": {"flagged": True}},
    ]
    m = prf(rows)
    assert (m["tp"], m["fp"], m["n_incorrect"], m["n_correct"]) == (1, 1, 2, 2)
    assert m["precision"] == 0.5 and m["recall"] == 0.5 and m["false_alarm"] == 0.5
    best = pick([{"params": {"a": 1}, "metrics": {"f1": 0.4, "false_alarm": 0.1}},
                 {"params": {"a": 2}, "metrics": {"f1": 0.6, "false_alarm": 0.9}}])
    assert best["params"] == {"a": 2}


def test_wilson_bounds():
    lo, hi = wilson(0, 0)
    assert (lo, hi) == (0.0, 1.0)
    lo, hi = wilson(5, 10)
    assert 0.2 < lo < 0.5 < hi < 0.8
