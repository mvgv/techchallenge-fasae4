# Progresso — MedWatch

Atualize este arquivo em **todo** commit (regras na seção 0.1 do `PLANO_IMPLEMENTACAO.md`).

- **Última atualização:** 2026-11-08 (planejamento)
- **Tarefa atual:** T00
- **Estado geral:** implementação não iniciada

## Tarefa em andamento

- **Tarefa:** T00 — Arquivos de continuidade
- **Passos concluídos:** 1 e 2 (arquivos `CLAUDE.md`, `PROGRESSO.md` e `docs/DECISOES.md` criados no planejamento)
- **Próximo passo exato:** passo 3 da T00: rodar `git config user.name` e `git config user.email`. Se vierem vazios, manter o bloqueio "Identidade do Git" aberto e pedir ao humano para configurar. Se estiverem preenchidos, fechar o bloqueio, marcar T00 como `concluída`, preencher esta seção com a T01 (passo 1) e fazer o commit `T00: Arquivos de continuidade` com push.
- **Arquivos tocados:** `CLAUDE.md`, `PROGRESSO.md`, `docs/DECISOES.md`
- **Comandos longos em execução:** nenhum
- **Testes falhando conhecidos:** nenhum (ainda não há código)
- **Observações:** nenhuma

## Status das tarefas

| Tarefa | Título | Status | Commit | Observação |
|---|---|---|---|---|
| T00 | Arquivos de continuidade | em andamento | | |
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
| Identidade do Git (`user.name` e `user.email`) não configurada nesta máquina | T00 (todos os commits) | 2026-11-08 | aberto |
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
| 2026-11-08 | planejamento | — | Plano, ambiente Docker e arquivos de continuidade criados. |
