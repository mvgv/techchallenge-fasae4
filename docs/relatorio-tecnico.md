# MedWatch — Relatório técnico

Tech Challenge IADT, Fase 4: monitoramento multimodal de pacientes com Python e Azure AI.

> Itens marcados **[PENDENTE]** dependem de passos humanos (chaves Azure, gravações, prints) e não foram verificados.

## 1. Introdução e objetivo

Equipes clínicas recebem informação dispersa: sinais vitais num sistema, prescrições noutro, vídeos de fisioterapia ou
de leito sem análise, consultas gravadas e laudos em texto. O MedWatch integra essas fontes num fluxo único. Cada
modalidade é analisada por modelos específicos e produz **evidências** padronizadas e explicáveis; um motor de fusão
transforma o conjunto num **escore de risco por paciente** e dispara **alertas** que a equipe confirma ou descarta.

Objetivos: (a) cobrir vídeo, áudio, texto e séries temporais; (b) usar serviços Azure AI onde há ganho (fala e
linguagem); (c) manter cada alerta rastreável até a mídia/medida de origem; (d) rodar de forma reprodutível com Docker Compose.

O sistema é um protótipo acadêmico, não um dispositivo médico.

## 2. Descrição do fluxo multimodal

Diagrama completo, serviços, streams e tabelas: [`arquitetura.md`](arquitetura.md).

```mermaid
sequenceDiagram
    participant U as Usuário / Simulador
    participant A as API
    participant R as Redis Streams
    participant W as Worker da modalidade
    participant F as worker-fusion
    participant L as worker-alerts
    participant D as Dashboard
    U->>A: upload de mídia (ou stream de vitais)
    A->>R: jobs.video / jobs.audio / jobs.text
    R->>W: job
    W->>W: modelos (YOLO, Speech, NEWS2...)
    W->>R: Evidence (stream evidence)
    R->>F: Evidence
    F->>F: noisy-OR + regras multimodais
    F->>R: alerta (stream alerts)
    R->>L: alerta
    L->>D: alerta visível na API/dashboard
    L-->>U: Teams / e-mail / console
    D->>A: confirmar ou descartar
```

**Sequência de um alerta (exemplo).** Um áudio de consulta é enviado para o paciente P-0001: o worker de áudio converte
para WAV 16 kHz, transcreve com Azure Speech, procura termos críticos (ex.: "falta de ar") e detecta tosse. Publica
`speech_critical_term` e `respiratory_sound`. Se o paciente já tem `news2_medium` recente, o worker de fusão aplica o
noisy-OR e a regra *respiratorio_multimodal* (×1,4), o escore cruza 70 e um alerta crítico é criado, com título e resumo
em português apontando as evidências. O worker de alertas notifica e, se ninguém confirmar em
`ALERT_ESCALATION_MINUTES`, escalona.

**Contrato de evidências.** Toda saída vira uma `Evidence` com `type` do catálogo (29 tipos, `arquitetura.md`), `score`
0–1, `severity`, intervalo de tempo, `explanation` em pt-BR, `source_ref` (ex.: `media:<uuid>#t=130`), `model_name`,
`model_version` e `payload`. O contrato desacopla os produtores da fusão: um novo modelo só precisa emitir evidências.

## 3. Modelos aplicados por tipo de dado

| Modalidade | Modelo / serviço | Entrada | Saída | Motivo da escolha | Limitações |
|---|---|---|---|---|---|
| Vídeo (objetos) | YOLOv8n (COCO) | frames | caixas e classes | leve, roda em CPU, pesos públicos | COCO só conhece objetos genéricos: instrumentos cirúrgicos reais não são reconhecidos; a análise de cirurgia é demonstrativa |
| Vídeo (pose) | YOLOv8n-pose | frames | 17 keypoints | mesmo runtime do detector, sem dependências extras | menos preciso que OpenPose em oclusão; OpenPose opcional (T19b/T34) não implementado |
| Fisioterapia | Ângulos articulares + contagem de repetições + **DTW** contra referência | keypoints | ROM, assimetria, desvio de padrão, compensação de tronco | DTW compara a forma do movimento sem depender da velocidade; referência gerada de um vídeo correto | depende de câmera lateral e corpo inteiro; referência real exige gravação **[PENDENTE]** |
| Leito | Regras sobre pose/posição do tronco | keypoints | queda, saída do leito | simples e explicável | sem validação em vídeo de queda real **[PENDENTE]**; ângulo de câmera sensível |
| Fala | **Azure Speech** (pt-BR) | WAV 16 kHz | transcrição por segmentos | qualidade e suporte a pt-BR sem treinar modelo | custo por hora de áudio; requer chaves **[PENDENTE]**; há cliente falso para testes |
| Linguagem | **Azure AI Language** + dicionário de termos críticos | transcrição / laudo | sentimento, entidades clínicas | entidades de saúde prontas; dicionário cobre termos críticos em pt-BR | entidades de saúde dependem da região; dicionário é lista fechada |
| Voz | **openSMILE** (eGeMAPS) + pausas/velocidade | áudio | indicadores de fadiga e disartria vs. linha de base | features acústicas interpretáveis | precisa de linha de base individual; no ambiente de desenvolvimento o openSMILE não importou (pyarrow x NumPy), então só pausa/velocidade foram exercitadas |
| Sons respiratórios | **AST** (`MIT/ast-finetuned-audioset-10-10-0.4593`) | janelas de áudio | tosse, espirro etc. com score | modelo treinado no AudioSet, sem treino próprio | ~350 MB; só eventos de classe respiratória com score ≥ 0,6 viram evidência; teste com modelo real não executado |
| Vitais (regra) | **NEWS2** + filtro fisiológico | FC, PA, SpO₂, FR, T, consciência, O₂ | escore 0–20 e evidências | padrão clínico conhecido e explicável | não substitui avaliação clínica; filtro descarta valores impossíveis (artefato de sensor) |
| Vitais (estatística) | **EWMA z-score** em streaming | série de cada sinal | desvio relativo ao próprio paciente | adapta-se a cada paciente, custo constante | limiar 3,0 gera falsos positivos em séries de baixa variância |
| Vitais (ML) | **Isolation Forest** | janela de features por minuto | score de anomalia | não supervisionado, não exige rótulos | treinado em dados sintéticos; `--mimic` não testado; muitos falsos positivos |
| Prescrições | Regras + `config/drugs.yaml` | eventos de prescrição | mudança de dose, medicamento de alta vigilância, interação, classe duplicada, rajada | explicável, baseado em listas curadas | lista pequena e não clínica; não cobre todas as interações |
| Movimentação | Regras sobre contagem de atividade | `MovementSample` | inatividade, agitação noturna, saída do leito | simples | noite definida em UTC na demo |
| Fusão | **noisy-OR** com decaimento exponencial e regras multimodais | evidências | risco 0–100, nível, contribuições | probabilístico, monotônico, cada contribuição explicável | pesos definidos por julgamento, não calibrados com desfechos reais |

## 4. Integração com a Azure

| Recurso | Uso | Observações |
|---|---|---|
| Azure AI Speech | transcrição pt-BR no worker de áudio | região padrão `brazilsouth` |
| Azure AI Language | sentimento e entidades clínicas | se a região não oferecer saúde, usar `eastus` com dados sintéticos |
| Azure Blob Storage | armazenamento de mídias e artefatos (opcional; padrão `local`) | `STORAGE_BACKEND=azure` |
| Logic App / Teams | alertas por e-mail e canal (opcional) | webhooks pelo `.env` |

O provisionamento é feito por `scripts/provision_azure.sh` (grupo `rg-medwatch`) e a verificação por
`scripts/check_azure.py`. Com `USE_FAKE_AZURE=true` todo o fluxo roda offline com clientes falsos.

- **Execução real:** feita em 2026-11-10 na assinatura POSTECH (região `brazilsouth`): Speech, Language (inclusive entidades
  de saúde em português) e Blob responderam, e uma consulta sintética de 38 s passou pelo pipeline completo, com separação de
  falantes correta. Detalhes, a transcrição e as limitações (erro de reconhecimento que gerou um termo crítico falso) estão
  em `docs/resultados/azure_integracao.md`.
- **Custos observados:** **[PENDENTE]** — ler no portal (Cost Management) depois da demo; o consumo até aqui foi de poucos
  minutos de áudio e algumas chamadas (Speech cobra por hora de áudio; Language por 1.000 registros).
- **Prints do portal:** **[PENDENTE]** — recursos criados, métricas de uso e orçamento.

## 5. Resultados obtidos

### 5.1 Sinais vitais (dados sintéticos)

Avaliação com `scripts/evaluate_vitals.py`: 30 pacientes sintéticos (seeds 100–129), 24 h cada, 15 episódios rotulados
(deterioração respiratória, hipotensão, taquicardia) e 10 pacientes normais. A T36 trocou o método da T31, que dava
precisão de 1% a 3%, por dois motivos: (1) no gerador a piora continuava até o fim do dia, mas o rótulo terminava no fim
da rampa, então cada repetição do NEWS2 com o paciente ainda grave contava como falso positivo (agora os rótulos de
`respiratory_deterioration` e `hypotension` vão até o fim da série); (2) contar cada evidência como um erro não mede o
que a equipe médica recebe. Passaram a existir três métricas: por evidência (a antiga), por episódio (detecções do mesmo
tipo com menos de 30 min entre si formam um episódio) e **por alerta** (evidências passadas pelo motor de fusão; o
alerta abre em nível `warning` ou mais e fecha com risco < 20 por 60 min). O número principal é o do alerta.

Limiares escolhidos numa grade de 24 combinações (`docs/resultados/vitals_tuning.md`): z-score 3,0 com persistência 1;
Isolation Forest no percentil 0,1 com persistência 3.

**Por alerta (seeds 100–129)**

| Configuração | TP | FP | FN | Precisão | Recall | Atraso mediano (min) | Alertas/dia em normais |
|---|---|---|---|---|---|---|---|
| NEWS2 | 6 | 1 | 9 | 0,86 | 0,40 | 40,0 | 0,00 |
| NEWS2 + z-score | 13 | 3 | 2 | 0,81 | 0,87 | 37,0 | 0,10 |
| NEWS2 + z-score + IForest | 14 | 3 | 1 | 0,82 | 0,93 | 30,5 | 0,10 |

**Antes × depois (NEWS2 + z-score + IForest)**

| Método | Precisão | Recall | FP por paciente-dia (normais) |
|---|---|---|---|
| T31: por evidência, rótulos curtos, limiares antigos | 0,01 | 1,00 | 87,7 (todos os pacientes) |
| T36: por evidência, rótulos persistentes | 0,01 | 1,00 | 49,5 (todos os pacientes) |
| T36: por episódio | 0,03 | 1,00 | 21,1 episódios/dia (normais) |
| **T36: por alerta, limiares ajustados** | **0,82** | **0,93** | **0,10 alertas/dia (normais)** |

Fonte: `docs/resultados/vitals_metrics.csv` / `.md`; exemplo gráfico em `docs/resultados/vitals_example.png`.

**Leitura honesta.** A meta de recall de 100% nos positivos não foi alcançada no conjunto de ajuste (14 de 15; no
conjunto de conferência, seeds 200–229, nunca usado no ajuste, o recall foi 1,00 com 0,00 alerta por paciente-dia em
normais). O rótulo perdido é uma hipotensão lenta cuja PAS (~82 mmHg) dá só 3 pontos de NEWS2 (faixa `low_medium`, peso
0,45), risco ≈ 14, abaixo do nível de alerta; resolver exigiria mexer nos pesos da fusão, o que ficou fora do escopo. A
meta de menos de 1 alerta por paciente-dia em normais foi atingida (0,10). Os dados são sintéticos e o gerador tem
ruído simples; o ganho em precisão vem principalmente de medir alertas em vez de evidências e de a fusão limitar o
efeito de detectores ruidosos (só a maior contribuição por tipo conta). Por evidência e por episódio o z-score continua
gerando muitas detecções em normais (21 episódios por paciente-dia); elas não viram alerta porque o peso é 0,40.

### 5.2 Vídeo

`scripts/evaluate_video.py` está pronto e compara detecções com `data/samples/video_annotations.csv`, mas não foi
executado: faltam vídeos anotados **[PENDENTE]**. Os módulos de vídeo foram verificados com keypoints e detecções
sintéticas (testes automatizados), não com vídeos reais.

### 5.3 Exemplos de anomalias detectadas

O roteiro `scripts/run_demo.py` injeta, em momentos definidos da linha do tempo simulada, as mídias de demonstração:
consulta em áudio (P-0001, min. 370), laudo (P-0002, min. 385), agachamento incorreto (P-0003, min. 365) e queda
(P-0004, min. 410), além da deterioração dos vitais. Os casos a documentar, com prints do dashboard:

1. Frame anotado de queda do leito (`fall_detected`) **[PENDENTE]**
2. Transcrição com termos críticos destacados (`speech_critical_term`) **[PENDENTE]**
3. Gráfico de vitais com NEWS2 e evidências (`news2_*`; exemplo sintético em `docs/resultados/vitals_example.png`)
4. Agachamento com amplitude reduzida (`physio_low_rom`, `physio_pattern_deviation`) **[PENDENTE]**
5. Alerta no Teams **[PENDENTE]**

Estes casos exigem as amostras de mídia, os pesos YOLO e (para 2 e 5) chaves Azure e webhook, ainda não disponíveis.

## 6. Limitações, ética e LGPD

- **Não é dispositivo médico.** Alertas são apoio à decisão; a confirmação é sempre humana (ack/descartar no dashboard).
- **Dados:** somente sintéticos, encenados ou públicos (MIMIC-IV Demo, Le2i/UR Fall, KIMORE), respeitando licenças. Nenhum
  dado real de paciente deve ser enviado. `.env`, `data/` e `models/` ficam fora do Git.
- **LGPD:** dados de saúde são sensíveis (art. 11). Um uso real exigiria base legal, minimização, controle de acesso,
  registro de auditoria, retenção definida, relatório de impacto e contrato com a Microsoft cobrindo o tratamento na
  nuvem (região, subprocessadores). Vídeo e voz também são dados pessoais/biométricos.
- **Vieses e validade:** modelos COCO/AudioSet não foram treinados para ambiente hospitalar; vozes, sotaques e câmeras
  diferentes alteram o desempenho; indicadores de fadiga/disartria exigem linha de base individual.
- **Validação:** métricas vêm de dados sintéticos; não há avaliação clínica. Pesos de fusão não são calibrados.
- **Falsos positivos** geram fadiga de alertas; cooldown e escalonamento mitigam, mas precisam de ajuste fino.
- **Explicabilidade:** cada alerta lista as evidências e as contribuições (top 10), com `source_ref` para a mídia.

## 7. Próximos passos

1. Executar a demonstração completa com amostras reais, chaves Azure e Teams, e preencher as seções 4 e 5.3.
2. Anotar vídeos e rodar `evaluate_video.py`.
3. Treinar o Isolation Forest com MIMIC-IV e reduzir os falsos positivos do z-score por evidência (agora só mitigados pela fusão).
4. Calibrar os pesos de fusão com desfechos rotulados.
5. Substituir/complementar o YOLO COCO por detector de instrumentos cirúrgicos treinado; avaliar OpenPose.
6. Integrar a um padrão de interoperabilidade (HL7 FHIR) e adicionar autenticação, auditoria e RBAC.
