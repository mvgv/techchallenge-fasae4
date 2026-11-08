# Progresso — MedWatch

Atualize este arquivo em **todo** commit (regras na seção 0.1 do `PLANO_IMPLEMENTACAO.md`).

- **Última atualização:** 2026-11-08 (T00 concluída)
- **Tarefa atual:** T01
- **Estado geral:** T00 concluída; implementação do código não iniciada

## Tarefa em andamento

- **Tarefa:** T01 — Esqueleto do repositório
- **Passos concluídos:** 1, 2, 3, 5 (arquivos escritos no disco, **sem commit**: falta identidade do Git). Criados: `pyproject.toml`, `.gitignore`, `.dockerignore`, `README.md`, `src/medwatch/__init__.py` (`__version__`), `tests/test_smoke.py`.
- **Próximo passo exato:** (1) humano configura a identidade do Git; (2) fazer `git add -A` (exceto `data/`, já ignorado) e commit `T01 [wip]: pyproject, gitignore, README e smoke test`, `git push`; (3) passo 4: instalar e rodar `pytest -q` e `ruff check .` num ambiente Python 3.11 (esta VPS só tem Python 3.12.3; o `pyproject` exige `>=3.11,<3.12`; usar `docker run python:3.11-slim` ou instalar python3.11); (4) passo 6: gerar `requirements.lock` com `pip freeze` e commitar; (5) commit final `T01: Esqueleto do repositório`.
- **Arquivos tocados:** `pyproject.toml`, `.gitignore`, `.dockerignore`, `README.md`, `src/medwatch/__init__.py`, `tests/test_smoke.py`, mais os `__init__.py`/`.gitkeep` do passo 1 (já em stage)
- **Comandos longos em execução:** nenhum
- **Testes falhando conhecidos:** não executados (sem Python 3.11 nesta máquina; execução via docker precisou de aprovação e não foi feita)
- **Observações:** aceite da T01 (`pytest -q` e `ruff check .`) ainda não verificado.

## Status das tarefas

| Tarefa | Título | Status | Commit | Observação |
|---|---|---|---|---|
| T00 | Arquivos de continuidade | concluída | | arquivos criados no planejamento (37cf1da); identidade do Git verificada |
| T01 | Esqueleto do repositório | pendente | | |
| T02 | Configuração, logging, contratos e tempo | pendente | | |
| T03 | Docker Compose, banco e camada de acesso | pendente | | |
| T04 | Barramento (Redis Streams) e storage | pendente | | |
| T05 | Provisionamento e verificação da Azure | pendente | | |
| T06 | API: pacientes, upload de mídia e documentos | pendente | | |
| T07 | Simulador de stream (sintético e MIMIC-IV Demo) | pendente | | |
| T08 | Filtro fisiológico e NEWS2 | pendente | | |
| T09 | Estatística em streaming (EWMA z-score) | pendente | | |
| T10 | Isolation Forest para vitais | pendente | | |
| T11 | Regras de prescrição | pendente | | |
| T12 | Regras de movimentação | pendente | | |
| T13 | Worker de anomalias | pendente | | |
| T14 | Conversão de áudio e Azure Speech | pendente | | |
| T15 | Azure AI Language e termos críticos | pendente | | |
| T16 | Features acústicas e linha de base de voz | pendente | | |
| T17 | Sons respiratórios (modelo AudioSet) | pendente | | |
| T18 | Workers de áudio e de texto | pendente | | |
| T19 | Leitura de frames e wrappers de modelos | pendente | | |
| T20 | Geometria, DTW, repetições e referência | pendente | | |
| T21 | Análise de fisioterapia | pendente | | |
| T22 | Análise de leito | pendente | | |
| T23 | Análise de cirurgia | pendente | | |
| T24 | Vídeo anotado e worker de vídeo | pendente | | |
| T25 | Motor de fusão | pendente | | |
| T26 | Worker de fusão | pendente | | |
| T27 | Canais de alerta e escalonamento | pendente | | |
| T28 | API de leitura e confirmação de alertas | pendente | | |
| T29 | Relatórios (HTML e PDF) | pendente | | |
| T30 | Dashboard Streamlit | pendente | | |
| T31 | Scripts de avaliação | pendente | | |
| T32 | Roteiro automatizado da demonstração | pendente | | |
| T33 | README, documentação e relatório técnico | pendente | | |
| T34 | Opcionais | pendente | | só após T01–T33 |

Status possíveis: `pendente`, `em andamento`, `concluída`, `bloqueada`, `pulada` (só T34).

## Bloqueios que dependem de pessoas

| Item | Tarefa afetada | Desde | Situação |
|---|---|---|---|
| Identidade do Git (`user.name` e `user.email`) não configurada nesta máquina | T00 (todos os commits) | 2026-11-08 | resolvido em 2026-11-08 |
| Identidade do Git ausente de novo nesta VPS (`Author identity unknown`); passo 1 da T01 está feito mas sem commit | T01 em diante (todos os commits) | 2026-11-08 | aberto: humano deve rodar `git config --global user.name` e `user.email` |
| `docker run` exige aprovação do humano nesta VPS; sem Python 3.11, `pytest -q` e `ruff check .` da T01 não puderam ser verificados | T01 passo 4 | 2026-11-08 | aberto: aprovar `docker run python:3.11-slim` ou instalar python3.11 |
| Escolher e configurar o ambiente remoto do agente (nuvem ou VPS, `docs/AMBIENTE_REMOTO.md`) | todas (opcional: dá para rodar localmente) | 2026-11-08 | aberto |
| Provisionar recursos Azure e preencher `.env` (`scripts/provision_azure.sh`) | T05 e verificações reais de T14, T15, T18 | — | aberto |
| Gravar `consulta_p0001.wav` e leituras de voz saudável | T16, T18, T32 | — | aberto |
| Vídeos de agachamento (correto e incorreto) | T20, T21, T32 | — | aberto |
| Vídeo de queda (Le2i ou UR Fall) | T22, T32 | — | aberto |
| Webhook do Teams e Logic App de e-mail | T27 | — | aberto |
| Modelo OpenPose em `models/openpose/` (opcional) | T19b, T34d | — | aberto |
| Gravar e publicar o vídeo de entrega | entrega | — | aberto |

## Estado fora do Git

Ver a tabela "Estado fora do Git" na seção 0.1 do plano. Registre aqui o que já foi gerado nesta máquina:

| Item | Gerado? | Quando / observação |
|---|---|---|
| `.env` | não | |
| Imagem `medwatch-app` | não | |
| Pesos YOLO e AST | não | |
| `models/vitals_iforest.*` | não | |
| `data/references/*` | não | |
| `data/samples/*` | não | |

## Histórico de sessões

| Data | Tarefas trabalhadas | Último commit | Resumo |
|---|---|---|---|
| 2026-11-08 | planejamento, T00 | 37cf1da | Plano, ambiente Docker e arquivos de continuidade criados; identidade do Git configurada pelo humano; T00 concluída. |
| 2026-11-08 | T01 (parcial) | — | Escritos pyproject, .gitignore, .dockerignore, README, `__version__` e smoke test; sem commit (identidade do Git ausente) e sem verificação (sem Python 3.11). |
| 2026-11-08 | planejamento | — | Modelo recomendado (seção 0.2), guia de ambiente remoto, `scripts/setup_vps.sh`, `.gitattributes` e portas do Compose presas a `127.0.0.1`. |
| 2026-11-08 | T01 (tentativa) | — | Identidade do Git ainda ausente (sem commit) e docker bloqueado por aprovação; nada novo além do registro dos bloqueios. Todas as tarefas seguintes exigem commit, então não há tarefa avançável. |
| 2026-11-08 | T01 (nova tentativa) | — | `git config user.name/email` continua vazio e o `docker run` foi bloqueado pelo verificador de permissões. Nada commitado; bloqueios acima seguem abertos. |
