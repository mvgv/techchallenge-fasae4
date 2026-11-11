# Detecção de queda no UR Fall (T37)

Câmera frontal (`cam0`), pose YOLOv8n a 8 quadros/s, regra `video.fall` do `analyze_bed` sem leito (zona `ur_fall`). Verdade: quadros rotulados como caindo/deitado. Acerto: detecção que cruza o intervalo rotulado (±2 s); detecção fora dele ou numa ADL é falso alarme.

Calibração: quedas 01–10 e ADL 01–10 (20 vídeos). Reservado: quedas 11–30 e ADL 11–40 (50 vídeos, 20 quedas), nunca usado na escolha.

## Calibração (10 melhores combinações por F1)

| hip_drop_min | lying_aspect_min | lying_min_s | TP | FP | FN | Precisão | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 1.0 | 0.25 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.1 | 1.0 | 0.5 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.1 | 1.0 | 1.0 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.1 | 1.15 | 0.25 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.1 | 1.15 | 0.5 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.1 | 1.15 | 1.0 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.1 | 1.3 | 0.25 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.1 | 1.3 | 0.5 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.15 | 1.0 | 0.25 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |
| 0.15 | 1.0 | 0.5 | 9 | 0 | 1 | 1.00 | 0.90 | 0.95 |

Escolhida: `{'hip_drop_min': 0.15, 'lying_aspect_min': 1.3, 'lying_min_s': 0.5}`. Valores anteriores (T22) na calibração: precisão 0.00, recall 0.00.

## Reservado

| hip_drop_min | lying_aspect_min | lying_min_s | TP | FP | FN | Precisão | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| anterior |  |  | 0 | 0 | 20 | 0.00 | 0.00 | 0.00 |
| 0.15 | 1.3 | 0.5 | 2 | 1 | 18 | 0.67 | 0.10 | 0.17 |

Sem alarme nas ADL: 29 de 30.
