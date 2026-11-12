import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from make_splits import load_splits, save_section, split_ids  # noqa: E402


def test_split_ids_disjoint_and_reproducible():
    ids = [f"M-{i}" for i in range(100)]
    a = split_ids(ids, (0.6, 0.2, 0.2), ("calibracao", "validacao", "reservado"))
    b = split_ids(list(reversed(ids)), (0.6, 0.2, 0.2), ("calibracao", "validacao", "reservado"))
    assert a == b
    assert [len(a[k]) for k in ("calibracao", "validacao", "reservado")] == [60, 20, 20]
    assert set().union(*a.values()) == set(ids)
    assert not set(a["calibracao"]) & set(a["reservado"])


def test_save_section_keeps_others(tmp_path):
    p = tmp_path / "splits.yaml"
    save_section("a", {"x": [1]}, p)
    save_section("b", {"y": [2]}, p)
    save_section("a", {"x": [3]}, p)
    assert load_splits(p) == {"a": {"x": [3]}, "b": {"y": [2]}}


def test_repo_splits_mimic_by_patient():
    data = load_splits()
    m = data["mimic"]
    parts = [set(m[k]) for k in ("calibracao", "validacao", "reservado")]
    assert sum(len(p) for p in parts) == len(set().union(*parts))


def test_rehab24_splits_by_volunteer(tmp_path):
    from make_splits import rehab24_splits
    seg = tmp_path / "Segmentation.csv"
    lines = ["video_id;repetition_number;exercise_id;person_id;first_frame;last_frame;correctness"]
    for pid in range(1, 10):
        lines += [f"PM_{pid:03d};{r};6;{pid};{r * 10};{r * 10 + 9};1" for r in (1, 2)]
    lines.append("PM_999;1;1;10;0;9;1")  # outro exercício: ignorado
    seg.write_text("\n".join(lines), encoding="utf-8")
    s = rehab24_splits(seg)
    parts = [set(s[k]) for k in ("calibracao", "validacao", "reservado")]
    assert [len(p) for p in parts] == [4, 2, 3]
    assert set().union(*parts) == {str(i) for i in range(1, 10)}
    assert rehab24_splits(seg) == s


def test_repo_splits_rehab24_disjoint():
    r = load_splits()["rehab24"]
    parts = [set(r[k]) for k in ("calibracao", "validacao", "reservado")]
    assert sum(len(p) for p in parts) == len(set().union(*parts)) == 9


def test_keraal_splits_by_volunteer(tmp_path):
    from make_splits import keraal_splits
    head = "video,subject,group,evaluation\n"
    rows = {"1A": [f"R{i}" for i in range(1, 7)], "2A": [f"S{i}" for i in range(1, 7)]}
    paths = []
    for g, subs in rows.items():
        f = tmp_path / f"recs_{g}.csv"
        lines = [f"v{s}{k}.mp4,{s},{g},{ev}" for s in subs for k, ev in enumerate(("Correct", "Incorrect"))]
        f.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
        paths.append(f)
    s = keraal_splits(paths)
    parts = [set(s[k]) for k in ("calibracao", "validacao", "reservado")]
    assert [len(p) for p in parts] == [6, 2, 4]
    assert set().union(*parts) == {f"R{i}" for i in range(1, 7)} | {f"S{i}" for i in range(1, 7)}
    assert {x[0] for x in s["reservado"]} == {"R", "S"}
    assert keraal_splits(paths) == s


def test_repo_splits_keraal_reserved_has_both_groups_and_labels():
    r = load_splits()["keraal"]
    parts = [set(r[k]) for k in ("calibracao", "validacao", "reservado")]
    assert sum(len(p) for p in parts) == len(set().union(*parts)) == 12
    res = r["reservado"]
    assert len(res) >= 2 and {x[0] for x in res} == {"R", "S"}
    assert sum(r["labels"][v]["corretas"] for v in res) > 0
    assert sum(r["labels"][v]["incorretas"] for v in res) > 0
