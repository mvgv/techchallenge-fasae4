# Queda v2 (T41, parte A)

## Diagnóstico das quedas perdidas (passo A2, só desenvolvimento)

Regra da T37 (`hip_drop_min` 0.15, `lying_aspect_min` 1.3, `lying_min_s` 0.5) no UR Fall inteiro: perde **19 de 30** quedas; 1 falso(s) alarme(s) nas 40 ADL.

Para cada queda perdida, a causa é a etapa da regra em que o par de quadros mais favorável parou (pessoa → quadril → descida → proporção → permanência).

| Causa | Quedas |
|---|---|
| (a) nenhuma pessoa detectada pela pose no chão | 0 |
| (b) pessoa detectada, mas sem os pontos do quadril | 0 |
| (c) descida do quadril abaixo de `hip_drop_min` | 8 |
| (d) caixa sem a proporção de deitado (largura/altura) | 6 |
| (e) o vídeo termina antes de `lying_min_s` | 5 |

| Sequência | Causa | Descida do quadril | Largura/altura em j | Deitado pela regra (s) | Quadros com pose após o início | Com quadril | Duração (s) |
|---|---|---|---|---|---|---|---|
| fall-01 | (d) | 0.40 | 1.15 | — | 53% | 47% | 5.2 |
| fall-13 | (d) | 0.17 | 0.42 | — | 55% | 55% | 2.8 |
| fall-14 | (e) | 0.16 | 3.17 | 0.00 | 100% | 100% | 2.0 |
| fall-15 | (e) | 0.36 | 1.73 | 0.27 | 91% | 82% | 2.3 |
| fall-16 | (c) | 0.14 | 2.90 | — | 100% | 100% | 1.7 |
| fall-17 | (c) | 0.03 | 0.45 | — | 67% | 44% | 3.1 |
| fall-18 | (c) | 0.09 | 1.84 | — | 54% | 54% | 2.1 |
| fall-19 | (d) | 0.18 | 0.62 | — | 37% | 37% | 3.2 |
| fall-20 | (c) | 0.14 | 1.20 | — | 100% | 100% | 3.6 |
| fall-21 | (c) | 0.05 | 0.57 | — | 67% | 67% | 1.7 |
| fall-22 | (e) | 0.31 | 2.87 | 0.13 | 85% | 62% | 1.7 |
| fall-23 | (d) | 0.15 | 0.63 | — | 83% | 50% | 2.4 |
| fall-24 | (c) | 0.15 | 1.61 | — | 58% | 50% | 1.9 |
| fall-25 | (d) | 0.31 | 0.89 | — | 64% | 55% | 2.8 |
| fall-26 | (e) | 0.23 | 3.72 | 0.00 | 69% | 62% | 2.0 |
| fall-27 | (c) | 0.10 | 0.83 | — | 50% | 50% | 2.9 |
| fall-28 | (e) | 0.15 | 2.26 | 0.00 | 70% | 70% | 2.1 |
| fall-29 | (d) | 0.23 | 1.10 | — | 69% | 54% | 3.2 |
| fall-30 | (c) | 0.10 | 1.45 | — | 58% | 58% | 2.3 |

Leitura:

- Nenhuma queda é perdida por falta total de pessoa: a pose acha a pessoa na descida, mas a perde depois de ela chegar ao chão (coluna "quadros com pose"). Isso também derruba a permanência: sem pose, a fase deitada não é confirmada (causa e).
- O UR Fall tem duas posições de câmera (quadril em pé a ~57% e a ~70% da altura do quadro). Na mais distante a pessoa é pequena e uma queda real move o quadril só 3% a 10% da altura do **quadro** (causa c): a descida precisa ser medida em relação à altura da **pessoa** antes da queda.
- Quem cai em direção à câmera fica com a caixa alta e estreita (largura/altura de 0,4 a 1,1), mas a altura da caixa cai muito (causa d): "deitado" precisa aceitar também uma queda grande da altura da caixa.
- Os clipes terminam até 0,5 s depois de a pessoa deitar (causa e): o fim do vídeo, ou a perda da pose com a pessoa já deitada, precisa contar como fim da fase deitada.

## Ajuste no desenvolvimento (passo A4)

Grade de 4032 combinações só no UR Fall inteiro (30 quedas, 40 ADL). Critério: maior F1 com no máximo 1 falso alarme nas ADL; empate vai para a regra com menos opções novas ligadas.

| Descida | Janela (s) | Largura/altura | Deitado (s) | Opções novas | TP | FP | FP em ADL | F1 |
|---|---|---|---|---|---|---|---|---|
| frame 0.12 | 1.0 | 1.3 | 1.0 | hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 26 | 1 | 1 | 0.91 |
| frame 0.1 | 0.5 | 1.3 | 0.5 | lying_height_ratio=0.5, hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 26 | 1 | 1 | 0.91 |
| frame 0.12 | 0.5 | 1.3 | 0.5 | lying_height_ratio=0.6, hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 26 | 1 | 1 | 0.91 |
| frame 0.12 | 0.5 | 1.3 | 1.0 | lying_height_ratio=0.6, hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 26 | 1 | 1 | 0.91 |
| frame 0.12 | 0.5 | 1.3 | 0.5 | lying_height_ratio=0.5, hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 25 | 0 | 0 | 0.91 |
| frame 0.1 | 0.5 | 1.3 | 0.5 | hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 25 | 1 | 1 | 0.89 |
| frame 0.15 | 1.0 | 1.3 | 0.5 | hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 25 | 1 | 1 | 0.89 |
| frame 0.15 | 1.0 | 1.3 | 1.0 | hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 25 | 1 | 1 | 0.89 |
| frame 0.1 | 0.5 | 1.3 | 1.0 | lying_height_ratio=0.5, hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 25 | 1 | 1 | 0.89 |
| frame 0.12 | 0.5 | 1.3 | 0.5 | hip_from_box=True, end_closes_lying=True, detector_fallback_conf=0.25 | 24 | 0 | 0 | 0.89 |

Escolhida: `drop_norm`: frame, `hip_drop_min`: 0.12, `window_s`: 1.0, `lying_aspect_min`: 1.3, `lying_min_s`: 1.0, `lying_height_ratio`: None, `hip_from_box`: True, `skip_missing_j`: False, `end_closes_lying`: True, `detector_fallback_conf`: 0.25.

| Regra | Quedas detectadas | Recall [IC 95% Wilson] | Precisão | Falsos alarmes | ADL com alarme | Atraso mediano (s) |
|---|---|---|---|---|---|---|
| T37 | 11/30 | 0.37 [0.22; 0.54] | 0.92 | 1 | 1/40 (2%; IC 0%–13%) | +1.1 |
| Nova | 26/30 | 0.87 [0.70; 0.95] | 0.96 | 1 | 1/40 (2%; IC 0%–13%) | +1.0 |

## Reservado novo: CAUCAFall (medido uma vez)

100 vídeos (10 voluntários, 50 quedas e 50 ADL), câmera alta no canto da sala, nunca usados no ajuste. Acerto: detecção que cruza o intervalo rotulado como queda (±2 s); atraso = instante da detecção menos o primeiro quadro com o corpo no chão (negativo: antes de o rótulo começar).

| Regra | Quedas detectadas | Recall [IC 95% Wilson] | Precisão | Falsos alarmes | ADL com alarme | Atraso mediano (s) |
|---|---|---|---|---|---|---|
| T37 | 10/50 | 0.20 [0.11; 0.33] | 1.00 | 0 | 0/50 (0%; IC 0%–7%) | +0.1 |
| Nova | 12/50 | 0.24 [0.14; 0.37] | 1.00 | 0 | 0/50 (0%; IC 0%–7%) | +0.0 |

| Atividade | Vídeos | T37 | Nova |
|---|---|---|---|
| Fall backwards | 10 | 0 | 1 |
| Fall forward | 10 | 0 | 0 |
| Fall left | 10 | 3 | 2 |
| Fall right | 10 | 4 | 4 |
| Fall sitting | 10 | 3 | 5 |
| Hop | 10 | 0 | 0 |
| Kneel | 10 | 0 | 0 |
| Pick up object | 10 | 0 | 0 |
| Sit down | 10 | 0 | 0 |
| Walk | 10 | 0 | 0 |

Nas atividades de queda a coluna conta quedas detectadas; nas ADL, vídeos com alarme falso.

### Por que o reservado ficou baixo (descrição posterior; nada foi ajustado)

Mesma classificação do diagnóstico, aplicada à regra nova nas 38 quedas reservadas perdidas: (a) 0; (b) 0; (c) 8; (d) 26; (e) 4. A pose acompanha a pessoa em 98% (mediana) dos quadros depois do início da queda, ao contrário do UR Fall.

Com a câmera no alto do canto, quem cai para frente ou para trás fica encurtado pela perspectiva: a caixa da pessoa deitada continua mais alta que larga (largura/altura mediana 0.64 nas quedas da causa d). A regra é geométrica e 2D, depende do ponto de vista da câmera, e o UR Fall (câmera frontal, baixa) não tinha esse caso. A opção `lying_height_ratio`, que cobriria parte dele, trouxe falsos alarmes em ADL no desenvolvimento e não foi escolhida.
