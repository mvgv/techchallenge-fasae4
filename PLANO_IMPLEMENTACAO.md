# MedWatch — Plano de Implementação (Stack A: Python + Azure AI)

Tech Challenge IADT · Fase 4 · Monitoramento multimodal de pacientes

Este documento é a especificação executável do projeto. Ele foi escrito para ser seguido por um agente de código (ou por um desenvolvedor) **tarefa por tarefa, na ordem**, sem precisar tomar decisões de arquitetura. Tudo que não estiver aqui deve seguir a opção mais simples que satisfaça os critérios de aceite.

---

## Sumário

0. [Regras para o agente](#0-regras-para-o-agente)
   - [0.1 Continuidade entre sessões](#01-continuidade-entre-sessões)
   - [0.2 Modelo e escalonamento](#02-modelo-e-escalonamento)
1. [Visão geral e decisões fixas](#1-visão-geral-e-decisões-fixas)
2. [Estrutura do repositório](#2-estrutura-do-repositório)
3. [Contratos compartilhados](#3-contratos-compartilhados)
4. [Catálogo de evidências](#4-catálogo-de-evidências)
5. [Tarefas](#5-tarefas)
   - Fase 0 — Fundação: T00–T05
   - Fase 1 — Ingestão e simulação: T06–T07
   - Fase 2 — Anomalias em séries: T08–T13
   - Fase 3 — Áudio e texto: T14–T18
   - Fase 4 — Vídeo: T19–T24
   - Fase 5 — Fusão e alertas: T25–T27
   - Fase 6 — Saídas: T28–T30
   - Fase 7 — Avaliação e entrega: T31–T34
   - Fase 8 — Integração, dados reais e gravação: T35–T38
6. [Passos manuais (somente humanos)](#6-passos-manuais-somente-humanos)
7. [Roteiro da demonstração](#7-roteiro-da-demonstração)
8. [Checklist final de aceite](#8-checklist-final-de-aceite)
9. [Ambiente Docker (referência completa)](#9-ambiente-docker-referência-completa)

---

## 0. Regras para o agente

0. **Toda sessão começa pelo protocolo de início e termina pelo de encerramento** da seção 0.1. A sessão pode acabar a qualquer momento (orçamento diário, erro, queda); o que não estiver em commit e no `PROGRESSO.md` é considerado perdido.
1. **Execute as tarefas na ordem numérica.** Cada tarefa lista suas dependências. Não comece uma tarefa sem que as dependências passem nos critérios de aceite.
2. **Não altere contratos** da seção 3 (modelos Pydantic, nomes de streams, esquema do banco, variáveis de ambiente) sem registrar a mudança em `docs/DECISOES.md` e atualizar todos os usos.
3. **Commits frequentes com progresso registrado.** Commit `T<NN> [wip]: <passo>` a cada passo concluído; commit final `T<NN>: <título da tarefa>` só com `pytest -q` e `ruff check .` passando. Todo commit inclui o `PROGRESSO.md` atualizado. Faça push depois de cada commit (detalhes na seção 0.1).
4. **Nunca commite segredos.** Chaves ficam somente em `.env` (que está no `.gitignore`). Use `.env.example` com valores vazios.
5. **Tudo deve funcionar sem Azure** quando `USE_FAKE_AZURE=true`. Os testes automatizados sempre rodam com clientes falsos. Testes que chamam a Azure de verdade levam o marcador `@pytest.mark.azure` e são pulados se as chaves não existirem.
6. **Timestamps sempre em UTC e com timezone** (`datetime.now(timezone.utc)`). Nunca use `datetime.utcnow()`.
7. **Use o tempo do evento, não o relógio da parede**, em toda lógica de janela, cooldown e decaimento (o simulador acelera o tempo).
8. **Limiares ficam em YAML** dentro de `config/`, nunca fixos no código. O código lê os valores via `medwatch.config.load_yaml(nome)`.
9. Se algo neste documento estiver ambíguo, escolha a solução mais simples, implemente, e registre a escolha em `docs/DECISOES.md` (uma linha por decisão).
10. Passos marcados como **[HUMANO]** não podem ser feitos pelo agente (login na Azure, Teams, gravação de áudio). Deixe o código pronto, registre o bloqueio no `PROGRESSO.md` (seção 0.1) e siga em frente.
11. Não adicione dependências fora da lista da T01 sem registrar em `docs/DECISOES.md`.
12. Funções públicas devem ter type hints e docstring de uma linha. Não é necessário documentação extensa.

### 0.1 Continuidade entre sessões

O trabalho será feito em várias sessões, possivelmente interrompidas sem aviso. Estas regras garantem que uma sessão nova, sem memória das anteriores, retome exatamente de onde a última parou, perdendo no máximo um passo.

#### Arquivos de estado

| Arquivo | Papel |
|---|---|
| `CLAUDE.md` | Ponto de entrada, lido automaticamente pelo agente ao abrir o repositório. Curto: aponta para o `PROGRESSO.md` e para este plano. |
| `PROGRESSO.md` | **Fonte da verdade do andamento:** status de cada tarefa, tarefa em andamento com o próximo passo exato, bloqueios que dependem de pessoas, estado fora do Git e histórico de sessões. |
| `docs/DECISOES.md` | Decisões tomadas pelo agente onde este plano era ambíguo. |
| `git log` | Histórico detalhado. Mensagens `T<NN> [wip]: ...` e `T<NN>: ...`. |

Valores de status no `PROGRESSO.md`: `pendente`, `em andamento`, `concluída`, `bloqueada` (a tarefa inteira depende de uma pessoa), `pulada` (só para opcionais da T34).

#### Protocolo de início de sessão (sempre, nesta ordem)

1. Ler `CLAUDE.md` e `PROGRESSO.md`. Neste plano, ler apenas a seção 0, a tarefa atual e as seções que ela referencia. Não releia o plano inteiro.
2. Verificar o Git:
   ```bash
   git status -sb
   git log --oneline -10
   git fetch && git status -sb
   ```
   Se a branch local estiver atrás da remota, `git pull --ff-only`. Se o `git` não estiver no PATH (Windows), use `"C:\Program Files\Git\cmd\git.exe"`.
3. Se houver mudanças sem commit, compare com a seção "Tarefa em andamento" do `PROGRESSO.md`:
   - **correspondem ao próximo passo registrado e parecem completas:** rodar os testes do módulo e fazer o commit `[wip]`;
   - **são parciais, mas dá para entender o que faltava:** completar o passo e fazer o commit;
   - **não são reconhecíveis ou estão quebradas:** `git stash push -u -m "sessao-anterior-<AAAA-MM-DD>"`, anotar o nome do stash em "Observações" e refazer o passo.
   Nunca use `git reset --hard`, `git checkout -- .` ou `git clean` para descartar trabalho sem antes guardá-lo num stash.
4. Rodar `pytest -q` (e subir os serviços Docker que a tarefa usa, conforme a tabela 9.6). Se algo de uma tarefa já concluída falhar, corrigir isso é o primeiro passo da sessão.
5. Revisar a tabela de bloqueios: o humano pode ter resolvido algum (`.env` preenchido, amostras em `data/samples/`). Atualizar a tabela.
6. Adicionar uma linha no "Histórico de sessões" com a data e a tarefa de partida.
7. Continuar a partir do "Próximo passo exato".

#### Durante a tarefa

- Trate cada item da lista "Passos" da tarefa como um passo. Tarefas sem lista numerada são divididas em passos de até ~30 minutos de trabalho e registradas no `PROGRESSO.md` antes de começar.
- Ao concluir cada passo:
  1. atualizar "Tarefa em andamento" (passos concluídos, próximo passo exato, arquivos tocados);
  2. `git add` dos arquivos do passo **e** do `PROGRESSO.md`;
  3. commit `T<NN> [wip]: <descrição curta do passo>`;
  4. `git push`.
- Num commit `[wip]` os testes podem falhar, mas o código precisa ser importável (`ruff check .` sem erros de sintaxe). Anote em "Observações" quais testes estão falhando e por quê.
- Limite de segurança: nunca acumule mais de ~5 arquivos alterados ou ~30 minutos de trabalho sem commit.
- Antes de comandos longos (build Docker, download de modelos, treino), registre no `PROGRESSO.md` o comando e o que ele produz. Se a sessão cair no meio, a próxima sabe que precisa rodar de novo.
- O "Próximo passo exato" deve ser acionável por quem não viu a sessão anterior. Ruim: "continuar o worker". Bom: "implementar `_handle_prescription` em `src/medwatch/anomaly/worker.py` chamando `PrescriptionMonitor.process` e publicando em `evidence`; depois o teste `test_rx_flow` em `tests/test_anomaly_worker.py`".

#### Ao concluir uma tarefa

1. Verificar o critério de aceite, `pytest -q` e `ruff check .`.
2. No `PROGRESSO.md`: status `concluída`, limpar "Tarefa em andamento" e preenchê-la com a próxima tarefa e o seu primeiro passo. A coluna "Commit" recebe o hash do commit final no primeiro commit da tarefa seguinte (antes do commit o hash ainda não existe).
3. Commit `T<NN>: <título da tarefa>` e `git push`.

#### Encerramento (orçamento acabando, contexto longo demais ou erro que impede continuar)

1. Parar de começar trabalho novo.
2. Deixar o código importável: terminar a função atual se for rápido; senão, comentar o trecho incompleto e marcar com `# TODO(T<NN>): <o que falta>`.
3. Atualizar "Tarefa em andamento" com o próximo passo exato e o que ficou pela metade.
4. Completar a linha da sessão no "Histórico de sessões".
5. Commit `T<NN> [wip]: checkpoint de fim de sessão` e `git push`.

Como o commit é feito a cada passo, uma interrupção abrupta (sem tempo para o encerramento) perde no máximo o passo em andamento.

#### Bloqueios que dependem de pessoas

- Ao encontrar um passo **[HUMANO]** pendente, registrar na tabela "Bloqueios" do `PROGRESSO.md`: o que é preciso, qual tarefa depende, desde quando.
- Se dá para concluir a tarefa com os clientes falsos (`USE_FAKE_AZURE=true`) ou com dados sintéticos, conclua e anote em "Observação": `verificação real pendente: <o quê>`.
- Só marque a tarefa como `bloqueada` se nada dela puder ser feito sem a pessoa. Nesse caso, siga para a próxima tarefa cujas dependências estejam concluídas.
- Se o commit falhar com `Please tell me who you are`, a identidade do Git não está configurada: registre o bloqueio e peça ao humano para rodar `git config --global user.name` e `user.email`. Não invente uma identidade.
- Se o push falhar por falta de credencial, continue trabalhando com commits locais, registre o bloqueio e peça ao humano para fazer o login.

#### Estado fora do Git

Nada desta tabela vai para o repositório. Nunca suponha que existe: verifique antes de usar e, se faltar, recrie.

| O quê | Onde | Como verificar | Como recriar |
|---|---|---|---|
| Variáveis e chaves | `.env` | `Test-Path .env` / `test -f .env` | Copiar `.env.example`; sem chaves, `USE_FAKE_AZURE=true` e pedir as chaves ao humano |
| Imagem Docker | Docker local | `docker image ls medwatch-app` | `docker compose build` |
| Banco e streams | volumes `pgdata`, `redisdata` | `docker compose ps` | `docker compose up -d db redis`, `scripts/seed.py`; o simulador repovoa vitais |
| Pesos YOLO e modelo AST | `models/`, volume `model-cache` | `ls models/` | `docker compose up models-init` |
| Isolation Forest | `models/vitals_iforest.*` | `ls models/` | `scripts/train_vitals_iforest.py` |
| Referências de exercício e voz | `data/references/` | `ls data/references/` | `build_exercise_reference.py`, `build_voice_baseline.py` (precisam das amostras) |
| Amostras de mídia | `data/samples/` | `ls data/samples/` | Humano, conforme `data/samples/README.md` |
| MIMIC-IV Demo | `data/mimic/` | `ls data/mimic/` | `download_mimic_demo.sh` e `prepare_mimic.py` |

### 0.2 Modelo e escalonamento

O humano escolhe o modelo da sessão (o agente não consegue trocar o próprio modelo). Recomendação:

| Situação | Modelo |
|---|---|
| Padrão para todas as tarefas | **Claude Sonnet 5.5** |
| T24 (worker de vídeo), T26 (worker de fusão), T30 (dashboard), T32 (demo automatizada), T35 (integração ponta a ponta), T37 (datasets reais com partes reservadas) | **Claude Opus 5.5** |
| Mesmo erro persistindo depois de 2 tentativas de correção, em qualquer tarefa | **Claude Opus 5.5** até destravar; depois volte ao Sonnet |
| Revisão ao fim de cada fase (opcional) | **Claude Opus 5.5** |

Quando o agente estiver no Sonnet e cair numa das situações marcadas como Opus, ele registra em "Observações" do `PROGRESSO.md`: `recomendação: trocar para Opus 5.5 — <motivo>`, faz o commit `[wip]` e avisa o humano na resposta. Se o humano não trocar, continue no modelo atual.

---

## 1. Visão geral e decisões fixas

### 1.1 O que o sistema faz

- Recebe **vídeos** (fisioterapia, cirurgia, câmera de leito), **áudios** de consulta e **laudos em texto** por upload.
- Recebe **sinais vitais, prescrições e movimentação** como stream (na demo, gerados por um simulador).
- Cada modalidade gera **evidências** padronizadas (seção 3.2).
- Um **motor de fusão** combina as evidências por paciente, calcula um **escore de risco 0–100** e cria **alertas**.
- Alertas vão para **console, Microsoft Teams, e-mail (Logic App) e dashboard**. O médico confirma ou descarta pelo dashboard.

### 1.2 Arquitetura

```
             ┌──────────────┐  jobs.video   ┌────────────────┐
 upload ───► │ API FastAPI  │ ────────────► │ worker-video   │──┐
             │  /media      │  jobs.audio   ├────────────────┤  │
             │  /documents  │ ────────────► │ worker-audio   │──┤  (Azure Speech + Language)
             └──────┬───────┘  jobs.text    ├────────────────┤  │
                    │        ────────────►  │ worker-text    │──┤
                    ▼                       └────────────────┘  │ evidence
              Storage (local                                     ▼
              ou Azure Blob)    vitals       ┌────────────────┐  ┌──────────────┐  alerts  ┌──────────────┐
 simulator ───────────────────► prescriptions│ worker-anomaly │─►│ worker-fusion│────────► │ worker-alerts│─► Teams / e-mail
                                movement ──► └────────────────┘  └──────┬───────┘          └──────────────┘
                                                                        │
                         PostgreSQL + TimescaleDB ◄─────────────────────┘
                                   ▲
                         dashboard (Streamlit) ──► API (leitura, ack, upload)
```

Comunicação entre processos: **Redis Streams** (consumer groups). Persistência: **PostgreSQL 16 + TimescaleDB**. Um único pacote Python (`medwatch`) e **uma única imagem Docker**; cada serviço é o mesmo container com um comando diferente.

### 1.3 Decisões fixas (não reabrir)

| Tema | Decisão |
|---|---|
| Linguagem | Python 3.11 |
| Gerenciador | `pip` + `pyproject.toml` (extras opcionais). Torch CPU via índice oficial |
| API | FastAPI + Uvicorn |
| Mensageria | Redis 7 Streams (`redis-py`) |
| Banco | PostgreSQL 16 + TimescaleDB, schema em `db/init.sql` (sem Alembic) |
| Acesso ao banco | SQLAlchemy 2.0 Core + psycopg 3 (sem ORM) |
| Storage | Abstração com backend `local` (padrão) e `azure` (Blob) |
| Transcrição | Azure AI Speech, `ConversationTranscriber` (diarização), pt-BR |
| NLP | Azure AI Language via `azure-ai-textanalytics` 5.3 (sentimento, frases-chave, entidades de saúde) |
| Detecção de objetos | Ultralytics YOLOv8 (`yolov8n.pt`) |
| Pose | Ultralytics YOLOv8-pose (`yolov8n-pose.pt`) como principal; OpenPose via OpenCV DNN como módulo opcional (T19b) |
| Features de voz | openSMILE (eGeMAPSv02 Functionals) + librosa |
| Sons respiratórios | Hugging Face `MIT/ast-finetuned-audioset-10-10-0.4593` (treinado no AudioSet) |
| Anomalias | NEWS2, EWMA z-score, Isolation Forest (scikit-learn), regras |
| Fusão | Noisy-OR ponderado com decaimento temporal + regras de combinação |
| Dashboard | Streamlit ≥ 1.37 (usa `st.fragment(run_every=...)`) |
| Relatórios | Jinja2 → HTML → PDF com WeasyPrint |
| Alertas | Teams via webhook do app Workflows (Adaptive Card); e-mail via Logic App HTTP |
| Testes | pytest; lint com ruff |
| Orquestração | Docker Compose |

**Importante:** o Azure AI Anomaly Detector foi descontinuado (out/2026). Não usar. A detecção de anomalias é feita no próprio código.

---

## 2. Estrutura do repositório

Crie exatamente esta estrutura (arquivos vazios são criados nas tarefas correspondentes):

```
medwatch/
├── README.md
├── CLAUDE.md                  # ponto de entrada do agente (T00)
├── PROGRESSO.md               # andamento e próximo passo (T00, atualizado em todo commit)
├── PLANO_IMPLEMENTACAO.md     # este documento
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml         # ambiente completo (seção 9)
├── docker-compose.dev.yml     # override de desenvolvimento: código montado + reload
├── docker-compose.gpu.yml     # override opcional: GPU NVIDIA no worker-video
├── .env.example
├── .gitignore
├── .gitattributes             # força LF em scripts (essencial no Windows)
├── .dockerignore
├── config/
│   ├── thresholds.yaml        # limiares de vitais, voz, vídeo
│   ├── exercises.yaml         # definição dos exercícios de fisioterapia
│   ├── zones.yaml             # polígonos de zonas por câmera
│   ├── critical_terms.yaml    # termos críticos pt-BR
│   ├── drugs.yaml             # alta vigilância, classes, interações
│   └── fusion.yaml            # pesos, regras, níveis, rótulos pt-BR
├── db/
│   └── init.sql
├── src/medwatch/
│   ├── __init__.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── contracts.py
│   ├── bus.py
│   ├── db.py
│   ├── storage.py
│   ├── timeutil.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routes_media.py
│   │   ├── routes_patients.py
│   │   └── routes_alerts.py
│   ├── simulator/
│   │   ├── __init__.py
│   │   ├── synthetic.py
│   │   ├── mimic.py
│   │   └── replay.py
│   ├── anomaly/
│   │   ├── __init__.py
│   │   ├── filters.py
│   │   ├── news2.py
│   │   ├── streaming_stats.py
│   │   ├── iforest.py
│   │   ├── prescriptions.py
│   │   ├── movement.py
│   │   └── worker.py
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── convert.py
│   │   ├── speech.py
│   │   ├── language.py
│   │   ├── terms.py
│   │   ├── acoustic.py
│   │   ├── events.py
│   │   └── worker.py
│   ├── text/
│   │   ├── __init__.py
│   │   └── worker.py
│   ├── video/
│   │   ├── __init__.py
│   │   ├── frames.py
│   │   ├── models.py
│   │   ├── geometry.py
│   │   ├── dtw.py
│   │   ├── reps.py
│   │   ├── physio.py
│   │   ├── bed.py
│   │   ├── surgery.py
│   │   ├── annotate.py
│   │   ├── openpose_cv.py     # opcional (T19b)
│   │   └── worker.py
│   ├── fusion/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── worker.py
│   ├── alerts/
│   │   ├── __init__.py
│   │   ├── channels.py
│   │   └── worker.py
│   ├── reports/
│   │   ├── __init__.py
│   │   ├── render.py
│   │   └── templates/
│   │       ├── video_report.html.j2
│   │       └── patient_report.html.j2
│   └── dashboard/
│       ├── __init__.py
│       ├── app.py
│       └── api_client.py
├── scripts/
│   ├── download_models.py     # baixa pesos YOLO e o modelo AST (seção 9.4)
│   ├── setup_vps.sh           # prepara uma VPS Ubuntu 24.04 (já existe; docs/AMBIENTE_REMOTO.md)
│   ├── provision_azure.sh
│   ├── check_azure.py
│   ├── download_mimic_demo.sh
│   ├── prepare_mimic.py
│   ├── train_vitals_iforest.py
│   ├── build_exercise_reference.py
│   ├── build_voice_baseline.py
│   ├── evaluate_vitals.py
│   ├── evaluate_video.py
│   ├── seed.py
│   └── run_demo.py
├── tests/
│   ├── conftest.py
│   └── ... (um arquivo test_<módulo>.py por módulo)
├── data/                      # gitignored (exceto data/samples/README.md)
│   ├── samples/
│   ├── references/
│   └── storage/
├── models/                    # gitignored
└── docs/
    ├── DECISOES.md
    ├── AMBIENTE_REMOTO.md     # nuvem do Claude Code ou VPS (já existe)
    ├── plano-fase4.html       # visão geral (já existe)
    ├── relatorio-tecnico.md
    ├── arquitetura.md
    └── resultados/
```

---

## 3. Contratos compartilhados

### 3.1 Variáveis de ambiente (`.env.example`)

```dotenv
# Infra — valores para rodar FORA do Docker (python local).
# Dentro do Docker, o docker-compose.yml sobrescreve DATABASE_URL, REDIS_URL, API_BASE_URL,
# CONFIG_DIR, MODELS_DIR, LOCAL_STORAGE_DIR e YOLO_*_WEIGHTS (seção 9.3). Não edite esses aqui para o Docker.
DATABASE_URL=postgresql+psycopg://medwatch:medwatch@localhost:5432/medwatch
REDIS_URL=redis://localhost:6379/0
API_BASE_URL=http://localhost:8000
CONFIG_DIR=config
MODELS_DIR=models
LOG_LEVEL=INFO

# Docker (usados pelo docker-compose.yml)
DB_PORT=5432                     # mude se a porta 5432 já estiver em uso na máquina
REDIS_PORT=6379
API_PORT=8000
DASHBOARD_PORT=8501
TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu   # GPU: .../whl/cu128 (RTX 50xx exige CUDA 12.8+; cu121 serve só até a série 40)

# Storage
STORAGE_BACKEND=local            # local | azure
LOCAL_STORAGE_DIR=data/storage
AZURE_STORAGE_CONNECTION_STRING=
AZURE_STORAGE_CONTAINER=media

# Azure AI
USE_FAKE_AZURE=false             # true = clientes falsos (offline/testes)
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=brazilsouth
SPEECH_LANGUAGE=pt-BR
AZURE_LANGUAGE_KEY=
AZURE_LANGUAGE_ENDPOINT=
LANGUAGE_CODE=pt

# Vídeo
YOLO_DET_WEIGHTS=models/yolov8n.pt
YOLO_POSE_WEIGHTS=models/yolov8n-pose.pt
VIDEO_TARGET_FPS=8

# Áudio
AUDIO_DISABLE_EVENTS=false       # true pula o modelo AST (máquinas com pouca memória)

# Simulador
SIM_SPEEDUP=60                   # 60 = 1 min simulado por segundo real
SIM_PATIENTS=5
SIM_SCENARIO=demo

# Alertas
ALERT_MIN_LEVEL=warning          # info | warning | critical
ALERT_COOLDOWN_MINUTES=15
ALERT_ESCALATION_MINUTES=5
TEAMS_WEBHOOK_URL=
LOGIC_APP_EMAIL_URL=
ALERT_EMAIL_TO=
DASHBOARD_URL=http://localhost:8501
```

`src/medwatch/config.py` expõe:

```python
from functools import lru_cache
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://medwatch:medwatch@localhost:5432/medwatch"
    redis_url: str = "redis://localhost:6379/0"
    api_base_url: str = "http://localhost:8000"
    config_dir: Path = Path("config")
    models_dir: Path = Path("models")
    log_level: str = "INFO"
    storage_backend: str = "local"
    local_storage_dir: Path = Path("data/storage")
    azure_storage_connection_string: str = ""
    azure_storage_container: str = "media"
    use_fake_azure: bool = False
    azure_speech_key: str = ""
    azure_speech_region: str = "brazilsouth"
    speech_language: str = "pt-BR"
    azure_language_key: str = ""
    azure_language_endpoint: str = ""
    language_code: str = "pt"
    yolo_det_weights: str = "models/yolov8n.pt"
    yolo_pose_weights: str = "models/yolov8n-pose.pt"
    video_target_fps: int = 8
    audio_disable_events: bool = False
    sim_speedup: float = 60.0
    sim_patients: int = 5
    sim_scenario: str = "demo"
    alert_min_level: str = "warning"
    alert_cooldown_minutes: int = 15
    alert_escalation_minutes: int = 5
    teams_webhook_url: str = ""
    logic_app_email_url: str = ""
    alert_email_to: str = ""
    dashboard_url: str = "http://localhost:8501"

@lru_cache
def get_settings() -> Settings:
    """Retorna as configurações (cacheadas)."""
    return Settings()

@lru_cache
def load_yaml(name: str) -> dict:
    """Carrega config/<name>.yaml."""
    path = get_settings().config_dir / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
```

### 3.2 Modelos Pydantic (`src/medwatch/contracts.py`)

```python
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class Modality(str, Enum):
    video = "video"
    audio = "audio"
    text = "text"
    vitals = "vitals"
    prescription = "prescription"
    movement = "movement"

class Severity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"

SEVERITY_ORDER = {"none": 0, "info": 1, "warning": 2, "critical": 3}

class Evidence(BaseModel):
    evidence_id: UUID = Field(default_factory=uuid4)
    patient_id: str
    modality: Modality
    type: str                       # ver catálogo (seção 4)
    score: float = Field(ge=0.0, le=1.0)
    severity: Severity
    ts_start: datetime
    ts_end: datetime | None = None
    explanation: str                # frase em pt-BR, legível pelo médico
    source_ref: str | None = None   # ex.: "media:<uuid>#t=130" ou "vitals:P-0001@<ts>"
    model_name: str
    model_version: str = "0.1.0"
    payload: dict = Field(default_factory=dict)

class VitalObservation(BaseModel):
    patient_id: str
    ts: datetime
    hr: float | None = None         # bpm
    sbp: float | None = None        # mmHg
    dbp: float | None = None        # mmHg
    spo2: float | None = None       # %
    rr: float | None = None         # irpm
    temp: float | None = None       # °C
    consciousness: str = "A"        # A | C | V | P | U  (ACVPU)
    on_oxygen: bool = False

class PrescriptionEvent(BaseModel):
    rx_id: str
    patient_id: str
    ts: datetime
    drug: str
    dose: float | None = None
    unit: str | None = None
    route: str | None = None
    frequency: str | None = None
    action: str                     # start | change | stop

class MovementSample(BaseModel):
    patient_id: str
    ts: datetime                    # início do minuto
    activity_count: float           # 0..100, contagem normalizada no minuto
    in_bed: bool | None = None
    source: str                     # sensor | video

class MediaJob(BaseModel):
    media_id: UUID
    patient_id: str
    kind: str                       # video | audio | document
    storage_uri: str
    recorded_at: datetime
    mode: str | None = None         # vídeo: physio | surgery | bed
    exercise: str | None = None     # vídeo physio: chave de exercises.yaml
    camera: str | None = None       # chave de zones.yaml
    patient_speaker: str | None = None  # áudio: ex. "Guest-2"

class Alert(BaseModel):
    alert_id: UUID = Field(default_factory=uuid4)
    patient_id: str
    level: Severity
    risk_score: float               # 0..100
    title: str
    summary: str                    # texto multilinha pt-BR
    evidence_ids: list[UUID]
    status: str = "open"            # open | acknowledged | dismissed | resolved
    escalated: bool = False
    created_at: datetime
    updated_at: datetime
    event: str = "created"          # created | escalated | updated (só no stream)
```

### 3.3 Streams Redis

| Stream | Produtor | Consumidor (grupo) | Mensagem (campo `data`, JSON) |
|---|---|---|---|
| `jobs.video` | API | `worker-video` | `MediaJob` |
| `jobs.audio` | API | `worker-audio` | `MediaJob` |
| `jobs.text` | API | `worker-text` | `MediaJob` |
| `vitals` | simulador | `worker-anomaly` | `VitalObservation` |
| `prescriptions` | simulador | `worker-anomaly` | `PrescriptionEvent` |
| `movement` | simulador, worker-video | `worker-anomaly` | `MovementSample` |
| `evidence` | todos os workers de análise | `worker-fusion` | `Evidence` |
| `alerts` | worker-fusion | `worker-alerts` | `Alert` |

Toda mensagem tem um único campo `data` contendo o JSON do modelo (`model.model_dump_json()`).

### 3.4 Quem escreve no banco

Um único escritor por tabela, para evitar conflitos:

| Tabela | Escritor |
|---|---|
| `patients` | API e `scripts/seed.py` |
| `media` | API (insert) e workers de mídia (status, artifacts) |
| `transcripts` | worker-audio |
| `vitals`, `prescriptions`, `movement` | worker-anomaly |
| `evidence` | worker-fusion (ao consumir o stream) |
| `alerts`, `risk_snapshots` | worker-fusion (criação e atualização de risco); API (ack) |

### 3.5 Esquema do banco (`db/init.sql`)

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE patients (
  patient_id   TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  bed          TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE media (
  media_id      UUID PRIMARY KEY,
  patient_id    TEXT NOT NULL REFERENCES patients(patient_id),
  kind          TEXT NOT NULL CHECK (kind IN ('video','audio','document')),
  mode          TEXT,
  exercise      TEXT,
  camera        TEXT,
  storage_uri   TEXT NOT NULL,
  original_name TEXT,
  recorded_at   TIMESTAMPTZ NOT NULL,
  status        TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued','processing','done','failed')),
  error         TEXT,
  artifacts     JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE vitals (
  patient_id    TEXT NOT NULL,
  ts            TIMESTAMPTZ NOT NULL,
  hr REAL, sbp REAL, dbp REAL, spo2 REAL, rr REAL, temp REAL,
  consciousness TEXT,
  on_oxygen     BOOLEAN,
  news2         INTEGER,
  PRIMARY KEY (patient_id, ts)
);
SELECT create_hypertable('vitals', 'ts');

CREATE TABLE prescriptions (
  rx_id       TEXT PRIMARY KEY,
  patient_id  TEXT NOT NULL,
  ts          TIMESTAMPTZ NOT NULL,
  drug        TEXT NOT NULL,
  drug_norm   TEXT NOT NULL,
  dose        REAL,
  unit        TEXT,
  route       TEXT,
  frequency   TEXT,
  action      TEXT NOT NULL CHECK (action IN ('start','change','stop'))
);
CREATE INDEX ON prescriptions (patient_id, ts);

CREATE TABLE movement (
  patient_id     TEXT NOT NULL,
  ts             TIMESTAMPTZ NOT NULL,
  activity_count REAL NOT NULL,
  in_bed         BOOLEAN,
  source         TEXT NOT NULL,
  PRIMARY KEY (patient_id, ts, source)
);
SELECT create_hypertable('movement', 'ts');

CREATE TABLE transcripts (
  media_id   UUID PRIMARY KEY REFERENCES media(media_id),
  language   TEXT NOT NULL,
  segments   JSONB NOT NULL,
  analysis   JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE evidence (
  evidence_id   UUID PRIMARY KEY,
  patient_id    TEXT NOT NULL,
  modality      TEXT NOT NULL,
  type          TEXT NOT NULL,
  score         REAL NOT NULL,
  severity      TEXT NOT NULL,
  ts_start      TIMESTAMPTZ NOT NULL,
  ts_end        TIMESTAMPTZ,
  explanation   TEXT NOT NULL,
  source_ref    TEXT,
  model_name    TEXT NOT NULL,
  model_version TEXT NOT NULL,
  payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON evidence (patient_id, ts_start DESC);

CREATE TABLE alerts (
  alert_id     UUID PRIMARY KEY,
  patient_id   TEXT NOT NULL,
  level        TEXT NOT NULL CHECK (level IN ('info','warning','critical')),
  risk_score   REAL NOT NULL,
  title        TEXT NOT NULL,
  summary      TEXT NOT NULL,
  evidence_ids UUID[] NOT NULL,
  status       TEXT NOT NULL DEFAULT 'open'
               CHECK (status IN ('open','acknowledged','dismissed','resolved')),
  escalated    BOOLEAN NOT NULL DEFAULT false,
  event_ts     TIMESTAMPTZ NOT NULL,          -- tempo do evento que gerou o alerta
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  acked_by     TEXT,
  acked_at     TIMESTAMPTZ,
  ack_note     TEXT
);
CREATE INDEX ON alerts (patient_id, status);

CREATE TABLE risk_snapshots (
  patient_id    TEXT NOT NULL,
  ts            TIMESTAMPTZ NOT NULL,
  risk_score    REAL NOT NULL,
  level         TEXT NOT NULL,
  contributions JSONB NOT NULL,
  PRIMARY KEY (patient_id, ts)
);
SELECT create_hypertable('risk_snapshots', 'ts');
```

### 3.6 API HTTP

| Método | Rota | Corpo / parâmetros | Resposta |
|---|---|---|---|
| GET | `/health` | — | `{"status":"ok","db":true,"redis":true}` |
| POST | `/patients` | `{patient_id, display_name, bed?}` | 201 + paciente |
| GET | `/patients` | — | lista com `latest_risk`, `latest_level`, `open_alerts` |
| GET | `/patients/{id}` | — | paciente + últimos vitais + risco atual |
| GET | `/patients/{id}/vitals` | `since`, `until` (ISO, opcionais; padrão últimas 6 h de tempo de evento) | lista de observações |
| GET | `/patients/{id}/evidence` | `since`, `limit=200` | lista de evidências |
| GET | `/patients/{id}/risk` | `since` | lista de `risk_snapshots` |
| POST | `/media` | multipart: `file`, `patient_id`, `kind`, `mode?`, `exercise?`, `camera?`, `patient_speaker?`, `recorded_at?` | 202 + `{media_id, status}` |
| POST | `/documents` | `{patient_id, text, recorded_at?, title?}` | 202 + `{media_id}` (salva o texto como `.txt`) |
| GET | `/media` | `patient_id?` | lista |
| GET | `/media/{id}` | — | registro + `artifacts` + transcrição (se houver) |
| GET | `/files/{key:path}` | — | conteúdo do arquivo do storage (stream) |
| GET | `/alerts` | `status?`, `patient_id?` | lista |
| POST | `/alerts/{id}/ack` | `{user, decision: "confirmed"\|"dismissed", note?}` | alerta atualizado |
| POST | `/reports/patient/{id}` | — | `{html_key, pdf_key}` |

---

## 4. Catálogo de evidências

Todos os produtores usam **somente** estes `type`. Pesos padrão ficam em `config/fusion.yaml` (T25).

| type | modality | produtor | severidade típica | peso | payload obrigatório |
|---|---|---|---|---|---|
| `news2_low_medium` | vitals | anomaly | warning | 0.45 | `{news2, params}` |
| `news2_medium` | vitals | anomaly | warning | 0.65 | `{news2, params}` |
| `news2_high` | vitals | anomaly | critical | 0.95 | `{news2, params}` |
| `vital_zscore` | vitals | anomaly | warning | 0.40 | `{vital, value, z}` |
| `vital_iforest` | vitals | anomaly | warning | 0.50 | `{iforest_score, features}` |
| `rx_dose_change` | prescription | anomaly | warning | 0.40 | `{drug, old_dose, new_dose, ratio}` |
| `rx_high_alert_start` | prescription | anomaly | info | 0.35 | `{drug}` |
| `rx_interaction` | prescription | anomaly | warning | 0.60 | `{drugs: [a, b], note}` |
| `rx_duplicate_class` | prescription | anomaly | info | 0.30 | `{drug_class, drugs}` |
| `rx_change_burst` | prescription | anomaly | warning | 0.40 | `{changes_24h}` |
| `movement_inactivity` | movement | anomaly | warning | 0.35 | `{minutes}` |
| `movement_night_agitation` | movement | anomaly | warning | 0.40 | `{activity, threshold}` |
| `movement_bed_exit` | movement | anomaly | warning | 0.50 | `{}` |
| `fall_detected` | video | video | critical | 0.95 | `{t_video_s, frame_key}` |
| `bed_exit_video` | video | video | warning | 0.50 | `{t_video_s}` |
| `physio_low_rom` | video | video | info | 0.25 | `{joint, rom, ref_rom, rep}` |
| `physio_asymmetry` | video | video | info | 0.25 | `{joint_pair, diff_deg, rep}` |
| `physio_pattern_deviation` | video | video | info | 0.30 | `{dtw, threshold, rep}` |
| `physio_trunk_compensation` | video | video | info | 0.20 | `{trunk_deg, rep}` |
| `surgery_zone_intrusion` | video | video | warning | 0.50 | `{zone, people, max}` |
| `surgery_instrument_out_of_zone` | video | video | warning | 0.40 | `{cls, seconds}` |
| `surgery_instrument_count_mismatch` | video | video | critical | 0.70 | `{start_count, end_count}` |
| `speech_critical_term` | audio | audio | warning | 0.50 | `{term, category, segment_index}` |
| `speech_negative_sentiment` | audio | audio | info | 0.20 | `{negative_ratio}` |
| `voice_fatigue` | audio | audio | warning | 0.35 | `{features, flags}` |
| `voice_dysarthria_indicator` | audio | audio | warning | 0.45 | `{features, flags}` |
| `respiratory_sound` | audio | audio | warning | 0.45 | `{label, max_score, windows}` |
| `clinical_entity` | audio/text | audio, text | info | 0.10 | `{entities}` |
| `text_critical_term` | text | text | warning | 0.45 | `{term, category}` |

Regra geral do `score` (0–1): o produtor normaliza a força da evidência. Quando não houver um score natural, use `0.5` para warning, `0.8` para critical e `0.3` para info.

---

## 5. Tarefas

Formato de cada tarefa: **Objetivo · Depende de · Arquivos · Passos · Código de referência (quando necessário) · Testes · Aceite**.

---

### Fase 0 — Fundação

#### T00 — Arquivos de continuidade

- **Objetivo:** garantir que qualquer sessão consiga retomar o trabalho (seção 0.1).
- **Depende de:** nada.
- **Arquivos:** `CLAUDE.md`, `PROGRESSO.md`, `docs/DECISOES.md`.
- **Passos:**
  1. Os três arquivos foram criados junto com este plano. Confirme que existem na raiz do repositório e em `docs/`.
  2. Se algum faltar, recrie:
     - `CLAUDE.md`: no máximo ~40 linhas. Manda ler o `PROGRESSO.md`, seguir o protocolo de início da seção 0.1 e ler só a tarefa atual do plano; resume as regras essenciais (ordem das tarefas, commit `[wip]` a cada passo com o `PROGRESSO.md`, push, nada de segredos, caminho do `git.exe` no Windows).
     - `PROGRESSO.md`: seções "Tarefa em andamento", "Status das tarefas" (tabela com T00–T34: tarefa, título, status, commit, observação), "Bloqueios que dependem de pessoas" (pré-preenchida com os itens da seção 6), "Estado fora do Git" (aponta para a tabela da seção 0.1) e "Histórico de sessões".
     - `docs/DECISOES.md`: título e tabela vazia com colunas data, tarefa, decisão, motivo.
  3. Verificar a identidade do Git (`git config user.name` e `git config user.email`). Se estiver vazia, registrar o bloqueio no `PROGRESSO.md` e pedir ao humano para configurar antes de qualquer commit.
- **Aceite:** os três arquivos existem; "Tarefa em andamento" aponta para a T01 e seu primeiro passo; commit `T00: Arquivos de continuidade` enviado com push (se a identidade estiver configurada).

#### T01 — Esqueleto do repositório

- **Objetivo:** projeto Python instalável, lint e testes funcionando.
- **Depende de:** T00.
- **Arquivos:** `pyproject.toml`, `.gitignore`, `.dockerignore`, `README.md` (stub), `src/medwatch/__init__.py`, `tests/test_smoke.py`. Não sobrescreva `CLAUDE.md`, `PROGRESSO.md` nem `docs/DECISOES.md` (criados na T00).
- **Passos:**
  1. No repositório já clonado, criar a estrutura de diretórios da seção 2 (com `__init__.py` vazios). O Git não versiona pastas vazias e o `Dockerfile` copia `config/`, `db/`, `scripts/` e `tests/`: coloque um `.gitkeep` em toda pasta que ainda não tiver arquivo.
  2. Criar `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "medwatch"
version = "0.1.0"
requires-python = ">=3.11,<3.12"
dependencies = [
  "fastapi>=0.110", "uvicorn[standard]>=0.29", "python-multipart>=0.0.9",
  "pydantic>=2.6", "pydantic-settings>=2.2", "pyyaml>=6.0",
  "sqlalchemy>=2.0", "psycopg[binary]>=3.1",
  "redis>=5.0", "httpx>=0.27",
  "numpy>=1.26,<2.0", "pandas>=2.2", "scipy>=1.12", "scikit-learn>=1.4", "joblib>=1.3",
  "unidecode>=1.3", "jinja2>=3.1",
  "azure-storage-blob>=12.19",
]

[project.optional-dependencies]
audio = [
  "azure-cognitiveservices-speech>=1.38",
  "azure-ai-textanalytics>=5.3,<5.4",
  "opensmile>=2.5", "librosa>=0.10", "soundfile>=0.12",
  "transformers>=4.40",
]
video = ["ultralytics>=8.2,<8.4", "opencv-python-headless>=4.9"]
reports = ["weasyprint>=62", "matplotlib>=3.8"]
dashboard = ["streamlit>=1.37", "plotly>=5.20"]
dev = ["pytest>=8.0", "pytest-cov>=5.0", "ruff>=0.4", "fakeredis>=2.23"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
medwatch = ["reports/templates/*.j2"]

[tool.ruff]
line-length = 110
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["azure: chama serviços Azure reais", "slow: baixa modelos ou processa mídia"]
addopts = "-m 'not azure and not slow'"
```

  3. `.gitignore`: `.env`, `data/*` (exceto `data/samples/README.md`), `models/`, `__pycache__/`, `.venv/`, `*.pt`, `runs/`, `.pytest_cache/`.
  4. Instalação local (documentar no README):
     ```bash
     python -m venv .venv && source .venv/bin/activate
     pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
     pip install -e ".[audio,video,reports,dashboard,dev]"
     ```
  5. `tests/test_smoke.py`: `import medwatch` e assert de `medwatch.__version__ == "0.1.0"` (defina `__version__` no `__init__.py`).
  6. Após a primeira instalação bem-sucedida, gerar `requirements.lock` com `pip freeze` e commitar.
- **Aceite:** `pytest -q` e `ruff check .` passam.

#### T02 — Configuração, logging, contratos e utilitários de tempo

- **Depende de:** T01.
- **Arquivos:** `config.py`, `logging_setup.py`, `contracts.py`, `timeutil.py`, `.env.example`, todos os YAML de `config/` (conteúdo inicial abaixo), `tests/test_contracts.py`.
- **Passos:**
  1. Implementar `config.py` e `contracts.py` exatamente como na seção 3.
  2. `logging_setup.py`: função `setup_logging(service: str)` com `logging.basicConfig(level=..., format="%(asctime)s %(levelname)s [" + service + "] %(name)s: %(message)s")`.
  3. `timeutil.py`: `utcnow()`, `parse_ts(s: str) -> datetime` (aceita ISO com ou sem `Z`; se vier sem timezone, assume UTC), `to_iso(dt)`.
  4. Criar os YAML iniciais:

`config/thresholds.yaml`
```yaml
vitals:
  physiologic_bounds:          # fora disso = artefato de sensor, valor descartado
    hr: [20, 250]
    sbp: [50, 260]
    dbp: [20, 180]
    spo2: [50, 100]
    rr: [4, 60]
    temp: [30, 43]
  zscore:
    alpha: 0.1
    warmup: 20
    threshold: 3.0
    cooldown_minutes: 10
  iforest:
    cooldown_minutes: 10
  news2:
    repeat_minutes: 15         # reemite se o nível se mantém >= medium
movement:
  inactivity_activity_max: 5
  inactivity_minutes: 120
  night_start_hour: 23
  night_end_hour: 6
  night_agitation_fixed: 80
  night_agitation_min_history: 60
voice:                         # valores PROVISÓRIOS; recalibrar com build_voice_baseline.py
  speech_rate_wpm_min: 100
  pause_ratio_max: 0.40
  z_threshold: 2.0
audio_events:
  window_s: 10
  hop_s: 5
  min_score: 0.30
  labels: ["Cough", "Wheeze", "Breathing", "Gasp", "Pant", "Snoring", "Throat clearing"]
video:
  keypoint_min_conf: 0.5
  fall:
    window_s: 1.0
    hip_drop_min: 0.25         # fração da altura do frame
    lying_aspect_min: 1.3      # largura/altura da bbox
    lying_min_s: 2.0
  inactivity_motion_max: 0.01  # deslocamento médio normalizado por frame
  instrument_out_min_s: 5
  count_window_s: 10
```

`config/exercises.yaml`
```yaml
squat:
  label: "Agachamento"
  primary_joint: knee_left
  joints:
    knee_left:  [11, 13, 15]   # quadril, joelho, tornozelo (índices COCO)
    knee_right: [12, 14, 16]
    hip_left:   [5, 11, 13]
    hip_right:  [6, 12, 14]
  pairs: [[knee_left, knee_right], [hip_left, hip_right]]
  rep_min_prominence_deg: 20
  rep_min_distance_s: 0.8
  rom_min_ratio: 0.8           # ROM < 80% da referência => physio_low_rom
  asymmetry_max_deg: 15
  dtw_max: 15                  # graus médios
  trunk_max_deg: 30
shoulder_abduction:
  label: "Abdução de ombro"
  primary_joint: shoulder_left
  joints:
    shoulder_left:  [11, 5, 7]
    shoulder_right: [12, 6, 8]
    elbow_left:     [5, 7, 9]
    elbow_right:    [6, 8, 10]
  pairs: [[shoulder_left, shoulder_right]]
  rep_min_prominence_deg: 30
  rep_min_distance_s: 1.0
  rom_min_ratio: 0.8
  asymmetry_max_deg: 15
  dtw_max: 18
  trunk_max_deg: 20
```

`config/zones.yaml` (coordenadas normalizadas 0–1, x à direita, y para baixo)
```yaml
default_bed:
  bed: [[0.20, 0.35], [0.80, 0.35], [0.80, 0.95], [0.20, 0.95]]
default_surgery:
  sterile_field: [[0.30, 0.30], [0.70, 0.30], [0.70, 0.80], [0.30, 0.80]]
  instrument_tray: [[0.75, 0.55], [0.98, 0.55], [0.98, 0.95], [0.75, 0.95]]
  max_people_sterile: 3
  instrument_classes: ["scissors", "knife"]
```

`config/critical_terms.yaml`
```yaml
terms:
  - {term: "falta de ar", category: respiratorio, weight: 0.8}
  - {term: "dificuldade para respirar", category: respiratorio, weight: 0.8}
  - {term: "chiado", category: respiratorio, weight: 0.6}
  - {term: "tosse", category: respiratorio, weight: 0.4}
  - {term: "dor no peito", category: cardiovascular, weight: 0.9}
  - {term: "aperto no peito", category: cardiovascular, weight: 0.8}
  - {term: "palpitacao", category: cardiovascular, weight: 0.6}
  - {term: "desmaio", category: neurologico, weight: 0.8}
  - {term: "tontura", category: neurologico, weight: 0.5}
  - {term: "fala enrolada", category: neurologico, weight: 0.9}
  - {term: "formigamento", category: neurologico, weight: 0.5}
  - {term: "fraqueza", category: geral, weight: 0.5}
  - {term: "cansaco", category: geral, weight: 0.5}
  - {term: "febre", category: infeccioso, weight: 0.5}
  - {term: "sangramento", category: hemorragico, weight: 0.8}
  - {term: "confusao", category: neurologico, weight: 0.7}
  - {term: "queda", category: trauma, weight: 0.7}
```

`config/drugs.yaml` (nomes normalizados: minúsculos e sem acento; inclui pt e en porque o MIMIC é em inglês)
```yaml
high_alert: [insulina, insulin, heparina, heparin, varfarina, warfarin, morfina, morphine,
             fentanil, fentanyl, noradrenalina, norepinephrine, cloreto de potassio,
             potassium chloride, midazolam, propofol, enoxaparina, enoxaparin]
classes:
  anticoagulante: [heparina, heparin, varfarina, warfarin, enoxaparina, enoxaparin, apixabana, apixaban]
  opioide: [morfina, morphine, fentanil, fentanyl, tramadol, oxicodona, oxycodone, hydromorphone]
  benzodiazepinico: [midazolam, diazepam, lorazepam, clonazepam]
  aine: [ibuprofeno, ibuprofen, cetorolaco, ketorolac, diclofenaco, diclofenac]
interactions:
  - {a: anticoagulante, b: aine, note: "Risco aumentado de sangramento"}
  - {a: opioide, b: benzodiazepinico, note: "Risco de depressão respiratória"}
  - {a: varfarina, b: aas, note: "Risco aumentado de sangramento"}
  - {a: warfarin, b: aspirin, note: "Risco aumentado de sangramento"}
sedatives_classes: [opioide, benzodiazepinico]
dose_change_ratio_high: 1.5
dose_change_ratio_low: 0.5
burst_changes_24h: 4
```

`config/fusion.yaml` — criado na T25 (deixe um arquivo com `{}` por enquanto).

  5. `tests/test_contracts.py`: criar um `Evidence` válido; verificar que `score=1.5` levanta `ValidationError`; serializar com `model_dump_json()` e reconstruir com `model_validate_json()`.
- **Aceite:** testes passam; `load_yaml("thresholds")["vitals"]["zscore"]["threshold"] == 3.0` num teste (use `monkeypatch` para apontar `CONFIG_DIR` para `config/` e limpe o cache com `get_settings.cache_clear()` e `load_yaml.cache_clear()`).

#### T03 — Docker Compose, banco e camada de acesso

- **Depende de:** T02.
- **Arquivos:** `Dockerfile`, `docker-compose.yml`, `db/init.sql`, `src/medwatch/db.py`, `tests/test_db.py`.
- **Passos:**
  1. `db/init.sql` conforme seção 3.5.
  2. Criar o ambiente Docker **exatamente como na [seção 9](#9-ambiente-docker-referência-completa)**: `Dockerfile`, `.dockerignore`, `.gitattributes`, `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.gpu.yml` e `scripts/download_models.py`. Não invente variações; se algo não funcionar, corrija e registre em `docs/DECISOES.md`.
  3. Validar com `docker compose config` (não pode haver erro) e `docker compose build`.
  4. `db.py` — funções usadas por todo o projeto. Use `sqlalchemy.create_engine(settings.database_url, pool_pre_ping=True)` num singleton `get_engine()`. Escreva com `text()` e parâmetros nomeados. Funções obrigatórias:

```python
def ping() -> bool
def upsert_patient(patient_id: str, display_name: str, bed: str | None) -> None
def list_patients() -> list[dict]          # inclui latest_risk, latest_level, open_alerts (subqueries)
def get_patient(patient_id: str) -> dict | None
def insert_media(row: dict) -> None
def update_media(media_id, *, status: str | None = None, error: str | None = None,
                 artifacts: dict | None = None) -> None   # artifacts faz merge: artifacts = artifacts || :new
def get_media(media_id) -> dict | None
def list_media(patient_id: str | None) -> list[dict]
def insert_vital(obs: VitalObservation, news2: int | None) -> None      # ON CONFLICT DO NOTHING
def insert_prescription(ev: PrescriptionEvent, drug_norm: str) -> None  # ON CONFLICT DO NOTHING
def insert_movement(s: MovementSample) -> None                          # ON CONFLICT DO NOTHING
def insert_transcript(media_id, language: str, segments: list, analysis: dict) -> None
def get_transcript(media_id) -> dict | None
def insert_evidence(ev: Evidence) -> None                               # ON CONFLICT DO NOTHING
def list_evidence(patient_id: str, since: datetime | None, limit: int) -> list[dict]
def recent_evidence_all(window_minutes: int) -> list[Evidence]
    # para cada paciente, evidências com ts_start >= max(ts_start do paciente) - window (reidratação da fusão)
def get_evidence_many(ids: list) -> list[dict]
def query_vitals(patient_id: str, since: datetime | None, until: datetime | None) -> list[dict]
def latest_event_ts(patient_id: str) -> datetime | None   # max(ts) em vitals; usado como "agora" do paciente
def insert_risk_snapshot(patient_id, ts, risk, level, contributions: dict) -> None  # ON CONFLICT (pk) DO UPDATE
def query_risk(patient_id: str, since: datetime | None) -> list[dict]
def get_open_alert(patient_id: str) -> dict | None
def last_closed_alert(patient_id: str) -> dict | None
def insert_alert(a: Alert, event_ts: datetime) -> None
def update_alert(alert_id, **fields) -> dict
def list_alerts(status: str | None, patient_id: str | None) -> list[dict]
def alerts_to_escalate(minutes: int) -> list[dict]   # open, critical, not escalated, created_at < now()-minutes (relógio de parede)
```

  JSONB: passe `json.dumps(...)` e use `CAST(:x AS JSONB)` no SQL. Arrays de UUID: `CAST(:ids AS UUID[])` passando lista de strings.

  5. `tests/test_db.py`: marque o módulo com `pytest.mark.skipif` se `DATABASE_URL` não conectar. Teste insert/consulta de paciente, evidência e alerta.
- **Aceite:** `docker compose build` termina sem erro; `docker compose up -d db redis` sobe com os dois serviços `healthy` em `docker compose ps`; `docker compose exec db psql -U medwatch -d medwatch -c "\dt"` mostra as tabelas; testes de banco passam com o banco no ar. Os demais serviços só sobem quando os módulos existirem (tabela 9.6).

#### T04 — Barramento (Redis Streams) e storage

- **Depende de:** T03.
- **Arquivos:** `bus.py`, `storage.py`, `tests/test_bus.py`, `tests/test_storage.py`.
- **Código de referência — `bus.py`:**

```python
import json, logging, socket, time
from collections.abc import Callable
import redis
from pydantic import BaseModel
from medwatch.config import get_settings

log = logging.getLogger(__name__)

class Bus:
    def __init__(self, client: redis.Redis | None = None):
        self.r = client or redis.Redis.from_url(get_settings().redis_url, decode_responses=True)

    def publish(self, stream: str, msg: BaseModel | dict) -> str:
        """Publica uma mensagem no stream."""
        data = msg.model_dump_json() if isinstance(msg, BaseModel) else json.dumps(msg, default=str)
        return self.r.xadd(stream, {"data": data}, maxlen=200_000, approximate=True)

    def ensure_group(self, stream: str, group: str) -> None:
        """Cria o consumer group se não existir."""
        try:
            self.r.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    def consume(self, streams: list[str], group: str, handler: Callable[[str, dict], None],
                block_ms: int = 5000, count: int = 20, stop_after: int | None = None) -> None:
        """Loop de consumo. handler(stream, payload). Mensagens com erro não recebem ACK."""
        consumer = f"{group}-{socket.gethostname()}"
        for s in streams:
            self.ensure_group(s, group)
        processed = 0
        while True:
            resp = self.r.xreadgroup(group, consumer, {s: ">" for s in streams}, count=count, block=block_ms)
            for stream, messages in resp or []:
                for msg_id, fields in messages:
                    try:
                        handler(stream, json.loads(fields["data"]))
                        self.r.xack(stream, group, msg_id)
                    except Exception:
                        log.exception("Falha ao processar %s %s", stream, msg_id)
                    processed += 1
            if stop_after is not None and processed >= stop_after:
                return
            if not resp:
                time.sleep(0.05)
```

  O parâmetro `stop_after` existe para os testes. Use `fakeredis.FakeRedis(decode_responses=True)` nos testes.

- **`storage.py`:** interface única.

```python
class Storage(Protocol):
    def put_file(self, local_path: Path, key: str) -> str: ...     # retorna uri
    def put_bytes(self, data: bytes, key: str) -> str: ...
    def get_to_path(self, uri: str, dest: Path) -> Path: ...
    def open_stream(self, key: str) -> Iterator[bytes]: ...
def get_storage() -> Storage
```

  - `LocalStorage`: raiz `LOCAL_STORAGE_DIR`; URI `local://<key>`.
  - `AzureBlobStorage`: `BlobServiceClient.from_connection_string(...)`; cria o container se não existir; URI `azure://<container>/<key>`.
  - Convenção de chaves: `media/<patient_id>/<media_id>/<nome_original>`, artefatos em `artifacts/<media_id>/<arquivo>`, relatórios em `reports/<patient_id>/<arquivo>`.
  - Função auxiliar `key_from_uri(uri) -> str`.
- **Testes:** publicar e consumir 3 mensagens com fakeredis; mensagem cujo handler lança exceção não recebe ACK (verifique com `xpending`). `LocalStorage` em `tmp_path`: put/get ida e volta.
- **Aceite:** testes passam.

#### T05 — Provisionamento e verificação da Azure

- **Depende de:** T02.
- **Arquivos:** `scripts/provision_azure.sh`, `scripts/check_azure.py`, `src/medwatch/audio/speech.py` (somente a fábrica de cliente, ver T14), seção "Azure" no README.
- **`scripts/provision_azure.sh`** (executado por humano após `az login`; o agente apenas escreve):

```bash
#!/usr/bin/env bash
set -euo pipefail
SUFFIX=${SUFFIX:-$RANDOM}
RG=${RG:-rg-medwatch}
LOC=${LOC:-brazilsouth}
az group create -n "$RG" -l "$LOC"
az cognitiveservices account create -n "medwatch-speech-$SUFFIX" -g "$RG" -l "$LOC" \
  --kind SpeechServices --sku S0 --yes
az cognitiveservices account create -n "medwatch-lang-$SUFFIX" -g "$RG" -l "$LOC" \
  --kind TextAnalytics --sku S --yes
az storage account create -n "medwatch$SUFFIX" -g "$RG" -l "$LOC" --sku Standard_LRS
CONN=$(az storage account show-connection-string -n "medwatch$SUFFIX" -g "$RG" -o tsv)
az storage container create --name media --connection-string "$CONN"
echo "AZURE_SPEECH_KEY=$(az cognitiveservices account keys list -n medwatch-speech-$SUFFIX -g $RG --query key1 -o tsv)"
echo "AZURE_SPEECH_REGION=$LOC"
echo "AZURE_LANGUAGE_KEY=$(az cognitiveservices account keys list -n medwatch-lang-$SUFFIX -g $RG --query key1 -o tsv)"
echo "AZURE_LANGUAGE_ENDPOINT=$(az cognitiveservices account show -n medwatch-lang-$SUFFIX -g $RG --query properties.endpoint -o tsv)"
echo "AZURE_STORAGE_CONNECTION_STRING=$CONN"
```

  Notas no README: (a) se a criação do recurso Language falhar pedindo aceite de termos de IA responsável, crie-o uma vez pelo portal; (b) se algum recurso (ex.: entidades de saúde) não estiver disponível em `brazilsouth`, use `LOC=eastus` e somente dados sintéticos/públicos; (c) as SKUs gratuitas (`F0`) podem ser usadas se disponíveis, com limites menores; (d) criar alerta de orçamento no portal.

- **`scripts/check_azure.py`:** lê `.env`; (1) sintetiza nada, apenas transcreve `data/samples/hello_ptbr.wav` se existir, senão imprime instrução; (2) chama `analyze_sentiment(["Estou com falta de ar e muito cansado."], language="pt")` e imprime o resultado; (3) se `STORAGE_BACKEND=azure`, faz upload e download de um arquivo de teste. Sai com código 0 se tudo OK, 1 caso contrário, imprimindo qual serviço falhou.
- **Aceite:** script existe e roda com `USE_FAKE_AZURE=true` imprimindo "modo fake". **[HUMANO]** roda com chaves reais.

---

### Fase 1 — Ingestão e simulação

#### T06 — API: pacientes, upload de mídia e documentos

- **Depende de:** T03, T04.
- **Arquivos:** `api/main.py`, `api/routes_media.py`, `api/routes_patients.py`, `api/routes_alerts.py` (stub), `tests/test_api_media.py`.
- **Passos:**
  1. `main.py`: cria `FastAPI(title="MedWatch")`, inclui os routers, configura CORS liberado (demo), `setup_logging("api")`, rota `/health`.
  2. `POST /patients`, `GET /patients`, `GET /patients/{id}` usando `db.py`.
  3. `POST /media`:
     - Validar `kind ∈ {video, audio, document}`; para `video`, `mode ∈ {physio, surgery, bed}` obrigatório; `exercise` obrigatório se `mode=physio` e deve existir em `exercises.yaml`; `camera` padrão `default_bed` ou `default_surgery` conforme o modo.
     - Validar extensão: vídeo `.mp4 .mov .avi .mkv`; áudio `.wav .mp3 .m4a .ogg`; documento `.txt .md`. Erro 422 com mensagem clara caso contrário.
     - Paciente precisa existir (404 caso contrário).
     - Gerar `media_id = uuid4()`, salvar o upload num arquivo temporário, enviar ao storage com a chave da convenção, inserir em `media` (`status=queued`), publicar `MediaJob` em `jobs.video` / `jobs.audio` / `jobs.text`.
     - `recorded_at` padrão: agora (UTC).
     - Retornar 202 `{media_id, status: "queued"}`.
  4. `POST /documents`: salva o texto em `.txt` no storage e segue o mesmo fluxo com `kind=document`.
  5. `GET /media`, `GET /media/{id}` (inclui `transcript` se existir).
  6. `GET /files/{key:path}`: `StreamingResponse(storage.open_stream(key))` com `media_type` por `mimetypes.guess_type`. Bloquear `..` no caminho (400).
  7. Injete `Bus` e `Storage` via dependências do FastAPI (`Depends`) para poder substituir nos testes.
- **Testes:** `TestClient` com fakeredis, `LocalStorage` em `tmp_path` e banco real (pular se indisponível): upload de áudio válido retorna 202 e gera mensagem em `jobs.audio`; extensão inválida retorna 422; paciente inexistente retorna 404; `mode=physio` sem `exercise` retorna 422.
- **Aceite:** testes passam; `curl -F file=@x.wav -F patient_id=P-0001 -F kind=audio localhost:8000/media` funciona com o compose no ar.

#### T07 — Simulador de stream (sintético e MIMIC-IV Demo)

- **Depende de:** T04.
- **Arquivos:** `simulator/synthetic.py`, `simulator/mimic.py`, `simulator/replay.py`, `scripts/seed.py`, `scripts/download_mimic_demo.sh`, `scripts/prepare_mimic.py`, `tests/test_synthetic.py`.
- **`synthetic.py`** — geração determinística (sempre `numpy.random.default_rng(seed)`):
  - `generate_patient_timeline(patient_id, start, minutes, scenario, seed) -> tuple[list[VitalObservation], list[PrescriptionEvent], list[MovementSample], list[dict]]` — o quarto item é a lista de **rótulos de verdade** `{patient_id, type, ts_start, ts_end}` para avaliação.
  - Uma observação de vitais por minuto; um `MovementSample` por minuto.
  - Linha de base por paciente (sorteada uma vez): `hr~N(75,8)`, `sbp~N(120,10)`, `dbp~N(75,7)`, `spo2~N(97.5,0.8)` limitado a 100, `rr~N(15,2)`, `temp~N(36.7,0.3)`.
  - Ruído AR(1): `x_t = base + 0.8*(x_{t-1}-base) + e_t`, com desvio de `e_t`: hr 2.0, sbp 3.0, dbp 2.0, spo2 0.4, rr 0.8, temp 0.05.
  - Movimento: dia (07–22 h) `activity~N(30,10)` limitado a [0,100]; noite `N(5,3)`; `in_bed=True` exceto ocasionalmente de dia.
  - Cenários (cada um injeta alterações a partir de `onset_min`, sobrescrevendo a série):

| Cenário | Alteração | Rótulos |
|---|---|---|
| `normal` | nenhuma | — |
| `respiratory_deterioration` | durante 60 min: spo2 97→87, rr 15→28, hr 78→118 (linear), `on_oxygen=True` após 40 min | `respiratory_deterioration` |
| `hypotension` | sbp 120→82 e hr +25 em 45 min | `hypotension` |
| `tachy_spike` | hr = 155 por 3 min | `tachy_spike` |
| `sensor_artifact` | um ponto com spo2 = 0 e outro com hr = 400 | `sensor_artifact` (não deve gerar alerta) |
| `night_agitation` | entre 01:00 e 02:30, activity ~ N(85,8) e `in_bed=False` por 10 min | `night_agitation` |
| `inactivity` | 150 min com activity 0–2 durante o dia | `inactivity` |
| `rx_risky` | start de heparina; 2 h depois start de cetorolaco (interação); 6 h depois insulina dose 10→20 (change) | `rx_interaction`, `rx_dose_change` |
| `demo` | combinação para a apresentação, ver seção 7 | todos os aplicáveis |

  - Prescrições de base para todos: 2–3 medicamentos comuns (dipirona, omeprazol, ceftriaxona) com `action=start` no início.
- **`mimic.py`** (opcional, mas recomendado para o relatório):
  - `scripts/download_mimic_demo.sh`: `wget -r -N -c -np https://physionet.org/files/mimic-iv-demo/2.2/ -P data/mimic` (acesso aberto, sem credenciamento).
  - `scripts/prepare_mimic.py`: lê `icu/chartevents.csv.gz` filtrando `itemid` — FC `220045`, PAS não invasiva `220179`, PAD `220180`, SpO₂ `220277`, FR `220210`, temperatura °F `223761` (converter para °C: `(F-32)*5/9`). Pivotar por `subject_id` e `charttime` arredondado para 5 min. Lê `hosp/prescriptions.csv.gz` (`subject_id, starttime, drug, dose_val_rx, dose_unit_rx, route`). Grava `data/mimic/vitals.parquet` e `data/mimic/prescriptions.parquet` com `patient_id = "M-" + subject_id`.
  - `mimic.py` expõe `load_mimic(limit_patients: int) -> (vitals, prescriptions)` como listas dos modelos de contrato.
- **`replay.py`** (`python -m medwatch.simulator.replay`):
  - Lê `SIM_SCENARIO`, `SIM_PATIENTS`, `SIM_SPEEDUP`.
  - Com `SIM_SCENARIO=demo`: pacientes `P-0001..P-0005` (garante que existem via `db.upsert_patient`), com a linha do tempo da seção 7.1. Com `SIM_SCENARIO=mimic`: usa `load_mimic`. Com qualquer outro nome de cenário: aplica esse cenário a `SIM_PATIENTS` pacientes, 24 h cada.
  - Junta todos os eventos, ordena por `ts` e publica em tempo acelerado: espera `(ts_i - ts_{i-1}).total_seconds() / speedup` entre eventos (agrupe eventos do mesmo `ts`).
  - **Velocidade por fase:** o replay aceita uma lista de fases `[(minuto_simulado_inicial, speedup), ...]`. Padrão: `[(0, SIM_SPEEDUP)]`. No cenário `demo`: `[(0, 60), (360, 6)]` — as primeiras 6 h simuladas passam em 6 min reais (histórico) e depois o tempo corre a 6x, para que o processamento de áudio e vídeo (30–90 s reais) caiba nas janelas da fusão.
  - Início do tempo simulado: no `demo`, o dia anterior às 19:00 UTC (assim o minuto 360 cai às 01:00 UTC, dentro do horário noturno); nos demais cenários, `utcnow() - 24h` arredondado para o minuto. Opção `--start` (ISO) sobrescreve.
  - A cada minuto simulado, grava em Redis a chave `sim:clock` com o `ts` atual (usado por `run_demo.py`).
  - Grava os rótulos de verdade em `data/storage/ground_truth/<scenario>.json`.
  - Flag `--fast` (publica tudo sem espera; usado em avaliação).
- **`scripts/seed.py`:** cria os pacientes `P-0001..P-0005` com nomes fictícios ("Paciente 01", leito "UTI-01" etc.).
- **Testes:** mesma seed gera exatamente a mesma série; `respiratory_deterioration` termina com spo2 < 90 e rr > 25; `normal` mantém spo2 ≥ 94 em 99% dos pontos; rótulos de verdade presentes.
- **Aceite:** `docker compose --profile demo up simulator` publica mensagens (verificar com `redis-cli XLEN vitals`).

---

### Fase 2 — Anomalias em séries

#### T08 — Filtro fisiológico e NEWS2

- **Depende de:** T02.
- **Arquivos:** `anomaly/filters.py`, `anomaly/news2.py`, `tests/test_news2.py`.
- **`filters.py`:** `clean_observation(obs, bounds) -> tuple[VitalObservation, list[str]]`. Campos fora dos limites de `thresholds.vitals.physiologic_bounds` viram `None`; retorna também a lista de campos descartados (log em nível INFO).
- **Código de referência — `news2.py`:**

```python
def score_rr(v):
    if v <= 8: return 3
    if v <= 11: return 1
    if v <= 20: return 0
    if v <= 24: return 2
    return 3

def score_spo2(v):           # escala 1
    if v <= 91: return 3
    if v <= 93: return 2
    if v <= 95: return 1
    return 0

def score_sbp(v):
    if v <= 90: return 3
    if v <= 100: return 2
    if v <= 110: return 1
    if v <= 219: return 0
    return 3

def score_hr(v):
    if v <= 40: return 3
    if v <= 50: return 1
    if v <= 90: return 0
    if v <= 110: return 1
    if v <= 130: return 2
    return 3

def score_temp(v):
    if v <= 35.0: return 3
    if v <= 36.0: return 1
    if v <= 38.0: return 0
    if v <= 39.0: return 1
    return 2

def news2(obs: VitalObservation) -> dict:
    """Calcula NEWS2. Parâmetros ausentes são ignorados e listados em 'missing'."""
    params, missing = {}, []
    for name, fn in [("rr", score_rr), ("spo2", score_spo2), ("sbp", score_sbp),
                     ("hr", score_hr), ("temp", score_temp)]:
        v = getattr(obs, name)
        if v is None:
            missing.append(name)
        else:
            params[name] = fn(v)
    params["consciousness"] = 0 if obs.consciousness == "A" else 3
    params["oxygen"] = 2 if obs.on_oxygen else 0
    total = sum(params.values())
    if total >= 7:
        band = "high"
    elif total >= 5:
        band = "medium"
    elif any(s == 3 for s in params.values()):
        band = "low_medium"
    else:
        band = "low"
    return {"total": total, "band": band, "params": params, "missing": missing}
```

- **Testes (obrigatórios):**
  - rr16, spo2 98, sbp120, hr70, temp37, A, ar ambiente → total 0, banda `low`.
  - rr26 e demais normais → total 3, banda `low_medium`.
  - hr115 (2) + spo2 94 (1) + rr22 (2), demais normais → total 5, `medium`.
  - rr25, spo2 91, sbp95, hr115, temp38.5, A, O₂ → 3+3+2+2+1+0+2 = 13, `high`.
  - Valores de fronteira: rr 8→3, 9→1, 20→0, 21→2; spo2 96→0, 95→1; sbp 111→0, 110→1; hr 90→0, 91→1; temp 38.0→0, 38.1→1.
  - `clean_observation` com spo2=0 retorna spo2=None e `["spo2"]`.
- **Aceite:** testes passam.

#### T09 — Estatística em streaming (EWMA z-score)

- **Depende de:** T02.
- **Arquivos:** `anomaly/streaming_stats.py`, `tests/test_streaming_stats.py`.
- **Código de referência:**

```python
import math

class EwmaZ:
    """Média e variância exponenciais; z calculado ANTES de atualizar."""
    def __init__(self, alpha: float = 0.1, warmup: int = 20):
        self.alpha, self.warmup = alpha, warmup
        self.mean: float | None = None
        self.var = 0.0
        self.n = 0

    def update(self, x: float) -> float:
        if self.mean is None:
            self.mean, self.n = x, 1
            return 0.0
        diff = x - self.mean
        z = diff / math.sqrt(self.var) if self.n >= self.warmup and self.var > 1e-6 else 0.0
        incr = self.alpha * diff
        self.mean += incr
        self.var = (1 - self.alpha) * (self.var + diff * incr)
        self.n += 1
        return z

class Cooldown:
    """Controla reemissão por chave usando tempo do evento."""
    def __init__(self):
        self.last: dict[tuple, datetime] = {}
    def ready(self, key: tuple, ts: datetime, minutes: float) -> bool:
        prev = self.last.get(key)
        if prev is None or (ts - prev).total_seconds() >= minutes * 60:
            self.last[key] = ts
            return True
        return False
```

- **Testes:** série constante com ruído pequeno e depois um degrau de +10 desvios → `|z| > 3` no degrau; nas primeiras `warmup` amostras z = 0; `Cooldown` bloqueia a segunda chamada dentro da janela e libera depois.
- **Aceite:** testes passam.

#### T10 — Isolation Forest para vitais

- **Depende de:** T07, T08.
- **Arquivos:** `anomaly/iforest.py`, `scripts/train_vitals_iforest.py`, `tests/test_iforest.py`.
- **Features** (função `build_features(history: list[VitalObservation]) -> np.ndarray | None`, usando a última observação e as 5 anteriores): `[hr, sbp, dbp, spo2, rr, temp, d_hr, d_sbp, d_spo2, d_rr]`, onde `d_x = x_t - média(x_{t-5..t-1})`. Retorna `None` se algum dos 6 valores atuais for `None` ou se houver menos de 6 observações.
- **Treino** (`scripts/train_vitals_iforest.py`):
  1. Gerar 20 pacientes `normal` × 48 h com `synthetic.py` (seeds 1–20). Opcional `--mimic` para incluir as primeiras 50% das observações de cada paciente do MIMIC.
  2. `IsolationForest(n_estimators=200, contamination="auto", random_state=42)` dentro de um `Pipeline` com `StandardScaler`.
  3. Limiar = percentil 0.5 de `score_samples` no treino (scores menores = mais anômalos).
  4. Salvar `models/vitals_iforest.joblib` e `models/vitals_iforest.json` com `{threshold, p01, p50, trained_at, n_samples}`.
- **Inferência** (`iforest.py`): classe `VitalsIForest` com `load()` e `score(features) -> tuple[bool, float]`. O score normalizado 0–1 é `clip((p50 - s) / (p50 - p01), 0, 1)`; é anomalia se `s < threshold`. Se o arquivo do modelo não existir, a classe fica desativada (loga um aviso uma vez e retorna `(False, 0.0)`).
- **Testes:** treinar com poucos dados no teste (fixture) e verificar que um ponto com hr=160, spo2=85 é anômalo e um ponto da base não é.
- **Aceite:** script gera os dois arquivos; testes passam.

#### T11 — Regras de prescrição

- **Depende de:** T02.
- **Arquivos:** `anomaly/prescriptions.py`, `tests/test_prescriptions.py`.
- **API:**

```python
def normalize_drug(name: str) -> str:
    """minúsculas, sem acento (unidecode), remove dose/unidade e conteúdo entre parênteses, colapsa espaços."""

class PrescriptionMonitor:
    def __init__(self, cfg: dict): ...
    def process(self, ev: PrescriptionEvent) -> list[Evidence]: ...
```

- **Estado por paciente:** `active: dict[drug_norm, PrescriptionEvent]` e `changes: deque[datetime]`.
- **Regras (na ordem):**
  1. `stop` → remove de `active`; nada a emitir.
  2. `rx_dose_change`: se o medicamento já está ativo e `dose` mudou, `ratio = new/old`; emite se `ratio >= dose_change_ratio_high` ou `ratio <= dose_change_ratio_low`. Score: `min(1, abs(log2(ratio)) / 2)`; severidade warning.
  3. `rx_high_alert_start`: `action=start` e o nome normalizado contém algum item de `high_alert`.
  4. Classe do medicamento: primeira classe em `classes` cuja lista contém um termo presente no nome normalizado.
  5. `rx_duplicate_class`: outro medicamento ativo da mesma classe.
  6. `rx_interaction`: para cada medicamento ativo, verificar pares em `interactions`, onde `a`/`b` podem ser nome de classe ou de medicamento; comparar nos dois sentidos. Score 0.7.
  7. `rx_change_burst`: registrar `ts` em `changes` (start e change), remover os mais antigos que 24 h; emitir se `len >= burst_changes_24h` (com cooldown de 12 h).
  8. Atualizar `active`.
- **Explicações em pt-BR**, por exemplo: `"Dose de insulina alterada de 10 para 20 UI (2,0x)"`, `"Heparina + cetorolaco: risco aumentado de sangramento"`.
- **Testes:** cenário `rx_risky` gera exatamente um `rx_interaction` e um `rx_dose_change`; `normalize_drug("Heparina Sódica 5000 UI (frasco)") == "heparina sodica"`; dose 10→12 não gera evidência.
- **Aceite:** testes passam.

#### T12 — Regras de movimentação

- **Depende de:** T02, T09.
- **Arquivos:** `anomaly/movement.py`, `tests/test_movement.py`.
- **API:** `class MovementMonitor: process(s: MovementSample) -> list[Evidence]`.
- **Regras** (limiares em `thresholds.movement`):
  - `movement_inactivity`: contar minutos consecutivos com `activity_count <= inactivity_activity_max` **fora** do horário noturno; ao atingir `inactivity_minutes`, emitir uma vez (rearmar quando a atividade voltar). Score `min(1, minutos / (2*inactivity_minutes))`.
  - `movement_night_agitation`: no horário noturno (atenção à virada da meia-noite: `hour >= night_start or hour < night_end`), limiar = maior entre `night_agitation_fixed` e o percentil 95 do histórico do paciente (se houver ≥ `night_agitation_min_history` amostras). Emitir com cooldown de 30 min.
  - `movement_bed_exit`: `in_bed` muda de `True` para `False` no horário noturno. Cooldown 30 min.
  - O horário usado é `ts` em UTC na demo (documentar em `DECISOES.md`; num hospital real seria o fuso local).
- **Testes:** cenário `inactivity` gera um `movement_inactivity`; `night_agitation` gera agitação e saída do leito; `normal` não gera nada.
- **Aceite:** testes passam.

#### T13 — Worker de anomalias

- **Depende de:** T08–T12, T04.
- **Arquivos:** `anomaly/worker.py`, `tests/test_anomaly_worker.py`.
- **Comportamento:**
  - Consome `vitals`, `prescriptions`, `movement` com o grupo `worker-anomaly`.
  - Estado em memória por paciente: `deque(maxlen=60)` de observações, um `EwmaZ` por sinal vital, `Cooldown`, `PrescriptionMonitor`, `MovementMonitor`, último nível NEWS2 emitido e o `ts` dessa emissão.
  - Para cada `VitalObservation`:
    1. `clean_observation` → `news2` → `db.insert_vital(obs, total)`.
    2. NEWS2: emitir evidência quando a banda **sobe** em relação à última emitida, ou quando a banda continua ≥ `medium` e já se passaram `repeat_minutes`. Mapear banda → type: `low_medium → news2_low_medium`, `medium → news2_medium`, `high → news2_high`. Score: `min(1, total / 10)`. Severidade: `high → critical`, demais `warning`. Explicação: `"NEWS2 = 7 (alto): FR 3, SpO₂ 3, FC 1"` (listar só os parâmetros com pontos > 0).
    3. Z-score por sinal: se `|z| >= threshold` e o cooldown `(patient, vital)` permitir → `vital_zscore`, score `min(1, |z|/6)`. Explicação: `"SpO₂ 88% fora do padrão do paciente (z = -4,2)"`.
    4. Isolation Forest: se anômalo e cooldown permitir → `vital_iforest`.
  - Para `PrescriptionEvent`: `db.insert_prescription` e `PrescriptionMonitor.process`.
  - Para `MovementSample`: `db.insert_movement` e `MovementMonitor.process`.
  - Toda evidência é publicada em `evidence` (o worker **não** grava evidências no banco).
  - `source_ref`: `vitals:<patient_id>@<iso ts>`; `model_name`: `news2`, `ewma-z`, `iforest`, `rx-rules`, `movement-rules`.
  - Na inicialização: `setup_logging("worker-anomaly")`, carregar YAML, carregar o Isolation Forest.
- **Testes:** usar fakeredis; injetar a série do cenário `respiratory_deterioration` e verificar que surgem `news2_medium` e depois `news2_high` em `evidence`; com `sensor_artifact` não deve surgir nenhum `news2_*` nem `vital_zscore` provocado pelo ponto inválido. (Substitua `db` por um objeto falso via injeção de dependência: o worker recebe `db_module` como parâmetro com padrão `medwatch.db`.)
- **Aceite:** testes passam; com o compose e o simulador no ar, `redis-cli XLEN evidence` cresce.

---

### Fase 3 — Áudio e texto

#### T14 — Conversão de áudio e transcrição com Azure Speech

- **Depende de:** T05.
- **Arquivos:** `audio/convert.py`, `audio/speech.py`, `tests/test_speech_fake.py`.
- **`convert.py`:** `to_wav_16k_mono(src: Path, dst: Path) -> Path` executando `ffmpeg -y -i <src> -ac 1 -ar 16000 -sample_fmt s16 <dst>` via `subprocess.run(check=True, capture_output=True)`. Em caso de erro, lançar `RuntimeError` com o stderr do ffmpeg. `duration_seconds(wav) -> float` com `soundfile.info`.
- **`speech.py`:**

```python
@dataclass
class Segment:
    speaker: str
    text: str
    offset_s: float
    duration_s: float

class Transcriber(Protocol):
    def transcribe(self, wav_path: Path) -> list[Segment]: ...

class AzureTranscriber:
    def __init__(self, key: str, region: str, language: str): ...
    def transcribe(self, wav_path: Path) -> list[Segment]:
        import threading
        import azure.cognitiveservices.speech as speechsdk
        cfg = speechsdk.SpeechConfig(subscription=self.key, region=self.region)
        cfg.speech_recognition_language = self.language
        audio = speechsdk.audio.AudioConfig(filename=str(wav_path))
        tr = speechsdk.transcription.ConversationTranscriber(speech_config=cfg, audio_config=audio)
        segments: list[Segment] = []
        errors: list[str] = []
        done = threading.Event()

        def on_transcribed(evt):
            r = evt.result
            if r.reason == speechsdk.ResultReason.RecognizedSpeech and r.text:
                segments.append(Segment(r.speaker_id or "Unknown", r.text,
                                        r.offset / 1e7, r.duration / 1e7))

        def on_canceled(evt):
            details = getattr(evt, "error_details", None) or getattr(evt, "cancellation_details", None)
            if details and "EndOfStream" not in str(getattr(evt, "reason", "")):
                errors.append(str(details))
            done.set()

        tr.transcribed.connect(on_transcribed)
        tr.canceled.connect(on_canceled)
        tr.session_stopped.connect(lambda evt: done.set())
        tr.start_transcribing_async().get()
        finished = done.wait(timeout=max(120, duration_seconds(wav_path) * 3))
        tr.stop_transcribing_async().get()
        if errors and not segments:
            raise RuntimeError(f"Azure Speech falhou: {errors[0]}")
        if not finished:
            raise TimeoutError("Transcrição excedeu o tempo limite")
        return sorted(segments, key=lambda s: s.offset_s)

class FakeTranscriber:
    """Retorna segmentos fixos; usado quando USE_FAKE_AZURE=true."""
    def transcribe(self, wav_path: Path) -> list[Segment]:
        return [
            Segment("Guest-1", "Bom dia, como o senhor está se sentindo hoje?", 0.5, 3.0),
            Segment("Guest-2", "Estou com falta de ar e muito cansaço desde ontem.", 4.0, 4.5),
            Segment("Guest-1", "Teve febre ou dor no peito?", 9.0, 2.0),
            Segment("Guest-2", "Um pouco de dor no peito quando tusso.", 11.5, 3.5),
        ]

def get_transcriber() -> Transcriber:
    s = get_settings()
    if s.use_fake_azure:
        return FakeTranscriber()
    if not s.azure_speech_key:
        raise RuntimeError("AZURE_SPEECH_KEY ausente. Defina no .env ou use USE_FAKE_AZURE=true")
    return AzureTranscriber(s.azure_speech_key, s.azure_speech_region, s.speech_language)
```

  Observação: os nomes de atributos do evento de cancelamento variam entre versões do SDK; por isso o `getattr` defensivo. Se o SDK instalado expuser outro nome, ajuste e registre em `DECISOES.md`.

- **Testes:** `FakeTranscriber` retorna 4 segmentos ordenados; teste `@pytest.mark.azure` transcreve `data/samples/hello_ptbr.wav` e verifica texto não vazio.
- **Aceite:** testes (não-azure) passam.

#### T15 — Azure AI Language e termos críticos

- **Depende de:** T14.
- **Arquivos:** `audio/language.py`, `audio/terms.py`, `tests/test_language_fake.py`, `tests/test_terms.py`.
- **`terms.py`:** `find_critical_terms(text: str, terms_cfg) -> list[dict]` → normaliza texto e termos (minúsculas + `unidecode`) e busca com regex `\b<termo>\b`. Retorna `{term, category, weight, start}` sem duplicatas por termo.
- **`language.py`:**

```python
@dataclass
class LanguageResult:
    sentiments: list[dict]       # por documento: {sentiment, positive, neutral, negative}
    key_phrases: list[list[str]]
    health_entities: list[list[dict]]  # {text, category, confidence}
    health_supported: bool

class LanguageAnalyzer(Protocol):
    def analyze(self, texts: list[str]) -> LanguageResult: ...

class AzureLanguageAnalyzer:
    def __init__(self, endpoint: str, key: str, language: str):
        from azure.ai.textanalytics import TextAnalyticsClient
        from azure.core.credentials import AzureKeyCredential
        self.client = TextAnalyticsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        self.language = language

    def analyze(self, texts: list[str]) -> LanguageResult:
        docs = [t[:5000] for t in texts if t.strip()]
        sentiments, phrases, entities = [], [], []
        health_supported = True
        for batch in _chunks(docs, 10):           # limite de 10 documentos por chamada
            for d in self.client.analyze_sentiment(batch, language=self.language):
                if d.is_error:
                    sentiments.append({"sentiment": "unknown", "positive": 0, "neutral": 0, "negative": 0})
                else:
                    cs = d.confidence_scores
                    sentiments.append({"sentiment": d.sentiment, "positive": cs.positive,
                                       "neutral": cs.neutral, "negative": cs.negative})
            for d in self.client.extract_key_phrases(batch, language=self.language):
                phrases.append([] if d.is_error else list(d.key_phrases))
            if health_supported:
                try:
                    poller = self.client.begin_analyze_healthcare_entities(batch, language=self.language)
                    for d in poller.result():
                        entities.append([] if d.is_error else [
                            {"text": e.text, "category": e.category, "confidence": e.confidence_score}
                            for e in d.entities])
                except Exception as exc:          # idioma ou região sem suporte
                    log.warning("Entidades de saúde indisponíveis: %s", exc)
                    health_supported = False
        if not health_supported:
            entities = [[] for _ in docs]
        return LanguageResult(sentiments, phrases, entities, health_supported)
```

  - `FakeLanguageAnalyzer`: sentimento `negative` (0.8) se o texto contiver "dor", "falta de ar" ou "cansa"; senão `neutral`; frases-chave = primeiras 3 palavras com mais de 4 letras; entidades de saúde = termos críticos encontrados com categoria `SymptomOrSign`.
  - `get_language_analyzer()` análogo a `get_transcriber()`.
- **Testes:** termos com acento e maiúsculas são encontrados ("Falta de AR" → "falta de ar"); fake retorna negativo para a frase de exemplo; teste `azure` chama o serviço real.
- **Aceite:** testes passam.

#### T16 — Features acústicas e linha de base de voz

- **Depende de:** T14.
- **Arquivos:** `audio/acoustic.py`, `scripts/build_voice_baseline.py`, `tests/test_acoustic.py`.
- **`acoustic.py`:**
  - `extract_features(wav: Path, segments: list[Segment], patient_speaker: str | None) -> dict`:
    - `y, sr = librosa.load(wav, sr=16000)`.
    - Se `patient_speaker` for informado, concatenar só os trechos desse falante (por `offset_s`/`duration_s`) num arquivo temporário e usar esse áudio no resto da função.
    - `intervals = librosa.effects.split(y, top_db=30)`; `voiced_s = soma das durações`; `pause_ratio = 1 - voiced_s / duração_total`.
    - `speech_rate_wpm = palavras / (soma de duration_s dos segmentos considerados / 60)`.
    - openSMILE: `opensmile.Smile(feature_set=opensmile.FeatureSet.eGeMAPSv02, feature_level=opensmile.FeatureLevel.Functionals).process_file(str(wav))` e extrair as colunas: `F0semitoneFrom27.5Hz_sma3nz_amean`, `F0semitoneFrom27.5Hz_sma3nz_stddevNorm`, `jitterLocal_sma3nz_amean`, `shimmerLocaldB_sma3nz_amean`, `HNRdBACF_sma3nz_amean`, `loudness_sma3_amean`. Se alguma coluna não existir na versão instalada, registrar `None` e seguir.
    - Retornar dict plano com essas chaves (nomes curtos: `f0_mean`, `f0_var`, `jitter`, `shimmer_db`, `hnr`, `loudness`, `pause_ratio`, `speech_rate_wpm`, `duration_s`).
  - `assess_voice(features, baseline: dict | None, cfg) -> list[tuple[str, float, dict]]` → lista de `(type, score, flags)`:
    - **Fadiga** (`voice_fatigue`): flags `slow_speech` (wpm < `speech_rate_wpm_min`), `many_pauses` (pause_ratio > `pause_ratio_max`), `low_loudness` (z < -z_threshold, se houver baseline). Emitir se ≥ 2 flags. Score = flags / 3.
    - **Indicador de disartria** (`voice_dysarthria_indicator`): só com baseline; flags `jitter_high`, `shimmer_high` (z > z_threshold), `hnr_low` (z < -z_threshold), `f0_monotone` (`f0_var` z < -z_threshold). Emitir se ≥ 2 flags. Score = flags / 4.
    - Sem baseline: avaliar só fadiga e registrar `"baseline_missing": true` no payload.
- **`scripts/build_voice_baseline.py --input data/samples/voice_healthy/*.wav`:** extrai features de gravações de voz saudáveis (o grupo grava 5–10 leituras) e salva `data/references/voice_baseline.json` com média e desvio de cada feature. O z de uma feature é `(x - média) / max(desvio, 1e-6)`.
- **Testes:** gerar um WAV sintético (seno 150 Hz com silêncios) via numpy + soundfile em `tmp_path`; `pause_ratio` entre 0 e 1; `assess_voice` com features fabricadas aciona fadiga quando wpm=70 e pause_ratio=0.5. O teste com openSMILE pode ser `slow`.
- **Aceite:** testes passam.

#### T17 — Sons respiratórios (modelo AudioSet)

- **Depende de:** T14.
- **Arquivos:** `audio/events.py`, `tests/test_events.py`.
- **Implementação:**

```python
class RespiratoryEventDetector:
    MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
    def __init__(self, cfg: dict):
        from transformers import pipeline
        self.clf = pipeline("audio-classification", model=self.MODEL, top_k=15)
        self.cfg = cfg
    def detect(self, wav: Path) -> list[dict]:
        """Retorna [{label, max_score, windows:[{t_start, score}]}] para rótulos-alvo."""
        y, sr = librosa.load(wav, sr=16000)
        win, hop = int(self.cfg["window_s"] * sr), int(self.cfg["hop_s"] * sr)
        hits: dict[str, list] = {}
        for start in range(0, max(1, len(y) - win + 1), hop):
            chunk = y[start:start + win].astype("float32")
            for p in self.clf({"raw": chunk, "sampling_rate": sr}):
                if p["label"] in self.cfg["labels"] and p["score"] >= self.cfg["min_score"]:
                    hits.setdefault(p["label"], []).append({"t_start": start / sr, "score": p["score"]})
        return [{"label": k, "max_score": max(w["score"] for w in v), "windows": v} for k, v in hits.items()]
```

  - Áudios menores que uma janela devem ser processados como uma única janela (o `range` acima já garante uma iteração).
  - O modelo é baixado no primeiro uso (≈ 350 MB) para o volume `hf-cache`.
  - Ignorar o rótulo `Breathing` sozinho (respiração normal); só emitir evidência para ele quando `max_score >= 0.6`. Documentar em `DECISOES.md`.
- **Testes:** o teste real é `slow` (usa um WAV de tosse em `data/samples/`, se existir; senão `pytest.skip`). Um teste rápido substitui `self.clf` por uma função falsa e verifica a agregação por janelas.
- **Aceite:** testes rápidos passam.

#### T18 — Workers de áudio e de texto

- **Depende de:** T14–T17, T13 (padrão de worker).
- **Arquivos:** `audio/worker.py`, `text/worker.py`, `tests/test_audio_worker.py`, `tests/test_text_worker.py`.
- **`audio/worker.py`** — para cada `MediaJob` de `jobs.audio`:
  1. `db.update_media(status="processing")`.
  2. Baixar do storage para um diretório temporário; converter para WAV 16 kHz mono.
  3. Transcrever (`get_transcriber()`).
  4. Analisar com `get_language_analyzer()` usando um documento por segmento (só do `patient_speaker`, se informado; senão todos).
  5. Termos críticos em cada segmento → uma evidência `speech_critical_term` por termo distinto (score = `weight` do termo; `ts_start = recorded_at + offset_s`; `payload.category` = categoria; explicação: `"Paciente relatou 'falta de ar' (01:04)"`).
  6. Sentimento: `negative_ratio` = fração de segmentos com sentimento `negative`. Se ≥ 0.5 → `speech_negative_sentiment` (score = `negative_ratio`).
  7. Entidades de saúde: se houver alguma, uma única evidência `clinical_entity` (info) com a lista.
  8. Features acústicas e `assess_voice` (baseline em `data/references/voice_baseline.json`, se existir).
  9. Sons respiratórios → uma evidência `respiratory_sound` por rótulo encontrado.
  10. `db.insert_transcript(media_id, language, segments, analysis)`, onde `analysis` contém: sentimentos, frases-chave, entidades, termos, features, eventos sonoros.
  11. Salvar `artifacts/<media_id>/analysis.json` no storage; `db.update_media(status="done", artifacts={"analysis": key})`.
  12. Publicar todas as evidências em `evidence` com `source_ref = media:<media_id>#t=<offset>`, `model_name` = `azure-speech+language`, `egemaps-rules` ou `ast-audioset`.
  13. Em exceção: `update_media(status="failed", error=str(exc))` e relançar (a mensagem fica pendente no stream; tudo bem).
  - Os modelos pesados (AST, openSMILE) são carregados **uma vez** na inicialização do worker.
  - `AUDIO_DISABLE_EVENTS=true` (`settings.audio_disable_events`) pula a T17 em máquinas fracas.
- **`text/worker.py`** — para `jobs.text`: ler o `.txt`, dividir em parágrafos (documentos ≤ 5000 caracteres), rodar `LanguageAnalyzer` e termos críticos; emitir `text_critical_term` e `clinical_entity` (modality `text`). Gravar `analysis.json` como artefato e atualizar o status.
- **Testes:** com `USE_FAKE_AZURE=true`, detector de eventos falso e um WAV sintético, o worker publica ao menos um `speech_critical_term` com `term="falta de ar"` e marca a mídia como `done` (db falso injetado).
- **Aceite:** testes passam; upload de áudio pela API com o compose no ar termina com status `done` e transcrição visível em `GET /media/{id}`.

---

### Fase 4 — Vídeo

#### T19 — Leitura de frames e wrappers de modelos

- **Depende de:** T02.
- **Arquivos:** `video/frames.py`, `video/models.py`, `tests/test_frames.py`.
- **`frames.py`:**

```python
@dataclass
class Frame:
    index: int          # índice no vídeo original
    t: float            # segundos desde o início
    image: np.ndarray   # BGR

def iter_frames(path: Path, target_fps: int) -> Iterator[Frame]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir o vídeo {path}")
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(src_fps / target_fps))
    i = 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if i % step == 0:
            yield Frame(i, i / src_fps, img)
        i += 1
    cap.release()

def video_info(path: Path) -> dict:  # {fps, frames, width, height, duration_s}
```

- **`models.py`:**

```python
@dataclass
class Detection:
    cls: str
    conf: float
    xyxy: tuple[float, float, float, float]   # pixels

@dataclass
class Person:
    track_id: int | None
    xyxy: tuple[float, float, float, float]
    keypoints: np.ndarray    # (17, 2) pixels
    kp_conf: np.ndarray      # (17,)

class Detector:
    def __init__(self, weights: str):
        from ultralytics import YOLO
        self.model = YOLO(weights)
    def __call__(self, img) -> tuple[list[Detection], object]:
        r = self.model.predict(img, verbose=False, conf=0.35)[0]
        names = r.names
        dets = [Detection(names[int(c)], float(p), tuple(map(float, b)))
                for b, c, p in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.cls.cpu().numpy(),
                                   r.boxes.conf.cpu().numpy())]
        return dets, r          # r é usado por annotate (r.plot())

class PoseEstimator:
    def __init__(self, weights: str):
        from ultralytics import YOLO
        self.model = YOLO(weights)
    def __call__(self, img) -> tuple[list[Person], object]:
        r = self.model.track(img, persist=True, verbose=False, conf=0.4)[0]
        people = []
        if r.keypoints is None or r.boxes is None:
            return people, r
        xy = r.keypoints.xy.cpu().numpy()
        conf = r.keypoints.conf.cpu().numpy() if r.keypoints.conf is not None else np.ones(xy.shape[:2])
        ids = r.boxes.id.cpu().numpy().astype(int) if r.boxes.id is not None else [None] * len(xy)
        for k, c, b, tid in zip(xy, conf, r.boxes.xyxy.cpu().numpy(), ids):
            people.append(Person(tid, tuple(map(float, b)), k, c))
        return people, r

def main_person(people: list[Person]) -> Person | None:
    """Pessoa com a maior bbox (vídeos de fisioterapia e leito têm um paciente principal)."""
```

  - Importante: `model.track(..., persist=True)` mantém estado entre chamadas. Crie **uma nova instância** de `PoseEstimator` para cada vídeo (ou chame `self.model.predictor = None` antes de um novo vídeo) para não misturar tracks.
- **T19b (opcional) — `openpose_cv.py`:** implementar `OpenPoseEstimator` com a mesma interface de `PoseEstimator`, usando `cv2.dnn.readNetFromCaffe` com o modelo COCO do OpenPose (arquivos `pose_deploy_linevec.prototxt` e `pose_iter_440000.caffemodel`, que o humano baixa para `models/openpose/`). Mapear os 18 pontos do OpenPose COCO para os 17 do formato COCO usado aqui (descartar o ponto "Neck", índice 1, e reordenar). Selecionável por `POSE_BACKEND=yolo|openpose`. Se os arquivos não existirem, lançar erro claro. Serve para a comparação no relatório; não é necessário para o restante funcionar.
- **Testes:** gerar um vídeo sintético de 2 s a 30 fps com `cv2.VideoWriter` em `tmp_path`; `iter_frames(target_fps=10)` retorna ~20 frames com `t` crescente. Testes com YOLO são `slow`.
- **Aceite:** testes rápidos passam.

#### T20 — Geometria, DTW, repetições e referência de exercício

- **Depende de:** T19.
- **Arquivos:** `video/geometry.py`, `video/dtw.py`, `video/reps.py`, `scripts/build_exercise_reference.py`, `tests/test_geometry.py`, `tests/test_dtw.py`, `tests/test_reps.py`.
- **`geometry.py`:**

```python
def joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Ângulo em b (graus) formado por a-b-c."""
    ba, bc = a - b, c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))

def trunk_angle(kp: np.ndarray) -> float:
    """Inclinação do tronco em relação à vertical: ponto médio dos ombros (5,6) vs. dos quadris (11,12)."""
    sh, hp = (kp[5] + kp[6]) / 2, (kp[11] + kp[12]) / 2
    v = sh - hp
    return float(np.degrees(np.arctan2(abs(v[0]), abs(v[1]) + 1e-9)))

def angle_series(people_per_frame: list[Person | None], joints: dict[str, list[int]],
                 min_conf: float) -> dict[str, np.ndarray]:
    """Uma série por articulação; NaN quando algum ponto tem confiança < min_conf. Depois interpola
    linearmente os NaN (pandas.Series.interpolate(limit_direction='both')) e aplica
    scipy.signal.medfilt(kernel_size=5)."""

def point_in_zone(pt_xy, polygon_norm, width, height) -> bool:
    """Converte o polígono normalizado para pixels e usa cv2.pointPolygonTest >= 0."""
```

- **`dtw.py`:**

```python
def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """DTW clássico; a e b com forma (n,) ou (n,k). Retorna custo / (n+m)."""
    a = a.reshape(len(a), -1); b = b.reshape(len(b), -1)
    n, m = len(a), len(b)
    D = np.full((n + 1, m + 1), np.inf); D[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = float(np.linalg.norm(a[i - 1] - b[j - 1]))
            D[i, j] = cost + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return float(D[n, m] / (n + m))

def resample(x: np.ndarray, n: int = 50) -> np.ndarray:
    """Reamostra linearmente para n pontos (np.interp)."""
```

- **`reps.py`:** `segment_reps(primary: np.ndarray, fps: float, prominence: float, min_distance_s: float) -> list[tuple[int, int]]`.
  - Encontrar os topos (posição estendida) com `scipy.signal.find_peaks(primary, prominence=prominence, distance=int(min_distance_s*fps))`.
  - Cada repetição vai de um topo ao próximo topo e precisa conter um vale com profundidade ≥ `prominence`. Retornar pares `(início, fim)` em índices da série.
  - Se houver menos de 2 topos, tentar a série invertida (exercícios como abdução, em que o ângulo **aumenta** durante o movimento) e documentar.
- **`scripts/build_exercise_reference.py --video correto.mp4 --exercise squat`:** roda pose em todos os frames, calcula as séries, segmenta as repetições, reamostra cada repetição de cada articulação para 50 pontos, salva `data/references/<exercise>.json` com `{exercise, fps, n_reps, mean_curves: {joint: [50 floats]}, rom: {joint: média de (max-min)}}`.
- **Testes:** ângulo reto = 90°; pontos colineares = 180°; `dtw_distance(x, x) == 0`; DTW de uma senoide e da mesma senoide deslocada é menor que o da senoide contra uma constante; `segment_reps` numa senoide sintética de 5 ciclos retorna 4 ou 5 repetições.
- **Aceite:** testes passam.

#### T21 — Análise de fisioterapia

- **Depende de:** T20.
- **Arquivos:** `video/physio.py`, `tests/test_physio.py`.
- **API:** `analyze_physio(people_per_frame, frame_times, fps, exercise_cfg, reference: dict | None, thr) -> PhysioResult` onde `PhysioResult` tem `reps: list[dict]`, `findings: list[dict]` (cada finding: `type, rep, t_start, t_end, score, payload, explanation`), `series: dict[str, list[float]]`.
- **Passos:**
  1. `angle_series` para todas as articulações do exercício.
  2. `segment_reps` na `primary_joint`.
  3. Para cada repetição *r*:
     - ROM de cada articulação = max − min no intervalo.
     - `physio_low_rom`: com referência, ROM < `rom_min_ratio × ref_rom` → score `1 - rom/ref_rom`. Sem referência, comparar com a mediana do ROM das repetições do próprio vídeo (ROM < 0.7 × mediana).
     - `physio_asymmetry`: para cada par em `pairs`, `|ROM_esq - ROM_dir| > asymmetry_max_deg` → score `min(1, diff/45)`.
     - `physio_pattern_deviation`: com referência, `dtw_distance(resample(curva da primary), mean_curves[primary]) > dtw_max` → score `min(1, dtw / (2*dtw_max))`.
     - `physio_trunk_compensation`: máximo de `trunk_angle` na repetição > `trunk_max_deg` → score `min(1, ângulo/60)`.
  4. Explicações, por exemplo: `"Rep. 3: amplitude do joelho esquerdo 62° (referência 95°)"`.
  5. Consolidação: se o mesmo tipo de achado ocorre em ≥ 50% das repetições, emitir **uma** evidência resumida (`payload.reps = [...]`), senão uma por repetição, com no máximo 5 por tipo.
- **Testes:** construir séries sintéticas de keypoints (pessoas falsas com coordenadas calculadas para gerar ângulos conhecidos) e verificar que ROM reduzido gera `physio_low_rom` e assimetria gera `physio_asymmetry`.
- **Aceite:** testes passam.

#### T22 — Análise de leito (queda, saída do leito, atividade)

- **Depende de:** T20.
- **Arquivos:** `video/bed.py`, `tests/test_bed.py`.
- **API:** `analyze_bed(people_per_frame, frame_times, width, height, zones, thr) -> BedResult` com `findings` e `activity_per_minute: list[tuple[float, float, bool]]` (segundo de início do minuto, activity 0–100, in_bed).
- **Regras:**
  - Para a pessoa principal em cada frame: `hip_y = média y dos pontos 11 e 12 / height`; `aspect = largura/altura da bbox`.
  - **Queda (`fall_detected`)**: existe *t* tal que `hip_y(t + window_s) - hip_y(t) >= hip_drop_min` e, a partir de `t + window_s`, `aspect >= lying_aspect_min` por pelo menos `lying_min_s`, e o quadril está **fora** da zona `bed` (se existir). Score 0.9. Guardar o frame do momento como JPEG no storage (`artifacts/<media_id>/fall_<t>.jpg`) — o worker faz o upload; a função só retorna o índice do frame.
  - **Saída do leito (`bed_exit_video`)**: quadril dentro da zona `bed` por ≥ 3 s e depois fora por ≥ 3 s.
  - **Atividade**: por frame, deslocamento médio dos keypoints confiáveis em relação ao frame anterior, dividido pela altura da bbox. Agregar por minuto de vídeo: `activity = clip(média / inactivity_motion_max * 10, 0, 100)`. `in_bed` = quadril dentro da zona na maior parte do minuto.
  - Sem pessoa detectada: atividade 0 e `in_bed=None`.
- **Testes:** sequência sintética de pessoa em pé (bbox alta) que cai (quadril desce 40% em 0,5 s e bbox fica larga por 3 s) gera `fall_detected`; pessoa parada não gera.
- **Aceite:** testes passam.

#### T23 — Análise de cirurgia (zonas e instrumentos)

- **Depende de:** T20.
- **Arquivos:** `video/surgery.py`, `tests/test_surgery.py`.
- **API:** `analyze_surgery(dets_per_frame, people_per_frame, frame_times, width, height, zones, thr) -> SurgeryResult`.
- **Regras:**
  - `surgery_zone_intrusion`: número de pessoas cujo centro da bbox está em `sterile_field` > `max_people_sterile` por ≥ 3 s seguidos. Uma evidência por episódio.
  - `surgery_instrument_out_of_zone`: detecção de classe em `instrument_classes` com centro fora de `instrument_tray` **e** fora de `sterile_field` por ≥ `instrument_out_min_s` seguidos.
  - `surgery_instrument_count_mismatch`: mediana da contagem de instrumentos nos primeiros `count_window_s` segundos ≠ mediana nos últimos `count_window_s` segundos dentro de `instrument_tray`. Score 0.8, severidade critical.
- **Limitação a documentar no relatório:** o YOLOv8 pré-treinado no COCO só conhece objetos genéricos (tesoura, faca). Para instrumentos cirúrgicos reais é preciso fine-tuning (ver T34, opcional).
- **Testes:** listas sintéticas de detecções cobrindo cada regra.
- **Aceite:** testes passam.

#### T24 — Vídeo anotado e worker de vídeo

- **Depende de:** T19–T23, T04.
- **Arquivos:** `video/annotate.py`, `video/worker.py`, `tests/test_video_worker.py`.
- **`annotate.py`:**
  - `AnnotatedWriter(path, fps, size)`: usa `cv2.VideoWriter(str(tmp), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)`. No `close()`, converte para H.264 compatível com navegador: `ffmpeg -y -i tmp.mp4 -c:v libx264 -pix_fmt yuv420p -movflags +faststart out.mp4`.
  - Para cada frame: começar de `result.plot()` (imagem anotada pelo Ultralytics) da pose (e da detecção, no modo surgery, desenhando as caixas por cima); desenhar os polígonos das zonas (`cv2.polylines`); escrever no canto superior o tempo e, durante ±1,5 s de cada achado, o texto do achado em vermelho.
- **`worker.py`** — para cada `MediaJob` de `jobs.video`:
  1. Status `processing`; baixar o vídeo; `video_info`.
  2. Instanciar `PoseEstimator` novo (e `Detector` se `mode == "surgery"`). O `Detector` pode ser compartilhado entre vídeos; o `PoseEstimator` não (por causa do tracking).
  3. Passagem 1: percorrer `iter_frames(target_fps)`, guardar por frame: pessoas, detecções, tempo; escrever o frame anotado (a anotação dos achados é feita numa passagem 2 sobre os mesmos frames, **ou** mais simples: guardar as imagens anotadas sem texto de achado em memória se o vídeo tiver ≤ 2 min; acima disso, refazer a leitura). Escolha registrada em `DECISOES.md`.
  4. Rodar a análise do modo (`physio`, `bed` ou `surgery`).
  5. Converter cada finding em `Evidence` (modality `video`, `ts_start = recorded_at + t_start`, `source_ref = media:<id>#t=<t_start>`, `model_name = "yolov8n-pose+rules"` ou `"yolov8n+rules"`).
  6. Modo `bed`: publicar `MovementSample(source="video")` para cada minuto em `movement`.
  7. Salvar no storage: `annotated.mp4`, `findings.json` (achados + séries de ângulos + reps), frames-chave em JPEG. Deixe uma função `build_session_report(media, findings) -> dict` que, nesta tarefa, retorna `{}`; ela é implementada na T29 e passa a gerar `report_html`/`report_pdf`.
  8. `update_media(status="done", artifacts={"annotated": key, "findings": key, **build_session_report(...)})`.
  9. Publicar as evidências.
- **Testes:** `slow`: processar um vídeo curto em `data/samples/` (se existir). Rápido: substituir os modelos por falsos que retornam uma pessoa fixa e verificar que o worker chega ao status `done` e grava `findings.json`.
- **Aceite:** upload de um vídeo de agachamento pela API gera vídeo anotado reproduzível no navegador e evidências no stream.

---

### Fase 5 — Fusão e alertas

#### T25 — Motor de fusão

- **Depende de:** T02.
- **Arquivos:** `config/fusion.yaml`, `fusion/engine.py`, `tests/test_fusion.py`.
- **`config/fusion.yaml`:**

```yaml
tau_minutes: 15            # decaimento: exp(-Δt/τ)
window_minutes: 360        # evidências mais antigas que isso (tempo do evento) são descartadas
levels: {critical: 70, warning: 40, info: 20}
default_weight_by_modality: {vitals: 0.4, prescription: 0.3, movement: 0.3, video: 0.3, audio: 0.3, text: 0.3}
weights:
  news2_low_medium: 0.45
  news2_medium: 0.65
  news2_high: 0.95
  vital_zscore: 0.40
  vital_iforest: 0.50
  rx_dose_change: 0.40
  rx_high_alert_start: 0.35
  rx_interaction: 0.60
  rx_duplicate_class: 0.30
  rx_change_burst: 0.40
  movement_inactivity: 0.35
  movement_night_agitation: 0.40
  movement_bed_exit: 0.50
  fall_detected: 0.95
  bed_exit_video: 0.50
  physio_low_rom: 0.25
  physio_asymmetry: 0.25
  physio_pattern_deviation: 0.30
  physio_trunk_compensation: 0.20
  surgery_zone_intrusion: 0.50
  surgery_instrument_out_of_zone: 0.40
  surgery_instrument_count_mismatch: 0.70
  speech_critical_term: 0.50
  speech_negative_sentiment: 0.20
  voice_fatigue: 0.35
  voice_dysarthria_indicator: 0.45
  respiratory_sound: 0.45
  clinical_entity: 0.10
  text_critical_term: 0.45
floor_critical: [news2_high, fall_detected, surgery_instrument_count_mismatch]
rules:
  - name: respiratorio_multimodal
    label: "Piora respiratória confirmada por sinais vitais e voz"
    window_minutes: 60
    all_of:
      - any_of: [{type: news2_medium}, {type: news2_high}, {type: vital_zscore, payload: {vital: spo2}},
                 {type: vital_zscore, payload: {vital: rr}}]
      - any_of: [{type: respiratory_sound}, {type: voice_fatigue},
                 {type: speech_critical_term, payload: {category: respiratorio}}]
    multiplier: 1.5
  - name: queda_com_sedativo
    label: "Queda em paciente com sedativo/opioide recente"
    window_minutes: 360
    all_of:
      - any_of: [{type: fall_detected}, {type: movement_bed_exit}, {type: bed_exit_video}]
      - any_of: [{type: rx_high_alert_start}, {type: rx_interaction}]
    multiplier: 1.4
  - name: neurologico
    label: "Sinais neurológicos em voz e movimento"
    window_minutes: 360
    all_of:
      - any_of: [{type: voice_dysarthria_indicator}, {type: speech_critical_term, payload: {category: neurologico}}]
      - any_of: [{type: physio_asymmetry}, {type: movement_inactivity}]
    multiplier: 1.4
labels:                    # rótulos pt-BR para títulos e dashboard
  news2_low_medium: "NEWS2 com parâmetro crítico"
  news2_medium: "NEWS2 médio"
  news2_high: "NEWS2 alto"
  vital_zscore: "Sinal vital fora do padrão"
  vital_iforest: "Padrão multivariado anômalo"
  rx_dose_change: "Mudança brusca de dose"
  rx_high_alert_start: "Medicamento de alta vigilância"
  rx_interaction: "Interação medicamentosa"
  rx_duplicate_class: "Duplicidade terapêutica"
  rx_change_burst: "Muitas alterações de prescrição"
  movement_inactivity: "Inatividade prolongada"
  movement_night_agitation: "Agitação noturna"
  movement_bed_exit: "Saída do leito à noite"
  fall_detected: "Queda detectada"
  bed_exit_video: "Saída do leito (vídeo)"
  physio_low_rom: "Amplitude reduzida"
  physio_asymmetry: "Assimetria de movimento"
  physio_pattern_deviation: "Padrão de movimento divergente"
  physio_trunk_compensation: "Compensação de tronco"
  surgery_zone_intrusion: "Excesso de pessoas no campo estéril"
  surgery_instrument_out_of_zone: "Instrumento fora da área"
  surgery_instrument_count_mismatch: "Contagem de instrumentos divergente"
  speech_critical_term: "Termo crítico na fala"
  speech_negative_sentiment: "Sentimento negativo na consulta"
  voice_fatigue: "Indícios de fadiga na voz"
  voice_dysarthria_indicator: "Indícios de alteração da fala"
  respiratory_sound: "Som respiratório anormal"
  clinical_entity: "Entidades clínicas"
  text_critical_term: "Termo crítico no laudo"
```

- **Algoritmo (`engine.py`):**

```python
@dataclass
class RiskResult:
    patient_id: str
    ts: datetime                   # tempo de referência (evento mais recente do paciente)
    risk: float                    # 0..100
    level: str                     # none | info | warning | critical
    contributions: list[dict]      # [{type, evidence_id, contrib, explanation}] ordenado desc
    rules_fired: list[str]
    floor_applied: bool

class FusionEngine:
    def __init__(self, cfg: dict): self.cfg = cfg; self.windows: dict[str, list[Evidence]] = {}
    def add(self, ev: Evidence) -> RiskResult:
        w = self.windows.setdefault(ev.patient_id, [])
        w.append(ev)
        t_ref = max(e.ts_start for e in w)
        horizon = t_ref - timedelta(minutes=self.cfg["window_minutes"])
        w[:] = [e for e in w if e.ts_start >= horizon]
        return self.compute(ev.patient_id, t_ref)

    def compute(self, patient_id: str, t_ref: datetime) -> RiskResult:
        ...
```

  Passos de `compute`:
  1. Para cada evidência: `weight = weights.get(type, default_weight_by_modality[modality])`; `decay = exp(-max(0, (t_ref - ts_start).minutes) / tau)`; `contrib = weight * score * decay`.
  2. **Por tipo, manter só a maior contribuição** (evita que evidências repetidas do mesmo tipo inflem o risco).
  3. `risk_raw = 1 - Π(1 - contrib)` sobre os tipos.
  4. Regras: uma regra dispara se, para cada item de `all_of`, existe ao menos uma evidência dentro de `window_minutes` antes de `t_ref` que case com algum item de `any_of` (casar = mesmo `type` e, se houver `payload`, todos os pares chave/valor iguais em `ev.payload`). Para cada regra disparada: `risk_raw = min(1, risk_raw * multiplier)`.
  5. `risk = round(100 * risk_raw, 1)`; nível pelos limiares de `levels` (≥ critical → `critical`, etc., senão `none`).
  6. Piso: se existe evidência de um tipo em `floor_critical` com `decay >= 0.5`, o nível passa a ser `critical` e `risk = max(risk, levels.critical)`; `floor_applied = True`.
- **Testes (obrigatórios):**
  - Uma evidência `news2_medium` score 0.6 em t0 → risco = 39.0 (0.65 × 0.6), nível `info`.
  - Mesma evidência repetida 5 vezes no mesmo t → risco igual ao de uma (máximo por tipo).
  - `news2_medium` (0.6) + `respiratory_sound` (0.8) no mesmo t: sem regra seria `1-(1-0.39)(1-0.36)=0.6096` → com a regra respiratória (×1.5) = 0.9144 → risco 91.4, `critical`.
  - Evidência com 30 min de idade e τ = 15: contribuição multiplicada por e⁻² ≈ 0.135.
  - `fall_detected` score 0.5 → nível `critical` por piso, risco ≥ 70.
  - Evidência mais antiga que `window_minutes` é descartada.
- **Aceite:** testes passam.

#### T26 — Worker de fusão (persistência de evidências e criação de alertas)

- **Depende de:** T25, T03, T04.
- **Arquivos:** `fusion/worker.py`, `tests/test_fusion_worker.py`.
- **Comportamento** — para cada `Evidence` de `evidence`:
  1. `db.insert_evidence(ev)`.
  2. `result = engine.add(ev)`; `db.insert_risk_snapshot(...)` com `contributions` (top 10).
  3. Decisão de alerta (`min_level = ALERT_MIN_LEVEL`):
     - Se `SEVERITY_ORDER[result.level] < SEVERITY_ORDER[min_level]` → nada.
     - Se existe alerta `open` para o paciente:
       - nível novo **maior** que o atual → `update_alert(level, risk_score, evidence_ids (união), summary, updated_at)` e publicar em `alerts` com `event="escalated"`;
       - senão → apenas atualizar `evidence_ids`, `risk_score` (se maior) e `updated_at`, **sem** publicar.
     - Se não existe alerta aberto: se o último alerta fechado do paciente tem `event_ts` a menos de `ALERT_COOLDOWN_MINUTES` (tempo de evento) e nível ≥ ao atual → nada. Caso contrário, criar `Alert` e publicar com `event="created"`.
  4. Título: `"[{NÍVEL}] {display_name} ({patient_id}) – {label da maior contribuição}"`. Nível em pt-BR: `CRÍTICO`, `ATENÇÃO`, `INFORMATIVO`.
  5. Resumo (multilinha): `"Risco {risk}/100."`, linha com as regras disparadas (`label`), e as 3 maiores contribuições no formato `"• {label}: {explanation}"`.
  6. Estado do motor é em memória. Na inicialização, **reidratar** a janela de cada paciente lendo do banco as evidências das últimas `window_minutes` relativas ao `max(ts_start)` do paciente (assim o worker pode reiniciar sem perder contexto).
- **Testes:** com fakeredis e db falso: sequência `news2_medium` + `respiratory_sound` cria um alerta `critical`; uma terceira evidência de menor peso não cria um novo alerta; evidência `info` isolada com `ALERT_MIN_LEVEL=warning` não cria alerta.
- **Aceite:** testes passam; com o simulador `demo` rodando, alertas aparecem em `GET /alerts` (após a T28).

#### T27 — Canais de alerta e escalonamento

- **Depende de:** T26.
- **Arquivos:** `alerts/channels.py`, `alerts/worker.py`, `tests/test_channels.py`.
- **`channels.py`:**
  - `ConsoleChannel` — sempre ativo; loga o título e o resumo.
  - `TeamsChannel(webhook_url)` — ativo se `TEAMS_WEBHOOK_URL` estiver definido. POST com `httpx` (timeout 10 s, 2 tentativas):

```python
def teams_payload(alert: Alert, dashboard_url: str) -> dict:
    color = {"critical": "Attention", "warning": "Warning", "info": "Accent"}[alert.level.value]
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.4",
                "body": [
                    {"type": "TextBlock", "text": alert.title, "weight": "Bolder",
                     "size": "Medium", "color": color, "wrap": True},
                    {"type": "TextBlock", "text": alert.summary, "wrap": True},
                    {"type": "FactSet", "facts": [
                        {"title": "Paciente", "value": alert.patient_id},
                        {"title": "Risco", "value": f"{alert.risk_score:.0f}/100"},
                        {"title": "Evento", "value": alert.event}]},
                ],
                "actions": [{"type": "Action.OpenUrl", "title": "Abrir no painel",
                             "url": f"{dashboard_url}/?patient={alert.patient_id}"}],
            },
        }],
    }
```

  - `EmailChannel(logic_app_url, to)` — ativo se ambos definidos. POST `{"to": ..., "subject": alert.title, "html": <resumo com <br>>}`.
  - Falha de um canal não impede os outros (try/except por canal, log de erro).
- **`worker.py`:**
  - Consome `alerts`; envia para todos os canais ativos. Em `event="escalated"`, prefixar o título com `"ESCALONADO: "`.
  - Thread/loop paralelo a cada 30 s: `db.alerts_to_escalate(ALERT_ESCALATION_MINUTES)` → reenviar com `"SEM RESPOSTA: "` no título e marcar `escalated=true`.
- **Testes:** `teams_payload` gera JSON com `attachments[0].content.type == "AdaptiveCard"`; com `httpx.MockTransport`, falha do Teams não impede o canal de e-mail.
- **Aceite:** testes passam. **[HUMANO]** configura o webhook do Teams e a Logic App (seção 6) e confirma o recebimento.

---

### Fase 6 — Saídas

#### T28 — API de leitura e confirmação de alertas

- **Depende de:** T06, T26.
- **Arquivos:** `api/routes_patients.py`, `api/routes_alerts.py`, `tests/test_api_read.py`.
- **Passos:** implementar as rotas restantes da seção 3.6.
  - `GET /patients/{id}/vitals`: se `since` não vier, usar `latest_event_ts(patient) - 6h`.
  - `POST /alerts/{id}/ack`: `decision=confirmed` → status `acknowledged`; `dismissed` → status `dismissed`. Grava `acked_by`, `acked_at`, `ack_note`. Retorna 409 se o alerta não estiver `open`.
  - Respostas em JSON com datas ISO 8601.
- **Testes:** ack de alerta aberto muda o status; segundo ack retorna 409; vitals respeitam `since`/`until`.
- **Aceite:** testes passam.

#### T29 — Relatórios (HTML e PDF)

- **Depende de:** T24 (sessão de vídeo), T28.
- **Arquivos:** `reports/render.py`, `reports/templates/video_report.html.j2`, `reports/templates/patient_report.html.j2`, rota `POST /reports/patient/{id}`, `tests/test_reports.py`.
- **`render.py`:**
  - `render_html(template: str, context: dict) -> str` com `jinja2.Environment(loader=PackageLoader("medwatch", "reports/templates"), autoescape=True)`.
  - `html_to_pdf(html: str) -> bytes | None` com `weasyprint.HTML(string=html).write_pdf()`; se o WeasyPrint não estiver disponível ou falhar, logar e retornar `None` (o HTML continua sendo entregue).
  - Imagens embutidas como data URI base64 (frames-chave, gráficos).
  - Gráficos: gerar PNG com matplotlib (backend `Agg`), por exemplo ângulo do joelho ao longo do tempo com as repetições marcadas.
  - Implementar `build_session_report` do worker de vídeo (T24) usando o template de sessão e salvando HTML e PDF em `artifacts/<media_id>/`.
- **Relatório de sessão de vídeo** — seções: cabeçalho (paciente, data, modo, exercício, duração), resumo (nº de repetições, nº de achados por tipo), tabela de achados (tempo, tipo, explicação), frames-chave, gráfico de ângulos, aviso fixo: *"Relatório gerado automaticamente para apoio à decisão. Requer revisão de profissional de saúde."*
- **Relatório do paciente** — risco atual, alertas das últimas 24 h, evidências por modalidade, gráfico de vitais (FC, SpO₂, FR) com as evidências marcadas.
- **Testes:** renderizar ambos os templates com contexto mínimo; o HTML contém o nome do paciente e o aviso; `html_to_pdf` retorna bytes começando com `%PDF` (marcar `slow` se o WeasyPrint não estiver instalado localmente).
- **Aceite:** relatórios gerados para um vídeo e um paciente de demonstração abrem corretamente.

#### T30 — Dashboard Streamlit

- **Depende de:** T28, T29.
- **Arquivos:** `dashboard/app.py`, `dashboard/api_client.py`.
- **`api_client.py`:** funções finas sobre `httpx` para todas as rotas usadas (base `API_BASE_URL`), com timeout de 10 s e tratamento de erro exibindo `st.error` com a mensagem da API.
- **Atenção:** `API_BASE_URL` (`http://api:8000`) só resolve dentro da rede do Docker, não no navegador do usuário. Por isso, vídeos, imagens e relatórios devem ser **baixados pelo servidor do Streamlit** (`api_client.get_file(key) -> bytes`) e entregues como bytes: `st.video(bytes)`, `st.image(bytes)`, `st.download_button(...)`. Nunca passe URLs da API para o navegador.
- **Layout (`app.py`)** — `st.set_page_config(page_title="MedWatch", layout="wide")`, navegação por `st.sidebar.radio` com quatro telas:
  1. **Painel geral**
     - Fragmento com `@st.fragment(run_every=5)` que recarrega `GET /patients` e `GET /alerts?status=open`.
     - Tabela de pacientes ordenada pelo risco: paciente, leito, risco (barra `st.progress`), nível (chip colorido: crítico vermelho, atenção âmbar, informativo azul), alertas abertos.
     - Lista de alertas abertos com botões **Confirmar** e **Descartar** (campo de nota opcional) chamando `POST /alerts/{id}/ack` com `user="medico.demo"`.
  2. **Paciente** — seletor de paciente (pré-selecionado por `st.query_params.get("patient")`, para o link do Teams funcionar):
     - Gráfico Plotly com 3 subplots compartilhando o eixo x (FC, SpO₂, FR) e marcadores verticais nas evidências de vitais.
     - Gráfico de risco ao longo do tempo (`/risk`) com linhas horizontais em 40 e 70.
     - Linha do tempo de evidências (tabela: hora, modalidade, tipo em pt-BR via `labels`, score, explicação).
     - Lista de mídias do paciente com status; para áudio, mostra a transcrição com os termos críticos destacados (`**negrito**`) e o sentimento por segmento; para vídeo, `st.video` do `annotated.mp4` (via `/files/...`) e link do relatório.
     - Botão **Gerar relatório do paciente**.
  3. **Enviar mídia** — formulário: paciente, tipo, modo/exercício/câmera (campos condicionais), `patient_speaker`, arquivo; envia para `POST /media`; mostra o `media_id` e acompanha o status a cada 3 s até `done`/`failed`.
  4. **Sobre** — descrição curta do sistema, diagrama (imagem `docs/arquitetura.png`, se existir) e o aviso de apoio à decisão.
- **Aceite:** com o compose e o simulador `demo` no ar, o painel atualiza sozinho, alertas aparecem e podem ser confirmados; upload de áudio e vídeo pela tela funciona.

---

### Fase 7 — Avaliação e entrega

#### T31 — Scripts de avaliação

- **Depende de:** T13, T21–T24, T18.
- **Arquivos:** `scripts/evaluate_vitals.py`, `scripts/evaluate_video.py`, `docs/resultados/`.
- **`evaluate_vitals.py`:**
  1. Gerar 30 pacientes (seeds 100–129), 24 h cada, cenários distribuídos: 10 `normal`, 5 `respiratory_deterioration`, 5 `hypotension`, 5 `tachy_spike`, 5 `sensor_artifact`.
  2. Rodar os detectores **diretamente** (sem Redis), em três configurações: só NEWS2; NEWS2 + z-score; NEWS2 + z-score + Isolation Forest.
  3. Uma detecção é verdadeiro positivo se ocorre dentro de `[ts_start, ts_end + 30 min]` de um rótulo; detecções fora de qualquer rótulo são falsos positivos; rótulos sem detecção são falsos negativos (o rótulo `sensor_artifact` não conta como positivo: qualquer detecção causada por ele é falso positivo).
  4. Métricas por configuração: precisão, recall, F1, atraso mediano (minutos entre `ts_start` do rótulo e a primeira detecção), falsos positivos por paciente-dia.
  5. Salvar `docs/resultados/vitals_metrics.csv`, `vitals_metrics.md` (tabela) e um gráfico PNG de um caso exemplo com as detecções marcadas.
- **`evaluate_video.py --annotations data/samples/video_annotations.csv`:** o CSV (preenchido pelo grupo) tem `video, t_start, t_end, type`. Rodar o pipeline de vídeo nos vídeos listados e calcular precisão/recall por tipo com tolerância de ±2 s. Salvar em `docs/resultados/video_metrics.md`.
- **Áudio:** documentar no relatório a avaliação qualitativa (transcrição vs. roteiro encenado) e o WER calculado manualmente ou com `jiwer` (opcional; registrar em `DECISOES.md` se adicionar).
- **Aceite:** os arquivos de resultado são gerados por um comando cada.

#### T32 — Roteiro automatizado da demonstração

- **Depende de:** T07, T30.
- **Arquivos:** `scripts/run_demo.py`, `data/samples/README.md`.
- **Comportamento:**
  1. Verifica `GET /health`.
  2. Cria os pacientes (`seed.py`).
  3. Inicia o simulador com `SIM_SCENARIO=demo` (subprocesso ou instrução para `docker compose --profile demo up simulator`).
  4. Lê `sim:clock` no Redis a cada segundo e, quando o minuto simulado atinge os valores da tabela 7.1, envia pela API os arquivos de `data/samples/` com `recorded_at = sim:clock`: vídeo de fisioterapia para P-0003, laudo para P-0002, áudio de consulta para P-0001, vídeo de queda para P-0004.
  5. Imprime no terminal cada etapa com horário, para guiar a gravação do vídeo.
- **`data/samples/README.md`:** lista os arquivos esperados e de onde vêm: `physio_squat_correct.mp4` e `physio_squat_wrong.mp4` (gravados pelo grupo ou do KIMORE/UI-PRMD), `bed_fall.mp4` (Le2i ou UR Fall), `consulta_p0001.wav` (encenada em pt-BR seguindo o roteiro da seção 7), `cough.wav` (trecho do AudioSet/Freesound com licença livre), `laudo_p0002.txt`, `hello_ptbr.wav`, `voice_healthy/*.wav`.
- **Aceite:** com as amostras presentes, `python scripts/run_demo.py` executa a demonstração completa sem intervenção.

#### T33 — README, documentação e relatório técnico

- **Depende de:** todas as anteriores.
- **Arquivos:** `README.md`, `docs/arquitetura.md`, `docs/relatorio-tecnico.md`.
- **README:** visão geral; requisitos (seção 9.1); passo a passo copiado da seção 9.7, em bash e PowerShell; problemas comuns (seção 9.9); como rodar os testes; estrutura de pastas; link do vídeo; aviso de uso.
- **`docs/arquitetura.md`:** diagrama (Mermaid), descrição de cada serviço, streams, tabelas e o catálogo de evidências.
- **`docs/relatorio-tecnico.md`** (estrutura obrigatória, alinhada ao enunciado):
  1. Introdução e objetivo.
  2. **Descrição do fluxo multimodal** (diagrama, sequência de um alerta, contrato de evidências).
  3. **Modelos aplicados por tipo de dado** — tabela: modalidade, modelo/serviço, entrada, saída, motivo da escolha, limitações (YOLOv8, YOLOv8-pose/OpenPose, DTW, Azure Speech, Azure AI Language, openSMILE, AST-AudioSet, NEWS2, EWMA, Isolation Forest, regras de prescrição, fusão noisy-OR).
  4. Integração com a Azure (recursos usados, região, custos observados, prints do portal).
  5. **Resultados obtidos** (tabelas da T31) e **exemplos de anomalias detectadas** (3 a 5 casos com prints: frame anotado, transcrição destacada, gráfico de vitais, alerta no Teams).
  6. Limitações, ética e LGPD.
  7. Próximos passos.
- **Aceite:** um colega consegue rodar o projeto do zero seguindo apenas o README.

#### T34 — Opcionais (só após T01–T33 completas)

- **T34a — Resumo do alerta com Azure OpenAI:** gerar um parágrafo a partir das evidências estruturadas (nunca de dados brutos), exibido junto ao resumo determinístico, com o rótulo "texto gerado por IA". Variáveis `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`, `AZURE_OPENAI_DEPLOYMENT`.
- **T34b — Fine-tuning do YOLOv8 para instrumentos cirúrgicos** com um dataset público (ex.: m2cai16-tool-locations), gerando `models/surgical_tools.pt` e `SURGERY_DET_WEIGHTS`.
- **T34c — Deploy em Azure Container Apps** (imagem no Azure Container Registry, PostgreSQL Flexible Server, Azure Cache for Redis), com script em `infra/`.
- **T34d — Comparação OpenPose × YOLOv8-pose** (requer T19b): tempo por frame e concordância dos ângulos em 3 vídeos, tabela no relatório.

### Fase 8 — Integração, dados reais e gravação

A T35 e a T36 vêm da revisão feita depois da T33: tudo foi testado só com unidades e modelos falsos, e a avaliação de vitais da T31 tem um erro de método. A T37 e a T38 vêm da preparação do vídeo de entrega: os datasets sugeridos no enunciado (PhysioNet e AudioSet) ainda não tinham sido usados, e a demonstração não cabia nos 15 minutos. Ordem: T35 → T36 → T37 → T38. A T34 continua opcional e **não** precisa ser feita antes delas.

#### T35 — Integração ponta a ponta (modo falso)

- **Objetivo:** provar que o sistema inteiro funciona junto, com `USE_FAKE_AZURE=true` e dados sintéticos, e corrigir o que quebrar. É a primeira vez que o Compose completo, os workers, o simulador, a API e o dashboard rodam juntos, e a primeira vez que YOLO, AST e openSMILE processam arquivos de verdade.
- **Depende de:** T01–T33.
- **Arquivos:** `docs/resultados/integracao.md` (novo) e qualquer arquivo de código que precisar de correção.
- **Regras desta tarefa:**
  - Rode tudo em primeiro plano. Se um comando estourar o tempo limite (o `docker compose build` pode passar de 10 minutos), rode-o de novo: o cache de camadas faz cada tentativa avançar.
  - Cada problema encontrado vira um passo: corrija, acrescente um teste que reproduza o erro quando for possível, faça o commit `T35 [wip]: corrige <o quê>` e registre no `integracao.md`.
  - Não altere o algoritmo do motor de fusão nem os limiares: isso é a T36.
- **Passos:**
  1. **Ambiente Python.** `.venv/bin/pip install "pyarrow<18"`; confirme `.venv/bin/python -c "import opensmile, pyarrow; print(pyarrow.__version__)"`; rode `.venv/bin/pytest -q` e `.venv/bin/ruff check .`. O teste da tela Paciente e o `test_mimic` que eram pulados por causa do pyarrow devem passar a rodar.
  2. **Imagem e modelos.** Confirme `USE_FAKE_AZURE=true` no `.env`. Rode `docker compose build` e depois `docker compose up models-init`, que precisa terminar com código 0 e deixar `models/yolov8n.pt` e `models/yolov8n-pose.pt`.
  3. **Stack completo.** `docker compose up -d`. Em `docker compose ps`, todos os serviços precisam estar `running`/`healthy` (e `models-init` com `exited (0)`). Para cada serviço, `docker compose logs --tail=50 <serviço>` não pode ter traceback. `curl -fsS localhost:8000/health` precisa responder `"status":"ok"`, e `curl -fsS localhost:8501/_stcore/health` precisa responder `ok`.
  4. **Pacientes e modelo de vitais.** `docker compose run --rm api python scripts/seed.py`, depois `docker compose run --rm api python scripts/train_vitals_iforest.py` e `docker compose restart worker-anomaly`.
  5. **Simulação de vitais, prescrições e movimento.** `docker compose --profile demo run --rm simulator python -m medwatch.simulator.replay --fast`. Depois confira:
     - `docker compose exec redis redis-cli XLEN vitals` e `XLEN evidence` maiores que zero, e `XPENDING evidence worker-fusion` sem acúmulo;
     - `curl -fsS "localhost:8000/alerts"` com alertas conforme a tabela abaixo.

     | Paciente | Esperado |
     |---|---|
     | P-0001 | alerta `critical` (piora respiratória; sem o áudio, pelo piso do `news2_high`) |
     | P-0002 | alerta `warning` ou maior (interação e mudança de dose) |
     | P-0003 | nenhum alerta (só cenário normal) |
     | P-0004 | alerta `warning` ou maior (agitação noturna e saída do leito) |
     | P-0005 | nenhum alerta (artefato de sensor filtrado) |

     Se o resultado divergir, descubra se é defeito (corrija) ou limitação do cenário (registre no `integracao.md`).
  6. **Mídias sintéticas.** Sem as amostras humanas, gere arquivos de teste:
     ```bash
     mkdir -p data/samples/sinteticos
     ffmpeg -y -f lavfi -i "sine=frequency=180:duration=20" -ac 1 -ar 16000 data/samples/sinteticos/tom.wav
     curl -fsSL https://ultralytics.com/images/bus.jpg -o data/samples/sinteticos/pessoas.jpg
     ffmpeg -y -loop 1 -i data/samples/sinteticos/pessoas.jpg -t 8 -r 10 -vf "scale=640:-2" -pix_fmt yuv420p data/samples/sinteticos/pessoas.mp4
     ```
     Envie pela API (com `curl -F`): o áudio como `kind=audio` para P-0001; o vídeo como `kind=video` três vezes, nos modos `physio` (exercício `squat`), `bed` e `surgery`, para P-0003. Em `GET /media/{id}`, cada um precisa terminar em `done` com os artefatos esperados; o `annotated.mp4` precisa ser H.264 (`ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0`). O vídeo tem pessoas paradas: o objetivo é exercitar o pipeline (YOLO, pose, anotação, relatório), não gerar achados clínicos. O áudio exercita o caminho com o transcritor falso, o openSMILE e o modelo AST reais.
  7. **Laudo.** `POST /documents` para P-0002 com um texto que contenha "falta de ar" e "dor no peito". Confira as evidências `text_critical_term` em `GET /patients/P-0002/evidence`.
  8. **Alertas.** Em `docker compose logs worker-alerts`, cada alerta criado aparece no canal de console. Confirme um alerta com `POST /alerts/{id}/ack` (`{"user": "teste", "decision": "confirmed"}`) e verifique `status=acknowledged`; um segundo ack precisa devolver 409. Para testar o escalonamento, suba com `ALERT_ESCALATION_MINUTES=1` (por exemplo, `docker compose run` ou ajuste temporário no `.env`, revertido no fim) e confira a mensagem `SEM RESPOSTA:` no log.
  9. **Relatórios e dashboard.** `POST /reports/patient/P-0001` precisa devolver as chaves de HTML e PDF, e `GET /files/<chave>` do PDF precisa começar com `%PDF`. Com o `ApiClient` do dashboard apontando para `http://localhost:8000`, chame as funções que as telas usam (pacientes, alertas, vitais, evidências, mídia) e confirme que nenhuma falha.
  10. **Roteiro da demo.** `python scripts/run_demo.py --external-simulator` (com `.venv/bin/python`) precisa rodar até o fim pulando as amostras ausentes, com aviso, sem traceback.
  11. **Registro.** Em `docs/resultados/integracao.md`: data, versão (hash do commit), uma tabela com cada verificação dos passos 1–10 (passou / falhou / corrigido / depende de humano), os alertas obtidos por paciente e a lista de defeitos corrigidos com o commit de cada um.
  12. **Limpeza.** Reverta qualquer ajuste temporário do `.env` e rode `docker compose down` (sem `-v`).
- **Aceite:** todas as verificações dos passos 1–10 passaram ou estão registradas como dependentes de passo humano; `pytest -q` e `ruff check .` passam; `integracao.md` commitado.

#### T36 — Avaliação de vitais corrigida e ajuste de limiares

- **Objetivo:** produzir números de avaliação confiáveis para o relatório. A T31 obteve precisão de 1% a 3% por dois motivos: (1) no gerador, a piora continua até o fim do dia, mas o rótulo termina no fim da rampa, então cada repetição do NEWS2 com o paciente ainda grave conta como falso positivo; (2) o z-score dispara em pacientes normais.
- **Depende de:** T35.
- **Arquivos:** `src/medwatch/simulator/synthetic.py`, `src/medwatch/anomaly/streaming_stats.py`, `src/medwatch/anomaly/worker.py`, `config/thresholds.yaml`, `scripts/evaluate_vitals.py`, os testes correspondentes, `docs/resultados/vitals_metrics.*`, `docs/resultados/vitals_tuning.md` (novo), `docs/relatorio-tecnico.md`.
- **Passos:**
  1. **Rótulos.** Nos cenários em que o estado alterado persiste (`respiratory_deterioration`, `hypotension`), o `ts_end` do rótulo passa a ser o fim da série. O `tachy_spike` continua com 3 minutos. Ajuste os testes do simulador.
  2. **Métrica por episódio.** No `evaluate_vitals.py`: um rótulo é TP se houver ao menos uma detecção em `[ts_start, ts_end + 30 min]`. Fora das janelas de rótulo, detecções do mesmo tipo com menos de 30 minutos entre si formam **um** episódio, e cada episódio conta como um falso positivo. Reporte também os falsos alarmes só dos pacientes `normal` (episódios por paciente-dia).
  3. **Avaliação no nível de alerta.** Passe as evidências de cada paciente, em ordem de tempo, por um `FusionEngine` com o `config/fusion.yaml`. Um alerta abre quando o nível chega a `warning` ou mais e fecha quando o risco fica abaixo de 20 por 60 minutos seguidos; cada abertura é um alerta. Calcule precisão, recall e atraso mediano dos alertas contra os rótulos, e alertas por paciente-dia nos pacientes `normal`. Esse é o número principal do relatório: é o que a equipe médica veria.
  4. **Persistência no z-score e no Isolation Forest.** Acrescente `persistence` (número de leituras consecutivas acima do limiar antes de emitir) em `thresholds.yaml` para `zscore` e `iforest`, com suporte no worker e teste. O valor padrão `1` reproduz o comportamento atual.
  5. **Busca de limiares.** Compare, no nível de alerta: z-score com limiar 3,0 / 3,5 / 4,0 × persistência 1 / 3; Isolation Forest com o limiar atual e com percentil 0,1 × persistência 1 / 3. Escolha a combinação com recall de 100% nos rótulos positivos e o menor número de alertas em pacientes normais. Grave a grade completa em `vitals_tuning.md` e os valores escolhidos em `thresholds.yaml`, com uma linha em `docs/DECISOES.md`.
  6. **Resultados.** Regere `vitals_metrics.md`, `vitals_metrics.csv` e `vitals_example.png`, com três blocos: por evidência (como antes, para comparação), por episódio e por alerta. Atualize a seção de resultados do `relatorio-tecnico.md`, explicando a mudança de método e mostrando antes × depois.
- **Aceite:** testes e lint passam; o relatório mostra a avaliação por alerta com recall de 100% nos positivos e menos de 1 alerta por paciente-dia nos pacientes normais. Se essa meta não for alcançável com os limiares da grade, registre o melhor resultado e o motivo no relatório, em vez de forçar o número.

#### T37 — Datasets públicos do enunciado com partes reservadas

- **Objetivo:** usar de fato os datasets sugeridos no enunciado (PhysioNet e AudioSet), que até a T36 só existiam no código, e separar em cada um uma parte **reservada**, nunca usada para ajustar nada, que serve para a demonstração e para o número final do relatório. Como não há vídeos reais de pacientes, é essa parte reservada que mostra o sistema funcionando com dados reais.
- **Depende de:** T36 (limiares ajustados e avaliação no nível de alerta).
- **Arquivos:** `scripts/download_datasets.py` (novo), `scripts/prepare_mimic.py`, `src/medwatch/simulator/mimic.py`, `src/medwatch/simulator/replay.py`, `scripts/train_vitals_iforest.py`, `scripts/evaluate_vitals.py` (ou `scripts/evaluate_mimic.py`, novo), `scripts/evaluate_audio_events.py` (novo), `config/splits.yaml` (novo), testes correspondentes, `docs/DATASETS.md` (novo), `docs/resultados/datasets.md` (novo), `docs/relatorio-tecnico.md`.
- **Regras desta tarefa:**
  - **Download só com `.venv/bin/python`** (`urllib` ou `httpx`) ou `curl`. Não dependa de `wget`, `unzip` nem de rodar scripts `.sh`: as permissões da VPS não liberam esses comandos. O pandas lê `.csv.gz` direto; para `.zip`, use o módulo `zipfile`.
  - Nada baixado vai para o Git (`data/` já é ignorado). Só vão para o Git os IDs das divisões, o código e os resultados agregados.
  - **O conjunto reservado não ajusta nada.** Limiares, modelos e parâmetros são escolhidos só com as partes de calibração e validação. Se depois de olhar o reservado for preciso mudar algo, registre em `docs/DECISOES.md` que o número ficou "contaminado" e não o apresente como resultado final.
  - Os testes unitários não podem depender dos downloads: use arquivos mínimos criados no próprio teste.
- **Passos:**
  1. **MIMIC-IV Demo (PhysioNet).** Acesso aberto, sem credenciamento, licença ODbL. `scripts/download_datasets.py --mimic` baixa de `https://physionet.org/files/mimic-iv-demo/2.2/` os arquivos `icu/chartevents.csv.gz` e `hosp/prescriptions.csv.gz` para `data/mimic/`, e então roda `prepare_mimic.py`. Registre em `docs/DATASETS.md`: versão, data do download, número de pacientes, linhas de vitais e o **intervalo mediano entre observações** por paciente. Os sinais vitais do MIMIC costumam ser horários, bem mais espaçados que o simulador de 1 minuto; isso precisa ficar escrito.
  2. **Divisão por paciente.** Ordene os `patient_id` do MIMIC, embaralhe com semente 42 e divida 60% / 20% / 20% em `calibracao`, `validacao` e `reservado`. Grave em `config/splits.yaml`. Divida **por paciente**, nunca por tempo dentro do mesmo paciente, para a linha de base de um paciente não vazar entre as partes.
  3. **Carregamento com divisão e datas realistas.** Em `load_mimic`, acrescente `split` (lê `config/splits.yaml`) e `rebase_start` (desloca as datas de cada paciente para que a primeira observação caia em `rebase_start`, mantendo os intervalos). O MIMIC tem as datas deslocadas para o futuro (anos como 2150), o que confunde o dashboard e o vídeo. No replay, aceite `--mimic-split <nome>`, usando o `--start` como `rebase_start`. Teste com um parquet mínimo.
  4. **Isolation Forest para dados reais.** O modelo atual foi treinado com dados sintéticos de 1 minuto, e as features (diferença para as 5 observações anteriores) mudam de sentido com observações horárias. Treine um modelo separado com a parte `calibracao`: `train_vitals_iforest.py --mimic-split calibracao --out models/vitals_iforest_mimic`, mantendo o modelo sintético. Escolha o limiar com a parte `validacao`. Documente como o worker escolhe o modelo (variável de ambiente nova em `.env.example` e na seção 3.1).
  5. **Carga de alarmes em dados reais.** Sem rótulos de anomalia no MIMIC, meça o que a equipe médica receberia: rode os detectores e a fusão offline, reaproveitando a avaliação por alerta da T36, nas partes `validacao` e `reservado`. Reporte alertas por paciente-dia, distribuição por nível e a frequência de NEWS2 alto, com 2 ou 3 exemplos explicados.
  6. **Recall com dados semissintéticos.** Na parte `reservado`, injete os cenários conhecidos (`respiratory_deterioration`, `hypotension`, `tachy_spike`) sobre a série real de cada paciente, em instantes sorteados com semente fixa, aplicando as rampas por cima dos valores reais. Isso gera rótulos de verdade sobre dados reais. Calcule precisão, recall e atraso mediano no nível de alerta. Qualquer parâmetro dessa injeção é escolhido na parte `validacao`.
  7. **Áudio (AudioSet ou alternativa).** O Google distribui o AudioSet só como IDs do YouTube; não baixe áudio do YouTube. Prefira clipes do **conjunto de avaliação** do AudioSet num espelho público que traga o áudio (por exemplo, no Hugging Face), conferindo licença e disponibilidade. Se não houver acesso viável, use o **ESC-50** (`https://github.com/karolpiczak/ESC-50`, licença CC BY-NC; `meta/esc50.csv` e `audio/*.wav` via `raw.githubusercontent.com`), que vem do Freesound e, portanto, é independente do treino do AST. Registre a escolha em `docs/DECISOES.md`.
     - Positivos: tosse, respiração, ronco e espirro (no ESC-50: `coughing`, `breathing`, `snoring`, `sneezing`). Negativos: 4 a 6 classes não respiratórias (por exemplo `clock_tick`, `keyboard_typing`, `door_wood_knock`, `rain`, `dog`). Cerca de 40 clipes de cada grupo.
     - Divisão: no ESC-50, respeite os `fold` (1–3 para calibração, 4–5 reservados); no AudioSet, 50% / 50% por clipe.
     - Calibre `audio_events.min_score` e a regra especial de `Breathing` só na calibração. Em `scripts/evaluate_audio_events.py`, reporte precisão e recall por classe na parte reservada.
  8. **Material para a demonstração.** Copie 2 ou 3 clipes reservados de tosse ou chiado para `data/samples/` (por exemplo `cough.wav`) e escolha 1 ou 2 pacientes reservados do MIMIC com eventos interessantes para o trecho "dados reais reservados" do vídeo. Registre a escolha e o motivo em `docs/DATASETS.md`.
  9. **Documentação.**
     - `docs/DATASETS.md`: fonte, versão, licença, data, tamanho, divisões e o uso de cada parte.
     - `docs/resultados/datasets.md`: os números da parte reservada.
     - `relatorio-tecnico.md`: reescreva a seção de dados (hoje cita o MIMIC sem tê-lo usado) e acrescente os resultados com dados reais, separando claramente sintético, semissintético e real.
- **Aceite:**
  - dados baixados e preparados;
  - `config/splits.yaml` commitado;
  - testes e lint passam sem depender dos downloads;
  - resultados da parte reservada documentados;
  - relatório sem afirmações sobre dados que não foram usados.

#### T38 — Preparação da gravação do vídeo

- **Objetivo:** deixar a demonstração gravável em até 15 minutos, reproduzível e com uma checagem prévia que diga o que está faltando. Hoje o cenário `demo` leva cerca de 26 minutos reais, e nada confere se as chaves, as amostras e os canais de alerta estão prontos antes de começar.
- **Depende de:** T35. Use os resultados da T36 e da T37 no roteiro, se já estiverem prontos.
- **Arquivos:** `src/medwatch/simulator/replay.py`, `scripts/run_demo.py`, `scripts/preflight_demo.py` (novo), `src/medwatch/dashboard/app.py`, testes correspondentes, `docs/ROTEIRO_VIDEO.md` (novo), README.
- **Passos:**
  1. **Velocidade do simulador.** Acrescente ao replay `--fast-until <minuto>` (publica sem espera até esse minuto simulado e depois segue as fases) e `--tail-speedup <fator>` (substitui a velocidade da fase final do `demo`). O `run_demo.py` repassa as duas opções. Meta: o trecho filmado, do minuto 360 ao 480, cabe em cerca de 10 minutos (por exemplo, `--fast-until 355 --tail-speedup 12` resulta em 125 minutos simulados ÷ 12 ≈ 10 minutos). Teste a função de velocidade e as opções.
  2. **Checagem prévia.** `scripts/preflight_demo.py` imprime uma lista com ✓ ou ✗ e termina com código 1 se faltar algo crítico. Ele confere:
     - a API (`/health`);
     - os workers consumindo: cada consumer group do Redis tem consumidor com `idle` baixo (`XINFO CONSUMERS`);
     - `USE_FAKE_AZURE=false`, chaves preenchidas e uma chamada real à Azure (reaproveite o `check_azure.py`);
     - `TEAMS_WEBHOOK_URL` e `LOGIC_APP_EMAIL_URL` preenchidos; com `--send-test`, envia uma mensagem de teste;
     - as amostras de `data/samples/README.md` presentes;
     - os modelos em `models/`;
     - o banco limpo: nenhuma evidência nem alerta e nenhuma linha `T-`, o que indica que o `docker compose down -v` foi feito antes.
     Teste com clientes falsos. Em modo falso, o script deve listar exatamente o que depende do humano.
  3. **Dashboard para a apresentação.** No cartão de alerta, mostre lado a lado o **risco de pico** do alerta e o **risco atual** do paciente, com esses nomes. Hoje aparece um número só ("risco 99"), enquanto a tabela de pacientes mostra o risco atual (por exemplo, 29), o que confunde no vídeo (ver `docs/resultados/integracao.md`). Ajuste o teste da tela.
  4. **Roteiro.** `docs/ROTEIRO_VIDEO.md` traz:
     - **Preparação:** `docker compose down -v`, subir o stack, `seed.py`, treino do modelo e `preflight_demo.py`, sem mostrar chaves na tela.
     - **Roteiro de cerca de 14 minutos**, minuto a minuto, cobrindo os 4 itens que o enunciado exige no vídeo: exemplo prático de áudio e vídeo, detecção e resposta a anomalias, integração dos serviços Azure e fluxo final do alerta à equipe médica. Para cada trecho: o comando a rodar, o que mostrar na tela e as frases-chave.
     - **Plano B por trecho:** se a Azure ou o Teams falharem, use um trecho gravado antes e mostre os logs.
     - **Cuidados de gravação:** 1080p a 30 fps, notificações do sistema desligadas e chaves fora da tela.
     - **Checklist final:** vídeo no YouTube ou Vimeo como não listado e link no README.
     O roteiro aponta para os pacientes e clipes reservados escolhidos na T37, se já existirem.
- **Aceite:**
  - testes e lint passam;
  - em modo falso, o `preflight_demo.py` lista o que falta e termina com código 1;
  - o replay com `--fast-until 355 --tail-speedup 12` cobre o trecho final em cerca de 10 minutos;
  - `docs/ROTEIRO_VIDEO.md` commitado.

---

## 6. Passos manuais (somente humanos)

Cada item abaixo também aparece na tabela "Bloqueios que dependem de pessoas" do `PROGRESSO.md`. O agente atualiza a tabela; o humano avisa quando resolver.

| Quando | Passo |
|---|---|
| Antes de começar (opcional) | Escolher onde o agente roda e configurar conforme `docs/AMBIENTE_REMOTO.md` (sessões na nuvem ou VPS). Escolher o modelo conforme a seção 0.2. |
| Antes da T05 | Criar/ativar assinatura Azure (Azure for Students, se disponível), `az login`, rodar `scripts/provision_azure.sh`, copiar a saída para `.env`. Criar alerta de orçamento. |
| Antes da T18 | Gravar `consulta_p0001.wav` (2–3 min, dois falantes, roteiro na seção 7) e 5–10 leituras de voz saudável para `voice_healthy/`. |
| Antes da T21 | Gravar ou obter um vídeo de agachamento correto e um incorreto (amplitude reduzida e joelho valgo). Rodar `build_exercise_reference.py` com o correto. |
| Antes da T22 | Baixar um vídeo de queda (Le2i ou UR Fall), respeitando a licença. |
| T27 | **Teams:** no canal desejado, abrir *Workflows* → modelo "Post to a channel when a webhook request is received" → copiar a URL para `TEAMS_WEBHOOK_URL`. **E-mail:** criar uma Logic App (Consumption) com gatilho "When a HTTP request is received" (schema `{to, subject, html}`) e ação "Send an email (V2)" do Outlook; copiar a URL do gatilho para `LOGIC_APP_EMAIL_URL`. |
| T19b (opcional) | Baixar os arquivos do modelo OpenPose COCO para `models/openpose/`. |
| Entrega | Gravar o vídeo (≤ 15 min), publicar como não listado no YouTube, colocar o link no README. Desligar/excluir recursos Azure após a avaliação. |

---

## 7. Roteiro da demonstração

### 7.1 Pacientes e cenários (`SIM_SCENARIO=demo`)

Linha do tempo do cenário `demo`: 480 minutos simulados. Minutos 0–360 a 60x (6 min reais, só para criar histórico); minutos 360–480 a 6x (20 min reais). O minuto 360 corresponde a 01:00 UTC.

| Paciente | Eventos do simulador (minuto simulado) | Mídia enviada por `run_demo.py` | Resultado esperado |
|---|---|---|---|
| P-0001 | `respiratory_deterioration` com início no minuto 375 e duração de 30 min (no demo, a piora é mais rápida que no cenário isolado) | `consulta_p0001.wav` quando `sim:clock` ≥ minuto 370 | Termos "falta de ar"/"cansaço", tosse e fadiga vocal; com a piora dos vitais, a regra `respiratorio_multimodal` dispara e gera alerta **crítico** no Teams |
| P-0002 | `rx_risky` deslocado: heparina no minuto 380, cetorolaco no 390, insulina 10→20 no 400 | `laudo_p0002.txt` no minuto 385 | `rx_interaction` e `rx_dose_change` → alerta de **atenção**; termos críticos do laudo |
| P-0003 | `normal` | `physio_squat_wrong.mp4` no minuto 365 | Amplitude reduzida e compensação; relatório PDF da sessão; sem alerta (só evidências `info`) |
| P-0004 | `night_agitation` nos minutos 360–450; morfina (`start`) no minuto 300 | `bed_fall.mp4` no minuto 410 | `fall_detected` → alerta **crítico** por piso; a regra `queda_com_sedativo` também dispara |
| P-0005 | `sensor_artifact` (pontos inválidos nos minutos 370 e 395) | — | Nenhum alerta (demonstra o filtro de artefato) |

O worker usa o tempo do evento, então toda mídia enviada na demo usa `recorded_at` = valor atual de `sim:clock` (lido do Redis por `run_demo.py`). Sem isso, as evidências de áudio e vídeo ficariam fora da janela da fusão.

### 7.2 Roteiro da consulta encenada (P-0001)

> **Médico:** Bom dia, seu João. Como o senhor passou a noite?
> **Paciente:** Mal, doutor. Estou com falta de ar desde ontem e um cansaço muito grande.
> **Médico:** O senhor teve febre? Sentiu dor no peito?
> **Paciente:** Febre não sei, mas tenho tossido bastante e dói um pouco no peito quando tusso. *(tossir duas ou três vezes)*
> **Médico:** Consegue subir escada?
> **Paciente:** Não, fico sem fôlego logo no começo. *(falar devagar, com pausas)*

### 7.3 Sequência do vídeo de entrega (≤ 15 min)

| Tempo | Conteúdo |
|---|---|
| 00:00–01:30 | Problema, objetivo e diagrama de arquitetura |
| 01:30–04:30 | Vídeo: fisioterapia (P-0003) com vídeo anotado e relatório; queda (P-0004) |
| 04:30–07:30 | Áudio: consulta (P-0001), transcrição Azure, termos críticos, sentimento, features de voz |
| 07:30–10:00 | Séries: painel com vitais em tempo real, NEWS2, z-score, prescrições (P-0002), artefato ignorado (P-0005) |
| 10:00–12:00 | Portal Azure: recursos, métricas de chamadas, logs |
| 12:00–14:00 | Fusão: piora de P-0001 → alerta crítico no Teams → abrir painel pelo link → confirmar alerta |
| 14:00–15:00 | Resultados (T31), limitações e conclusão |

---

## 8. Checklist final de aceite

- [ ] Num clone limpo, a sequência da seção 9.7 sobe o ambiente; `docker compose ps` mostra todos os serviços `running`/`healthy` (e `models-init` com `exited (0)`); `GET /health` retorna `ok`.
- [ ] `pytest -q` e `ruff check .` passam.
- [ ] Com `USE_FAKE_AZURE=true`, o fluxo completo funciona sem chaves.
- [ ] Com chaves reais, `scripts/check_azure.py` retorna 0.
- [ ] Vídeo de fisioterapia gera vídeo anotado, achados e relatório PDF.
- [ ] Vídeo de queda gera `fall_detected` e alerta crítico.
- [ ] Áudio de consulta gera transcrição Azure pt-BR, termos críticos, sentimento e features de voz.
- [ ] Laudo em texto gera termos críticos e entidades.
- [ ] Simulador gera anomalias em vitais, prescrições e movimentação; artefato de sensor não gera alerta.
- [ ] Motor de fusão combina modalidades e a regra respiratória é demonstrável.
- [ ] Alerta chega ao Teams (e/ou e-mail) e pode ser confirmado no dashboard; escalonamento funciona.
- [ ] `docs/resultados/` contém métricas de vitais e de vídeo.
- [ ] `docs/relatorio-tecnico.md` cobre fluxo multimodal, modelos por tipo de dado, resultados e exemplos de anomalias.
- [ ] README permite rodar do zero; link do vídeo incluído.
- [ ] Nenhum segredo ou dado real de paciente no repositório.
- [ ] `docs/resultados/integracao.md` mostra o stack completo funcionando de ponta a ponta (T35).
- [ ] Avaliação de vitais por alerta no relatório, com o método corrigido (T36).
- [ ] PhysioNet (MIMIC-IV Demo) e AudioSet (ou ESC-50, com a escolha registrada) usados de fato, com divisão calibração / validação / reservado e resultados da parte reservada no relatório (T37).
- [ ] `docs/ROTEIRO_VIDEO.md` pronto e `preflight_demo.py` todo em ✓ antes da gravação (T38).
- [ ] `PROGRESSO.md` com T00–T33 e T35–T38 `concluída` (T34 `concluída` ou `pulada`), sem bloqueios abertos e com a seção "Tarefa em andamento" vazia.

---

## 9. Ambiente Docker (referência completa)

Esta seção contém o conteúdo **final** de todos os arquivos de container. A T03 manda criá-los exatamente assim. Todo o sistema roda com Docker Compose numa única máquina: uma imagem Python compartilhada por todos os serviços da aplicação, mais PostgreSQL/TimescaleDB e Redis.

### 9.1 Pré-requisitos

| Item | Requisito |
|---|---|
| Docker | Docker Desktop 4.30+ (Windows/macOS) ou Docker Engine 26+ (Linux), com **Compose v2** (comando `docker compose`, sem hífen) |
| Windows | Backend WSL 2 ativado no Docker Desktop |
| Memória para o Docker | Mínimo 8 GB, recomendado 10–12 GB. No Windows, defina em `%UserProfile%\.wslconfig`: `[wsl2]` e `memory=10GB`, depois `wsl --shutdown` |
| Disco | ~15 GB (imagem ~5 GB com Torch CPU, modelos ~0,5 GB, banco e mídias) |
| Rede | Acesso a PyPI, download.pytorch.org, Docker Hub, GitHub (pesos YOLO) e Hugging Face (modelo AST) no primeiro build/execução |
| GPU (opcional) | NVIDIA com driver recente e suporte a CUDA no WSL 2 / NVIDIA Container Toolkit no Linux |

### 9.2 Visão dos serviços

| Serviço | Imagem | Comando | Porta no host | Depende de |
|---|---|---|---|---|
| `db` | `timescale/timescaledb:latest-pg16` | padrão da imagem | `${DB_PORT:-5432}` | — |
| `redis` | `redis:7-alpine` | `redis-server --appendonly yes` | `${REDIS_PORT:-6379}` | — |
| `models-init` | `medwatch-app` | `python scripts/download_models.py` (roda uma vez e sai) | — | — |
| `api` | `medwatch-app` | `uvicorn medwatch.api.main:app` | `${API_PORT:-8000}` | db, redis |
| `worker-video` | `medwatch-app` | `python -m medwatch.video.worker` | — | db, redis, models-init |
| `worker-audio` | `medwatch-app` | `python -m medwatch.audio.worker` | — | db, redis, models-init |
| `worker-text` | `medwatch-app` | `python -m medwatch.text.worker` | — | db, redis |
| `worker-anomaly` | `medwatch-app` | `python -m medwatch.anomaly.worker` | — | db, redis |
| `worker-fusion` | `medwatch-app` | `python -m medwatch.fusion.worker` | — | db, redis |
| `worker-alerts` | `medwatch-app` | `python -m medwatch.alerts.worker` | — | db, redis |
| `dashboard` | `medwatch-app` | `streamlit run ...` | `${DASHBOARD_PORT:-8501}` | api (healthy) |
| `simulator` | `medwatch-app` | `python -m medwatch.simulator.replay` | — | api (healthy); só no profile `demo` |

Volumes: `pgdata` (banco), `redisdata` (streams), `model-cache` (cache do Hugging Face e afins). Pastas do host montadas: `./data` → `/app/data`, `./models` → `/app/models`, `./config` → `/app/config` (somente leitura).

### 9.3 Arquivos

#### `Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim-bookworm

# CPU por padrão. Para GPU: docker compose build --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG EXTRAS=audio,video,reports,dashboard,dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/root/.cache/huggingface \
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    MPLBACKEND=Agg

# ffmpeg: conversão de áudio/vídeo | libgl1, libglib2.0-0: OpenCV | libsndfile1: soundfile/librosa
# libpango*, libharfbuzz-subset0, fonts-dejavu-core: WeasyPrint (PDF) | curl: healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 libsndfile1 \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Torch (camada grande, muda raramente)
RUN pip install torch torchvision --index-url ${TORCH_INDEX_URL}

# 2) Dependências do projeto SEM o código, para aproveitar o cache de camadas:
#    alterar código em src/ não reinstala dependências.
COPY pyproject.toml README.md ./
RUN mkdir -p src/medwatch \
    && echo '__version__ = "0.1.0"' > src/medwatch/__init__.py \
    && pip install -e ".[${EXTRAS}]"

# 3) Código e arquivos de apoio (o install editável aponta para /app/src)
COPY src ./src
COPY config ./config
COPY db ./db
COPY scripts ./scripts
COPY tests ./tests

RUN mkdir -p /app/data/storage /app/data/references /app/data/samples /app/models

EXPOSE 8000 8501
CMD ["uvicorn", "medwatch.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Notas:
- `python:3.11-slim-bookworm` fixa a versão do Debian para que os nomes dos pacotes `apt` não mudem.
- Se o `pip install -e` falhar por conflito de versões, ajuste o `pyproject.toml` (não o Dockerfile) e registre em `DECISOES.md`.
- O container roda como root. É aceitável para desenvolvimento e para a demo; não é configuração de produção.

#### `.dockerignore`

```
.git
.github
.venv
venv
**/__pycache__
**/*.pyc
.pytest_cache
.ruff_cache
.env
data/
models/
runs/
docs/resultados/
**/*.mp4
**/*.wav
**/*.mp3
**/*.pt
```

Sem isso, o contexto de build envia mídias e modelos para o Docker e o build fica lento.

#### `.gitattributes`

```
* text=auto
*.sh      text eol=lf
*.py      text eol=lf
*.sql     text eol=lf
*.yml     text eol=lf
*.yaml    text eol=lf
*.toml    text eol=lf
*.j2      text eol=lf
Dockerfile text eol=lf
*.ps1     text eol=crlf
*.png     binary
*.jpg     binary
*.mp4     binary
*.wav     binary
```

No Windows, sem `eol=lf`, scripts `.sh` executados dentro do container falham com `/usr/bin/env: 'bash\r': No such file or directory`. Crie este arquivo **antes** de commitar qualquer `.sh`. Se já houver arquivos com CRLF, rode `git add --renormalize .` e commite.

#### `docker-compose.yml`

```yaml
name: medwatch

x-app: &app
  image: medwatch-app:latest
  build:
    context: .
    args:
      TORCH_INDEX_URL: ${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cpu}
  env_file: .env
  # Sobrescreve os valores "locais" do .env com os endereços da rede Docker.
  environment:
    DATABASE_URL: postgresql+psycopg://medwatch:medwatch@db:5432/medwatch
    REDIS_URL: redis://redis:6379/0
    API_BASE_URL: http://api:8000
    CONFIG_DIR: /app/config
    MODELS_DIR: /app/models
    LOCAL_STORAGE_DIR: /app/data/storage
    YOLO_DET_WEIGHTS: /app/models/yolov8n.pt
    YOLO_POSE_WEIGHTS: /app/models/yolov8n-pose.pt
  volumes:
    - ./data:/app/data
    - ./models:/app/models
    - ./config:/app/config:ro
    - model-cache:/root/.cache
  depends_on: &app-deps
    db:
      condition: service_healthy
    redis:
      condition: service_healthy
  restart: unless-stopped

x-needs-models: &needs-models
  depends_on:
    <<: *app-deps
    models-init:
      condition: service_completed_successfully

services:
  db:
    image: timescale/timescaledb:latest-pg16
    environment:
      POSTGRES_USER: medwatch
      POSTGRES_PASSWORD: medwatch
      POSTGRES_DB: medwatch
    ports:
      - "127.0.0.1:${DB_PORT:-5432}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U medwatch -d medwatch"]
      interval: 5s
      timeout: 5s
      retries: 30
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "127.0.0.1:${REDIS_PORT:-6379}:6379"
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  models-init:
    <<: *app
    command: ["python", "scripts/download_models.py"]
    depends_on: {}
    restart: "no"

  api:
    <<: *app
    command: ["uvicorn", "medwatch.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
    ports:
      - "127.0.0.1:${API_PORT:-8000}:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 12
      start_period: 20s

  worker-video:
    <<: [*needs-models, *app]
    command: ["python", "-m", "medwatch.video.worker"]

  worker-audio:
    <<: [*needs-models, *app]
    command: ["python", "-m", "medwatch.audio.worker"]

  worker-text:
    <<: *app
    command: ["python", "-m", "medwatch.text.worker"]

  worker-anomaly:
    <<: *app
    command: ["python", "-m", "medwatch.anomaly.worker"]

  worker-fusion:
    <<: *app
    command: ["python", "-m", "medwatch.fusion.worker"]

  worker-alerts:
    <<: *app
    command: ["python", "-m", "medwatch.alerts.worker"]

  dashboard:
    <<: *app
    command: ["streamlit", "run", "src/medwatch/dashboard/app.py",
              "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true"]
    ports:
      - "127.0.0.1:${DASHBOARD_PORT:-8501}:8501"
    depends_on:
      api:
        condition: service_healthy

  simulator:
    <<: *app
    command: ["python", "-m", "medwatch.simulator.replay"]
    profiles: ["demo"]
    restart: "no"
    depends_on:
      api:
        condition: service_healthy

volumes:
  pgdata:
  redisdata:
  model-cache:
```

Notas sobre o YAML:
- **Merge de âncoras é raso.** Um serviço que declara `depends_on` ou `environment` substitui o bloco inteiro da âncora. Por isso `worker-video` e `worker-audio` usam `<<: [*needs-models, *app]` (a primeira âncora da lista tem prioridade e traz o `depends_on` completo), e `dashboard`/`simulator` declaram o `depends_on` completo.
- Todos os serviços da aplicação compartilham `build` e `image: medwatch-app:latest`. O Compose constrói a imagem uma vez (os demais builds usam o cache) e todos os serviços usam a mesma imagem.
- `models-init` usa `depends_on: {}` porque não precisa do banco nem do Redis.
- O `init.sql` só roda quando o volume `pgdata` está vazio. Para recriar o banco do zero: `docker compose down -v` (apaga os dados).
- **Portas só em `127.0.0.1`.** Todas as portas publicadas ficam presas ao localhost. Numa VPS, o Docker publica portas por cima das regras do firewall (`ufw`), então `"5432:5432"` deixaria o banco, com a senha `medwatch`, aberto para a internet. Para abrir o dashboard ou a API de outra máquina, use um túnel SSH (`docs/AMBIENTE_REMOTO.md`). Não remova o `127.0.0.1:`.

#### `docker-compose.dev.yml` (override de desenvolvimento)

Monta o código do host dentro dos containers e reinicia os processos quando um arquivo `.py` muda. Use durante o desenvolvimento; para a demo e para a gravação, use só o `docker-compose.yml`.

```yaml
x-dev-mounts: &dev-mounts
  volumes:
    - ./src:/app/src
    - ./scripts:/app/scripts
    - ./tests:/app/tests

services:
  api:
    <<: *dev-mounts
    command: ["uvicorn", "medwatch.api.main:app", "--host", "0.0.0.0", "--port", "8000",
              "--reload", "--reload-dir", "/app/src"]
  worker-video:
    <<: *dev-mounts
    command: ["watchfiles", "--filter", "python", "python -m medwatch.video.worker", "/app/src"]
  worker-audio:
    <<: *dev-mounts
    command: ["watchfiles", "--filter", "python", "python -m medwatch.audio.worker", "/app/src"]
  worker-text:
    <<: *dev-mounts
    command: ["watchfiles", "--filter", "python", "python -m medwatch.text.worker", "/app/src"]
  worker-anomaly:
    <<: *dev-mounts
    command: ["watchfiles", "--filter", "python", "python -m medwatch.anomaly.worker", "/app/src"]
  worker-fusion:
    <<: *dev-mounts
    command: ["watchfiles", "--filter", "python", "python -m medwatch.fusion.worker", "/app/src"]
  worker-alerts:
    <<: *dev-mounts
    command: ["watchfiles", "--filter", "python", "python -m medwatch.alerts.worker", "/app/src"]
  dashboard:
    <<: *dev-mounts
    command: ["streamlit", "run", "src/medwatch/dashboard/app.py", "--server.port", "8501",
              "--server.address", "0.0.0.0", "--server.headless", "true", "--server.runOnSave", "true"]
```

- `watchfiles` já vem instalado com `uvicorn[standard]`.
- Em arquivos de override, o Compose junta as listas de `volumes` usando o caminho de destino como chave, então as montagens do arquivo base continuam valendo.
- No Windows, a detecção de mudanças em pastas montadas pode atrasar alguns segundos. Se não reiniciar, use `docker compose restart <serviço>`.

#### `docker-compose.gpu.yml` (opcional)

```yaml
services:
  worker-video:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Uso: definir `TORCH_INDEX_URL=https://download.pytorch.org/whl/cu128` no `.env`, rodar `docker compose build` e subir com `-f docker-compose.yml -f docker-compose.gpu.yml`. O Ultralytics usa a GPU automaticamente quando `torch.cuda.is_available()`. Conferir com `docker compose exec worker-video python -c "import torch; print(torch.cuda.is_available())"`.

### 9.4 `scripts/download_models.py`

Baixa os pesos para a pasta `models/` (montada do host, então o download acontece uma vez) e o modelo AST para o cache do Hugging Face (volume `model-cache`). É idempotente: se os arquivos já existem, não baixa de novo.

```python
"""Baixa os modelos usados pelos workers (idempotente)."""
import shutil
import sys
from pathlib import Path

from medwatch.config import get_settings

YOLO_WEIGHTS = ["yolov8n.pt", "yolov8n-pose.pt"]
AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"


def download_yolo(models_dir: Path) -> None:
    from ultralytics import YOLO

    for name in YOLO_WEIGHTS:
        dest = models_dir / name
        if dest.exists():
            print(f"[ok] {dest}")
            continue
        model = YOLO(name)  # baixa para o diretório atual se não existir
        src = Path(getattr(model, "ckpt_path", None) or name)
        shutil.copy2(src, dest)
        if src.resolve() != dest.resolve() and src.parent.resolve() == Path.cwd().resolve():
            src.unlink(missing_ok=True)
        print(f"[baixado] {dest}")


def download_ast() -> None:
    from transformers import ASTForAudioClassification, AutoFeatureExtractor

    AutoFeatureExtractor.from_pretrained(AST_MODEL)
    ASTForAudioClassification.from_pretrained(AST_MODEL)
    print(f"[ok] {AST_MODEL} no cache do Hugging Face")


def main() -> int:
    settings = get_settings()
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    try:
        download_yolo(settings.models_dir)
        if not settings.audio_disable_events:
            download_ast()
    except Exception as exc:  # falha de rede, por exemplo
        print(f"[erro] download de modelos falhou: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 9.5 Variáveis e caminhos dentro do container

| Caminho no container | Origem | Uso |
|---|---|---|
| `/app/src` | imagem (ou host, no modo dev) | código |
| `/app/config` | host `./config` (somente leitura) | YAMLs de limiares e regras |
| `/app/data` | host `./data` | `storage/` (mídias e artefatos), `references/`, `samples/`, `mimic/` |
| `/app/models` | host `./models` | pesos YOLO, Isolation Forest, OpenPose (opcional) |
| `/root/.cache` | volume `model-cache` | cache do Hugging Face |

Os scripts devem usar caminhos relativos a `/app` (diretório de trabalho), por exemplo `data/references/squat.json`. Assim, o mesmo script funciona dentro do container e localmente na raiz do repositório.

### 9.6 Quais serviços subir em cada fase

Serviços cujo módulo Python ainda não existe entram em loop de reinício. Durante o desenvolvimento, suba só o que já foi implementado:

| Após a tarefa | Comando |
|---|---|
| T03 | `docker compose up -d db redis` |
| T06 | `docker compose up -d db redis api` |
| T13 | `docker compose up -d db redis api worker-anomaly` + `docker compose --profile demo up simulator` |
| T18 | acrescentar `models-init worker-audio worker-text` |
| T24 | acrescentar `worker-video` |
| T27 | acrescentar `worker-fusion worker-alerts` |
| T30 em diante | `docker compose up -d` (tudo) |

### 9.7 Subir o ambiente do zero

Os comandos `docker` são iguais no PowerShell e no bash. Só a cópia do `.env` muda.

1. Criar o `.env`:
   ```bash
   cp .env.example .env
   ```
   ```powershell
   Copy-Item .env.example .env
   ```
   Preencha as chaves Azure ou defina `USE_FAKE_AZURE=true`.
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
   ```
   ```bash
   docker compose restart worker-anomaly
   ```
7. Iniciar o simulador da demo:
   ```bash
   docker compose --profile demo up simulator
   ```
8. Abrir o dashboard em `http://localhost:8501` e a documentação da API em `http://localhost:8000/docs`.

Modo desenvolvimento (código montado e reload automático):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

### 9.8 Comandos do dia a dia

| Objetivo | Comando |
|---|---|
| Rodar os testes no container | `docker compose run --rm api pytest -q` |
| Lint | `docker compose run --rm api ruff check .` |
| Ver logs de um serviço | `docker compose logs -f worker-fusion` |
| Shell dentro da imagem | `docker compose run --rm api bash` |
| Consultar o banco | `docker compose exec db psql -U medwatch -d medwatch -c "select count(*) from evidence"` |
| Tamanho de um stream | `docker compose exec redis redis-cli XLEN evidence` |
| Mensagens pendentes de um grupo | `docker compose exec redis redis-cli XPENDING evidence worker-fusion` |
| Reconstruir após mudar dependências | `docker compose build && docker compose up -d` |
| Parar tudo (mantém dados) | `docker compose down` |
| Apagar banco, streams e caches | `docker compose down -v` |

### 9.9 Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `Bind for 0.0.0.0:5432 failed: port is already allocated` | Postgres local usando a porta | Mude `DB_PORT` no `.env` (ex.: `5433`); vale o mesmo para `REDIS_PORT`, `API_PORT`, `DASHBOARD_PORT` |
| Tabelas não existem | `pgdata` já existia quando o `init.sql` mudou | `docker compose down -v` e subir de novo |
| `env file .env not found` | `.env` não foi criado | Passo 1 da seção 9.7 |
| Worker reiniciando em loop com `ModuleNotFoundError` | Módulo ainda não implementado | Suba só os serviços da tabela 9.6 |
| Container encerrado com código 137 | Falta de memória (YOLO, AST, Torch) | Aumentar a memória do WSL 2/Docker Desktop; `AUDIO_DISABLE_EVENTS=true`; `VIDEO_TARGET_FPS=5` |
| `bash\r: No such file or directory` | Script com CRLF | `.gitattributes` da seção 9.3 e `git add --renormalize .` |
| `models-init` termina com código 1 | Sem acesso a GitHub ou Hugging Face | Verificar rede/proxy e rodar `docker compose up models-init` de novo |
| Dashboard não mostra vídeo | URL da API passada ao navegador | Baixar os bytes no servidor do Streamlit (T30) |
| `could not translate host name "db"` ao rodar Python fora do Docker | `.env` com host do Docker | Fora do Docker use `localhost`, como no `.env.example` |
| Build muito lento ou enorme | `.dockerignore` ausente | Criar o `.dockerignore` da seção 9.3 |
