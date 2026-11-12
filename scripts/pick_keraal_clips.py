"""Escolhe os clipes do Keraal para a demonstração (T40, passo 8): só saudáveis (grupo 2A) reservados.

Errado: gravação incorreta de saudável reservado que o analisador sinaliza com o erro nomeado e
coincidindo no tempo. Certo: gravação correta do mesmo voluntário e exercício que não é sinalizada.
Copia para data/samples/ como physio_keraal_wrong.mp4 e physio_keraal_correct.mp4, com um .txt
(exercício e anotação). Dados de pacientes (grupo 1A) nunca entram. Uso: python scripts/pick_keraal_clips.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_keraal import (  # noqa: E402
    EXERCISES,
    ROOT,
    analyze,
    build_reference,
    judge,
    load_recordings,
)

OUT = ROOT / "data" / "samples"
BASE = ROOT / "data" / "datasets" / "keraal"


def main() -> None:
    """Escolhe, copia e imprime a escolha para registrar em docs/DATASETS.md."""
    cfgs = yaml.safe_load((ROOT / "config" / "exercises.yaml").read_text(encoding="utf-8"))
    state = {}
    recs = load_recordings()
    pool = [r for r in recs if r["group"] == "2A" and r["split"] == "reservado" and not r["uncertain"]]
    cache: dict = {}
    for code, name in EXERCISES.items():
        cfg = {**cfgs[name], **_tuned(name)}
        wrong = [r for r in pool if r["exercise"] == code and r["evaluation"] == "Incorrect"]
        right = [r for r in pool if r["exercise"] == code and r["evaluation"] == "Correct"]
        if not wrong or not right:
            continue
        ref = build_reference(recs, code, cfg)
        for w in wrong:
            jw = judge(w, analyze(w, cfg, ref, cache), cfg)
            if not (jw["named"] and jw["timed"]):
                continue
            for c in right:
                if c["subject"] == w["subject"] and not judge(
                        c, analyze(c, cfg, ref, cache), cfg)["flagged"]:
                    state = {"exercise": name, "wrong": w, "right": c}
                    break
            if state:
                break
        if state:
            break
    if not state:
        print("nenhum par satisfaz o critério; veja docs/resultados/physio_keraal.md")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    w, c = state["wrong"], state["right"]
    for tag, r in (("wrong", w), ("correct", c)):
        shutil.copy(BASE / "g2a" / "videos" / r["video"], OUT / f"physio_keraal_{tag}.mp4")
        e = r["errors"][0] if r["errors"] else None
        note = f"exercise: {state['exercise']}\n"
        note += f"source: Keraal grupo 2A, voluntário saudável {r['subject']}, reservado\n"
        note += f"video: {r['video']}\nannotator A: {r['evaluation']}\n"
        if e:
            note += f"error: {e['type']} ({e['body_part']}) de {e['t0']} s a {e['t1']} s\n"
        (OUT / f"physio_keraal_{tag}.txt").write_text(note, encoding="utf-8")
    print("escolha:", state["exercise"], w["video"], c["video"])


def _tuned(name: str) -> dict:
    """Limiares da melhor combinação da grade (física: o mesmo usado no reservado), se existir."""
    import json
    p = ROOT / "docs" / "resultados" / "physio_keraal.json"
    return json.loads(p.read_text())[name]["final_cfg"] if p.exists() else {}


if __name__ == "__main__":
    main()
