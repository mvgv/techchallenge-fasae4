"""Renderização de relatórios (HTML e PDF) de sessões de vídeo e de pacientes."""
from __future__ import annotations

import base64
import io
import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from jinja2 import Environment, PackageLoader  # noqa: E402

from medwatch.storage import Storage  # noqa: E402

log = logging.getLogger(__name__)

DISCLAIMER = ("Relatório gerado automaticamente para apoio à decisão. "
              "Requer revisão de profissional de saúde.")

_env = Environment(loader=PackageLoader("medwatch", "reports/templates"), autoescape=True)


def render_html(template: str, context: dict) -> str:
    """Renderiza um template Jinja2 de reports/templates com o contexto dado."""
    return _env.get_template(template).render(disclaimer=DISCLAIMER, **context)


def html_to_pdf(html: str) -> bytes | None:
    """Converte HTML em PDF com WeasyPrint; devolve None se indisponível ou se falhar."""
    try:
        import weasyprint

        return weasyprint.HTML(string=html).write_pdf()
    except Exception:
        log.exception("Falha ao gerar PDF; o HTML continua disponível")
        return None


def data_uri(data: bytes, mime: str = "image/png") -> str:
    """Codifica bytes como data URI base64."""
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def _png(fig: Any) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    return data_uri(buf.getvalue())


def angles_chart(series: dict[str, list[float]], fps: float, reps: list) -> str | None:
    """Gráfico PNG (data URI) dos ângulos ao longo do tempo, com as repetições marcadas."""
    if not series or not any(series.values()):
        return None
    fig, ax = plt.subplots(figsize=(8, 3))
    for name, vals in series.items():
        ax.plot([i / fps for i in range(len(vals))], vals, label=name, linewidth=1.2)
    for n, r in enumerate(reps, 1):
        if isinstance(r, dict):
            a, b = r.get("start"), r.get("end")
        else:
            a, b = r[0], r[1]
        if a is None or b is None:
            continue
        ax.axvspan(a / fps, b / fps, alpha=0.08, color="tab:blue")
        ax.text(a / fps, ax.get_ylim()[1], str(n), va="top", fontsize=7)
    ax.set_xlabel("tempo (s)")
    ax.set_ylabel("ângulo (°)")
    ax.legend(fontsize=7)
    return _png(fig)


def vitals_chart(vitals: list[dict], evidence: list[dict]) -> str | None:
    """Gráfico PNG (data URI) de FC, SpO₂ e FR com as evidências de vitais marcadas."""
    if not vitals:
        return None
    fig, axes = plt.subplots(3, 1, figsize=(8, 5), sharex=True)
    ts = [v["ts"] for v in vitals]
    labels = ("FC (bpm)", "SpO₂ (%)", "FR (irpm)")
    for ax, key, label in zip(axes, ("hr", "spo2", "rr"), labels, strict=True):
        pts = [(t, v[key]) for t, v in zip(ts, vitals, strict=True) if v.get(key) is not None]
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], linewidth=1)
        ax.set_ylabel(label, fontsize=8)
    for e in evidence:
        if str(e.get("modality")) in ("vitals", "Modality.vitals"):
            for ax in axes:
                ax.axvline(e["ts_start"], color="tab:red", alpha=0.4, linewidth=1)
    fig.autofmt_xdate()
    return _png(fig)


def fmt_dt(v: Any) -> str:
    """Formata datetime em UTC legível; outros valores viram texto."""
    if isinstance(v, datetime):
        return v.astimezone(UTC).strftime("%d/%m/%Y %H:%M UTC")
    return str(v) if v else "—"


def build_session_report(media: dict, findings: dict, storage: Storage | None = None) -> dict:
    """Gera HTML/PDF da sessão de vídeo e devolve as chaves em artifacts/<media_id>/."""
    frames = []
    for f in findings.get("findings", []):
        key = f.get("frame_key")
        if key and storage is not None:
            try:
                data = b"".join(storage.open_stream(key))
                frames.append({"caption": f"{f['t_start']:.1f} s — {f['type']}",
                               "src": data_uri(data, "image/jpeg")})
            except Exception:
                log.warning("Frame-chave indisponível: %s", key)
    fps = findings.get("analysis_fps") or 1.0
    reps = findings.get("reps") or []
    ctx = {
        "media": media, "findings": findings, "recorded_at": fmt_dt(media.get("recorded_at")),
        "duration": (findings.get("video") or {}).get("duration"),
        "n_reps": len(reps),
        "by_type": dict(Counter(f["type"] for f in findings.get("findings", []))),
        "frames": frames,
        "chart": angles_chart(findings.get("series") or {}, fps, reps),
    }
    html = render_html("video_report.html.j2", ctx)
    out: dict[str, str] = {}
    if storage is None:
        return out
    prefix = f"artifacts/{media['media_id']}"
    out["report_html"] = f"{prefix}/report.html"
    storage.put_bytes(html.encode("utf-8"), out["report_html"])
    pdf = html_to_pdf(html)
    if pdf:
        out["report_pdf"] = f"{prefix}/report.pdf"
        storage.put_bytes(pdf, out["report_pdf"])
    return out


def build_patient_report(patient: dict, risk: dict | None, alerts: list[dict],
                         evidence: list[dict], vitals: list[dict]) -> str:
    """Renderiza o HTML do relatório do paciente."""
    by_mod: dict[str, list[dict]] = {}
    for e in evidence:
        by_mod.setdefault(str(e["modality"]), []).append(e)
    ctx = {"patient": patient, "risk": risk, "alerts": alerts, "by_modality": by_mod,
           "chart": vitals_chart(vitals, evidence), "generated_at": fmt_dt(datetime.now(UTC)),
           "fmt": fmt_dt}
    return render_html("patient_report.html.j2", ctx)
