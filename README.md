# MedWatch

Monitoramento multimodal de pacientes (Python + Azure AI) — Tech Challenge IADT Fase 4.

## Instalação local

```bash
python -m venv .venv && source .venv/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[audio,video,reports,dashboard,dev]"
pytest -q && ruff check .
```

## Azure

Sem chaves, use `USE_FAKE_AZURE=true` no `.env` (clientes falsos, offline).

Para usar os serviços reais (após `az login`):

```bash
bash scripts/provision_azure.sh > azure.env   # cria Speech, Language e Storage; imprime as variáveis
cat azure.env >> .env                          # nunca commite o .env
python scripts/check_azure.py                  # verifica Speech, Language e Storage
```

Variáveis opcionais do script: `SUFFIX`, `RG` (padrão `rg-medwatch`), `LOC` (padrão `brazilsouth`).

Notas:

- Se a criação do recurso Language falhar pedindo aceite de termos de IA responsável, crie-o uma vez pelo portal.
- Se algum recurso (ex.: entidades de saúde) não estiver disponível em `brazilsouth`, use `LOC=eastus` e somente dados sintéticos/públicos.
- SKUs gratuitas (`F0`) podem ser usadas se disponíveis, com limites menores.
- Crie um alerta de orçamento no portal da Azure.
- Para testar a transcrição, grave `data/samples/hello_ptbr.wav` (fala curta em pt-BR).

Documentação completa: em construção (T33). Plano: `PLANO_IMPLEMENTACAO.md`.
