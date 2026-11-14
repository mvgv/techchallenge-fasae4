"""Fisioterapia com aprendizado (T41, passo B5): medição única no reservado.

Uso: python scripts/evaluate_physio_learned.py
Pré-requisito: scripts/train_physio_model.py (grava docs/resultados/physio_learned_cv.json).

Para cada exercício com dados (agachamento do REHAB24-6 e "esconder o rosto" do Keraal), treina
em calibração + validação a melhor configuração de cada família escolhida na validação cruzada
e mede uma vez no reservado, ao lado das regras da T39/T40 (mesma referência e limiares) e das
regras com os achados novos da T41. Nos exercícios sem dados para aprender (alongamento lateral
e rotação de tronco) mede só as regras, com e sem os achados novos. Grava
docs/resultados/physio_learned.md (o JSON com linhas por gravação fica fora do Git).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_keraal as ek  # noqa: E402
import train_physio_model as tp  # noqa: E402

OUT = ROOT / "docs" / "resultados"
NEW_KEYS = ("incomplete_rom_min_deg", "trunk_min_expected_deg", "rotation_ratio_range_min")
NAMES = {"squat": "Agachamento (REHAB24-6)", "hide_face": "Esconder o rosto (Keraal CTK)",
         "lateral_stretch": "Alongamento lateral (Keraal ELK)",
         "trunk_rotation": "Rotação de tronco (Keraal RTK)"}
FAMILY = {"regras": "Regras (T39/T40)", "regras_novas": "Regras + achados da T41",
          "sinalizar_tudo": "Sinalizar tudo (base)", "mahalanobis": "Mahalanobis (só corretas)",
          "iforest": "IsolationForest (só corretas)", "logistic": "Regressão logística",
          "tree": "Árvore rasa", "gbm": "GradientBoosting pequeno"}


def without_new(cfg: dict, exercise: str | None = None) -> dict:
    """Configuração das regras como na T39/T40 (sem os achados novos)."""
    base = {**cfg, **(tp.t40_params(exercise) if exercise else {})}
    return {k: v for k, v in base.items() if k not in NEW_KEYS}


def with_new(cfg: dict, exercise: str) -> dict:
    """Regras da T39/T40 mais os achados novos da T41."""
    return {**without_new(cfg, exercise), **{k: cfg[k] for k in NEW_KEYS if k in cfg}}


def t40_reference(exercise: str, cfg: dict) -> dict:
    """Referência da T39/T40: corretas só da calibração."""
    if exercise == "squat":
        path = ROOT / "data" / "references" / "squat.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return tp.squat_reference(cfg, set(tp.ep.load_splits()["rehab24"]["calibracao"]))
    return ek.build_reference(ek.load_recordings(), tp.KERAAL[exercise], cfg)


def scored(y: np.ndarray, s: np.ndarray, flag: np.ndarray, subjects: list[str]) -> dict:
    """Métricas binárias, AUC e IC da AUC por bootstrap de voluntário."""
    return {"metrics": tp.binary_metrics(y, flag), "auc": tp.auc(y, s),
            "auc_ci": tp.auc_ci_by_subject(y, s, subjects)}


def measure(exercise: str, cfg: dict, units: list[dict], cv: dict | None) -> dict:
    """Regras, regras + achados novos e (se houver CV) cada família, no reservado."""
    tr = [u for u in units if u["split"] in tp.TRAIN_SPLITS]
    te = [u for u in units if u["split"] == "reservado"]
    y = np.array([u["y"] for u in te])
    subj = [u["subject"] for u in te]
    ref40 = t40_reference(exercise, cfg)
    res: dict = {"n_incorrect": int(y.sum()), "n_correct": int((1 - y).sum()),
                 "subjects": sorted(set(subj)), "rows": {}}
    for key, c in (("regras", without_new(cfg, exercise)), ("regras_novas", with_new(cfg, exercise))):
        flag = tp.rule_flags(exercise, c, te, ref40)
        res["rows"][key] = scored(y, flag.astype(float), flag, subj)
    res["rows"]["sinalizar_tudo"] = scored(y, np.ones(len(y)), np.ones(len(y), int), subj)
    if cv is None:
        return res
    ref = tp.reference_for(exercise, cfg, {u["subject"] for u in tr})
    Xtr, ytr = tp.matrix(tr, cfg, ref), np.array([u["y"] for u in tr])
    Xte = tp.matrix(te, cfg, ref)
    for fam, best in cv["models"].items():
        m = tp.fit(fam, best["hyper"], Xtr, ytr)
        s = tp.anomaly_score(fam, m, Xte)
        if fam in tp.UNSUPERVISED:
            cut = np.percentile(tp.anomaly_score(fam, m, Xtr[ytr == 0]), best["percentile"])
        else:
            cut = 0.5
        res["rows"][fam] = scored(y, s, (s >= cut).astype(int), subj)
    return res


def named_error(exercise: str, cfg: dict, units: list[dict]) -> dict:
    """Erro nomeado no reservado: logística multiclasse × mapa de regras da T40."""
    tr = [u for u in units if u["split"] in tp.TRAIN_SPLITS]
    classes = tp.error_classes(tr)
    te = [u for u in units if u["split"] == "reservado" and u["y"] == 1 and u["error"]]
    out: dict = {"classes": classes, "n": len(te)}
    if len(classes) < 2 or not te:
        return out
    inc = [u for u in tr if u["y"] == 1 and u["error"] in classes]
    ref = tp.reference_for(exercise, cfg, {u["subject"] for u in inc})
    m = tp.fit("logistic", {"C": 1.0}, tp.matrix(inc, cfg, ref),
               np.array([classes.index(u["error"]) for u in inc]))
    pred = [classes[k] for k in m.predict(tp.matrix(te, cfg, ref))]
    true = [u["error"] for u in te]
    rows = sorted(set(true) | set(classes))
    out["confusion"] = {a: {b: sum(1 for t, p in zip(true, pred, strict=True) if t == a and p == b)
                            for b in classes} for a in rows}
    out["accuracy"] = float(np.mean([t == p for t, p in zip(true, pred, strict=True)]))
    # regras: o mapa `errors` da T40 nomeia o erro se o achado esperado aparece
    ref40 = t40_reference(exercise, cfg)
    cache: dict = {}
    rules_cfg = without_new(cfg, exercise)
    judged = [ek.judge(u["rec"], ek.analyze(u["rec"], rules_cfg, ref40, cache), rules_cfg)
              for u in te]
    out["rules_named"] = [sum(bool(j["named"]) for j in judged), len(judged)]
    out["rules_finding"] = {e: cfg.get("errors", {}).get(e) for e in rows}
    return out


def new_findings_reserved(exercise: str, cfg: dict) -> dict:
    """Quanto cada achado novo dispara no reservado: corretas, casos-alvo e incompletas."""
    code = tp.KERAAL[exercise]
    ref40 = t40_reference(exercise, cfg)
    cache: dict = {}
    out: dict = {}
    recs = [r for r in ek.load_recordings() if r["exercise"] == code
            and r["split"] == "reservado"]
    for r in recs:
        if r["uncertain"] and r["evaluation"] in ("Correct", "Incorrect"):
            continue
        types = {f["type"] for f in ek.analyze(r, with_new(cfg, exercise), ref40, cache)}
        err = r["errors"][0]["type"] if r["errors"] else None
        group = ("corretas" if r["evaluation"] == "Correct" else
                 "incompletas" if r["evaluation"] in ("Incomplete", "Motionless") else
                 f"incorretas {err}")
        configured = {"physio_incomplete": "incomplete_rom_min_deg",
                      "physio_rotation_low": "rotation_ratio_range_min",
                      "physio_trunk_insufficient": "trunk_min_expected_deg"}
        for t in (t for t, k in configured.items() if k in cfg):
            c = out.setdefault(t, {}).setdefault(group, [0, 0])
            c[0] += t in types
            c[1] += 1
    return out


# ---------------------------------------------------------------- relatório


def _row(name: str, r: dict) -> str:
    m = r["metrics"]
    a = r.get("auc", float("nan"))
    ci = r.get("auc_ci", (float("nan"), float("nan")))
    auc_txt = "—" if np.isnan(a) else f"{a:.2f} [{ci[0]:.2f}; {ci[1]:.2f}]"
    return (f"| {name} | {auc_txt} | {m['precision']:.2f} | {m['recall']:.2f} "
            f"[{m['recall_ci'][0]:.2f}; {m['recall_ci'][1]:.2f}] | {m['false_alarm']:.2f} "
            f"[{m['false_alarm_ci'][0]:.2f}; {m['false_alarm_ci'][1]:.2f}] | {m['f1']:.2f} |")


HEAD = ("| Método | AUC [IC 95% por voluntário] | Precisão | Recall [IC 95%] | Falsos alarmes "
        "[IC 95%] | F1 |\n|---|---|---|---|---|---|")


def render(cv_state: dict, res: dict) -> str:
    """Markdown de docs/resultados/physio_learned.md."""
    L = [
        "# Fisioterapia com aprendizado (T41, parte B)", "",
        "Duas técnicas clássicas de detecção de anomalias, comparadas com as regras fixas da "
        "T39/T40 sobre as mesmas medidas da pose 2D (`physio_features.py`: amplitude e DTW por "
        "articulação, assimetria, tronco, razão ombros/quadris, cotovelo, duração, curva da "
        "articulação principal):", "",
        "- **sem supervisão**: aprende só o movimento correto e mede a distância até ele "
        "(Mahalanobis com covariância encolhida de Ledoit-Wolf; IsolationForest). O limiar é o "
        "percentil das corretas de treino que, na validação cruzada, dá no máximo 20% de falsos "
        "alarmes;",
        "- **supervisionado**: aprende a fronteira entre corretas e incorretas (regressão "
        "logística com padronização e classes balanceadas; árvore rasa; GradientBoosting "
        "pequeno). Limiar 0,5.", "",
        "Seleção por **validação cruzada deixando um voluntário de fora**, em calibração + "
        "validação (com 6 a 8 voluntários, uma validação de 2 pessoas seria ruído); a referência "
        "do DTW é refeita em cada dobra sem o voluntário de fora. Um modelo só **vence** as "
        "regras se, na validação cruzada, tiver F1 acima das regras e de sinalizar tudo, "
        "respeitar o teto de falsos alarmes (sem supervisão) e tiver AUC com IC 95% por "
        "voluntário acima de 0,5. O reservado foi medido uma única vez, depois da escolha.", ""]
    for ex, sel in cv_state["exercises"].items():
        L += [f"## {NAMES[ex]}", "",
              f"Calibração + validação: {sel['why'].replace(' fora do reservado', '')}, "
              f"{len(sel['subjects'])} voluntários.", "",
              "### Validação cruzada (um voluntário de fora)", "", HEAD,
              _row(FAMILY["regras"], sel["rules"]),
              _row(FAMILY["sinalizar_tudo"], {"metrics": sel["flag_all"]})]
        for fam, r in sel["models"].items():
            extra = f" (p{r['percentile']})" if "percentile" in r else ""
            L.append(_row(FAMILY[fam] + extra, r))
        w = sel["winner"]
        L += ["", f"Vencedor na validação cruzada: **{FAMILY[w] if w else 'nenhum'}**.", "",
              f"### Reservado (voluntários {', '.join(res[ex]['subjects'])}; "
              f"{res[ex]['n_incorrect']} incorretas, {res[ex]['n_correct']} corretas)", "", HEAD]
        for key, r in res[ex]["rows"].items():
            L.append(_row(FAMILY[key], r))
        ne = res[ex].get("named")
        if ne and ne.get("confusion"):
            cls = ne["classes"]
            L += ["", "### Erro nomeado no reservado", "",
                  f"Regressão logística multiclasse treinada com as incorretas de "
                  f"{' e '.join(cls)} fora do reservado (na validação cruzada: acerto "
                  f"{sel['named_error']['accuracy']:.2f} em {sel['named_error']['n']}). Linhas: "
                  "erro anotado; colunas: erro previsto.", "",
                  "| Anotado | " + " | ".join(cls) + " | Achado da regra (T40) |",
                  "|---|" + "---|" * (len(cls) + 1)]
            for a, row in ne["confusion"].items():
                L.append(f"| {a} | " + " | ".join(str(row[b]) for b in cls) +
                         f" | `{ne['rules_finding'].get(a)}` |")
            L += ["", f"Acerto do modelo: {ne['accuracy']:.2f} ({ne['n']} gravações). As regras "
                  f"\"nomeiam\" o erro em {ne['rules_named'][0]} de {ne['rules_named'][1]}, mas "
                  "usam o mesmo achado (`physio_low_rom`) para os três erros: não distinguem um "
                  "do outro."]
        L.append("")
    for ex, why in cv_state["skipped"].items():
        L += [f"## {NAMES[ex]}", "",
              f"Sem dados para aprender: {why} (o mínimo é {tp.MIN_PER_CLASS} de cada). Só as "
              "regras foram medidas.", "", HEAD]
        for key, r in res[ex]["rows"].items():
            L.append(_row(FAMILY[key], r))
        L.append("")
    L += ["## Achados novos (passo B4)", "",
          "Limiares tirados das gravações corretas fora do reservado "
          "(`train_physio_model.calibrate_new_findings`); a conferência abaixo também é fora do "
          "reservado.", "", "| Exercício | Limiar | Valor | Corretas sinalizadas | Casos-alvo "
          "sinalizados |", "|---|---|---|---|---|"]
    targets = {"incomplete_rom_min_deg": "incompletas/paradas",
               "trunk_min_expected_deg": "Error2 (tronco pouco inclinado)",
               "rotation_ratio_range_min": "Error2 (pouca rotação)"}
    for ex, d in cv_state["new_findings"].items():
        for k, v in d["thresholds"].items():
            c = d["check"][k]
            L.append(f"| {NAMES[ex]} | `{k}` | {v} | {c['corretas'][0]}/{c['corretas'][1]} | "
                     f"{c['alvo'][0]}/{c['alvo'][1]} ({targets[k]}) |")
    L += ["", "No reservado (gravações sem incerteza; incompletas incluídas):", "",
          "| Exercício | Achado | Grupo | Disparou |", "|---|---|---|---|"]
    for ex in tp.KERAAL:
        for t, groups in res[ex].get("new_findings", {}).items():
            for g, (k, n) in sorted(groups.items()):
                L.append(f"| {NAMES[ex]} | `{t}` | {g} | {k}/{n} |")
    L.append("")
    L += leitura(cv_state, res)
    return "\n".join(L)


def leitura(cv_state: dict, res: dict) -> list[str]:
    """Resumo em texto, com os números do reservado."""
    out = ["## Leitura", ""]
    for ex, sel in cv_state["exercises"].items():
        rr = res[ex]["rows"]
        r0 = rr["regras"]
        w = sel["winner"]
        if w:
            rw = rr[w]
            out.append(
                f"- **{NAMES[ex]}:** a {FAMILY[w].lower()} venceu as regras na validação cruzada "
                f"(AUC {sel['models'][w]['auc']:.2f}) e, no reservado, ficou com AUC "
                f"{rw['auc']:.2f} (IC {rw['auc_ci'][0]:.2f}–{rw['auc_ci'][1]:.2f}), recall "
                f"{rw['metrics']['recall']:.2f}, precisão {rw['metrics']['precision']:.2f} e "
                f"{rw['metrics']['false_alarm']:.0%} de falsos alarmes, contra recall "
                f"{r0['metrics']['recall']:.2f}, precisão {r0['metrics']['precision']:.2f} e "
                f"{r0['metrics']['false_alarm']:.0%} das regras. Foi integrada (passo B6).")
        else:
            best_res = max((k for k in rr if k in sel["models"]),
                           key=lambda k: rr[k]["metrics"]["f1"])
            out.append(
                f"- **{NAMES[ex]}:** nenhum modelo venceu na validação cruzada, então o sistema "
                f"fica com as regras. No reservado a {FAMILY[best_res].lower()} pareceu melhor "
                f"(F1 {rr[best_res]['metrics']['f1']:.2f} contra {r0['metrics']['f1']:.2f}), mas "
                f"o reservado não escolhe modelo: com {len(res[ex]['subjects'])} voluntários, "
                "essa diferença não autoriza trocar.")
        ne = res[ex].get("named")
        if ne and ne.get("confusion"):
            out.append(f"- **Erro nomeado ({NAMES[ex]}):** acerto {ne['accuracy']:.2f} no "
                       f"reservado e {sel['named_error']['accuracy']:.2f} na validação cruzada, "
                       "perto do acaso: as medidas 2D não distinguem os tipos de erro.")
    out += [f"- **{NAMES[ex]}:** {why}; sem modelo." for ex, why in cv_state["skipped"].items()]
    out += ["- **Achados novos:** separam pouco. O mais útil é o tronco insuficiente no "
            "alongamento lateral; o \"incompleto\" pega gravações paradas, mas não as "
            "incompletas da rotação de tronco, em que o ombro se move normalmente.",
            "- Os intervalos são largos (3 a 4 voluntários no reservado). A seleção por "
            "validação cruzada usa os mesmos dados para escolher hiperparâmetros e estimar o "
            "desempenho, então os números da validação são otimistas; o do reservado não é.", ""]
    return out


def main() -> None:
    """Ponto de entrada da linha de comando."""
    cv_path = OUT / "physio_learned_cv.json"
    if not cv_path.exists():
        raise SystemExit("rode antes scripts/train_physio_model.py")
    cv_state = json.loads(cv_path.read_text(encoding="utf-8"))
    cfgs = tp.load_cfgs()
    res = {}
    for ex in ("squat", *tp.KERAAL):
        cfg = cfgs[ex]
        units = tp.units_for(ex, cfg)
        res[ex] = measure(ex, cfg, units, cv_state["exercises"].get(ex))
        if ex in cv_state["exercises"] and ex != "squat":
            res[ex]["named"] = named_error(ex, cfg, units)
        if ex in tp.KERAAL:
            res[ex]["new_findings"] = new_findings_reserved(ex, cfg)
        print(ex, {k: round(v["metrics"]["f1"], 2) for k, v in res[ex]["rows"].items()},
              flush=True)
    (OUT / "physio_learned.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    (OUT / "physio_learned.md").write_text(render(cv_state, res), encoding="utf-8")
    print("relatório em", OUT / "physio_learned.md")


if __name__ == "__main__":
    main()
