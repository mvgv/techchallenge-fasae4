# MedWatch

Monitoramento multimodal de pacientes (Python + Azure AI) — Tech Challenge IADT Fase 4.

## Instalação local

```bash
python -m venv .venv && source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[audio,video,reports,dashboard,dev]"
pytest -q && ruff check .
```

Documentação completa: em construção (T33). Plano: `PLANO_IMPLEMENTACAO.md`.
