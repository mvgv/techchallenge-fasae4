# Roteiro da apresentação: script para gravar sozinho (14 min 30 s)

Como usar: cada passo tem **AÇÃO** (o que fazer, exato), **TELA** (o que deve aparecer) e **FALE** (texto para ler;
pode parafrasear, mas não tire os números). Os tempos acumulados entre parênteses são metas, não pausas: se estiver
adiantado, fale mais devagar; se atrasado, use a lista de cortes no fim.

Os quatro itens que o enunciado exige no vídeo e onde estão: **(1)** exemplo de áudio e vídeo → partes 1 e 3;
**(2)** detecção e resposta a anomalias → partes 1 e 2; **(3)** integração com a Azure → parte 3;
**(4)** fluxo do alerta à equipe → parte 2, passo 2.6.

---

## A. Preparação (antes de apertar "gravar")

### A.1 Subir o ambiente limpo (leva ~20 min; faça uma vez, antes)

Em PowerShell, na pasta do projeto, **um comando de cada vez**:

```bash
docker compose down -v
```

```bash
docker compose up -d --build
```

```bash
python scripts/seed.py
```

```bash
python scripts/train_vitals_iforest.py
```

```bash
python scripts/preflight_demo.py
```

O `preflight_demo.py` deve mostrar ✓ em tudo, exceto Teams e e-mail se ainda não estiverem configurados (✗ nesses dois é esperado).

```bash
python scripts/run_demo.py --fast-until 355 --tail-speedup 12
```

Esse último leva ~13 minutos. **Espere terminar** (aparece `fim do cenário demo` e a lista de alertas). Ele deixa o histórico
dos pacientes P-0001 a P-0005 pronto. **Não crie o P-0006 antes de gravar**: ele nasce ao vivo na parte 2.

### A.2 Conferir o estado do painel (30 s)

Abra <http://localhost:8501> e confira, sem falar nada:

- 5 pacientes (Paciente 01 a 05) na lista; **nenhum** Paciente 06.
- Pelo menos um alerta crítico em "Alertas abertos" (P-0001). Se o P-0004 também tiver um, ótimo (a queda).
- Abra `?page=Paciente&patient=P-0004`, role até a tabela **Linha do tempo de evidências** e confirme uma linha
  **Vídeo · Queda detectada · 0,90**. Se **não** tiver, a queda não foi detectada: pare, não grave, e me chame.

### A.3 Janelas (monte uma vez e não mexa mais)

| Janela | Posição | Conteúdo |
|---|---|---|
| **Navegador** | tela cheia, zoom 125% (`Ctrl` + `+`) | 4 abas, nesta ordem: (1) `http://localhost:8501/?page=Painel+geral` (2) `http://localhost:8000/docs` (3) `http://localhost:8501/?page=Paciente&patient=P-0001` (4) `http://localhost:8501/?page=Paciente&patient=P-0006` |
| **Terminal 1** | metade direita | `docker compose logs -f --tail 0 worker-fusion worker-alerts` (fica rodando; só aparecem linhas novas) |
| **Terminal 2** | metade esquerda | PowerShell na pasta do projeto, vazio, fonte grande |
| **VS Code** | tela cheia, zoom alto (`Ctrl` + `+` três vezes), explorador de arquivos fechado (`Ctrl+B`) | abra uma aba vazia; vai navegar com `Ctrl+P` (arquivo) e `Ctrl+G` (linha) |

Alterne entre as janelas com `Alt+Tab`. **Nunca abra o `.env`**.

### A.4 Gravador

- 1080p, 30 fps. Capture **a tela e o áudio do computador** (o som da consulta na parte 3 sai pelas caixas; sem captura de
  áudio do sistema ele não vai para o vídeo) e o microfone.
- Teste: rode `python scripts/demo_azure_live.py data/samples/consulta_p0001.wav --no-audio` uma vez fora da gravação só
  para ver que a Azure responde, depois grave 10 s de teste e ouça se a voz da consulta está no arquivo.
- Notificações do Windows desligadas. Feche e-mail, chat e qualquer janela com dados pessoais.
- Cronômetro visível em outro monitor ou no celular: veja as metas de tempo abaixo.

---

## Parte 1: Pacientes cadastrados e como avaliamos sinais, sons e vídeos (0:00 a 3:30)

### 1.1 Abertura (0:00 a 0:35)

**AÇÃO:** navegador, aba 1 (Painel geral). Não clique em nada.

**TELA:** lista dos cinco pacientes com risco e nível; alertas abertos abaixo.

**FALE:**
> Este é o MedWatch, um sistema de monitoramento de pacientes que combina sinais vitais, prescrições, movimentação, áudio, texto e vídeo. Cada modalidade analisa os seus dados e emite evidências padronizadas. Um motor de fusão junta essas evidências num risco de zero a cem por paciente, e acima de certos limiares abre um alerta para a equipe médica. O painel se atualiza sozinho a cada cinco segundos. Vou mostrar os cinco pacientes que já estão cadastrados, cada um ilustrando uma modalidade.

### 1.2 P-0001: sinais vitais e voz (0:35 a 1:35)

**AÇÃO:** clique na **aba 3** (Paciente P-0001). Role devagar: gráficos "Sinais vitais", gráfico "Risco ao longo do tempo"
(com as linhas "atenção" e "crítico") e a tabela "Linha do tempo de evidências".

**TELA:** gráficos de frequência cardíaca, saturação e respiração com **linhas verticais tracejadas** (os momentos das
evidências); o risco subindo até passar da linha "crítico"; e a tabela com hora, modalidade, tipo e score de cada evidência.

**FALE:**
> O paciente um é o caso de sinais e voz. Os sinais vitais chegam um por minuto e passam por três detectores. O primeiro é o NEWS2, um escore clínico usado em hospitais, que é regra, não aprendizado. O segundo é um z-score em streaming, que compara cada leitura com o padrão recente do próprio paciente. O terceiro é um Isolation Forest, que olha vários sinais ao mesmo tempo e foi treinado só com dados normais. As linhas tracejadas nos gráficos marcam cada evidência, e a tabela embaixo lista todas, com o tipo e o escore. Cada uma tem uma explicação em português.

**AÇÃO:** role até "Mídias". Clique no item **Áudio · consulta_p0001.wav**. Ligue a chave **Mostrar transcrição e análise**.

**TELA:** a transcrição por falante, com sentimento por trecho e "Termos críticos".

**FALE:**
> A consulta deste paciente foi transcrita pela Azure, com os dois falantes separados. A Azure Language marca o sentimento de cada fala, e o nosso dicionário acha os termos críticos: falta de ar, dor no peito, febre. A confirmação por sinais e por voz disparou uma regra multimodal, que multiplica o risco quando duas modalidades concordam.

### 1.3 P-0002: prescrição e laudo (1:35 a 2:05)

**AÇÃO:** na barra de endereço, abra `http://localhost:8501/?page=Paciente&patient=P-0002` (ou troque o paciente no seletor). Role até a tabela "Linha do tempo de evidências".

**TELA:** linhas das modalidades **Prescrição** e **Texto** (por exemplo, interação medicamentosa e termo crítico no documento).

**FALE:**
> O paciente dois mostra prescrições e texto. As prescrições viram regras: interação entre medicamentos, mudança brusca de dose, início de medicamento de alta vigilância. O laudo em texto passa pela Azure Language e pelo mesmo dicionário de termos críticos, e aqui achou sangramento e falta de ar.

### 1.4 P-0003: vídeo de fisioterapia (2:05 a 2:50)

**AÇÃO:** abra `?page=Paciente&patient=P-0003`. Role até "Mídias", abra **Vídeo · physio_squat_wrong.mp4** e ligue **Mostrar vídeo anotado**. Dê play.

**TELA:** o agachamento com o esqueleto desenhado sobre a pessoa.

**FALE:**
> O paciente três tem um vídeo de fisioterapia. O YOLO versão oito extrai o esqueleto, dezessete pontos do corpo. Dele calculamos medidas por repetição: amplitude de cada articulação, assimetria, distância até uma execução de referência e inclinação do tronco. Um modelo de regressão logística, escolhido por validação cruzada, diz se a repetição está incorreta. Este clipe é de um voluntário que ficou reservado e nunca foi usado para ajustar nada. A evidência fica como informação e não vira alerta, porque o modelo ainda erra uma em cada três repetições corretas.

### 1.5 P-0004 e P-0005: movimento, queda e controle (2:50 a 3:30)

**AÇÃO:** abra `?page=Paciente&patient=P-0004`. Role até a tabela "Linha do tempo de evidências" e **aponte com o mouse** a
linha **Vídeo · Queda detectada**. Opcional (10 s): em "Mídias", abra **Vídeo · bed_fall.mp4**, ligue **Mostrar vídeo anotado**
e dê play. Depois abra `?page=Paciente&patient=P-0005`.

**TELA:** P-0004 com **Agitação noturna** (Movimentação), **Queda detectada** (Vídeo) e NEWS2; P-0005 com risco baixo e nenhum alerta.

**FALE:**
> O paciente quatro mostra movimentação e queda. A agitação noturna e a saída do leito vêm de regras sobre a atividade do paciente. A queda vem de um vídeo de um dataset público: o quadril desce rápido e a pessoa fica deitada, e quando o esqueleto some com a pessoa no chão usamos a caixa que o detector desenha. Essa é a parte mais frágil do sistema, e vou mostrar o número real mais adiante. O paciente cinco é o controle: sem alertas.

---

## Parte 2: Cadastrar um paciente pela API e ver a execução em tempo real (3:30 a 6:15)

### 2.1 Preparar a tela (3:30 a 3:40)

**AÇÃO:** navegador, **aba 2** (`/docs`). Arrume o **Terminal 1** (logs) visível ao lado do navegador.

**FALE:**
> Agora vou cadastrar um paciente novo, ao vivo, pela API, e acompanhar o processamento.

### 2.2 Criar o paciente (3:40 a 4:15)

**AÇÃO:** na página `/docs`, abra **POST /patients**, clique **Try it out**. Apague o corpo e cole exatamente:

```json
{"patient_id": "P-0006", "display_name": "Paciente 06 (ao vivo)", "bed": "UTI-06"}
```

Clique **Execute**. Role até a **Server response**.

**TELA:** código `201` e o JSON do paciente criado.

**FALE:**
> O cadastro é uma chamada REST. A resposta é o código duzentos e um, criado, com o paciente. Nenhum serviço precisou ser reiniciado.

**AÇÃO:** `Alt+Tab` para o navegador, **aba 1**, aperte `F5`.

**TELA:** o Paciente 06 aparece na lista, sem risco ainda.

### 2.3 Enviar a consulta e ver os serviços trabalhando (4:15 a 5:25)

**AÇÃO:** **Terminal 2**, cole e execute:

```bash
curl.exe -s -X POST localhost:8000/media -F patient_id=P-0006 -F kind=audio -F "file=@data/samples/consulta_p0001.wav;type=audio/wav"
```

**TELA:** `{"media_id":"…","status":"queued"}`. Em seguida, no navegador, **aba 4** (Paciente P-0006): em "Mídias" o item
de áudio passa de **na fila** a **processando**.

**FALE (enquanto espera, ~45 s):**
> Enviei a consulta pela API. Ela entra numa fila, o status é "na fila". Cada etapa do sistema é um serviço independente que lê de um fluxo do Redis e escreve em outro. O serviço de áudio converte o arquivo, manda para a Azure transcrever, analisa o texto, e roda um modelo treinado no AudioSet para achar tosse e respiração. As evidências vão para o serviço de fusão, que recalcula o risco, e se o risco passa do limiar, o serviço de alertas notifica a equipe. Estamos esperando a Azure.

**AÇÃO:** aperte `F5` na aba 4 de vez em quando. Olhe o Terminal 1.

**TELA (após ~40 s):** o status vira **concluído**; no Terminal 1 aparecem duas linhas novas: `alerta criado: [ATENÇÃO] Paciente 06 (ao vivo) (P-0006) – Termo crítico na fala`, e o texto `ALERTA [ATENÇÃO] ...` com o risco e os termos.

### 2.4 Mostrar o resultado (5:25 a 5:50)

**AÇÃO:** aba 4, role até o gráfico "Risco ao longo do tempo" (a curva cruza a linha "atenção") e a tabela "Linha do tempo de evidências", depois "Mídias" → áudio → **Mostrar transcrição e análise**.

**FALE:**
> Pronto. O paciente seis subiu de risco sem nenhum sinal vital, só pela consulta: a Azure achou falta de ar e dor no peito, e o sistema abriu um alerta de atenção. Cada linha desta tabela é uma evidência, com o horário do áudio em que ela apareceu.

**AÇÃO (tosse):** **Terminal 2**:

```bash
curl.exe -s -X POST localhost:8000/media -F patient_id=P-0006 -F kind=audio -F "file=@data/samples/cough.wav;type=audio/wav"
```

**FALE:**
> Também enviei um áudio só de tosse, sem fala. A Azure não devolve texto, e o sistema segue só com o detector de sons respiratórios.

(O processamento da tosse leva ~10 s. Se ao final dos 5:50 já tiver concluído, mostre a evidência `Som respiratório detectado: Cough`; se
não, siga em frente, e ele aparece sozinho.)

### 2.5 O alerta chega à equipe (5:50 a 6:15)

**AÇÃO:** navegador, **aba 1**, aperte `F5`. Role até "Alertas abertos". No cartão do **Paciente 06**: digite a nota `Avaliado no leito, em acompanhamento` no campo **Nota (opcional)** e clique **Confirmar**.

**TELA:** o cartão mostra "risco de pico … · risco atual …" e some da lista, com a mensagem "Alerta confirmado."

**FALE:**
> O alerta chega ao painel, ao console e, quando configurados, ao Teams e ao e-mail. Cada cartão mostra o risco de pico do alerta e o risco atual do paciente. Se ninguém confirmar em cinco minutos, o alerta escala. Aqui a equipe confirma com uma nota, e o sistema registra quem confirmou e quando.

### 2.6 Teams e e-mail (se configurados)

Se o webhook do Teams e a Logic App estiverem configurados: **antes de** 2.5, mostre a janela do Teams com a mensagem do alerta e a
caixa de e-mail com a mensagem, e diga: "O mesmo alerta chegou ao Teams e ao e-mail." Se **não** estiverem configurados, diga em 2.5:
"Nesta gravação os canais de Teams e e-mail não estão configurados, então o alerta sai pelo console, que é o que aparece no log."

---

## Parte 3: Integração com a Azure por código, ouvindo e vendo em paralelo (6:15 a 8:15)

### 3.1 O código (6:15 a 6:45)

**AÇÃO:** `Alt+Tab` para o VS Code. `Ctrl+P`, digite `audio/speech.py`, `Enter`. `Ctrl+G`, digite `35`, `Enter`.

**TELA:** a classe `AzureTranscriber`.

**FALE:**
> Aqui está a integração com a Azure Speech. Usamos o ConversationTranscriber, que além de transcrever separa os falantes, e isso é importante numa consulta com médico e paciente. Cada trecho reconhecido volta com o texto, o falante e o instante.

**AÇÃO:** `Ctrl+P`, `audio/language.py`, `Enter`. `Ctrl+G`, `29`, `Enter`.

**FALE:**
> E aqui a Azure Language: para cada fala pedimos o sentimento, as frases-chave e as entidades de saúde.

### 3.2 A demonstração ao vivo (6:45 a 7:55)

**AÇÃO:** `Alt+Tab` para o **Terminal 2**. **Aumente o volume do computador.** Cole e execute:

```bash
python scripts/demo_azure_live.py data/samples/consulta_p0001.wav --language
```

**TELA (durante ~40 s, com o áudio tocando):** o título "Azure Speech ao vivo"; uma linha cinza que se reescreve com a hipótese
da Azure enquanto a voz fala; quando a frase termina, a linha final com `Guest-1` ou `Guest-2`, e os termos críticos em vermelho
(`falta de ar`, `dor no peito`, `febre`).

**FALE (comece quando a voz começar, e fale por cima, em tom baixo, só nas pausas do áudio):**
> Estamos ouvindo a consulta e, ao mesmo tempo, vendo a Azure transcrever em tempo real. A linha cinza é a hipótese parcial, que muda enquanto a pessoa fala. Quando a frase fecha, ela vira definitiva, com o falante. Os termos em vermelho vêm do nosso dicionário de termos críticos.

**TELA (depois da transcrição, ~5 s):** o bloco "Azure Language", com sentimento, frases-chave e entidades de saúde por trecho.

**FALE:**
> A Azure Language devolve o sentimento de cada fala, as frases-chave e as entidades de saúde, por exemplo falta de ar como sintoma e peito como estrutura do corpo.

### 3.3 Os limites, ditos em voz alta (7:55 a 8:15)

**FALE:**
> Dois limites aparecem aqui. A Azure ouviu "mau tontura" onde o áudio sintético dizia outra coisa, e isso virou um termo crítico falso. E "febre, não sei" foi marcado como febre, porque ainda não tratamos negação. São limitações conhecidas e estão documentadas.

---

## Parte 4: Código do processamento de vídeo (8:15 a 9:45)

Para cada arquivo: `Ctrl+P`, digite o caminho, `Enter`; `Ctrl+G`, digite a linha, `Enter`. Fale enquanto rola devagar.

| Passo | Arquivo, linha | FALE |
|---|---|---|
| 4.1 (8:15) | `video/models.py`, **50** (`PoseEstimator`); depois **26** (`Detector`) | "O YOLO versão oito nos dá duas coisas. A pose, com dezessete pontos do corpo por pessoa, e o detector, que dá caixas de pessoas e objetos." |
| 4.2 (8:40) | `video/worker.py`, **146** (`_process`) | "O trabalhador de vídeo lê o arquivo a cinco a dez quadros por segundo e roda a pose em cada um. Se o modo é leito e a pose some, ele usa a caixa do detector de pessoas. Depois chama a análise do modo certo: fisioterapia, leito ou cirurgia, e na segunda passada desenha o vídeo anotado que vimos no painel." |
| 4.3 (9:05) | `video/physio.py`, **132** (`analyze_physio`); depois **231** (`_model_findings`) | "Na fisioterapia, ele segmenta as repetições pelo ângulo da articulação principal, calcula amplitude, assimetria, distância DTW até a referência e inclinação do tronco. Essas medidas alimentam o modelo, que decide se a repetição está incorreta." |
| 4.4 (9:25) | `video/bed.py`, **37** (`_detect_falls`) | "A queda é uma regra: o quadril desce mais que um limite em uma janela de tempo e a pessoa fica deitada, com a caixa mais larga que alta, por um tempo mínimo. Os limites foram ajustados num dataset e medidos em outro." |

---

## Parte 5: Código do processamento de som (9:45 a 11:15)

| Passo | Arquivo, linha | FALE |
|---|---|---|
| 5.1 (9:45) | `audio/worker.py`, **78** (`_process`) | "O trabalhador de áudio converte o arquivo para dezesseis quilohertz mono, transcreve na Azure, analisa o texto, extrai características da voz e detecta sons respiratórios. Cada resultado vira uma evidência com o tipo, o escore e a explicação." |
| 5.2 (10:10) | `audio/terms.py`, **11** (`find_critical_terms`) | "Os termos críticos vêm de um dicionário em YAML, com categoria e peso. A busca ignora acento e maiúsculas." |
| 5.3 (10:30) | `audio/acoustic.py`, **42** (`extract_features`); depois **85** (`assess_voice`) | "A voz do paciente vira características como ritmo de fala, pausas e jitter, comparadas por z-score com uma linha de base de vozes saudáveis. É isso que indicaria cansaço ou disartria." |
| 5.4 (10:50) | `audio/events.py`, **23** (`RespiratoryEventDetector`) | "Um modelo treinado no AudioSet, o AST, classifica janelas de áudio, e marcamos tosse, respiração ofegante, ronco e espirro." |

---

## Parte 6: Código do processamento de sinais (11:15 a 12:30)

| Passo | Arquivo, linha | FALE |
|---|---|---|
| 6.1 (11:15) | `anomaly/worker.py`, **100** (`process_vital`) | "Cada leitura passa por um filtro fisiológico, que descarta valores impossíveis, e depois pelos três detectores." |
| 6.2 (11:35) | `anomaly/news2.py`, **67** (`news2`) | "O NEWS2 é o escore clínico: pontos por frequência respiratória, saturação, pressão, frequência cardíaca e temperatura. São regras, sem aprendizado." |
| 6.3 (11:55) | `anomaly/streaming_stats.py`, **7** (`EwmaZ`) | "O z-score usa média e variância móveis por paciente, e avisa quando um sinal foge do padrão dele, não do padrão da população." |
| 6.4 (12:10) | `anomaly/iforest.py`, **54** (`VitalsIForest`) | "O Isolation Forest olha vários sinais ao mesmo tempo, treinado só com dados normais: é aprendizado não supervisionado, e pega combinações incomuns que cada sinal sozinho não mostraria." |

---

## Parte 7: Estratégia de classificação (12:30 a 13:30)

**AÇÃO:** `Ctrl+P`, `config/fusion.yaml`, `Enter`, topo do arquivo. Depois `Ctrl+P`, `fusion/engine.py`, `Enter`, `Ctrl+G`, `49` (`compute`).

**FALE:**
> A nossa estratégia é fusão tardia. Cada modalidade faz a sua análise e emite evidências com tipo, escore de zero a um e explicação. No motor de fusão, cada evidência tem um peso, definido neste arquivo, e perde força com o tempo: o peso cai com a exponencial do tempo dividido por quinze minutos. Combinamos as contribuições com noisy-or: o risco é um menos o produto de um menos cada contribuição. Várias evidências fracas somam, mas nunca passam de cem. Depois, regras multimodais multiplicam o risco quando duas modalidades se confirmam, como piora respiratória em sinais e em voz. E há um piso crítico: queda, NEWS2 alto e contagem de instrumentos inconsistente garantem alerta crítico mesmo com poucas outras evidências. Acima de quarenta é aviso, acima de setenta é crítico. E onde havia dados com rótulo, aprendemos: o Isolation Forest nos sinais e um classificador no agachamento. Onde não havia, ficamos com regras que o médico consegue ler.

---

## Parte 8: Métricas de avaliação e fechamento (13:30 a 14:30)

**AÇÃO:** VS Code: `Ctrl+P`, `docs/resultados/datasets.md`, `Enter`. Abra a prévia com `Ctrl+Shift+V` (a tabela fica legível).

**FALE (método, 13:30 a 13:50):**
> Como medimos. Cada dataset tem três partes: calibração e validação ajustam limiares e modelos, e o reservado nunca ajusta nada, e é medido uma só vez. Reportamos precisão, recall e falsos alarmes com intervalo de confiança, e nos modelos, a área sob a curva com intervalo por voluntário. Nos sinais, medimos por alerta, que é o que a equipe veria.

**FALE (resultados, 13:50 a 14:20; aponte cada linha com o mouse):**
> Nos sinais vitais reais do MIMIC, com cenários injetados, o recall foi zero vírgula oitenta e sete. Nos sons respiratórios, precisão e recall de zero vírgula noventa e sete. Na voz saudável, sete por cento de falsos alarmes. No agachamento, o modelo chegou a AUC zero vírgula oitenta e cinco, com recall de zero vírgula oitenta e três e trinta e um por cento de falsos alarmes, contra sessenta e um por cento de recall e quarenta e quatro de falsos alarmes das regras. E agora o que não funcionou: a queda detectou doze de cinquenta no dataset reservado, porque a câmera alta no canto deixa a pessoa caída parecer em pé para uma regra em duas dimensões; e o erro nomeado da fisioterapia, nos dados do Keraal, ficou no nível do acaso.

**FALE (fechamento, 14:20 a 14:30):**
> O sistema roda de ponta a ponta com a Azure, e cada limite está medido e documentado no repositório. Obrigado.

**AÇÃO:** pare a gravação.

---

## Se o tempo estourar: o que cortar (nesta ordem)

1. Parte 6: reduza para 40 s (só 6.1 e 6.4).
2. Parte 4: reduza para 1 min (só 4.2 e 4.4).
3. Passo 1.3 (P-0002): 15 s.
4. A tosse do passo 2.4.

**Não corte:** a parte 3 inteira, o passo 2.5 (alerta) e a parte 8 (métricas e limites).

## Se algo der errado durante a gravação

| Situação | O que fazer |
|---|---|
| A consulta do P-0006 demora mais de 60 s | Continue falando sobre a arquitetura; ela termina. Se passar de 2 min, corte e refaça só esse trecho depois (grave os trechos separados). |
| `demo_azure_live.py` sem som no vídeo | A captura de áudio do sistema não estava ligada: grave só a parte 3 de novo. Com `--no-audio`, a transcrição aparece igual, sem o som. |
| `demo_azure_live.py` dá erro de chave ou rede | Pare, grave a parte 3 com o trecho de ensaio gravado antes e diga que é um trecho gravado. |
| O painel não atualiza | `F5` na página; os dados continuam no banco. |
| Errou uma fala | Pare 3 s em silêncio e repita a frase inteira do começo; corte na edição. |

## Checklist final

- [ ] A.1 a A.4 feitos; `preflight_demo.py` com ✓ (Teams e e-mail, se configurados) e `run_demo.py` já concluído.
- [ ] A.2: `fall_detected` aparece no P-0004 antes de gravar.
- [ ] Nenhuma chave, e-mail ou webhook na tela (revise o vídeo inteiro).
- [ ] Duração final **menor que 15:00**.
- [ ] Vídeo publicado no YouTube ou Vimeo como **não listado**, e o link no `README.md`.
