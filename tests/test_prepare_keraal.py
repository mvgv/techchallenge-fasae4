import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "prepare_keraal", Path(__file__).parent.parent / "scripts" / "prepare_keraal.py"
)
pk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pk)

HEAD = '<?xml version="1.0" encoding="UTF-16"?><annotation><body>'
ERR = (
    '<el index="0" start="3.5" end="6"><attribute name="Evaluation">SmallError</attribute>'
    '<attribute name="type">Error2</attribute><attribute name="bodyPart">Spine</attribute></el>'
)


def _write(p: Path, ev: str, errs: str) -> None:
    xml = (
        HEAD
        + '<track name="Global evaluation"><el index="0" start="0" end="20">'
        + f'<attribute name="evaluation">{ev}</attribute></el></track>'
        + f'<track name="Temporal error">{errs}</track></body></annotation>'
    )
    p.write_text(xml, encoding="utf-16")


def test_build_rows(tmp_path):
    for d in ("annotatorA", "annotatorB"):
        (tmp_path / d).mkdir()
    _write(tmp_path / "annotatorA" / "G2A-ELK-S1-Brest-001.anvil", "Incorrect", ERR)
    _write(tmp_path / "annotatorB" / "G2A-ELK-S1-Brest-001.anvil", "Correct", "")
    _write(tmp_path / "annotatorA" / "G2A-CTK-S2-Brest-002.anvil", "Correct", "")
    _write(tmp_path / "annotatorB" / "G2A-CTK-S2-Brest-002.anvil", "Correct", "")
    rows = {r["subject"]: r for r in pk.build_rows(tmp_path, "2A")}
    bad, ok = rows["S1"], rows["S2"]
    assert bad["error_type"] == "Error2" and bad["body_part"] == "Spine"
    assert (bad["t_start_s"], bad["t_end_s"], bad["uncertain"]) == (3.5, 6.0, 1)
    assert bad["video"] == "G2A-Anon-ELK-S1-Brest-001.mp4"
    assert ok["error_type"] == "" and ok["uncertain"] == 0
