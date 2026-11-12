# Fisioterapia com erros nomeados: Keraal (T40)

Dados: Keraal, grupo 1A (6 pacientes com dor lombar, 249 gravações anotadas) e grupo 2A (6 voluntários saudáveis, 51 gravações), vídeo frontal 480×360. Licença CC BY-NC-SA; **dados clínicos: nada deles está no Git** (só estes números agregados). Poses do nosso YOLOv8n-pose a 5 quadros/s (as 16 primeiras gravações a 10; o cache guarda os tempos). Gerado por `scripts/evaluate_keraal.py`.

## Método

- **Unidade:** a gravação (um vídeo, um exercício). Referência: anotador A. Gravações em que A e B discordam no rótulo global (`uncertain`) saem do cálculo principal; a linha "com incertas" as inclui.
- **Concordância A×B (kappa de Cohen):** pacientes, global 4 classes 0,59 (acordo 0,756, n=250), correto×incorreto 0,54, tipo de erro 0,70 (n=79); saudáveis, 0,83, 0,82 e 0,44 (n=9, pouco). Os pacientes são mais ambíguos, e é isso que limita o teto de qualquer sistema.
- **Divisão por voluntário** (`config/splits.yaml`, seção `keraal`, semente 42): calibração R2, R3, R4, S2, S3, S4; validação R5, S5; **reservado R1, R6, S1, S6** (2 pacientes e 2 saudáveis, com corretas e incorretas).
- **Referência:** repetições detectadas nas gravações corretas da calibração. **Grade** de 81 combinações (`rom_min_ratio`, `asymmetry_max_deg`, `dtw_max`, `trunk_max_deg`, 3 valores cada) medida na calibração e validação **somadas**. O reservado não ajusta nada.
- **Sinalizada** = o analisador devolveu algum achado `physio_*` na gravação inteira. **Erro nomeado** = algum achado cujo tipo é o que o mapa `errors` de `exercises.yaml` prevê para o erro anotado; **tempo** = esse achado coincide com o intervalo anotado (±2 s). Erros sem achado em 2D (mapa `null`) não entram em nomeado/tempo e são contados como "sem achado possível".

## Escolha dos limiares: nada separou as classes

Para cada exercício, a melhor combinação da grade tem precisão (calibração+validação) cujo IC de 95% inclui ou fica abaixo da proporção de incorretas, ou seja, **não separa melhor que sinalizar tudo**:

| Exercício | Melhor combinação | Precisão (IC 95%) | Recall | Falso alarme | Sinalizar tudo daria |
|---|---|---|---|---|---|
| Rotação de tronco (RTK) | 0,6 / 40 / 15 / 30 | 5% (1% a 23%) | 20% | 71% | precisão 15% |
| Alongamento lateral (ELK) | 0,6 / 15 / 15 / 10 | 83% (63% a 93%) | 70% | 100% | precisão 87% |
| Esconder o rosto (CTK) | 0,6 / 40 / 15 / 20 | 57% (42% a 71%) | 88% | 55% | precisão 46% |

Valores de `exercises.yaml` **mantidos** (regra do plano); o reservado foi avaliado com a melhor combinação da grade, para mostrar o melhor caso, que já é fraco.

## Reservado (R1, R6, S1, S6), sem incertas

| Exercício | Incorretas / corretas | Precisão (IC 95%) | Recall (IC 95%) | Falsos alarmes (IC 95%) |
|---|---|---|---|---|
| RTK | 6 / 25 | 12% (4% a 29%) | 50% (19% a 81%) | 92% (75% a 98%) |
| ELK | 14 / 11 | 52% (33% a 71%) | 86% (60% a 96%) | 100% (74% a 100%) |
| CTK | 10 / 24 | 36% (21% a 54%) | 100% (72% a 100%) | 75% (55% a 88%) |

Pacientes e saudáveis separados (reservado): RTK pacientes precisão 6% / recall 33% / falsos alarmes 88%, saudáveis 20% / 67% / 100%; ELK pacientes 57% / 92% / 100%, saudáveis 0% / 0% / 100% (1 incorreta e 2 corretas: sem poder estatístico); CTK pacientes 41% / 100% / 87%, saudáveis 17% / 100% / 56%. Com as incertas: RTK precisão 10%, recall 50%; ELK 46% e 80%; CTK 41% e 100%.

**Leitura honesta:** o sistema acusa quase tudo. O recall alto no CTK e no ELK vem de sinalizar quase todas as gravações (falsos alarmes de 75% a 100%), não de separar o erro: a precisão fica na proporção de incorretas do próprio reservado (ELK 56%, CTK 29%, RTK 19%) ou abaixo dela. O Keraal não confirma que a análise por ângulos de 17 pontos 2D separa correto de incorreto nestes exercícios.

## Erro certo (gravações incorretas do reservado)

| Exercício | Incorretas | Sinalizadas | Erro visível em 2D | Achado nomeia o erro | Coincide no tempo (±2 s) |
|---|---|---|---|---|---|
| RTK | 6 | 3 | 2 (4 são Error2, pouca rotação) | 2 | 2 |
| ELK | 14 | 12 | 0 (todas Error2, tronco pouco inclinado) | 0 | 0 |
| CTK | 10 | 10 | 10 | 8 | 8 |

No CTK o mapa é `physio_low_rom` para os três erros, então "nomear" aqui só diz *braços pouco levantados ou afastados*; não distingue Error1, 2 e 3 entre si. O ganho sobre o agachamento (T39: recall 0,61, precisão 0,32, falsos alarmes 44%): o erro nomeado e localizado existe no CTK (8 de 10 com tempo coincidente), mas a custa de 75% de falsos alarmes, pior que os 44% da T39.

## Limitações (erros que não dá para ver com 17 pontos em 2D)

- **RTK Error2 (pouca rotação do tronco):** a rotação é em torno do eixo vertical; de frente, só se vê a razão entre a largura dos ombros e a dos quadris, e não há achado para isso (seria um `physio_rotation`). Não implementado.
- **ELK Error2 (tronco pouco inclinado):** `physio_trunk_compensation` só detecta inclinação *acima* do limite, não abaixo: o erro anotado é o inverso. Todas as 14 gravações incorretas do ELK no reservado são desse tipo: **nenhum achado existente cobre**.
- **Parte do corpo:** o achado `physio_low_rom` traz uma única articulação (esquerda ou direita) e a anotação é `BothArms` ou `Spine` na maioria; não avaliada.
- **Incompleto e imóvel (códigos 4 e 5):** no reservado há 5 incompletas (RTK 1, ELK 3, CTK 1) e 1 imóvel (ELK); 4 das 6 foram sinalizadas como se fossem erro de execução (ELK 3 incompletas, CTK 1). O sistema **não** as distingue.
- Poucos voluntários (12) e poucas gravações corretas no ELK; as saudáveis do reservado têm 3 a 6 gravações cada. ICs largos.

## Reprodução

`python scripts/cache_keraal_poses.py --fps 5` (repetir até terminar, ~2,5 h na VPS) → `python scripts/evaluate_keraal.py --stage all`. O `physio_keraal.json` tem linhas por gravação de pacientes e fica fora do Git.
