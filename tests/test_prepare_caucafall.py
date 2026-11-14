import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "prepare_caucafall", Path(__file__).parent.parent / "scripts" / "prepare_caucafall.py"
)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


def test_seq_name():
    assert pc.seq_name(1, "Fall backwards") == "s01-fall-backwards"
    assert pc.seq_name(10, "Pick up object") == "s10-pick-up-object"


def test_label_frame_offset_and_duplicates():
    assert pc.label_frame("cas100001.txt") == 0
    assert pc.label_frame("cfs1-00190.txt") == 189
    assert pc.label_frame("classes.txt") is None
    assert pc.label_frame("sals800096a.txt") is None


def test_frame_labels_drops_beyond_video_and_span():
    files = {
        "classes.txt": "nofall\nfall\n",
        "x00001.txt": "0 0.5 0.5 0.2 0.6\n",
        "x00002.txt": "1 0.5 0.7 0.6 0.2\n",
        "x00003.txt": "1 0.5 0.7 0.6 0.2\n",
        "x00004.txt": "1 0.5 0.7 0.6 0.2\n",  # quadro 3: além de um AVI de 3 quadros
        "x00005.txt": "",
    }
    labels = pc.frame_labels(files, n_frames=3)
    assert sorted(labels) == [0, 1, 2]
    assert labels[0] == (0, 0.5, 0.5, 0.2, 0.6)
    assert pc.fall_span(labels) == (1, 2)
    assert pc.fall_span({0: labels[0]}) is None
