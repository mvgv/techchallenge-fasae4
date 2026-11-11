import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from prepare_rehab24 import build_rows, extract_videos  # noqa: E402

SPLITS = {"calibracao": ["1"], "validacao": [], "reservado": ["2"]}


def _seg(tmp_path):
    seg = tmp_path / "Segmentation.csv"
    seg.write_text(
        "video_id;repetition_number;exercise_id;person_id;first_frame;last_frame;"
        "cam17_orientation;correctness\n"
        "PM_008;1;6;1;30;90;front;1\n"
        "PM_008;2;6;1;91;180;half-profile;0\n"
        "PM_022;1;6;2;60;120;front;1\n"
        "PM_000;1;1;1;0;10;front;1\n",
        encoding="utf-8")
    return seg


def test_build_rows_filters_exercise_and_links_labels(tmp_path):
    rows = build_rows(_seg(tmp_path), SPLITS)
    assert len(rows) == 6  # 3 repetições x 2 câmeras; o Ex1 fica de fora
    r = rows[0]
    assert r["video"] == "PM_008-Camera17-30fps.mp4" and r["camera"] == 17
    assert (r["rep_start_s"], r["rep_end_s"]) == (1.0, 3.0)
    assert r["split"] == "calibracao" and r["label"] == "correct"
    assert rows[3]["video"] == "PM_008-Camera18-30fps-transposed.mp4"
    assert rows[2]["label"] == "incorrect" and rows[2]["orientation"] == "half-profile"
    assert rows[4]["split"] == "reservado"


def test_extract_videos_only_exercise(tmp_path):
    zp = tmp_path / "v.zip"
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("Ex6/", "")
        z.writestr("Ex6/PM_008-Camera17-30fps.mp4", b"abc")
        z.writestr("Ex1/PM_000-Camera17-30fps.mp4", b"xyz")
    out = extract_videos(zp, tmp_path / "squat")
    assert [p.name for p in out] == ["PM_008-Camera17-30fps.mp4"]
    assert out[0].read_bytes() == b"abc"
