# Roteiro da apresentação (vídeo de até 15 minutos)

Substitui a seção 2 do `ROTEIRO_VIDEO.md` (que continua valendo para a **preparação**, a seção 1, e para o plano B).
O enunciado exige no vídeo: **(1)** exemplo prático de áudio e vídeo, **(2)** detecção e resposta a anomalias,
**(3)** integração dos serviços Azure e **(4)** fluxo final do alerta à equipe médica. A ordem abaixo cobre os quatro,
mostra o código de cada parte e termina com a estratégia de classificação e as métricas.

Total: **14 min 30 s**. Quem fala: uma pessoa só, com o painel, o terminal e o editor de código em três janelas.

## Antes de gravar (fora do vídeo)

```bash
docker compose down -v
docker compose up -d --build
python scripts/seed.py
python scripts/train_vitals_iforest.py
python scripts/preflight_demo.py          # tudo ✓; Teams e e-mail dependem do humano
python scripts/run_demo.py --fast-until 355 --tail-speedup 12   # ~13 min; deixe terminar ANTES de gravar
```

Quando o `run_demo.py` terminar, o painel tem o histórico pronto: P-0001 a P-0005 com evidências e alertas. É esse
estado que a **parte 1** mostra. O P-0006 **não** existe ainda: ele é criado ao vivo na parte 2.

Abas e janelas prontas, na ordem em que aparecem:

| Janela | Conteúdo |
|---|---|
| Navegador A | painel <http://localhost:8501> (zoom 110–125%) |
| Navegador B | documentação da API <http://localhost:8000/docs> |
| Terminal 1 | `docker compose logs -f worker-audio worker-video worker-fusion worker-alerts` |
| Terminal 2 | vazio, para os comandos da parte 3 |
| Editor | VS Code com os arquivos das partes 4 a 6 abertos nas funções indicadas |
| Teams / e-mail | outro monitor, se configurados |

Chaves e `.env` fora da tela. Notificações do sistema desligadas. 1080p, 30 fps.

---

## Parte 1 — Pacientes já cadastrados e como avaliamos sinais, sons e vídeos (0:00–3:30)

**Tela:** painel geral. Diga que as cinco pessoas foram criadas pelo `seed.py` e que o simulador alimenta os sinais vitais
de cada uma em tempo acelerado.

| Tempo | Paciente | Abrir | Dizer |
|---|---|---|---|
| 0:00–0:30 | todos | Painel geral | "Cinco modalidades entram pela mesma esteira de eventos (Redis Streams) e viram *evidências* padronizadas; um motor de fusão calcula um risco de 0 a 100 por paciente. O painel se atualiza a cada 5 segundos." |
| 0:30–1:15 | **P-0001** (sinais + voz) | Paciente → gráficos de vitais e a linha do tempo de evidências | "Os **sinais** passam por três detectores: o escore clínico NEWS2, um z-score em streaming e um Isolation Forest sobre vários sinais ao mesmo tempo. Cada evidência traz a explicação em português. Aqui a piora respiratória foi confirmada por sinais **e** pela voz: a regra multimodal multiplicou o risco." |
| 1:15–1:45 | **P-0001** (som) | evidências de áudio: termos críticos, tosse | "O **som** tem dois caminhos: a fala vai para a Azure, que transcreve e acha termos críticos; e a tosse é detectada por um modelo treinado no AudioSet." |
| 1:45–2:15 | **P-0002** | evidências de prescrição e texto | "Prescrições viram regras (interação medicamentosa, mudança brusca de dose); o laudo em texto passa pela Azure Language." |
| 2:15–2:55 | **P-0003** | Mídias → vídeo anotado; evidência `physio_pattern_deviation` | "No **vídeo** de fisioterapia, a pose do YOLO vira medidas por repetição e um modelo decide se a repetição está incorreta. Este clipe é de um voluntário reservado do REHAB24-6." |
| 2:55–3:20 | **P-0004** | evidência `fall_detected`, saída do leito | "A queda vem do UR Fall; a regra usa a caixa da pessoa quando a pose some. É a parte mais frágil, e mostramos o número honesto mais adiante." |
| 3:20–3:30 | **P-0005** | risco baixo | "O quinto paciente é o controle: sem alertas." |

---

## Parte 2 — Cadastrar um paciente pela API e ver a execução em tempo real (3:30–6:00)

**Tela:** navegador B (`/docs`) e, ao lado, o terminal 1 com os logs.

1. **3:30–4:10 — criar o paciente.** Em `POST /patients` → *Try it out*:

   ```json
   {"patient_id": "P-0006", "display_name": "Paciente 06 (ao vivo)", "bed": "UTI-06"}
   ```

   Execute e mostre a resposta `201`. Troque para o painel e atualize: o P-0006 aparece com risco vazio.
   Diga: "O cadastro é uma chamada REST; nenhum serviço precisa ser reiniciado."

2. **4:10–5:10 — enviar mídia e ver os workers.** No painel, em **Enviar mídia**, escolha o P-0006 e envie
   `consulta_p0001.wav` (áudio). Volte ao terminal 1 e mostre, linha a linha, a esteira:
   `api` aceita o upload → `worker-audio` transcreve e analisa → `worker-fusion` recalcula o risco → `worker-alerts`
   decide se abre alerta. Diga: "Cada etapa é um serviço independente que lê de um stream e escreve outro."

3. **5:10–5:40 — resultado.** No painel, o P-0006 sobe de risco (no ensaio chegou a 60, nível **atenção**) e abre
   o alerta `[ATENÇÃO] ... Termo crítico na fala`; abra o paciente e mostre os termos críticos (falta de ar, dor no
   peito) com os horários do áudio. Em seguida envie `cough.wav` e mostre o evento de tosse (`Cough`, 0,46).
   O áudio de tosse não tem fala: a Azure não devolve texto e o sistema segue só com o detector de sons.

4. **5:40–6:00 — alerta à equipe (item 4 do enunciado).** Mostre o alerta **do P-0006**, que acabou de nascer, e o
   do P-0001 com **risco de pico** e **risco atual**; a mensagem no Teams e o e-mail. Clique em **Confirmar** com uma
   nota e mostre o status mudar. Se o Teams e o e-mail não estiverem configurados: mostre o `ConsoleChannel` nos
   logs do `worker-alerts` e diga isso.

> **Observação honesta:** o P-0006 não tem sinais vitais, porque eles vêm do simulador. O risco dele vem só do áudio.

---

## Parte 3 — Integração com a Azure via código: ouvir e ver a transcrição em paralelo (6:00–8:00)

**Tela:** terminal 2, com o som ligado e o editor ao lado.

1. **6:00–6:25 — o código (editor).** Abra `src/medwatch/audio/speech.py`, classe `AzureTranscriber`: "usamos o
   `ConversationTranscriber`, que separa os falantes (diarização)". Depois `src/medwatch/audio/language.py`,
   `AzureLanguageAnalyzer.analyze`: "sentimento, frases-chave e entidades de saúde".
2. **6:25–7:35 — a demonstração ao vivo.** No terminal 2:

   ```bash
   python scripts/demo_azure_live.py data/samples/consulta_p0001.wav --language
   ```

   O script **toca o áudio e, ao mesmo tempo, envia o som à Azure em ritmo real**. Na tela aparecem as hipóteses
   parciais (linha cinza que se reescreve) e depois o trecho final com o **falante** (`Guest-1` e `Guest-2`) e os
   **termos críticos** marcados em vermelho. Diga: "Estamos ouvindo e vendo a Azure transcrever no mesmo instante."

3. **7:35–8:00 — a análise de texto.** Quando a fala termina, o mesmo comando mostra, para cada trecho, sentimento,
   frases-chave e entidades de saúde (por exemplo `falta de ar [SymptomOrSign]`, `peito [BodyStructure]`).
   Diga: "Isso é a Azure Language; os termos críticos vêm do nosso dicionário em `config/critical_terms.yaml`."

> **Limites a dizer em voz alta** (aparecem na saída): a Azure ouviu "mau tontura" onde a voz sintética disse outra
> coisa, e isso virou um termo crítico falso (`tontura`); e "Febre, não sei." foi marcado como febre, porque ainda não
> tratamos **negação**. Ver `docs/resultados/azure_integracao.md`.

---

## Parte 4 — Código do processamento de vídeo (8:00–9:30)

**Tela:** editor. Um arquivo por vez, só a função indicada.

| Tempo | Arquivo → função | O que dizer |
|---|---|---|
| 8:00–8:25 | `src/medwatch/video/models.py` → `PoseEstimator` e `Detector` | "O YOLOv8 dá duas coisas: a pose, com 17 pontos do corpo, e as caixas de objetos e pessoas." |
| 8:25–8:50 | `src/medwatch/video/worker.py` → `VideoWorker._process` | "O worker lê o vídeo a 5–10 quadros por segundo, roda a pose e o detector, e chama a análise do modo certo: fisioterapia, leito ou cirurgia. Gera o vídeo anotado e as evidências." |
| 8:50–9:10 | `src/medwatch/video/physio.py` → `analyze_physio` e `_model_findings` | "Segmenta as repetições pelo ângulo da articulação principal, calcula amplitude, assimetria e distância DTW até a referência, e um modelo decide se a repetição está incorreta." |
| 9:10–9:30 | `src/medwatch/video/bed.py` → `_detect_falls` | "A queda é uma regra: o quadril desce rápido e a caixa da pessoa fica deitada. Quando a pose some com a pessoa no chão, usamos a caixa do detector." |

---

## Parte 5 — Código do processamento de som (9:30–11:00)

| Tempo | Arquivo → função | O que dizer |
|---|---|---|
| 9:30–9:50 | `src/medwatch/audio/worker.py` → `AudioWorker._process` | "Converte para 16 kHz mono, transcreve, acha termos, analisa sentimento, extrai características acústicas e detecta sons respiratórios. Cada resultado vira uma evidência." |
| 9:50–10:10 | `src/medwatch/audio/terms.py` → `find_critical_terms` | "Busca termos do dicionário sem acento e sem diferenciar maiúsculas." |
| 10:10–10:35 | `src/medwatch/audio/acoustic.py` → `extract_features`, `assess_voice` | "Características da voz (ritmo de fala, pausas, jitter) comparadas, por z-score, com uma linha de base de voz saudável. É a parte que indicaria cansaço ou disartria." |
| 10:35–11:00 | `src/medwatch/audio/events.py` → `RespiratoryEventDetector` | "Um modelo treinado no AudioSet (AST) classifica janelas de áudio e marcamos tosse, respiração ofegante, ronco e espirro." |

---

## Parte 6 — Código do processamento de sinais (11:00–12:15)

| Tempo | Arquivo → função | O que dizer |
|---|---|---|
| 11:00–11:20 | `src/medwatch/anomaly/worker.py` → `AnomalyWorker.process_vital` | "Cada leitura passa por filtro fisiológico e por três detectores." |
| 11:20–11:40 | `src/medwatch/anomaly/news2.py` → `news2` | "Escore clínico NEWS2: regras do prontuário, sem aprendizado." |
| 11:40–12:00 | `src/medwatch/anomaly/streaming_stats.py` → `EwmaZ` | "Média e variância móveis por paciente: avisa quando um sinal foge do padrão **dele**." |
| 12:00–12:15 | `src/medwatch/anomaly/iforest.py` → `VitalsIForest` | "Isolation Forest sobre vários sinais ao mesmo tempo, treinado só com dados normais: aprendizado não supervisionado." |

---

## Parte 7 — Estratégia de classificação (12:15–13:15)

**Tela:** `config/fusion.yaml` e `src/medwatch/fusion/engine.py` → `FusionEngine.compute`. Diga, nesta ordem:

1. "**Fusão tardia.** Cada modalidade faz a sua análise e emite evidências com tipo, escore de 0 a 1 e explicação."
2. "Cada evidência tem um **peso** (`weights` no YAML) e **decai com o tempo** (`exp(-Δt/15 min)`)."
3. "Combinamos com **noisy-OR**: `risco = 1 − ∏(1 − contribuição)`. Várias evidências fracas somam, mas nunca passam de 100."
4. "**Regras multimodais** multiplicam o risco quando as modalidades se confirmam (por exemplo, piora respiratória em
   sinais **e** voz, queda em paciente com sedativo)."
5. "**Piso crítico:** queda e NEWS2 alto garantem alerta crítico mesmo com poucos outros sinais."
6. "Os alertas abrem a partir de 40 (aviso) e 70 (crítico), são enviados ao Teams e ao e-mail e escalonam se ninguém confirmar."
7. "Onde há dados rotulados, **aprendemos**: Isolation Forest nos sinais e um classificador no agachamento, escolhido
   por validação cruzada deixando um voluntário de fora. Onde não há, ficamos com regras explicáveis."

---

## Parte 8 — Métricas de avaliação (13:15–14:30)

**Tela:** `docs/resultados/datasets.md` (a tabela de resumo). Diga primeiro **como** medimos:

- "Cada dataset tem três partes: **calibração** e **validação** ajustam limiares e modelos; o **reservado** nunca
  ajusta nada e é medido uma vez. As divisões estão em `config/splits.yaml`."
- "Reportamos **precisão, recall e falsos alarmes** com intervalo de confiança de Wilson; nos modelos, **AUC** com
  intervalo por *bootstrap* de voluntário; nos sinais, métricas **por alerta** (o que a equipe veria), atraso mediano
  e alertas por paciente-dia."

| Componente | Dado real, parte reservada | Resultado |
|---|---|---|
| Sinais vitais | MIMIC-IV, 20 pacientes, 107 paciente-dias, com cenários injetados | recall 0,87; 1,09 alerta por paciente-dia |
| Sons respiratórios | ESC-50, 160 clipes | precisão 0,97 e recall 0,97 |
| Voz saudável | Common Voice, 27 falantes | 7,4% de falsos alarmes (IC 2%–23%) |
| Fisioterapia, agachamento | REHAB24-6, 3 voluntários, 70 repetições | AUC **0,85**; recall 0,83; 31% de falsos alarmes |
| Fisioterapia, erro nomeado | Keraal | o modelo acerta 0,30 (acaso); as regras dão o mesmo achado para os três erros: **não distingue** |
| Queda | CAUCAFall, 100 vídeos | recall **0,24**, nenhum falso alarme |

Termine com os limites, em uma frase cada: "a queda generaliza mal entre câmeras; o erro de fisioterapia não é
distinguível com 17 pontos em 2D; a voz só mede falsos alarmes; os sinais do MIMIC são horários."

**Fechamento (14:20–14:30):** "O sistema roda de ponta a ponta com a Azure, e cada limite está medido e documentado."

---

## Plano B por trecho

| Se falhar | Faça |
|---|---|
| `demo_azure_live.py` sem som ou sem rede | rodar com `--no-audio`, ou mostrar o trecho gravado no ensaio; a transcrição final está em `docs/resultados/azure_integracao.md` |
| Upload do P-0006 lento (a consulta leva ~40 s) | enviar primeiro o `cough.wav` (rápido) e deixar a consulta processando enquanto fala da API |
| Teams ou e-mail sem configuração | mostrar a mensagem de teste do ensaio e o `ConsoleChannel` no `worker-alerts` |
| Painel travado | recarregar a página; os dados continuam no banco |
| Falta de tempo | cortar a parte 6 (sinais) para 40 s e a parte 4 para 1 min; a parte 3 e a parte 8 não se cortam |

## Checklist

- [ ] `preflight_demo.py` todo em ✓ (Teams e e-mail, se configurados) e `run_demo.py` já concluído antes de gravar.
- [ ] Ensaio completo uma vez, cronometrado: o total não pode passar de 15 minutos.
- [ ] `demo_azure_live.py` testado **com o som saindo no dispositivo padrão** e a captura de áudio do sistema ligada.
- [ ] Nenhuma chave, e-mail ou webhook na tela (revisar o vídeo inteiro).
- [ ] Vídeo publicado no YouTube ou Vimeo como **não listado**, e o link no `README.md`.
