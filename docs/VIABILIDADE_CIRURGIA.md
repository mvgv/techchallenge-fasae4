# Viabilidade: mudar o foco do vídeo para cirurgia

Estudo de 2026-11-13. Pergunta: depois dos resultados fracos de fisioterapia (T39, T40) e de queda (T37), vale trocar o foco da análise de vídeo para cirurgia, onde talvez existam datasets melhores?

**Resposta curta:** trocar, não; **complementar**, sim, em duas etapas. A fisioterapia e a queda precisam ficar, porque são elas que cobrem a análise postural e a movimentação do paciente que o enunciado pede. A cirurgia entra como **cirurgia laparoscópica com YOLOv8 treinado em instrumentos** (dados abertos, sem formulário), e a detecção de desvios no fluxo da cirurgia só depois, se o acesso ao Cholec80 completo sair.

## 1. O que o enunciado pede

Do PDF do Tech Challenge (Fase 4):

- **Análise de vídeo:** processar vídeos clínicos, "por exemplo sessões de fisioterapia **ou** cirurgias gravadas"; detectar movimentos ou eventos fora do padrão com **OpenPose para análise postural** e **YOLOv8 para detecção de objetos e áreas críticas**; gerar relatórios de desvios ou falhas no procedimento.
- **Detecção de anomalias:** sinais vitais, prescrições e **padrões de movimentação do paciente durante a internação**.
- **Datasets sugeridos:** só PhysioNet e AudioSet. Nenhum tem vídeo de cirurgia.

Consequências:

1. Cirurgia **ou** fisioterapia: as duas atendem o item de vídeo. Mudar o foco é permitido.
2. A análise **postural** (pose) não tem uso em vídeo laparoscópico, que mostra o interior do abdome. Se a fisioterapia sair, o requisito de pose fica sem demonstração.
3. A **movimentação do paciente** (queda, saída do leito) é um item separado, de anomalias. A queda fica de qualquer jeito.

## 2. O que existe hoje em cirurgia

T23 (`src/medwatch/video/surgery.py`): regras sobre a câmera da **sala** de cirurgia.

| Regra | Como funciona | Medida com dado real? |
|---|---|---|
| `surgery_zone_intrusion` | mais pessoas que o permitido no polígono do campo estéril por ≥ 3 s | não |
| `surgery_instrument_out_of_zone` | tesoura ou faca do COCO fora da bandeja e do campo | não |
| `surgery_instrument_count_mismatch` | contagem na bandeja no início ≠ no fim | não |

O YOLOv8 usado é o pré-treinado no COCO, que só conhece objetos genéricos (`scissors`, `knife`). O próprio plano registra que instrumento cirúrgico real exige ajuste fino (T34, opcional). "Pessoa sem paramentação", que estava na proposta inicial, não foi implementado: o COCO não distingue avental cirúrgico.

## 3. Dois tipos de vídeo de cirurgia, e por que isso importa

| Tipo | Câmera | O que se vê | Combina com o módulo atual? |
|---|---|---|---|
| **Sala** | fixa no teto ou parede | equipe, mesa, bandeja | sim: é o que a T23 assume |
| **Laparoscópica / endoscópica** | dentro do paciente | órgãos e pontas dos instrumentos | não: exige um modo novo |

Os datasets públicos bons e grandes são quase todos **laparoscópicos**. Os de **sala** são pequenos, sem rótulo de anomalia ou de acesso incerto.

## 4. Datasets levantados

| Dataset | Tipo | Conteúdo e rótulos | Licença | Acesso | Tamanho | Uso possível |
|---|---|---|---|---|---|---|
| [Cholec80](https://camma.unistra.fr/?p=641) | laparoscópica | 80 colecistectomias de 13 cirurgiões; fase da cirurgia por quadro; presença de 7 instrumentos a cada 25 quadros | CC BY-NC-SA 4.0 | **formulário** (CAMMA, Estrasburgo) | não confirmado (dezenas de GB) | fases e presença de instrumentos ao longo do tempo: base para "desvio do fluxo normal" |
| [Cholec80-Boxes](https://zenodo.org/records/13170928) | laparoscópica | quadros a 1 Hz de 5 vídeos do Cholec80 (PNG 854×480) com **caixas** de instrumentos (`ROI_Labels.csv`) | CC BY-NC-SA 4.0 | **aberto** (Zenodo) | 6,5 GB (`Images.rar`) + 1,5 MB | ajuste fino do YOLOv8 para instrumentos, com mAP medido num vídeo reservado |
| m2cai16-tool-locations | laparoscópica | caixas de instrumentos | não confirmada | não confirmado | — | alternativa ao anterior |
| [SurgBlood](https://arxiv.org/html/2503.22174v3) | laparoscópica | 5.330 quadros de 95 vídeos com máscara e ponto de **sangramento**, anotados por dois cirurgiões | não confirmada | o artigo (CVPR 2026) diz que os dados estão disponíveis; link não confirmado | — | **anomalia real rotulada** (sangramento) |
| [Smoke_cholec80](https://ftp.itec.aau.at/datasets/Smoke_cholec80) | laparoscópica | imagens com e sem fumaça de cauterização | não confirmada | aberto (FTP) | — | evento visual "fora do padrão", de baixo valor clínico |
| [MVOR](https://github.com/CAMMA-public/MVOR) | sala | 732 quadros sincronizados de 3 câmeras RGB-D numa sala híbrida; caixas e pose 2D/3D das pessoas; rostos borrados | não confirmada | link de download no GitHub | — | medir se o YOLO conta pessoas numa sala real (valida `surgery_zone_intrusion`); **sem rótulo de anomalia** |
| 4D-OR | sala | 10 cirurgias simuladas de joelho, 6 câmeras RGB-D | não confirmada | não confirmado | — | idem, mas sem acesso confirmado |
| Bandeja de instrumentos | sala | — | — | nenhum dataset aberto encontrado; o mais próximo é de [instrumentos odontológicos](https://data.mendeley.com/datasets/mh6zpc7y9g) | — | contagem na bandeja continuaria sem medida |

**Nenhum dataset traz rótulo de "procedimento anômalo"** do jeito que o enunciado sugere. As anomalias em cirurgia teriam de ser **definidas por nós**: sangramento (SurgBlood, se acessível), instrumento inesperado para a fase, fase longa demais ou fora de ordem (aprendendo o normal no Cholec80, com validação semissintética como fizemos no MIMIC).

## 5. Opções

### Opção A: manter como está

Fisioterapia e queda como foco (com a T41), cirurgia só com as regras da T23.

- Custo: zero.
- Risco: a cirurgia aparece no sistema sem nenhuma medida; o relatório precisa dizer isso.

### Opção B: cirurgia de sala com o MVOR

Medir a detecção e a contagem de pessoas do YOLO nos 732 quadros e desenhar o polígono do campo estéril para as 3 câmeras.

- Custo: 1 tarefa pequena; o polígono das zonas é trabalho manual (humano ou agente olhando os quadros).
- Ganho: um número real (precisão e recall da contagem de pessoas em sala de cirurgia, com oclusão e aventais).
- Limites: o MVOR não tem rótulo de intrusão nem de anomalia; "sem paramentação" continua impossível; licença ainda por confirmar.

### Opção C: cirurgia laparoscópica (modo novo)

**C1. Instrumentos com YOLOv8 ajustado (dados abertos).** Ajuste fino do YOLOv8n no Cholec80-Boxes, dividido **por vídeo** (3 treino, 1 validação, 1 reservado), e um modo de vídeo novo `laparoscopy` que gera evidências de presença de instrumento ao longo do tempo.

- Custo: 1 a 2 tarefas. O treino precisa de **GPU**: roda no desktop (RTX 5070, em Docker com `cu128`), **não** na VPS. O `Images.rar` precisa de um extrator de RAR (`unrar` ou o pacote `rarfile`), que é dependência nova.
- Ganho: atende diretamente "YOLOv8 para detecção de objetos" com **ajuste fino de verdade e mAP medido num vídeo reservado**. É o tipo de resultado que hoje falta no vídeo.
- Limites: 5 vídeos é pouco para anomalia de fluxo; C1 sozinho mede detecção, não anomalia.

**C2. Desvios no fluxo da cirurgia (depende do Cholec80 completo).** Com 80 vídeos rotulados por fase e instrumento:

- **Sem supervisão:** aprender a duração normal de cada fase, a ordem das fases e quais instrumentos aparecem em cada fase, nos vídeos de treino; sinalizar fase longa demais, ordem trocada e instrumento inesperado. É exatamente a abordagem "aprender só o normal" que se aplica a cirurgia.
- **Validação semissintética:** injetar desvios conhecidos nos vídeos reservados (trocar a ordem de duas fases, inserir um instrumento fora de fase, esticar uma fase), como na injeção de cenários do MIMIC.
- **Sangramento (opcional):** se o SurgBlood estiver acessível, é a única anomalia **real** rotulada por cirurgiões.
- Custo: 2 a 3 tarefas, mais o **passo humano** de pedir acesso ao Cholec80 pelo formulário do CAMMA (pode levar dias e pode exigir e-mail institucional).

## 6. Comparação

| | A (manter) | B (MVOR, sala) | C1 (YOLO em instrumentos) | C2 (fluxo da cirurgia) |
|---|---|---|---|---|
| Esforço | nenhum | baixo | médio | alto |
| Onde roda | — | VPS | desktop com GPU | desktop com GPU |
| Depende de humano | não | desenhar zonas | não | formulário do Cholec80 |
| Dado real com rótulo | — | pessoas (não anomalia) | caixas de instrumentos | fases e instrumentos (anomalia semissintética) |
| Atende "YOLOv8 objetos" | fraco (COCO) | parcial (pessoas) | **forte** (ajuste fino) | forte |
| Atende "eventos fora do padrão" | regras sem medida | não | não | **sim** |
| Risco | relatório admite lacuna | licença incerta | RAR, GPU | acesso pode não sair a tempo |

## 7. Recomendação

1. **Não tirar a fisioterapia nem a queda.** Elas são as únicas que demonstram pose (OpenPose/YOLO-pose) e movimentação do paciente. Seguir com a **T41** na VPS, que não depende de nada novo.
2. **Pedir agora o acesso ao Cholec80** (passo humano, formulário do CAMMA), para não depender do prazo de resposta mais tarde.
3. **Em paralelo, fazer a C1 no desktop** (YOLOv8 ajustado no Cholec80-Boxes, mAP num vídeo reservado). É a parte de cirurgia com melhor relação custo/benefício e usa só dados abertos.
4. **Fazer a C2 só se o acesso ao Cholec80 sair** e houver tempo antes da gravação. Se não sair, o relatório apresenta a C1 como detecção de instrumentos e explica que desvio de fluxo exige o dataset completo.
5. A **opção B** (MVOR) só vale se a licença se confirmar e sobrar tempo; o ganho é pequeno.

## 8. O que decidir

- Prazo até a entrega do vídeo: define se cabe C1, C1 + C2 ou só a T41.
- Se o grupo topa preencher o formulário do Cholec80 (e com qual e-mail).
- Se o trecho de cirurgia entra no vídeo de 15 minutos. Se entrar, ele **substitui** parte do trecho de fisioterapia (não há tempo sobrando no roteiro), e os quadros do Cholec80 aparecem com crédito e a licença CC BY-NC-SA.

Se a decisão for seguir com C1 (e C2), as tarefas correspondentes (T42 e T43) são escritas no `PLANO_IMPLEMENTACAO.md` no mesmo formato das T37–T41.
