"""Fisioterapia com aprendizado (T41, passos B2, B3 e B6): seleção por validação cruzada.

Uso: python scripts/train_physio_model.py [--save]

Unidades: repetição anotada do agachamento (REHAB24-6, câmera 18) e gravação do "esconder o
rosto" (Keraal CTK, sem as incertas). Só calibração + validação; a validação cruzada deixa um
voluntário de fora por vez, e a referência (curva média das corretas, usada no DTW e nas
regras) é refeita em cada dobra sem esse voluntário. Compara, na mesma validação:
  regras      achados `physio_*` com os limiares de config/exercises.yaml;
  sem supervisão  Mahalanobis (LedoitWolf) e IsolationForest treinados só com corretas;
  supervisionado  regressão logística balanceada, árvore rasa e GradientBoosting pequeno.
Grava docs/resultados/physio_learned_cv.json. Com --save, treina em calibração + validação e
salva models/physio_<exercício>.joblib só para o exercício em que um modelo venceu as regras.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_keraal as ek  # noqa: E402
import evaluate_physio as ep  # noqa: E402
from build_exercise_reference import reference_from_intervals  # noqa: E402

from medwatch.video.geometry import angle_series  # noqa: E402
from medwatch.video.physio_features import (  # noqa: E402
    dtw_features,
    feature_names,
    feature_vector,
    joint_series,
    to_matrix,
)
from medwatch.video.reps import segment_reps  # noqa: E402

OUT = ROOT / "docs" / "resultados"
SEED = 42
CAMERA = 18
TRAIN_SPLITS = ("calibracao", "validacao")
MIN_PER_CLASS = 10
MAX_FALSE_ALARM = 0.20
PERCENTILES = (70, 75, 80, 85, 90, 95)
HYPER = {
    "mahalanobis": [{}],
    "iforest": [{"n_estimators": 300}],
    "logistic": [{"C": c} for c in (0.01, 0.1, 1.0, 10.0)],
    "tree": [{"max_depth": d} for d in (2, 3)],
    "gbm": [{"n_estimators": 100, "max_depth": 2}],
}
UNSUPERVISED = ("mahalanobis", "iforest")
KERAAL = {"hide_face": "CTK", "lateral_stretch": "ELK", "trunk_rotation": "RTK"}


def load_cfgs() -> dict:
    """config/exercises.yaml."""
    return yaml.safe_load((ROOT / "config" / "exercises.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- unidades


def squat_units(cfg: dict) -> list[dict]:
    """Uma unidade por repetição anotada (câmera 18), com o bloco para as regras."""
    rows = ep.load_reps()
    out = []
    blocks = ep.blocks_of(rows, CAMERA, {"calibracao", "validacao", "reservado"})
    for bi, b in enumerate(blocks):
        t, people = ep.load_poses(b["video"])
        for ri, r in enumerate(b["reps"]):
            idx = np.where((t >= r["rep_start_s"]) & (t <= r["rep_end_s"]))[0]
            if len(idx) < 3:
                continue
            pp, tt = [people[i] for i in idx], [float(t[i]) for i in idx]
            out.append({
                "key": f"{b['video']}#{r['rep_start_s']:.2f}", "subject": str(b["subject"]),
                "split": b["split"], "y": int(r["label"] == "incorrect"), "error": None,
                "evaluation": r["label"], "block": bi, "rep_in_block": ri,
                "base": feature_vector(pp, tt, cfg, None, ep.MIN_CONF, ep.FPS),
                "series": joint_series(pp, cfg, ep.MIN_CONF),
            })
    return out


def keraal_units(code: str, cfg: dict, evaluations=("Correct", "Incorrect")) -> list[dict]:
    """Uma unidade por gravação do exercício (sem as incertas)."""
    out = []
    for r in ek.load_recordings():
        if r["exercise"] != code or r["evaluation"] not in evaluations or r["uncertain"]:
            continue
        t, people, fps = ek.load_poses(r["video"])
        tt = [float(x) for x in t]
        out.append({
            "key": r["video"], "subject": r["subject"], "split": r["split"],
            "y": int(r["evaluation"] == "Incorrect"), "evaluation": r["evaluation"],
            "error": r["errors"][0]["type"] if r["errors"] else None, "rec": r,
            "base": feature_vector(people, tt, cfg, None, ek.MIN_CONF, fps),
            "series": joint_series(people, cfg, ek.MIN_CONF),
        })
    return out


def units_for(exercise: str, cfg: dict) -> list[dict]:
    """Unidades do exercício (agachamento ou Keraal)."""
    return squat_units(cfg) if exercise == "squat" else keraal_units(KERAAL[exercise], cfg)


# ---------------------------------------------------------------- referência


def squat_reference(cfg: dict, subjects: set[str]) -> dict:
    """Curva média das repetições corretas anotadas dos voluntários dados (câmera 18)."""
    rows = [r for r in ep.load_reps() if r["camera"] == CAMERA and str(r["subject"]) in subjects]
    series_list, intervals = [], []
    for video in dict.fromkeys(r["video"] for r in rows):
        t, people = ep.load_poses(video)
        series = angle_series(people, cfg["joints"], ep.MIN_CONF)
        ivs = []
        for r in rows:
            if r["video"] == video and r["label"] == "correct":
                a, b = int(np.searchsorted(t, r["rep_start_s"])), int(np.searchsorted(t, r["rep_end_s"]))
                if b - a >= 5:
                    ivs.append((a, min(b, len(t) - 1)))
        series_list.append(series)
        intervals.append(ivs)
    return reference_from_intervals("squat", series_list, intervals, ep.FPS)


def keraal_reference(code: str, cfg: dict, subjects: set[str]) -> dict:
    """Curva média das repetições detectadas nas gravações corretas dos voluntários dados."""
    series_list, intervals, fps_all = [], [], []
    for r in ek.load_recordings():
        if (r["exercise"], r["evaluation"], r["uncertain"]) != (code, "Correct", 0):
            continue
        if r["subject"] not in subjects:
            continue
        _, people, fps = ek.load_poses(r["video"])
        s = angle_series(people, cfg["joints"], ek.MIN_CONF)
        reps = segment_reps(s[cfg["primary_joint"]], fps, cfg["rep_min_prominence_deg"],
                            cfg["rep_min_distance_s"])
        if reps:
            series_list.append(s)
            intervals.append(reps)
            fps_all.append(fps)
    return reference_from_intervals(code, series_list, intervals,
                                    float(np.mean(fps_all)) if fps_all else 10.0)


def reference_for(exercise: str, cfg: dict, subjects: set[str]) -> dict:
    """Referência montada só com os voluntários de treino."""
    if exercise == "squat":
        return squat_reference(cfg, subjects)
    return keraal_reference(KERAAL[exercise], cfg, subjects)


def matrix(units: list[dict], cfg: dict, reference: dict) -> np.ndarray:
    """Medidas das unidades com o DTW para a referência dada."""
    names = feature_names(cfg)
    rows = [{**u["base"], **dtw_features(u["series"], reference)} for u in units]
    return to_matrix(rows, names)


# ---------------------------------------------------------------- regras


def t40_params(exercise: str) -> dict:
    """Limiares com que a T40 mediu o reservado (`final_cfg` de physio_keraal.json, fora do Git);
    vazio no agachamento (a T39 manteve os de exercises.yaml) ou se o JSON não existir."""
    path = OUT / "physio_keraal.json"
    if exercise == "squat" or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get(exercise, {}).get("final_cfg", {})


def rule_flags(exercise: str, cfg: dict, units: list[dict], reference: dict) -> np.ndarray:
    """1 se algum achado `physio_*` das regras atuais cobre a unidade."""
    if exercise != "squat":
        cache: dict = {}
        return np.array([int(bool(ek.analyze(u["rec"], cfg, reference, cache))) for u in units])
    rows = ep.load_reps()
    blocks = ep.blocks_of(rows, CAMERA, {"calibracao", "validacao", "reservado"})
    flags = {}
    for bi in sorted({u["block"] for u in units}):
        res = ep.evaluate_blocks([blocks[bi]], cfg, reference)
        for ri, row in enumerate(res):
            flags[(bi, ri)] = int(row["flagged"])
    return np.array([flags[(u["block"], u["rep_in_block"])] for u in units])


# ---------------------------------------------------------------- modelos


def make_model(family: str, h: dict):
    """Pipeline do scikit-learn (imputação pela mediana; padronização onde importa)."""
    from sklearn.covariance import LedoitWolf
    from sklearn.ensemble import GradientBoostingClassifier, IsolationForest
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier

    imp = SimpleImputer(strategy="median", keep_empty_features=True)
    if family == "mahalanobis":
        return make_pipeline(imp, StandardScaler(), LedoitWolf())
    if family == "iforest":
        return make_pipeline(imp, IsolationForest(random_state=SEED, **h))
    if family == "logistic":
        return make_pipeline(imp, StandardScaler(), LogisticRegression(
            class_weight="balanced", max_iter=5000, **h))
    if family == "tree":
        return make_pipeline(imp, DecisionTreeClassifier(
            class_weight="balanced", min_samples_leaf=5, random_state=SEED, **h))
    if family == "gbm":
        return make_pipeline(imp, GradientBoostingClassifier(
            learning_rate=0.1, subsample=0.8, random_state=SEED, **h))
    raise ValueError(family)


def fit(family: str, h: dict, X: np.ndarray, y: np.ndarray):
    """Treina; os modelos sem supervisão veem só as corretas (y = 0)."""
    model = make_model(family, h)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if family in UNSUPERVISED:
            model.fit(X[y == 0])
        elif family == "gbm":
            w = np.where(y == 1, (y == 0).sum() / max(1, (y == 1).sum()), 1.0)
            model.fit(X, y, gradientboostingclassifier__sample_weight=w)
        else:
            model.fit(X, y)
    return model


def anomaly_score(family: str, model, X: np.ndarray) -> np.ndarray:
    """Quanto maior, mais suspeita a unidade (distância, isolamento ou probabilidade)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if family == "mahalanobis":
            Xt = model[:-1].transform(X)
            return model[-1].mahalanobis(Xt)
        if family == "iforest":
            return -model.score_samples(X)
        return model.predict_proba(X)[:, 1]


# ---------------------------------------------------------------- métricas


def auc(y: np.ndarray, s: np.ndarray) -> float:
    """Área sob a curva ROC (NaN com uma classe só)."""
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(y, s)) if len(set(y.tolist())) == 2 else float("nan")


def auc_ci_by_subject(y: np.ndarray, s: np.ndarray, subjects: list[str], n_boot: int = 1000,
                      seed: int = SEED) -> tuple[float, float]:
    """IC 95% da AUC por bootstrap de voluntários (sorteia voluntários inteiros, com reposição)."""
    rng = np.random.default_rng(seed)
    subj = np.array(subjects)
    ids = sorted(set(subjects))
    idx = {k: np.where(subj == k)[0] for k in ids}
    vals = []
    for _ in range(n_boot):
        pick = np.concatenate([idx[k] for k in rng.choice(ids, size=len(ids), replace=True)])
        a = auc(y[pick], s[pick])
        if not np.isnan(a):
            vals.append(a)
    if not vals:
        return (float("nan"), float("nan"))
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))


def binary_metrics(y: np.ndarray, flag: np.ndarray) -> dict:
    """Precisão, recall, falsos alarmes e F1 da classe incorreta, com IC de Wilson."""
    tp = int(((flag == 1) & (y == 1)).sum())
    fp = int(((flag == 1) & (y == 0)).sum())
    n_inc, n_cor = int((y == 1).sum()), int((y == 0).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / n_inc if n_inc else 0.0
    return {"tp": tp, "fp": fp, "n_incorrect": n_inc, "n_correct": n_cor, "precision": p,
            "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "false_alarm": fp / n_cor if n_cor else 0.0,
            "precision_ci": ep.wilson(tp, tp + fp), "recall_ci": ep.wilson(tp, n_inc),
            "false_alarm_ci": ep.wilson(fp, n_cor)}


# ---------------------------------------------------------------- validação cruzada


def folds(exercise: str, cfg: dict, units: list[dict]) -> list[dict]:
    """Uma dobra por voluntário: matrizes com a referência sem o voluntário de fora."""
    out = []
    subjects = sorted({u["subject"] for u in units})
    for s in subjects:
        tr = [u for u in units if u["subject"] != s]
        te = [u for u in units if u["subject"] == s]
        ref = reference_for(exercise, cfg, {u["subject"] for u in tr})
        out.append({"subject": s, "train": tr, "test": te, "ref": ref,
                    "Xtr": matrix(tr, cfg, ref), "ytr": np.array([u["y"] for u in tr]),
                    "Xte": matrix(te, cfg, ref), "yte": np.array([u["y"] for u in te])})
    return out


def cv_model(family: str, h: dict, fs: list[dict]) -> dict:
    """Escores fora da dobra; limiar: 0,5 (supervisionado) ou percentil das corretas de treino."""
    ys, scores, thr_by_q, subj = [], [], {q: [] for q in PERCENTILES}, []
    for f in fs:
        subj += [f["subject"]] * len(f["yte"])
        m = fit(family, h, f["Xtr"], f["ytr"])
        s = anomaly_score(family, m, f["Xte"])
        ys.append(f["yte"])
        scores.append(s)
        if family in UNSUPERVISED:
            train_cor = anomaly_score(family, m, f["Xtr"][f["ytr"] == 0])
            for q in PERCENTILES:
                thr_by_q[q].append(s >= np.percentile(train_cor, q))
    y, s = np.concatenate(ys), np.concatenate(scores)
    res = {"family": family, "hyper": h, "auc": auc(y, s), "auc_ci": auc_ci_by_subject(y, s, subj),
           "y": y.tolist(), "score": s.tolist(), "subjects": subj, "meets_fa": True}
    if family in UNSUPERVISED:
        opts = []
        for q in PERCENTILES:
            m = binary_metrics(y, np.concatenate(thr_by_q[q]).astype(int))
            opts.append((q, m))
        ok = [o for o in opts if o[1]["false_alarm"] <= MAX_FALSE_ALARM]
        q, m = max(ok, key=lambda o: (o[1]["f1"], o[0])) if ok else opts[-1]
        res.update(percentile=q, metrics=m, meets_fa=bool(ok))
    else:
        res.update(metrics=binary_metrics(y, (s >= 0.5).astype(int)))
    return res


def cv_rules(exercise: str, cfg: dict, fs: list[dict]) -> dict:
    """As regras atuais na mesma validação (referência refeita por dobra)."""
    y = np.concatenate([f["yte"] for f in fs])
    cfg = {**cfg, **t40_params(exercise)}
    flag = np.concatenate([rule_flags(exercise, cfg, f["test"], f["ref"]) for f in fs])
    subj = [f["subject"] for f in fs for _ in f["yte"]]
    return {"family": "regras", "auc": auc(y, flag), "auc_ci": auc_ci_by_subject(y, flag, subj),
            "metrics": binary_metrics(y, flag), "flags": flag.tolist()}


def flag_all(y: np.ndarray) -> dict:
    """Sinalizar tudo: a base que um detector precisa superar."""
    return binary_metrics(y, np.ones_like(y))


def wins(r: dict, bar: float) -> bool:
    """Vence as regras: F1 acima delas e de sinalizar tudo, teto de falsos alarmes respeitado
    (sem supervisão) e AUC fora da dobra com IC 95% por voluntário acima de 0,5."""
    return bool(r["metrics"]["f1"] > bar and r["meets_fa"] and r["auc_ci"][0] > 0.5)


def select(exercise: str, cfg: dict, units: list[dict]) -> dict:
    """Validação cruzada de todas as famílias; a melhor de cada uma pela AUC fora da dobra."""
    fs = folds(exercise, cfg, units)
    y = np.concatenate([f["yte"] for f in fs])
    rules = cv_rules(exercise, cfg, fs)
    best: dict[str, dict] = {}
    for family, hs in HYPER.items():
        cands = [cv_model(family, h, fs) for h in hs]
        best[family] = max(cands, key=lambda c: (np.nan_to_num(c["auc"]), c["metrics"]["f1"]))
        b = best[family]
        print(f"  {family}: AUC {b['auc']:.2f} [{b['auc_ci'][0]:.2f}; {b['auc_ci'][1]:.2f}], "
              f"F1 {b['metrics']['f1']:.2f}, FA {b['metrics']['false_alarm']:.2f}", flush=True)
    base = flag_all(y)
    bar = max(rules["metrics"]["f1"], base["f1"])
    winners = [f for f, r in best.items() if wins(r, bar)]
    winner = max(winners, key=lambda f: best[f]["metrics"]["f1"]) if winners else None
    return {"exercise": exercise, "n_units": len(units), "subjects": [f["subject"] for f in fs],
            "n_incorrect": int(y.sum()), "n_correct": int((1 - y).sum()), "rules": rules,
            "flag_all": base, "models": best, "winner": winner}


# ---------------------------------------------------------------- erro nomeado (B3)


def error_classes(units: list[dict]) -> list[str]:
    """Tipos de erro com pelo menos 5 gravações incorretas fora do reservado."""
    from collections import Counter

    c = Counter(u["error"] for u in units if u["y"] == 1 and u["error"])
    return sorted(k for k, v in c.items() if v >= 5)


def cv_named_error(exercise: str, cfg: dict, units: list[dict]) -> dict:
    """Logística multiclasse sobre as incorretas: acerto do tipo de erro, um voluntário de fora."""
    classes = error_classes(units)
    inc = [u for u in units if u["y"] == 1 and u["error"] in classes]
    if len(classes) < 2:
        return {"classes": classes, "skipped": "menos de dois tipos de erro com 5+ gravações"}
    true, pred = [], []
    for f in folds(exercise, cfg, inc):
        ytr = np.array([classes.index(u["error"]) for u in f["train"]])
        if len(set(ytr.tolist())) < 2:
            continue
        m = fit("logistic", {"C": 1.0}, f["Xtr"], ytr)
        true += [u["error"] for u in f["test"]]
        pred += [classes[k] for k in m.predict(f["Xte"])]
    acc = float(np.mean([a == b for a, b in zip(true, pred, strict=True)])) if true else 0.0
    return {"classes": classes, "n": len(true), "accuracy": acc,
            "confusion": {a: {b: sum(1 for t, p in zip(true, pred, strict=True)
                                     if t == a and p == b) for b in classes} for a in classes}}


# ---------------------------------------------------------------- achados novos (B4)

NEW_FINDING_TARGETS = {
    "physio_incomplete": ("Incomplete", "Motionless"),
    "physio_trunk_insufficient": ("Error2",),   # alongamento lateral: tronco pouco inclinado
    "physio_rotation_low": ("Error2",),         # rotação de tronco: pouca rotação
}


def _recording_stats(people, fps: float, cfg: dict) -> dict:
    """Amplitude da articulação principal, inclinação máxima por repetição e faixa da razão
    ombros/quadris, calculadas como em `physio.py`."""
    from medwatch.video.geometry import trunk_angle

    s = angle_series(people, cfg["joints"], ek.MIN_CONF)[cfg["primary_joint"]]
    rom = float(np.nanmax(s) - np.nanmin(s)) if np.isfinite(s).any() else 0.0
    segs = segment_reps(s, fps, cfg["rep_min_prominence_deg"], cfg["rep_min_distance_s"])
    trunk = []
    for a, b in segs:
        ang = [trunk_angle(p.keypoints) for p in people[a:b + 1] if p is not None]
        if ang:
            trunk.append(max(ang))
    ratios = []
    for p in people:
        if p is None or any(p.kp_conf[i] < ek.MIN_CONF for i in (5, 6, 11, 12)):
            continue
        hip = abs(p.keypoints[11][0] - p.keypoints[12][0])
        if hip > 1e-6:
            ratios.append(abs(p.keypoints[5][0] - p.keypoints[6][0]) / hip)
    rr = float(np.percentile(ratios, 90) - np.percentile(ratios, 10)) if len(ratios) >= 5 else None
    return {"rom": rom, "trunk_reps": trunk, "ratio_range": rr}


def calibrate_new_findings(cfgs: dict) -> dict:
    """Limiares dos achados novos a partir das gravações corretas fora do reservado.

    `incomplete_rom_min_deg`: metade da amplitude mediana das corretas (todos os exercícios do
    Keraal); `trunk_min_expected_deg` (alongamento lateral): percentil 10 da inclinação máxima
    por repetição das corretas; `rotation_ratio_range_min` (rotação de tronco): percentil 10 da
    faixa da razão ombros/quadris das corretas. As corretas incertas entram aqui (no
    alongamento lateral só 4 corretas são certas). Devolve os limiares e quanto cada um
    sinaliza nas corretas e nos casos-alvo, ainda fora do reservado.
    """
    out = {}
    recs = [r for r in ek.load_recordings() if r["split"] in TRAIN_SPLITS]
    for name, code in KERAAL.items():
        cfg = cfgs[name]
        rows = []
        for r in recs:
            if r["exercise"] != code:
                continue
            _, people, fps = ek.load_poses(r["video"])
            st = _recording_stats(people, fps, cfg)
            rows.append({"evaluation": r["evaluation"],
                         "error": r["errors"][0]["type"] if r["errors"] else None, **st})
        cor = [x for x in rows if x["evaluation"] == "Correct"]
        thr = {"incomplete_rom_min_deg": round(0.5 * float(np.median([x["rom"] for x in cor])), 1)}
        if name == "lateral_stretch":
            vals = [v for x in cor for v in x["trunk_reps"]]
            thr["trunk_min_expected_deg"] = round(float(np.percentile(vals, 10)), 1)
        if name == "trunk_rotation":
            vals = [x["ratio_range"] for x in cor if x["ratio_range"] is not None]
            thr["rotation_ratio_range_min"] = round(float(np.percentile(vals, 10)), 2)

        def fires(x: dict, key: str, thr: dict = thr) -> bool:
            if key == "incomplete_rom_min_deg":
                return x["rom"] < thr[key]
            if key == "trunk_min_expected_deg":
                return any(v < thr[key] for v in x["trunk_reps"])
            return x["ratio_range"] is not None and x["ratio_range"] < thr[key]

        check = {}
        targets = {"incomplete_rom_min_deg": ("Incomplete", "Motionless"),
                   "trunk_min_expected_deg": ("Error2",), "rotation_ratio_range_min": ("Error2",)}
        for key in thr:
            tgt = [x for x in rows if x["evaluation"] in targets[key] or x["error"] in targets[key]]
            check[key] = {"corretas": [sum(fires(x, key) for x in cor), len(cor)],
                          "alvo": [sum(fires(x, key) for x in tgt), len(tgt)]}
        out[name] = {"thresholds": thr, "check": check}
    return out


# ---------------------------------------------------------------- principal


def eligible(units: list[dict]) -> tuple[bool, str]:
    """Há pelo menos `MIN_PER_CLASS` corretas e incorretas fora do reservado?"""
    tr = [u for u in units if u["split"] in TRAIN_SPLITS]
    n_inc, n_cor = sum(u["y"] for u in tr), sum(1 - u["y"] for u in tr)
    ok = n_inc >= MIN_PER_CLASS and n_cor >= MIN_PER_CLASS
    return ok, f"{n_cor} corretas e {n_inc} incorretas fora do reservado"


def save_model(exercise: str, cfg: dict, units: list[dict], sel: dict) -> Path:
    """Treina o vencedor em calibração + validação e salva em models/physio_<exercício>.joblib."""
    import joblib

    tr = [u for u in units if u["split"] in TRAIN_SPLITS]
    ref = reference_for(exercise, cfg, {u["subject"] for u in tr})
    fam = sel["winner"]
    best = sel["models"][fam]
    X, y = matrix(tr, cfg, ref), np.array([u["y"] for u in tr])
    model = fit(fam, best["hyper"], X, y)
    bundle = {"exercise": exercise, "family": fam, "hyper": best["hyper"], "model": model,
              "features": feature_names(cfg), "reference": ref, "threshold": 0.5}
    if fam in UNSUPERVISED:
        bundle["threshold"] = float(np.percentile(anomaly_score(fam, model, X[y == 0]),
                                                  best["percentile"]))
    path = ROOT / "models" / f"physio_{exercise}.joblib"
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, path)
    return path


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args(argv)
    cfgs = load_cfgs()
    state: dict = {"exercises": {}, "skipped": {}, "new_findings": calibrate_new_findings(cfgs)}
    for exercise in ("squat", "hide_face", "lateral_stretch", "trunk_rotation"):
        cfg = cfgs[exercise]
        units = units_for(exercise, cfg)
        ok, why = eligible(units)
        print(exercise, why, flush=True)
        if not ok:
            state["skipped"][exercise] = why
            continue
        tr = [u for u in units if u["split"] in TRAIN_SPLITS]
        sel = select(exercise, cfg, tr)
        sel["why"] = why
        if exercise != "squat":
            sel["named_error"] = cv_named_error(exercise, cfg, tr)
        state["exercises"][exercise] = sel
        if a.save and sel["winner"]:
            print("  salvo em", save_model(exercise, cfg, units, sel))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "physio_learned_cv.json").write_text(
        json.dumps(state, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    for ex, sel in state["exercises"].items():
        r = sel["rules"]["metrics"]
        print(f"{ex}: regras F1 {r['f1']:.2f}, sinalizar tudo F1 {sel['flag_all']['f1']:.2f}, "
              f"vencedor {sel['winner']}")


if __name__ == "__main__":
    main()
