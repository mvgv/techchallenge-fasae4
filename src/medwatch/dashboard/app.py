"""Dashboard Streamlit do MedWatch (`streamlit run src/medwatch/dashboard/app.py`).

Todas as chamadas à API passam pelo servidor do Streamlit (`ApiClient`);
vídeos, imagens e relatórios são baixados aqui e entregues como bytes.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from medwatch.config import load_yaml
from medwatch.dashboard.api_client import ApiClient

ACK_USER = "medico.demo"
DISCLAIMER = ("Sistema de apoio à decisão. Os alertas e relatórios são gerados automaticamente "
              "e requerem revisão de profissional de saúde.")
LEVELS = {  # nível -> (rótulo pt-BR, cor do chip no markdown do Streamlit)
    "critical": ("crítico", "red"),
    "warning": ("atenção", "orange"),
    "info": ("informativo", "blue"),
}
MODALITIES = {"vitals": "Sinais vitais", "prescription": "Prescrição", "movement": "Movimentação",
              "video": "Vídeo", "audio": "Áudio", "text": "Texto"}
MEDIA_STATUS = {"queued": "na fila", "processing": "processando", "done": "concluído",
                "failed": "falhou"}
KIND_LABELS = {"audio": "Áudio", "video": "Vídeo", "document": "Documento"}
MODE_LABELS = {"physio": "Fisioterapia", "bed": "Leito", "surgery": "Cirurgia"}
UPLOAD_TYPES = {"audio": ["wav", "mp3", "m4a", "ogg"], "video": ["mp4", "mov", "avi", "mkv"],
                "document": ["txt", "md"]}
ARCH_IMAGE = Path("docs/arquitetura.png")


# ---------------------------------------------------------------- funções puras

def level_chip(level: str | None) -> str:
    """Chip colorido (markdown do Streamlit) para o nível de risco."""
    if level not in LEVELS:
        return ":gray-background[normal]"
    label, color = LEVELS[level]
    return f":{color}-background[{label}]"


def risk_pct(risk: float | None) -> int:
    """Converte o risco (0–100) num inteiro limitado para `st.progress`."""
    if risk is None:
        return 0
    return int(max(0, min(100, round(float(risk)))))


def sort_patients(patients: list[dict]) -> list[dict]:
    """Ordena pacientes pelo risco atual, maior primeiro."""
    return sorted(patients, key=lambda p: (-(p.get("latest_risk") or 0), p["patient_id"]))


def _fold(text: str) -> str:
    """Minúsculas sem acentos, preservando o comprimento de cada caractere."""
    out = []
    for ch in text:
        base = unicodedata.normalize("NFD", ch)[0]
        out.append(base.lower() if len(base.lower()) == 1 else ch)
    return "".join(out)


def highlight_terms(text: str, terms: list[str]) -> str:
    """Coloca em **negrito** os termos críticos (sem diferenciar acento ou caixa)."""
    folded = _fold(text)
    spans: list[tuple[int, int]] = []
    for term in sorted({t for t in terms if t}, key=len, reverse=True):
        for m in re.finditer(rf"\b{re.escape(_fold(term))}\b", folded):
            if all(m.end() <= a or m.start() >= b for a, b in spans):
                spans.append((m.start(), m.end()))
    out, pos = [], 0
    for a, b in sorted(spans):
        out.append(text[pos:a])
        out.append(f"**{text[a:b]}**")
        pos = b
    out.append(text[pos:])
    return "".join(out)


def transcript_rows(transcript: dict, patient_speaker: str | None = None) -> list[dict]:
    """Junta segmentos, termos e sentimento por segmento para exibição.

    O sentimento só existe para as falas analisadas (as do paciente, ou todas se
    `patient_speaker` não foi informado), na mesma ordem dos segmentos.
    """
    segments = transcript.get("segments") or []
    analysis = transcript.get("analysis") or {}
    sentiments = list(analysis.get("sentiments") or [])
    terms_by_seg: dict[int, list[str]] = {}
    for t in analysis.get("terms") or []:
        terms_by_seg.setdefault(t.get("segment_index"), []).append(t["term"])
    rows = []
    s_iter = iter(sentiments)
    for i, seg in enumerate(segments):
        used = patient_speaker is None or seg.get("speaker") == patient_speaker
        sent = next(s_iter, None) if used else None
        rows.append({
            "offset_s": seg.get("offset_s", 0.0), "speaker": seg.get("speaker"),
            "text": highlight_terms(seg.get("text", ""), terms_by_seg.get(i, [])),
            "sentiment": sent.get("sentiment") if sent else None,
        })
    return rows


def evidence_table(evidence: list[dict], labels: dict) -> pd.DataFrame:
    """Tabela da linha do tempo de evidências (hora, modalidade, tipo, score, explicação)."""
    rows = [{
        "hora": _ts(e.get("ts_start")),
        "modalidade": MODALITIES.get(e.get("modality"), e.get("modality")),
        "tipo": labels.get(e.get("type"), e.get("type")),
        "score": round(float(e.get("score") or 0), 2),
        "explicação": e.get("explanation", ""),
    } for e in sorted(evidence, key=lambda e: e.get("ts_start") or "", reverse=True)]
    return pd.DataFrame(rows, columns=["hora", "modalidade", "tipo", "score", "explicação"])


def report_keys(resp: dict) -> tuple[str | None, str | None]:
    """Chaves (html, pdf) do relatório, aceitando os nomes da API e do plano."""
    return (resp.get("report_html") or resp.get("html_key"),
            resp.get("report_pdf") or resp.get("pdf_key"))


def mmss(seconds: float | None) -> str:
    """Formata segundos como mm:ss."""
    s = int(seconds or 0)
    return f"{s // 60:02d}:{s % 60:02d}"


def _ts(value) -> str:
    """Formata um timestamp ISO como 'dd/mm HH:MM:SS' (UTC)."""
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return dt.strftime("%d/%m %H:%M:%S")


# ---------------------------------------------------------------- gráficos

def vitals_figure(vitals: list[dict], evidence: list[dict], labels: dict):
    """Três subplots (FC, SpO₂, FR) com eixo x compartilhado e marcadores de evidências."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    series = (("hr", "FC (bpm)", "#d62728"), ("spo2", "SpO₂ (%)", "#1f77b4"),
              ("rr", "FR (irpm)", "#2ca02c"))
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        subplot_titles=[s[1] for s in series])
    xs = [v["ts"] for v in vitals]
    for row, (key, name, color) in enumerate(series, start=1):
        fig.add_trace(go.Scatter(x=xs, y=[v.get(key) for v in vitals], name=name,
                                 mode="lines", line={"color": color, "width": 1.5},
                                 connectgaps=False), row=row, col=1)
    for e in evidence:
        if e.get("modality") != "vitals" or not e.get("ts_start"):
            continue
        color = "#d62728" if e.get("severity") == "critical" else "#ff7f0e"
        for row in (1, 2, 3):
            fig.add_vline(x=e["ts_start"], line={"color": color, "width": 1, "dash": "dot"},
                          opacity=0.5, row=row, col=1)
    # um traço invisível para a legenda dos marcadores
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name="Evidência de vitais",
                             line={"color": "#ff7f0e", "dash": "dot"}), row=1, col=1)
    fig.update_layout(height=620, margin={"l": 40, "r": 20, "t": 40, "b": 30},
                      legend={"orientation": "h", "y": -0.08}, hovermode="x unified")
    return fig


def risk_figure(risks: list[dict], levels: dict):
    """Risco ao longo do tempo com linhas horizontais nos limiares de atenção e crítico."""
    import plotly.graph_objects as go

    fig = go.Figure(go.Scatter(x=[r["ts"] for r in risks], y=[r["risk_score"] for r in risks],
                               mode="lines", name="Risco", line={"color": "#7f3fbf"}))
    fig.add_hline(y=levels.get("warning", 40), line={"color": "#ff7f0e", "dash": "dash"},
                  annotation_text="atenção")
    fig.add_hline(y=levels.get("critical", 70), line={"color": "#d62728", "dash": "dash"},
                  annotation_text="crítico")
    fig.update_layout(height=280, yaxis={"range": [0, 100], "title": "risco"},
                      margin={"l": 40, "r": 20, "t": 20, "b": 30})
    return fig


# ---------------------------------------------------------------- recursos

@st.cache_resource
def get_api() -> ApiClient:
    """Cliente da API compartilhado entre sessões."""
    return ApiClient()


@st.cache_data
def fusion_cfg() -> dict:
    """Rótulos pt-BR e limiares de nível de `config/fusion.yaml`."""
    try:
        cfg = load_yaml("fusion")
    except FileNotFoundError:
        cfg = {}
    return {"labels": cfg.get("labels") or {},
            "levels": cfg.get("levels") or {"critical": 70, "warning": 40, "info": 20}}


@st.cache_data
def exercise_options() -> dict[str, str]:
    """Exercícios conhecidos: chave -> rótulo."""
    try:
        return {k: v.get("label", k) for k, v in load_yaml("exercises").items()}
    except FileNotFoundError:
        return {}


@st.cache_data
def camera_options() -> list[str]:
    """Câmeras (zonas) configuradas em `config/zones.yaml`."""
    try:
        return list(load_yaml("zones"))
    except FileNotFoundError:
        return []


@st.cache_data(ttl=600, show_spinner="Baixando arquivo...")
def fetch_file(key: str) -> bytes | None:
    """Baixa um arquivo do storage pela API (cache de 10 min)."""
    return get_api().get_file(key)


# ---------------------------------------------------------------- telas

def page_overview() -> None:
    """Painel geral: pacientes por risco e alertas abertos (atualiza a cada 5 s)."""
    st.title("Painel geral")
    st.caption("Atualiza automaticamente a cada 5 segundos.")
    overview_fragment()


@st.fragment(run_every=5)
def overview_fragment() -> None:
    """Fragmento do painel geral recarregado periodicamente."""
    api = get_api()
    patients = api.list_patients()
    alerts = api.list_alerts(status="open")
    if patients is None or alerts is None:
        return
    st.subheader("Pacientes")
    if not patients:
        st.info("Nenhum paciente cadastrado. Rode `scripts/seed.py` ou o simulador.")
    else:
        cols = st.columns([2, 1, 3, 1.3, 1])
        for c, h in zip(cols, ["Paciente", "Leito", "Risco", "Nível", "Alertas"], strict=True):
            c.markdown(f"**{h}**")
        for p in sort_patients(patients):
            c = st.columns([2, 1, 3, 1.3, 1])
            c[0].markdown(f"[{p['display_name']}](?page=Paciente&patient={p['patient_id']})  \n"
                          f"`{p['patient_id']}`")
            c[1].write(p.get("bed") or "—")
            pct = risk_pct(p.get("latest_risk"))
            c[2].progress(pct, text=f"{pct}")
            c[3].markdown(level_chip(p.get("latest_level")))
            c[4].write(str(p.get("open_alerts") or 0))

    st.subheader(f"Alertas abertos ({len(alerts)})")
    if not alerts:
        st.success("Nenhum alerta aberto.")
    names = {p["patient_id"]: p["display_name"] for p in patients or []}
    for a in alerts:
        render_alert(a, names.get(a["patient_id"], a["patient_id"]), api)


def render_alert(alert: dict, patient_name: str, api: ApiClient) -> None:
    """Cartão de alerta com nota opcional e botões Confirmar/Descartar."""
    aid = str(alert["alert_id"])
    with st.container(border=True):
        top = st.columns([4, 1])
        esc = " · escalonado" if alert.get("escalated") else ""
        top[0].markdown(f"{level_chip(alert.get('level'))} **{alert['title']}**  \n"
                        f"{patient_name} · risco {risk_pct(alert.get('risk_score'))} · "
                        f"{_ts(alert.get('event_ts'))}{esc}")
        st.write(alert.get("summary", ""))
        note = st.text_input("Nota (opcional)", key=f"note-{aid}")
        b = st.columns([1, 1, 4])
        decision = None
        if b[0].button("Confirmar", key=f"confirm-{aid}", type="primary"):
            decision = "confirmed"
        if b[1].button("Descartar", key=f"dismiss-{aid}"):
            decision = "dismissed"
        if decision:
            if api.ack_alert(aid, decision, user=ACK_USER, note=note) is not None:
                st.toast("Alerta confirmado." if decision == "confirmed" else "Alerta descartado.")
                st.rerun()


def select_patient(patients: list[dict], key: str) -> str | None:
    """Seletor de paciente pré-selecionado por `?patient=` na URL."""
    ids = [p["patient_id"] for p in patients]
    if not ids:
        st.info("Nenhum paciente cadastrado.")
        return None
    names = {p["patient_id"]: f"{p['display_name']} ({p['patient_id']})" for p in patients}
    wanted = st.query_params.get("patient")
    index = ids.index(wanted) if wanted in ids else 0
    pid = st.selectbox("Paciente", ids, index=index, format_func=names.get, key=key)
    if pid and st.query_params.get("patient") != pid:
        st.query_params["patient"] = pid
    return pid


def page_patient() -> None:
    """Tela do paciente: vitais, risco, evidências, mídias e relatório."""
    api = get_api()
    st.title("Paciente")
    patients = api.list_patients()
    if not patients:
        if patients is not None:
            st.info("Nenhum paciente cadastrado.")
        return
    pid = select_patient(sort_patients(patients), key="patient_select")
    if pid is None:
        return
    patient = next(p for p in patients if p["patient_id"] == pid)
    cfg = fusion_cfg()
    labels = cfg["labels"]

    m = st.columns(4)
    m[0].metric("Risco atual", risk_pct(patient.get("latest_risk")))
    m[1].markdown(f"**Nível**  \n{level_chip(patient.get('latest_level'))}")
    m[2].metric("Alertas abertos", patient.get("open_alerts") or 0)
    m[3].metric("Leito", patient.get("bed") or "—")

    vitals = api.get_vitals(pid) or []
    evidence = api.get_evidence(pid, limit=200) or []
    risks = api.get_risk(pid) or []

    st.subheader("Sinais vitais")
    if vitals:
        st.plotly_chart(vitals_figure(vitals, evidence, labels))
    else:
        st.info("Sem sinais vitais para este paciente.")

    st.subheader("Risco ao longo do tempo")
    if risks:
        st.plotly_chart(risk_figure(risks, cfg["levels"]))
    else:
        st.info("Sem histórico de risco.")

    st.subheader("Linha do tempo de evidências")
    if evidence:
        st.dataframe(evidence_table(evidence, labels), hide_index=True,
                     column_config={"score": st.column_config.ProgressColumn(
                         "score", min_value=0.0, max_value=1.0, format="%.2f")})
    else:
        st.info("Sem evidências registradas.")

    st.subheader("Mídias")
    media = api.list_media(pid) or []
    if not media:
        st.info("Nenhuma mídia enviada para este paciente.")
    for item in media:
        render_media(item, api)

    st.subheader("Relatório do paciente")
    if st.button("Gerar relatório do paciente"):
        with st.spinner("Gerando relatório..."):
            resp = api.patient_report(pid)
        if resp is not None:
            st.session_state[f"report-{pid}"] = report_keys(resp)
    html_key, pdf_key = st.session_state.get(f"report-{pid}", (None, None))
    if html_key:
        download_buttons(html_key, pdf_key, prefix=f"patient-{pid}")


def download_buttons(html_key: str | None, pdf_key: str | None, prefix: str) -> None:
    """Botões de download do relatório (HTML e, se houver, PDF)."""
    c = st.columns(2)
    if html_key and (data := fetch_file(html_key)) is not None:
        c[0].download_button("Baixar relatório (HTML)", data, file_name=Path(html_key).name,
                             mime="text/html", key=f"{prefix}-html")
    if pdf_key and (data := fetch_file(pdf_key)) is not None:
        c[1].download_button("Baixar relatório (PDF)", data, file_name=Path(pdf_key).name,
                             mime="application/pdf", key=f"{prefix}-pdf")
    elif html_key and not pdf_key:
        c[1].caption("PDF indisponível (WeasyPrint ausente); use o HTML.")


def render_media(item: dict, api: ApiClient) -> None:
    """Item da lista de mídias com status, transcrição (áudio) ou vídeo anotado."""
    mid = str(item["media_id"])
    kind = item.get("kind")
    status = MEDIA_STATUS.get(item.get("status"), item.get("status"))
    extra = MODE_LABELS.get(item.get("mode"), "") if kind == "video" else ""
    title = (f"{KIND_LABELS.get(kind, kind)} · {item.get('original_name') or mid} · "
             f"{_ts(item.get('recorded_at'))} · {status}{' · ' + extra if extra else ''}")
    with st.expander(title):
        if item.get("status") == "failed":
            st.error(item.get("error") or "Processamento falhou.")
            return
        if item.get("status") != "done":
            st.info("Ainda em processamento.")
            return
        if kind in ("audio", "document"):
            if not st.toggle("Mostrar transcrição e análise", key=f"show-{mid}"):
                return
            detail = api.get_media(mid) or {}
            transcript = detail.get("transcript")
            if transcript:
                render_transcript(transcript)
            elif (key := (detail.get("artifacts") or {}).get("analysis")):
                st.caption("Análise do documento")
                data = fetch_file(key)
                if data:
                    st.json(data.decode("utf-8", errors="replace"), expanded=False)
        elif kind == "video":
            artifacts = item.get("artifacts") or {}
            if artifacts.get("annotated") and st.toggle("Mostrar vídeo anotado", key=f"show-{mid}"):
                data = fetch_file(artifacts["annotated"])
                if data:
                    st.video(data, format="video/mp4")
            if artifacts.get("report_html"):
                download_buttons(artifacts.get("report_html"), artifacts.get("report_pdf"),
                                 prefix=f"media-{mid}")


def render_transcript(transcript: dict) -> None:
    """Transcrição com termos críticos em negrito e sentimento por segmento."""
    icons = {"negative": "🔴 negativo", "neutral": "⚪ neutro", "positive": "🟢 positivo",
             "mixed": "🟡 misto"}
    for row in transcript_rows(transcript):
        sent = icons.get(row["sentiment"], "") if row["sentiment"] else ""
        st.markdown(f"`{mmss(row['offset_s'])}` **{row['speaker'] or '?'}:** {row['text']}"
                    + (f"  \n<small>{sent}</small>" if sent else ""), unsafe_allow_html=True)
    terms = (transcript.get("analysis") or {}).get("terms") or []
    if terms:
        st.caption("Termos críticos: " + ", ".join(
            f"{t['term']} ({t.get('category', '')})" for t in terms))


def page_upload() -> None:
    """Formulário de envio de mídia com acompanhamento do processamento."""
    api = get_api()
    st.title("Enviar mídia")
    patients = api.list_patients()
    if not patients:
        if patients is not None:
            st.info("Cadastre um paciente antes de enviar mídia.")
        return
    pid = select_patient(patients, key="upload_patient")
    kind = st.radio("Tipo", list(KIND_LABELS), format_func=KIND_LABELS.get, horizontal=True)
    mode = exercise = camera = speaker = None
    if kind == "video":
        mode = st.selectbox("Modo", list(MODE_LABELS), format_func=MODE_LABELS.get)
        if mode == "physio":
            ex = exercise_options()
            exercise = st.selectbox("Exercício", list(ex), format_func=lambda k: ex.get(k, k))
        else:
            cams = ["(padrão)"] + [c for c in camera_options() if c.endswith(mode) or
                                   not c.startswith("default_")]
            cam = st.selectbox("Câmera (zonas)", cams)
            camera = None if cam == "(padrão)" else cam
    elif kind == "audio":
        speaker = st.text_input("Locutor do paciente (`patient_speaker`, ex.: Guest-2)",
                                help="Vazio = analisar todas as falas.") or None
    file = st.file_uploader("Arquivo", type=UPLOAD_TYPES[kind])
    if st.button("Enviar", type="primary", disabled=file is None or pid is None):
        with st.spinner("Enviando..."):
            resp = api.upload_media(filename=file.name, content=file.getvalue(), patient_id=pid,
                                    kind=kind, mode=mode, exercise=exercise, camera=camera,
                                    patient_speaker=speaker)
        if resp is not None:
            st.session_state["upload_media_id"] = resp["media_id"]
            st.session_state["upload_status"] = resp.get("status", "queued")
    if st.session_state.get("upload_media_id"):
        upload_status_fragment()


@st.fragment(run_every=3)
def upload_status_fragment() -> None:
    """Acompanha o status da mídia enviada a cada 3 s até `done`/`failed`."""
    mid = st.session_state.get("upload_media_id")
    if not mid:
        return
    status = st.session_state.get("upload_status")
    if status not in ("done", "failed"):
        media = get_api().get_media(mid)
        if media is not None:
            status = media.get("status")
            st.session_state["upload_status"] = status
            st.session_state["upload_error"] = media.get("error")
    st.markdown(f"**media_id:** `{mid}` · status: **{MEDIA_STATUS.get(status, status)}**")
    if status == "done":
        st.success("Processamento concluído. Veja os resultados na tela do paciente.")
    elif status == "failed":
        st.error(st.session_state.get("upload_error") or "Processamento falhou.")
    else:
        st.caption("Atualizando a cada 3 segundos...")


def page_about() -> None:
    """Descrição do sistema, diagrama e aviso de apoio à decisão."""
    st.title("Sobre o MedWatch")
    st.markdown(
        "O **MedWatch** monitora pacientes de forma multimodal: sinais vitais (NEWS2, "
        "z-score em streaming e Isolation Forest), prescrições, movimentação, áudio de "
        "consultas (Azure Speech e Azure AI Language, termos críticos, voz e sons "
        "respiratórios), documentos e vídeo (fisioterapia, leito e cirurgia com YOLO). "
        "As evidências de cada modalidade são fundidas num risco de 0 a 100; acima dos "
        "limiares, alertas vão para console, Teams, e-mail e este painel, onde o médico "
        "confirma ou descarta.")
    if ARCH_IMAGE.exists():
        st.image(str(ARCH_IMAGE), caption="Arquitetura")
    st.warning(DISCLAIMER)


PAGES = {"Painel geral": page_overview, "Paciente": page_patient,
         "Enviar mídia": page_upload, "Sobre": page_about}


def main() -> None:
    """Ponto de entrada do dashboard."""
    st.set_page_config(page_title="MedWatch", layout="wide")
    if "page" not in st.session_state:
        wanted = st.query_params.get("page")
        if wanted not in PAGES:
            wanted = "Paciente" if st.query_params.get("patient") else next(iter(PAGES))
        st.session_state["page"] = wanted
    page = st.sidebar.radio("Navegação", list(PAGES), key="page")
    if st.query_params.get("page") != page:
        st.query_params["page"] = page
    st.sidebar.caption(DISCLAIMER)
    PAGES[page]()


if __name__ == "__main__":
    main()
