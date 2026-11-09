# Integração ponta a ponta (T35)

- **Data:** 2026-11-09
- **Versão:** `main` a partir de `3ec3182` (correções desta tarefa nos commits `T35 [wip]` seguintes)
- **Modo:** `USE_FAKE_AZURE=true` (Azure Speech e Language falsos), dados sintéticos, notificações só no console
- **Máquina:** desktop Windows 11 com Docker Desktop 29.9, 16 CPUs, 31 GB de RAM e GPU NVIDIA RTX 5070 (12 GB)
- **Imagens:** `medwatch-app:cpu` (Torch 2.15 CPU, usada na linha de base dos testes) e `medwatch-app:latest` (Torch 2.11 + CUDA 12.8, usada no stack)

## Resultado por verificação

| # | Verificação | Resultado |
|---|---|---|
| 1 | Ambiente Python, `pytest -q`, `ruff check .` | **Passou.** 181 testes na imagem CPU (os 2 `slow` ficam de fora por padrão); depois das correções, 184. No Windows nativo o Torch não carrega (política de Controle de Aplicativo bloqueia `shm.dll`), então os testes rodam no container. Com `pyarrow` 17 e `numpy` 1.26 o openSMILE importa e os testes antes pulados por causa do `pyarrow` rodam |
| 2 | Build da imagem e `models-init` | **Passou.** `models-init` saiu com código 0 e deixou `yolov8n.pt`, `yolov8n-pose.pt` e o AST no cache |
| 3 | Stack completo, logs, `/health`, `/_stcore/health` | **Corrigido.** Na primeira subida, 4 workers (`anomaly`, `fusion`, `alerts`, `text`) reiniciavam em loop (defeito 1). Depois da correção, 10 serviços estáveis, zero reinícios, sem traceback nos logs, `/health` = `ok` |
| 4 | `seed.py`, treino do Isolation Forest, reinício do worker | **Passou.** 5 pacientes, modelo treinado com 57.500 amostras |
| 5 | Simulação `demo --fast` e alertas por paciente | **Passou em 3 de 5 pacientes.** Ver tabela abaixo |
| 6 | Mídias sintéticas (áudio e 3 vídeos) | **Passou.** Os 4 envios terminaram em `done` em cerca de 30 s |
| 7 | Laudo em texto | **Passou**, com uma limitação (negação, abaixo) |
| 8 | Confirmação, 409 e escalonamento | **Passou.** Ver detalhes abaixo |
| 9 | Relatório do paciente, `ApiClient` e dashboard | **Passou.** PDF de 80 KB válido; as 7 chamadas do `ApiClient` funcionam; as telas "Painel geral" e "Paciente" renderizam com dados reais num navegador |
| 10 | `scripts/run_demo.py` | **Passou.** Rodou até o fim, pulou as 4 amostras ausentes com aviso e sem traceback |
| extra | Testes `slow` (AST real e YOLO real) | **Passaram** com mídia sintética |

## Passo 5: alertas por paciente

Streams depois do replay (4.817 mensagens): `vitals` 2.400, `prescriptions` 17, `movement` 2.400, `evidence` 143, `alerts` 7. Nenhuma mensagem pendente (`XPENDING` = 0) em `evidence` e `vitals`.

| Paciente | Esperado | Obtido | Veredito |
|---|---|---|---|
| P-0001 | crítico | crítico, risco 97,2 (NEWS2 alto) | ok |
| P-0002 | atenção ou mais | atenção, risco 50,1 (interação medicamentosa, mudança de dose) | ok |
| P-0003 | nenhum | atenção, risco 60,8 (padrão multivariado anômalo) | **falso alarme** |
| P-0004 | atenção ou mais | crítico, risco 98,8 (saída do leito; regra "queda com sedativo" disparou) | ok |
| P-0005 | nenhum | atenção, risco 62,8 (padrão multivariado anômalo) | **falso alarme** |

**Os falsos alarmes não vêm do filtro de artefatos.** Os valores injetados em P-0005 (SpO₂ = 0 e FC = 400) foram descartados e gravados como nulos, e nenhuma evidência cai nos minutos dos artefatos. Os alertas vêm do ruído do Isolation Forest (limiar no percentil 0,5, ou seja, cerca de 0,5% dos pontos normais são marcados) somado ao z-score em limiar 3,0. A T35 não altera limiares: isso é a T36.

## Passo 6: mídias

- **Áudio** (tom de 180 Hz, transcrição falsa): 4 termos críticos (`falta de ar` 0,8; `dor no peito` 0,9; `cansaço` 0,5; `febre` 0,5), sentimento negativo (0,75) e entidades clínicas. O openSMILE devolveu atributos reais (`f0_mean`, `jitter`, `shimmer_db`, `hnr`, `loudness`); na VPS eles vinham `None`. O AST real rodou e não encontrou evento respiratório no tom, como esperado.
- **Vídeos** (foto de rua com pessoas, 8 s a 10 fps, nos modos `physio`, `bed` e `surgery`): os três processaram os 80 quadros e geraram `annotated.mp4` (H.264, `yuv420p`, 640×854), `findings.json` e relatório HTML e PDF. Zero achados é o esperado para uma imagem estática: o objetivo era exercitar o pipeline.
- **A fusão usou o áudio:** o alerta crítico do P-0001 passou a citar "Paciente relatou 'dor no peito' (00:09)" junto com o NEWS2 alto.
- **Validações da API:** extensão inválida 422, `physio` sem exercício 422, paciente inexistente 404.

### YOLO: CPU contra GPU (RTX 5070)

| Modelo | CPU | GPU | Detecções |
|---|---|---|---|
| YOLOv8n-pose | 26,4 ms/imagem | 22,9 ms/imagem | 4 pessoas, 17 pontos cada |
| YOLOv8n | 22,9 ms/imagem | 22,7 ms/imagem | ônibus, pessoas, placa |

Com os modelos "nano" a GPU não ganha da CPU: eles são pequenos demais. A GPU só valeria com modelos maiores (`yolov8m`, `yolov8l`) ou processamento em lote.

## Passo 8: alertas

- Primeiro `ack` em um alerta aberto: `status = acknowledged`. Segundo `ack`: HTTP 409.
- **Escalonamento por falta de resposta:** o alerta crítico aberto do P-0004 gerou `ALERTA SEM RESPOSTA` 5 minutos após a criação (`ALERT_ESCALATION_MINUTES = 5`) e ficou com `escalated = true`. O alerta já confirmado do P-0001 não foi escalonado.
- **Elevação de nível:** `ALERTA ESCALONADO` no log é outra coisa: o alerta subiu de atenção para crítico quando chegou mais evidência.

## Defeitos encontrados e corrigidos

| # | Defeito | Correção |
|---|---|---|
| 1 | `redis-py` 8.1.0: um `XREADGROUP BLOCK` vazio levanta `TimeoutError` quando o `socket_timeout` não é maior que o tempo de bloqueio. Derrubava os 4 workers que consomem streams. O `fakeredis` dos testes não bloqueia e não reproduzia | `socket_timeout=60` em `Bus`, `consume` rejeita `block_ms` próximo disso, testes contra Redis real (`tests/test_bus_redis_real.py`). Commit `3ec3182` |
| 2 | Os testes de banco e de API criavam pacientes, alertas e mídias `T-…` no banco ao vivo e não apagavam: 14 pacientes de teste apareciam no dashboard | `tests/conftest.py` apaga só linhas `T-%` no início e no fim da sessão de testes |
| 3 | Dashboard: a coluna "Nível" quebrava "informativo" em duas linhas | Proporção das colunas ajustada em `dashboard/app.py` |
| 4 | Documentação indicava `cu121` para GPU, que não funciona em RTX 50xx (precisa de CUDA 12.8+) | `.env.example`, `Dockerfile`, plano e README passam a usar `cu128` |

## Pontos abertos (não corrigidos nesta tarefa)

1. **Falsos alarmes em pacientes normais** (P-0003 e P-0005): resolvidos pela T36 (persistência e limiares).
2. **Negação não é tratada.** O laudo "Nega febre. Sem sangramento." gerou os termos críticos `febre` e `sangramento`. Para um uso clínico, o detector de termos deveria ignorar menções negadas ("nega", "sem", "ausência de", "descarta"). Fica como melhoria; não está no plano.
3. **Risco do alerta e risco do paciente divergem.** O alerta guarda o risco de pico (P-0004: 99) e o paciente mostra o risco atual, que decai com o tempo (29, "informativo") enquanto o alerta continua aberto. Está coerente com o desenho, mas pode confundir numa demonstração: vale rotular o valor do alerta como "pico".
4. **Repetir o replay duplica evidências.** Rodar o simulador duas vezes sobre o mesmo período gera evidências novas (novos UUIDs) para os mesmos eventos: 143 → 206 neste teste. O risco não muda (a fusão usa a maior contribuição por tipo), mas as contagens crescem. Antes da gravação do vídeo, rode `docker compose down -v` e suba o ambiente uma vez só.
5. **`run_demo.py --external-simulator`** apaga `sim:clock` ao iniciar e espera o simulador publicá-lo de novo; é preciso iniciar o simulador em outro terminal.
6. O aviso `At least one mel filter has all zero values` do extrator do AST é conhecido e inofensivo para este uso.

## O que ainda depende de pessoas

Azure Speech e Language reais (chaves), Teams e Logic App reais, e as amostras reais (consulta em pt-BR, vídeos de agachamento e de queda). Com elas, os testes com `@pytest.mark.azure` e a demonstração completa podem ser verificados de verdade.
