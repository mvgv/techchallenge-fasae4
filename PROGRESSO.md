# Progresso — MedWatch

Atualize este arquivo em **todo** commit (regras na seção 0.1 do `PLANO_IMPLEMENTACAO.md`).

- **Última atualização:** 2026-11-10 (Common Voice incorporado; T37 concluída)
- **Tarefa atual:** nenhuma tarefa pendente (restam só passos humanos para gravar o vídeo)
- **Estado geral:** T00–T33 e T35–T38 concluídas; T34 opcional e fora da ordem

## Tarefa em andamento

- **Tarefa:** nenhuma em andamento. Os passos 9 e 10 da T37 foram feitos no desktop do humano em 2026-11-10: a consulta sintética pela Azure (`scripts/synthesize_consulta.py`, `docs/resultados/azure_integracao.md`) e a linha de base de voz com o Common Voice pt-BR (`scripts/evaluate_voice.py`, `docs/resultados/voice_baseline.md`; falsos alarmes 2 de 27 vozes reservadas). As chaves da Azure e os áudios do Common Voice estão só no desktop; **a VPS não os tem**, então não tente chamar a Azure daqui nem rodar `evaluate_voice.py`.
- **Próximo passo exato:** nenhum para o agente. Para gravar o vídeo faltam passos humanos (ver a tabela de bloqueios): vídeos de agachamento, Teams e e-mail, orçamento e prints da Azure; depois `docker compose down -v`, `preflight_demo.py` e `docs/ROTEIRO_VIDEO.md`. T34 só se o humano pedir.
- **Ambiente:** VPS Linux, Python 3.11 em `.venv` (`.venv/bin/python`, `.venv/bin/pytest -q`, `.venv/bin/ruff check .`). `pyarrow` 17 instalado.
- **Arquivos tocados:** `scripts/download_datasets.py`, `scripts/prepare_mimic.py` (PA arterial e °C), `tests/test_mimic.py`, `docs/DATASETS.md`, `scripts/make_splits.py`, `config/splits.yaml`, `tests/test_splits.py`, `src/medwatch/simulator/mimic.py`, `src/medwatch/simulator/replay.py`, `src/medwatch/anomaly/iforest.py`, `src/medwatch/anomaly/worker.py`, `src/medwatch/config.py`, `scripts/train_vitals_iforest.py`, `.env.example`, `scripts/evaluate_mimic.py`, `scripts/evaluate_vitals.py`, `tests/test_evaluate_mimic.py`, `config/thresholds.yaml`, `docs/resultados/mimic_*`
- **Comandos longos em execução:** nenhum
- **Testes falhando conhecidos:** nenhum (221 passam)
- **Observações:** `docs/resultados/mimic_alarm_load.{md,json}` são sobras não versionadas de uma rodada intermediária (substituídas por `mimic_results.*`); podem ser apagadas. Resultados MIMIC: recall semissintético 0,87 no reservado (`tachy_spike` 0,69: o z-score precisa de 20 leituras ≈ 20 h), 1,09 alerta/paciente-dia só com vitais e 1,87 com prescrições. Relatório tem itens marcados [PENDENTE]. `dbg_tmp.py` e `dbg_diag.py` (vazio) na raiz são arquivos não versionados que o agente não pôde apagar (rm exige aprovação): apague à mão. `models/vitals_iforest.json` foi regravado com o campo `p0_1` (fora do Git; rode `scripts/train_vitals_iforest.py` em outra máquina para o limiar `p0_1` existir, senão o IForest cai no `threshold` antigo).

## Status das tarefas

| Tarefa | Título | Status | Commit | Observação |
|---|---|---|---|---|
| T00 | Arquivos de continuidade | concluída | | arquivos criados no planejamento (37cf1da); identidade do Git verificada |
| T01 | Esqueleto do repositório | concluída | dafde2b | `pytest -q` e `ruff check .` passam; `requirements.lock` gerado |
| T02 | Configuração, logging, contratos e tempo | concluída | ver `git log` | `pytest -q` e `ruff check .` passam |
| T03 | Docker Compose, banco e camada de acesso | concluída | 3951ed5 | `docker compose build` OK; db/redis healthy; test_db passa com banco real |
| T04 | Barramento (Redis Streams) e storage | concluída | 1bd2ab9 | `pytest -q` e `ruff check .` passam (fakeredis e LocalStorage; AzureBlobStorage sem teste real) |
| T05 | Provisionamento e verificação da Azure | concluída | 41feab5 | `pytest -q` e `ruff check .` passam; verificação real pendente: rodar `scripts/check_azure.py` com chaves reais [HUMANO] |
| T06 | API: pacientes, upload de mídia e documentos | concluída | ver `git log` | `pytest -q` e `ruff check .` passam com banco real; `routes_alerts.py` é stub; B008 isento para Depends/File/Form no ruff |
| T07 | Simulador de stream (sintético e MIMIC-IV Demo) | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; `test_mimic` pulado (pyarrow 26 da `.venv` incompatível com numpy<2: `pip install "pyarrow<18"`); aceite com `docker compose --profile demo up simulator` (XLEN vitals) não verificado; MIMIC não baixado |
| T08 | Filtro fisiológico e NEWS2 | concluída | ver `git log` | `pytest -q` e `ruff check .` passam |
| T09 | Estatística em streaming (EWMA z-score) | concluída | ver `git log` | `pytest -q` e `ruff check .` passam |
| T10 | Isolation Forest para vitais | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; modelo gerado em `models/` (fora do Git); `--mimic` não testado |
| T11 | Regras de prescrição | concluída | ver `git log` | `pytest -q` e `ruff check .` passam |
| T12 | Regras de movimentação | concluída | ver `git log` | `pytest -q` e `ruff check .` passam |
| T13 | Worker de anomalias | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; aceite com compose + simulador (XLEN evidence) não verificado |
| T14 | Conversão de áudio e Azure Speech | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; AzureTranscriber sem teste real (chaves [HUMANO]) |
| T15 | Azure AI Language e termos críticos | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; AzureLanguageAnalyzer sem teste real (chaves [HUMANO]) |
| T16 | Features acústicas e linha de base de voz | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; openSMILE não importa na `.venv` (pyarrow 26 x numpy<2, ver T07): features eGeMAPS ficam None; teste com openSMILE real não feito; baseline real depende de gravações [HUMANO] |
| T17 | Sons respiratórios (modelo AudioSet) | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; teste com AST real (`slow`) não executado (modelo ~350 MB não baixado, sem WAV de tosse) |
| T18 | Workers de áudio e de texto | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; aceite com compose + upload pela API não verificado; Azure real e AST real sem teste |
| T19 | Leitura de frames e wrappers de modelos | concluída | 8bd7cb7 | `pytest -q` e `ruff check .` passam; Detector/PoseEstimator (YOLO) sem teste real (pesos não baixados); T19b opcional não feita |
| T20 | Geometria, DTW, repetições e referência | concluída | 4e70525 | `pytest -q` e `ruff check .` passam; `build_exercise_reference.py` sem teste real (sem vídeo de agachamento nem pesos YOLO) [HUMANO] |
| T21 | Análise de fisioterapia | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; testes com keypoints sintéticos |
| T22 | Análise de leito | concluída | 36e6010 | `pytest -q` e `ruff check .` passam; testes com keypoints sintéticos; sem vídeo de queda real [HUMANO] |
| T23 | Análise de cirurgia | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; testes com detecções sintéticas; YOLO COCO só conhece objetos genéricos (documentar no relatório) |
| T24 | Vídeo anotado e worker de vídeo | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; testes com modelos falsos; aceite (upload de agachamento pela API + YOLO real + compose) não verificado: sem pesos YOLO nem vídeo [HUMANO] |
| T25 | Motor de fusão | concluída | ver `git log` | `pytest -q` e `ruff check .` passam |
| T26 | Worker de fusão | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; testes com fakeredis e db falso; aceite (simulador `demo` + `GET /alerts`) depende da T28 e do compose, não verificado |
| T27 | Canais de alerta e escalonamento | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; testes com httpx.MockTransport; Teams e Logic App reais sem teste [HUMANO] |
| T28 | API de leitura e confirmação de alertas | concluída | ver `git log` | `pytest -q` (153 passed) e `ruff check .` passam com banco real; `db.get_alert`/`ack_alert` (ack atômico) adicionados |
| T29 | Relatórios (HTML e PDF) | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; `POST /reports/patient/{id}`; `build_session_report` movido para `reports/render.py`; aceite visual com vídeo real não verificado |
| T30 | Dashboard Streamlit | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; testes com MockTransport e AppTest (smoke da tela Paciente pulado na `.venv`: `st.dataframe` precisa do pyarrow, quebrado como na T07; verificada à parte com `st.dataframe` neutralizado); aceite com compose + simulador `demo` (painel ao vivo, ack, upload real) não verificado |
| T31 | Scripts de avaliação | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; `vitals_metrics.*` gerados (muitos FP, ver DECISOES); `evaluate_video.py` pronto, verificação real pendente: precisa de `video_annotations.csv` e vídeos [HUMANO] |
| T32 | Roteiro automatizado da demonstração | concluída | ver `git log` | `pytest -q` e `ruff check .` passam; testes com fakeredis e MockTransport; envio checado com TestClient e banco real; aceite (demo completa com amostras, workers e simulador) não verificado: amostras [HUMANO] |
| T33 | README, documentação e relatório técnico | concluída | ver `git log` | `pytest -q` (178 passed) e `ruff check .` passam; seções de custos Azure, prints e avaliação de vídeo marcadas [PENDENTE] (dependem de humano); aceite "colega roda do zero" não testado |
| T34 | Opcionais | pendente | | opcional; fora da ordem, só se o humano pedir |
| T35 | Integração ponta a ponta (modo falso) | concluída | ver `git log` | stack completo sobe e funciona (184 testes, zero reinícios); 4 defeitos corrigidos; falsos alarmes em P-0003/P-0005 vão para a T36; ver `docs/resultados/integracao.md`. Azure e Teams reais seguem pendentes [HUMANO] |
| T36 | Avaliação de vitais corrigida e ajuste de limiares | concluída | ver `git log` | `pytest -q` (190) e `ruff check .` passam; por alerta: recall 0,93 (ajuste) / 1,00 (conferência) e 0,10 alertas/dia em normais; recall 100% no ajuste não alcançado (hipotensão lenta, ver `vitals_tuning.md`) |
| T37 | Datasets públicos do enunciado com partes reservadas | concluída | ver `git log` | MIMIC-IV Demo, ESC-50 (no lugar do AudioSet), UR Fall, Common Voice pt-BR e consulta sintética pela Azure, todos com parte reservada; resultados em `docs/resultados/datasets.md`; queda generaliza mal (recall 0,10 no reservado) |
| T38 | Preparação da gravação do vídeo | concluída | ver `git log` | `pytest -q` (221) e `ruff check .` passam; `--fast-until`/`--tail-speedup`, `preflight_demo.py` (testes com clientes falsos), cartão com risco de pico e atual, `docs/ROTEIRO_VIDEO.md`; ensaio real e checagem com Azure/Teams [HUMANO]; simulador mais rápido, checagem prévia, roteiro; adicionada na preparação do vídeo |

Status possíveis: `pendente`, `em andamento`, `concluída`, `bloqueada`, `pulada` (só T34).

## Bloqueios que dependem de pessoas

| Item | Tarefa afetada | Desde | Situação |
|---|---|---|---|
| Identidade do Git (`user.name` e `user.email`) não configurada nesta máquina | T00 (todos os commits) | 2026-11-08 | resolvido em 2026-11-08 |
| Identidade do Git ausente de novo nesta VPS (`Author identity unknown`); passo 1 da T01 está feito mas sem commit | T01 em diante (todos os commits) | 2026-11-08 | resolvido em 2026-11-08 (identidade `mvgv` presente; commit wip criado) |
| `docker run` exige aprovação do humano nesta VPS; sem Python 3.11, `pytest -q` e `ruff check .` da T01 não puderam ser verificados | T01 passo 4 | 2026-11-08 | resolvido em 2026-11-08 (`.venv` com Python 3.11 disponível) |
| `git push` falha: sem credenciais do GitHub nesta VPS (`could not read Username`); commit `T01 [wip]` existe só localmente | todos (push) | 2026-11-08 | resolvido em 2026-11-08 (push funciona; origin/main em dia) |
| Escolher e configurar o ambiente remoto do agente (nuvem ou VPS, `docs/AMBIENTE_REMOTO.md`) | todas (opcional: dá para rodar localmente) | 2026-11-08 | resolvido em 2026-11-08 (VPS) |
| Provisionar recursos Azure e preencher `.env` (`scripts/provision_azure.sh`) | T05, verificações reais de T14, T15, T18 e a consulta sintética da T37 (passo 10) | — | resolvido em 2026-11-10 no desktop (assinatura POSTECH, `rg-medwatch`, `brazilsouth`; `check_azure.py` OK nos três serviços). A VPS não tem as chaves |
| ~~Gravar `consulta_p0001.wav` e leituras de voz saudável~~ | T16, T18, T32 | — | substituído em 2026-11-09: a consulta e o `hello_ptbr.wav` passam a ser gerados pela Azure (T37, passo 10) e a voz saudável vem do Common Voice (linha abaixo) |
| Common Voice (português): aceitar os termos no site oficial e disponibilizar os clipes em `data/datasets/commonvoice/` (ou o token no `.env`) | T37 passo 9 | 2026-11-09 | resolvido em 2026-11-10 (recorte brasileiro de 122 MB baixado pelo humano) |
| Três vídeos de agachamento (correto para referência, correto de controle, incorreto), câmera lateral, ~30 s cada | T20, T21, T32, T38 | — | aberto |
| ~~Vídeo de queda (Le2i ou UR Fall)~~ | T22, T32 | — | substituído em 2026-11-09: o agente baixa o UR Fall na T37 (passo 8); só volta a ser humano se o dataset estiver inacessível ou sem anotações |
| Webhook do Teams e Logic App de e-mail | T27 | — | aberto |
| Orçamento de alerta no portal da Azure (Cost Management) e prints do portal (recursos, métricas de uso, custo) | relatório e vídeo | 2026-11-10 | aberto |
| Modelo OpenPose em `models/openpose/` (opcional) | T19b, T34d | — | aberto |
| Gravar e publicar o vídeo de entrega | entrega | — | aberto |

## Estado fora do Git

Ver a tabela "Estado fora do Git" na seção 0.1 do plano. Registre aqui o que já foi gerado nesta máquina:

| Item | Gerado? | Quando / observação |
|---|---|---|
| `.env` | sim | presente em 2026-11-08 (sem chaves Azure nem Teams; USE_FAKE_AZURE definido) |
| Imagem `medwatch-app` | não | |
| Pesos YOLO e AST | parcial | 2026-11-10: `models/yolov8n-pose.pt` baixado; AST no cache do Hugging Face; `lap` instalado na `.venv` |
| `data/datasets/urfall/` | sim | 2026-11-10, `scripts/download_datasets.py --urfall` (pasta `probe/` é sobra de teste; `people_v2/` é cache de poses) |
| `models/vitals_iforest.*` | sim | 2026-11-08, sintético (sem --mimic) |
| `data/references/*` | não | |
| `data/samples/*` | não | |
| `models/vitals_iforest_mimic.*` | sim | 2026-11-09, `scripts/train_vitals_iforest.py --mimic-split calibracao --out models/vitals_iforest_mimic` |
| `data/datasets/esc50/` (ESC-50, 10 classes, 400 clipes) | sim | 2026-11-09, `scripts/download_datasets.py --esc50` |
| `data/mimic/*` (MIMIC-IV Demo 2.2 + parquets) | sim | 2026-11-09, `scripts/download_datasets.py --mimic` |

## Histórico de sessões

| Data | Tarefas trabalhadas | Último commit | Resumo |
|---|---|---|---|
| 2026-11-08 | planejamento, T00 | 37cf1da | Plano, ambiente Docker e arquivos de continuidade criados; identidade do Git configurada pelo humano; T00 concluída. |
| 2026-11-08 | T01 (parcial) | — | Escritos pyproject, .gitignore, .dockerignore, README, `__version__` e smoke test; sem commit (identidade do Git ausente) e sem verificação (sem Python 3.11). |
| 2026-11-08 | planejamento | — | Modelo recomendado (seção 0.2), guia de ambiente remoto, `scripts/setup_vps.sh`, `.gitattributes` e portas do Compose presas a `127.0.0.1`. |
| 2026-11-08 | revisão pós-T33 | — | Revisão do trabalho: só testes unitários com falsos, avaliação de vitais com erro de método, `.venv` com pyarrow incompatível e imagem Docker antiga. Adicionadas T35 (integração ponta a ponta) e T36 (avaliação corrigida). |
| 2026-11-08 | T01 (tentativa) | — | Identidade do Git ainda ausente (sem commit) e docker bloqueado por aprovação; nada novo além do registro dos bloqueios. Todas as tarefas seguintes exigem commit, então não há tarefa avançável. |
| 2026-11-08 | T01 (nova tentativa) | — | `git config user.name/email` continua vazio e o `docker run` foi bloqueado pelo verificador de permissões. Nada commitado; bloqueios acima seguem abertos. |
| 2026-11-08 | T01 (parcial) | ver `git log` | Identidade do Git OK; commit wip criado; push falhou (sem credenciais); docker run bloqueado pelo verificador, pytest/ruff ainda não verificados. |
| 2026-11-08 | T01 (nova tentativa) | ver `git log` | `git push` ainda falha (sem credenciais). Criar venv e instalar pytest/ruff (alternativa à falta de Python 3.11) foi bloqueado pelo verificador de permissões. Nenhum código novo; T01 segue sem verificação e T02+ dependem dela. |
| 2026-11-08 | T01 (nova tentativa) | ver `git log` | Push OK. `docker run python:3.11-slim ...` foi barrado pelo verificador (comando não verificável); sem Python 3.11 local. T01 continua sem verificação de `pytest -q`/`ruff check .`; nenhuma tarefa seguinte avança sem isso. |
| 2026-11-08 | T01 (nova tentativa) | ver `git log` | Estado inalterado: sem python3.11, pytest nem ruff nesta VPS; `docker run` e criação de venv já foram barrados antes e não foram reexecutados. Aguardando o humano: aprovar `docker run python:3.11-slim` ou instalar python3.11 (ou pytest/ruff). Nenhuma tarefa seguinte avança sem a verificação da T01. |
| 2026-11-08 | T01 | ver `git log` | Verificação com `.venv` (Python 3.11): `pytest -q` e `ruff check .` OK; `requirements.lock` gerado; T01 concluída. |
| 2026-11-08 | T02 | ver `git log` | config, contracts, logging, timeutil, YAML de config/ e testes; `pytest -q` e `ruff check .` OK. Próxima: T03. |
| 2026-11-08 | T03 | ver `git log` | init.sql, Dockerfile, compose, db.py e test_db.py; build, up db/redis, pytest e ruff OK. Próxima: T04. |
| 2026-11-08 | T04 | ver `git log` | bus.py, storage.py e testes; `pytest -q` e `ruff check .` OK. Próxima: T05. |
| 2026-11-08 | T05 | ver `git log` | provision_azure.sh, check_azure.py, speech.py (fábrica + Fake), README e teste; `pytest -q` e `ruff check .` OK. Próxima: T06. |
| 2026-11-08 | T06 | ver `git log` | api (main, deps, routes_patients/media/alerts stub) e test_api_media; `pytest -q` e `ruff check .` OK. Próxima: T07. |
| 2026-11-08 | T07 | ver `git log` | synthetic, replay (fases de velocidade, sim:clock, ground truth), seed, mimic + scripts, testes; `pytest -q` e `ruff check .` OK. Próxima: T08. |
| 2026-11-08 | T08 | ver `git log` | filters.py, news2.py e test_news2.py; `pytest -q` e `ruff check .` OK. Próxima: T09. |
| 2026-11-08 | T09 | ver `git log` | streaming_stats.py (EwmaZ, Cooldown) e testes; `pytest -q` e `ruff check .` OK. Próxima: T10. |
| 2026-11-08 | T10 | ver `git log` | iforest.py, train_vitals_iforest.py e testes; `pytest -q` e `ruff check .` OK. Próxima: T11. |
| 2026-11-08 | T11 | ver `git log` | prescriptions.py (PrescriptionMonitor, normalize_drug) e testes; `pytest -q` e `ruff check .` OK. Próxima: T12. |
| 2026-11-08 | T12 | ver `git log` | movement.py (MovementMonitor) e testes; `pytest -q` e `ruff check .` OK. Próxima: T13. |
| 2026-11-08 | T13 | ver `git log` | anomaly/worker.py (AnomalyWorker, db injetável) e testes com fakeredis; `pytest -q` e `ruff check .` OK. Próxima: T14. |
| 2026-11-08 | T14 | ver `git log` | audio/convert.py (ffmpeg, duration_seconds), speech.py usa duration_seconds, test_speech_fake.py; `pytest -q` e `ruff check .` OK. Próxima: T15. |
| 2026-11-08 | T15 | ver `git log` | audio/terms.py, audio/language.py (Azure + Fake + fábrica) e testes; `pytest -q` e `ruff check .` OK. Próxima: T16. |
| 2026-11-08 | T16 | ver `git log` | audio/acoustic.py (extract_features, assess_voice), build_voice_baseline.py e testes; `pytest -q` e `ruff check .` OK. Próxima: T17. |
| 2026-11-08 | T17 | ver `git log` | audio/events.py (RespiratoryEventDetector, clf injetável, filtro de Breathing) e test_events.py; `pytest -q` e `ruff check .` OK. Próxima: T18. |
| 2026-11-08 | T18 | ver `git log` | audio/worker.py (AudioWorker), text/worker.py (TextWorker, split_paragraphs) e testes com fakes; `pytest -q` e `ruff check .` OK. Próxima: T19. |
| 2026-11-08 | T19 | ver `git log` | video/frames.py (iter_frames, video_info), video/models.py (Detector, PoseEstimator, main_person) e test_frames.py; `pytest -q` e `ruff check .` OK. Próxima: T20. |
| 2026-11-08 | T20 | ver `git log` | video/geometry.py, dtw.py, reps.py, build_exercise_reference.py e testes; `pytest -q` e `ruff check .` OK. Próxima: T21. |
| 2026-11-08 | T21 | ver `git log` | video/physio.py (analyze_physio, PhysioResult) e test_physio.py; `pytest -q` e `ruff check .` OK. Próxima: T22. |
| 2026-11-08 | T22 | ver `git log` | video/bed.py (analyze_bed, BedResult) e test_bed.py; `pytest -q` e `ruff check .` OK. Próxima: T23. |
| 2026-11-08 | T23 | ver `git log` | video/surgery.py (analyze_surgery, SurgeryResult) e test_surgery.py; `pytest -q` e `ruff check .` OK. Próxima: T24 (recomenda-se Opus 5.5). |
| 2026-11-08 | T24 | ver `git log` | video/annotate.py (AnnotatedWriter H.264, overlay), video/worker.py (VideoWorker, duas passagens, evidências, MovementSample, findings.json, frames-chave) e test_video_worker.py; `pytest -q` e `ruff check .` OK. Próxima: T25. |
| 2026-11-08 | T25 | ver `git log` | config/fusion.yaml, fusion/engine.py (FusionEngine, RiskResult) e test_fusion.py; `pytest -q` e `ruff check .` OK. Próxima: T26 (recomenda-se Opus 5.5). |
| 2026-11-08 | T26 | ver `git log` | fusion/worker.py (FusionWorker: evidência no banco, snapshot top 10, criação/escalonamento/cooldown de alertas, título e resumo pt-BR, reidratação) e test_fusion_worker.py; `pytest -q` (143 passed) e `ruff check .` OK. Próxima: T27. |
| 2026-11-08 | T27 | ver `git log` | alerts/channels.py (Console, Teams, Email, dispatch), alerts/worker.py (AlertWorker, escalonamento a cada 30 s) e test_channels.py; `pytest -q` (147 passed) e `ruff check .` OK. Próxima: T28. |
| 2026-11-08 | T28 | ver `git log` | routes_alerts (GET /alerts, ack com 404/409), routes_patients (vitals/evidence/risk), db.get_alert/ack_alert e test_api_read.py; `pytest -q` e `ruff check .` OK. Próxima: T29. |
| 2026-11-08 | T29 | ver `git log` | reports/render.py, templates, routes_reports e test_reports.py; worker de vídeo gera report.html/pdf; `pytest -q` e `ruff check .` OK. Próxima: T30. |
| 2026-11-08 | T30 | ver `git log` | Sessão no Opus 5.5. dashboard/api_client.py (ApiClient), dashboard/app.py (4 telas), test_dashboard.py; corrigido `load_yaml("exercises.yaml")` em routes_media (500 no upload physio) + teste; `pytest -q` (170 passed) e `ruff check .` OK. Próxima: T31. |
| 2026-11-08 | T31 | ver `git log` | scripts/evaluate_vitals.py (execução ~10 min por causa do IForest por minuto), evaluate_video.py, resultados em docs/resultados/ e testes; `pytest -q` e `ruff check .` OK. Próxima: T32. |
| 2026-11-08 | T32 | ver `git log` | Sessão no Opus 5.5. scripts/run_demo.py (health, pacientes, simulador subprocesso ou externo, envio por `sim:clock`), data/samples/README.md e tests/test_run_demo.py; `pytest -q` (178 passed) e `ruff check .` OK. Próxima: T33. |
| 2026-11-08 | T33 | ver `git log` | README reescrito (requisitos, passo a passo bash/PowerShell, problemas comuns, testes, estrutura), docs/arquitetura.md (Mermaid, serviços, streams, tabelas, catálogo) e docs/relatorio-tecnico.md (7 seções); `pytest -q` e `ruff check .` OK. Próxima: T34 opcional / passos humanos. |
| 2026-11-09 | T35 | ver `git log` | Rodada no desktop do humano (Windows, RTX 5070, Docker Desktop). Stack completo com mídias sintéticas, laudo, alertas, confirmação, escalonamento, relatório e dashboard num navegador. Defeitos: redis-py 8 derrubava 4 workers (`bus.py`), testes sujavam o banco ao vivo (`tests/conftest.py`), coluna "Nível" do dashboard, `cu121` na documentação (RTX 50xx precisa de `cu128`). Pendências: falsos alarmes em pacientes normais (T36) e laudo sem tratamento de negação. |
| 2026-11-09 | T36 | ver `git log` | VPS. Rótulos persistentes, persistência no z-score/IForest (`p0_1`), métricas por episódio e por alerta, grade de 24 combinações (ajuste e conferência), limiares escolhidos, relatório atualizado. Próxima: T37. |
| 2026-11-09 | T37 | ver `git log` | VPS, Opus 5.5. Em andamento. |
| 2026-11-10 | T37 (passos 7, 8, 11), T38 | ver `git log` | VPS. ESC-50 avaliado e `audio_events` calibrado; UR Fall baixado, dividido e avaliado (queda: reservado precisão 0,67, recall 0,10; `bed.py` tolera lacunas de pose); material da demonstração e `docs/resultados/datasets.md`; T38 completa. T37 passos 9 e 10 aguardam humano. |
| 2026-11-10 | T37 (passo 10), Azure | ver `git log` | Desktop do humano, Sonnet 5.5. Assinatura POSTECH: provedores registrados, `provision_azure.sh` criou Speech, Language e Blob em `brazilsouth`; `check_azure.py` OK nos três serviços. `scripts/synthesize_consulta.py` (voz da Azure + tosses reservadas do ESC-50) gerou `consulta_p0001.wav` e `hello_ptbr.wav`; a consulta passou pelo pipeline real: separação de falantes correta, 5 termos críticos (um falso por erro de reconhecimento), sentimento, 15 entidades de saúde, tosse detectada (score 0,17). Resultados em `docs/resultados/azure_integracao.md`. |
| 2026-11-10 | T37 (passo 9), fechamento | ver `git log` | Desktop do humano, Sonnet 5.5. O humano baixou o Common Voice (recorte brasileiro, 122 MB). `scripts/evaluate_voice.py`: 81 falantes com 10+ clipes, 54 de calibração e 27 reservados, linha de base só da calibração; falsos alarmes nas vozes reservadas 2 de 27 (7,4%; IC 95% de 2% a 23%), ambos `voice_fatigue` por fala lenta; limiares mantidos. Relatório técnico ganhou a seção 5.4 com os resultados em dados reservados e as fontes de dados corrigidas. T37 concluída. |
