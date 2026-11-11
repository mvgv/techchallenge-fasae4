# Integração com a Azure, com chamadas reais

- **Data:** 2026-11-10
- **Assinatura:** POSTECH, região `brazilsouth`, grupo de recursos `rg-medwatch`
- **Recursos criados por `scripts/provision_azure.sh`:** Azure AI Speech `medwatch-speech-15770` (S0), Azure AI Language `medwatch-lang-15770` (TextAnalytics, S) e conta de armazenamento `medwatch15770` com o contêiner `media`
- **Chaves:** ficam só no `.env` (fora do Git). Este arquivo não contém segredos.

## 1. Verificação de conectividade (`scripts/check_azure.py`)

| Serviço | Resultado |
|---|---|
| Speech (transcrição) | OK |
| Language | OK: sentimento `negative` (0,0 / 0,0 / 1,0) para "Estou com falta de ar e muito cansado." |
| Armazenamento Blob | OK: gravação e leitura de volta em `azure://media/check/...` (com `STORAGE_BACKEND=azure` só nesta execução; o padrão do projeto continua `local`) |

O `hello_ptbr.wav` ("Olá, este é um teste do MedWatch.") foi gerado pela síntese de voz da Azure (`pt-BR-FranciscaNeural`) e transcrito de volta como "Olá, este é um teste do **med Watt**": o nome da marca não é reconhecido.

## 2. Consulta sintética passando pelo pipeline completo

`scripts/synthesize_consulta.py` gerou `consulta_p0001.wav` (38 s, 16 kHz, mono): a médica (`pt-BR-FranciscaNeural`) e o paciente "seu João" (`pt-BR-AntonioNeural`, ritmo mais lento e pausas), com duas tosses **reais** de clipes reservados do ESC-50 (fold 4). O arquivo foi enviado pela API como áudio do paciente P-0001 e processado com a Azure real (`USE_FAKE_AZURE=false`). Terminou em `done` em cerca de 40 s.

### Transcrição e separação de falantes (Azure Speech)

| Tempo | Falante | Texto reconhecido |
|---|---|---|
| 00:00 | Guest-1 | Bom dia, seu João, como senhor passou a noite? |
| 00:04 | Guest-2 | Mau tontura. |
| 00:07 | Guest-2 | Estou com falta de ar desde ontem e um cansaço muito grande. |
| 00:13 | Guest-1 | O senhor teve febre, sentiu dor no peito? |
| 00:18 | Guest-2 | Febre, não sei. |
| 00:20 | Guest-2 | Mas tenho tossido bastante e dói um pouco no peito quando tosso. |
| 00:29 | Guest-1 | Consegue subir escada? |
| 00:32 | Guest-2 | Não fico sem fôlego logo no começo. |

A separação de falantes acertou as 8 falas: Guest-1 é a médica e Guest-2 é o paciente.

### Análise (Azure AI Language, dicionário de termos, AST, openSMILE)

- **Termos críticos:** `dor no peito` (0,9), `falta de ar` (0,8), `febre` (0,5), `cansaço` (0,5) e `tontura` (0,5).
- **Sentimento por fala:** 1 positivo, 5 negativos e 2 neutros; evidência `speech_negative_sentiment` com score 0,63.
- **Entidades de saúde (Text Analytics for Health):** 15 entidades extraídas em português; evidência `clinical_entity`.
- **Sons respiratórios (AST):** `Cough`, score máximo 0,17 em 2 janelas.
- **Atributos de voz (openSMILE):** calculados, mas **sem sentido clínico** numa voz sintética (ver limitações).

Evidências geradas no banco: 5 `speech_critical_term`, 1 `speech_negative_sentiment`, 1 `clinical_entity` e 1 `respiratory_sound`.

O dashboard (tela "Paciente", item da mídia, "Mostrar transcrição e análise") exibe as falas com horário e falante, os termos críticos em negrito e o sentimento de cada fala.

## 3. Limitações observadas

1. **Um erro de reconhecimento virou evidência clínica falsa.** "Mal, doutora" foi reconhecido como "Mau tontura", e `tontura` é um termo crítico (neurológico). A evidência `speech_critical_term: tontura` foi gerada sem que o paciente tenha dito isso. Num uso real, erros de transcrição podem produzir termos clínicos; o sistema deve mostrar o trecho de origem (o dashboard mostra) e o alerta precisa de revisão humana.
2. **A tosse dentro da fala tem score baixo no AST** (0,17), bem abaixo dos 0,46 de uma tosse isolada. A evidência respiratória pesa pouco na fusão nesse caso.
3. **Atributos de voz não valem para voz sintética.** Fadiga e alteração da fala (jitter, pausas, F0) só têm sentido com vozes reais (Common Voice, passo 9 da T37, ainda dependente do humano).
4. **O nome da marca** ("MedWatch") não é reconhecido pelo Speech. Uma lista de frases personalizada poderia corrigir.
5. **A negação continua sem tratamento** nos termos críticos (ver `integracao.md`).

## 4. Pendente (depende de pessoas)

- Custos observados e prints do portal (recursos, métricas de uso e orçamento): preencher no `relatorio-tecnico.md` depois de usar a Azure.
- Orçamento de alerta no portal (Cost Management).
- Teams e Logic App de e-mail.
