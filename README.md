# MedWatch

Monitoramento multimodal de pacientes (Python + Azure AI) — Tech Challenge IADT Fase 4.

O MedWatch recebe **vídeo** (fisioterapia, leito, centro cirúrgico), **áudio** de consultas, **texto** (laudos),
**sinais vitais**, **prescrições** e **movimentação**. Cada modalidade gera *evidências* padronizadas; um motor de fusão
combina as evidências num **escore de risco (0–100)** por paciente e cria **alertas** (console, Teams, e-mail) que a equipe
confirma no dashboard.

- Arquitetura: [`docs/arquitetura.md`](docs/arquitetura.md)
- Relatório técnico: [`docs/relatorio-tecnico.md`](docs/relatorio-tecnico.md)
- Decisões: [`docs/DECISOES.md`](docs/DECISOES.md) · Plano: `PLANO_IMPLEMENTACAO.md`
- Vídeo de demonstração: **[link a ser inserido após a gravação]**

> **Aviso de uso:** projeto acadêmico. Não é dispositivo médico, não substitui o julgamento clínico e deve usar apenas
> dados sintéticos, encenados ou públicos. Nunca envie dados reais de pacientes (LGPD).

## Requisitos

| Item | Requisito |
|---|---|
| Docker | Docker Desktop 4.30+ (Windows/macOS) ou Docker Engine 26+ (Linux), com **Compose v2** (`docker compose`) |
| Windows | Backend WSL 2 ativado no Docker Desktop |
| Memória para o Docker | Mínimo 8 GB, recomendado 10–12 GB. No Windows, em `%UserProfile%\.wslconfig`: `[wsl2]` e `memory=10GB`, depois `wsl --shutdown` |
| Disco | ~15 GB (imagem ~5 GB com Torch CPU, modelos ~0,5 GB, banco e mídias) |
| Rede | PyPI, download.pytorch.org, Docker Hub, GitHub (pesos YOLO) e Hugging Face (modelo AST) no primeiro build/execução |
| GPU (opcional) | NVIDIA com driver recente (CUDA no WSL 2 / NVIDIA Container Toolkit); use `docker-compose.gpu.yml` |
| Azure (opcional) | Speech e Language reais. Sem chaves, use `USE_FAKE_AZURE=true` |

## Passo a passo (Docker)

Os comandos `docker` são iguais no PowerShell e no bash. Só a cópia do `.env` muda.

1. Criar o `.env` (preencha as chaves Azure ou defina `USE_FAKE_AZURE=true`):

   ```bash
   cp .env.example .env
   ```
   ```powershell
   Copy-Item .env.example .env
   ```
2. Construir a imagem (o primeiro build leva de 10 a 20 minutos):

   ```bash
   docker compose build
   ```
3. Subir tudo (o `models-init` baixa os modelos e termina; os workers de áudio e vídeo esperam por ele):

   ```bash
   docker compose up -d
   ```
4. Conferir o estado:

   ```bash
   docker compose ps
   ```
5. Criar os pacientes de demonstração:

   ```bash
   docker compose run --rm api python scripts/seed.py
   ```
6. Treinar o Isolation Forest e reiniciar o worker que o carrega:

   ```bash
   docker compose run --rm api python scripts/train_vitals_iforest.py
   docker compose restart worker-anomaly
   ```
7. Iniciar o simulador da demo:

   ```bash
   docker compose --profile demo up simulator
   ```
8. Abrir o dashboard em <http://localhost:8501> e a documentação da API em <http://localhost:8000/docs>.

Modo desenvolvimento (código montado e reload automático):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### Demonstração completa com mídias

Coloque as amostras em `data/samples/` (veja [`data/samples/README.md`](data/samples/README.md)) e rode:

```bash
python scripts/run_demo.py                       # inicia o simulador como subprocesso
python scripts/run_demo.py --external-simulator  # e, em outro terminal: docker compose --profile demo up simulator
```

## Instalação local (sem Docker)

```bash
python -m venv .venv && source .venv/bin/activate        # PowerShell: .venv\Scripts\Activate.ps1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[audio,video,reports,dashboard,dev]"
```

Fora do Docker use `localhost` para banco e Redis (como no `.env.example`); suba `db` e `redis` com o Compose.

## Testes

```bash
pytest -q && ruff check .                      # local
docker compose run --rm api pytest -q          # no container
```

Os testes usam fakeredis, `USE_FAKE_AZURE` e modelos falsos; alguns precisam do banco do Compose (`db`).

## Azure

Sem chaves, use `USE_FAKE_AZURE=true` (clientes falsos, offline). Para os serviços reais (após `az login`):

```bash
bash scripts/provision_azure.sh > azure.env   # cria Speech, Language e Storage; imprime as variáveis
cat azure.env >> .env                          # nunca commite o .env
python scripts/check_azure.py                  # verifica Speech, Language e Storage
```

Variáveis opcionais do script: `SUFFIX`, `RG` (padrão `rg-medwatch`), `LOC` (padrão `brazilsouth`).

- Se a criação do recurso Language pedir aceite de termos de IA responsável, crie-o uma vez pelo portal.
- Se algum recurso (ex.: entidades de saúde) não existir em `brazilsouth`, use `LOC=eastus` e somente dados sintéticos/públicos.
- SKUs gratuitas (`F0`) servem, com limites menores. Crie um alerta de orçamento no portal.
- Para testar a transcrição, grave `data/samples/hello_ptbr.wav` (fala curta em pt-BR).

## Comandos do dia a dia

| Objetivo | Comando |
|---|---|
| Logs de um serviço | `docker compose logs -f worker-fusion` |
| Shell na imagem | `docker compose run --rm api bash` |
| Consultar o banco | `docker compose exec db psql -U medwatch -d medwatch -c "select count(*) from evidence"` |
| Tamanho de um stream | `docker compose exec redis redis-cli XLEN evidence` |
| Mensagens pendentes | `docker compose exec redis redis-cli XPENDING evidence worker-fusion` |
| Parar (mantém dados) | `docker compose down` |
| Apagar banco, streams e caches | `docker compose down -v` |

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `Bind for 0.0.0.0:5432 failed: port is already allocated` | Postgres local usando a porta | Mude `DB_PORT` no `.env` (ex.: `5433`); vale também para `REDIS_PORT`, `API_PORT`, `DASHBOARD_PORT` |
| Tabelas não existem | `pgdata` já existia quando o `init.sql` mudou | `docker compose down -v` e subir de novo |
| `env file .env not found` | `.env` não foi criado | Passo 1 |
| Container encerrado com código 137 | Falta de memória (YOLO, AST, Torch) | Aumentar a memória do WSL 2/Docker Desktop; `AUDIO_DISABLE_EVENTS=true`; `VIDEO_TARGET_FPS=5` |
| `bash\r: No such file or directory` | Script com CRLF | `.gitattributes` do repositório e `git add --renormalize .` |
| `models-init` termina com código 1 | Sem acesso a GitHub ou Hugging Face | Verificar rede/proxy e `docker compose up models-init` de novo |
| `could not translate host name "db"` fora do Docker | `.env` com host do Docker | Fora do Docker use `localhost`, como no `.env.example` |
| `pyarrow`/openSMILE não importam | pyarrow 26 exige NumPy 2 | `pip install "pyarrow<18"` |
| Build muito lento ou enorme | `.dockerignore` ausente | Restaurar o `.dockerignore` |

## Estrutura de pastas

```
config/        limiares, pesos de fusão, exercícios, termos críticos (YAML)
db/            init.sql (TimescaleDB)
docs/          arquitetura, relatório técnico, decisões, resultados da avaliação
scripts/       seed, treino do Isolation Forest, avaliação, demo, Azure, modelos
src/medwatch/
  api/         FastAPI (pacientes, mídia, alertas, relatórios)
  simulator/   dados sintéticos e replay do MIMIC-IV Demo
  anomaly/     NEWS2, EWMA z-score, Isolation Forest, prescrições, movimentação
  audio/       Azure Speech, Azure Language, features acústicas, sons respiratórios
  text/        worker de documentos
  video/       YOLO, pose, DTW, fisioterapia, leito, cirurgia, vídeo anotado
  fusion/      motor de fusão e worker
  alerts/      canais (console, Teams, e-mail) e escalonamento
  reports/     relatórios HTML/PDF
  dashboard/   Streamlit
tests/         testes automatizados
data/, models/ amostras e modelos (fora do Git)
```
