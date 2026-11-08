from datetime import UTC, datetime, timedelta

from medwatch.anomaly.prescriptions import PrescriptionMonitor, normalize_drug
from medwatch.config import load_yaml
from medwatch.contracts import PrescriptionEvent
from medwatch.simulator.synthetic import generate_patient_timeline

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _ev(i, minutes, drug, dose, action, unit="mg"):
    return PrescriptionEvent(rx_id=f"r{i}", patient_id="P", ts=T0 + timedelta(minutes=minutes),
                             drug=drug, dose=dose, unit=unit, action=action)


def test_normalize():
    assert normalize_drug("Heparina Sódica 5000 UI (frasco)") == "heparina sodica"


def test_rx_risky_scenario():
    _, rx, _, _ = generate_patient_timeline("P", T0, 600, "rx_risky", seed=1)
    mon = PrescriptionMonitor(load_yaml("drugs"))
    types = [e.type for ev in rx for e in mon.process(ev)]
    assert types.count("rx_interaction") == 1
    assert types.count("rx_dose_change") == 1


def test_small_dose_change_ignored():
    mon = PrescriptionMonitor(load_yaml("drugs"))
    mon.process(_ev(1, 0, "insulina", 10, "start", "UI"))
    assert mon.process(_ev(2, 10, "insulina", 12, "change", "UI")) == []


def test_dose_change_text_and_stop():
    mon = PrescriptionMonitor(load_yaml("drugs"))
    mon.process(_ev(1, 0, "insulina", 10, "start", "UI"))
    (e,) = mon.process(_ev(2, 10, "insulina", 20, "change", "UI"))
    assert e.explanation == "Dose de insulina alterada de 10 para 20 UI (2,0x)"
    mon.process(_ev(3, 20, "insulina", None, "stop"))
    assert mon.process(_ev(4, 30, "insulina", 40, "start", "UI"))[0].type == "rx_high_alert_start"


def test_duplicate_class_and_burst():
    mon = PrescriptionMonitor(load_yaml("drugs"))
    mon.process(_ev(1, 0, "ibuprofeno", 400, "start"))
    types = [e.type for e in mon.process(_ev(2, 1, "cetorolaco", 30, "start"))]
    assert "rx_duplicate_class" in types
    mon.process(_ev(3, 2, "dipirona", 500, "start"))
    types = [e.type for e in mon.process(_ev(4, 3, "paracetamol", 500, "start"))]
    assert "rx_change_burst" in types
    assert "rx_change_burst" not in [e.type for e in mon.process(_ev(5, 4, "x", 1, "start"))]
