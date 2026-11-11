# Sons respiratórios no ESC-50 (T37)

Detector: `RespiratoryEventDetector` (AST `MIT/ast-finetuned-audioset-10-10-0.4593`, top 15 rótulos, uma janela por clipe de 5 s). Um clipe é "respiratório" se o detector devolve qualquer evento. Calibração: folds 1–3 (240 clipes); reservado: folds 4–5 (160 clipes), nunca usado na escolha.

## Calibração (10 melhores combinações por F1)

| min_score | breathing_min_score | Sneeze | TP | FP | FN | Precisão | Recall | F1 |
|---|---|---|---|---|---|---|---|---|
| 0.05 | 0.2 | sim | 90 | 6 | 6 | 0,94 | 0,94 | 0,94 |
| 0.05 | 0.3 | sim | 90 | 6 | 6 | 0,94 | 0,94 | 0,94 |
| 0.05 | 0.4 | sim | 90 | 6 | 6 | 0,94 | 0,94 | 0,94 |
| 0.05 | 0.5 | sim | 90 | 6 | 6 | 0,94 | 0,94 | 0,94 |
| 0.05 **(escolhida; empata com 0.2–0.5, mantido 0.6 por causa de fala)** | 0.6 | sim | 90 | 6 | 6 | 0,94 | 0,94 | 0,94 |
| 0.1 | 0.2 | sim | 85 | 6 | 11 | 0,93 | 0,89 | 0,91 |
| 0.1 | 0.3 | sim | 85 | 6 | 11 | 0,93 | 0,89 | 0,91 |
| 0.1 | 0.4 | sim | 85 | 6 | 11 | 0,93 | 0,89 | 0,91 |
| 0.1 | 0.5 | sim | 85 | 6 | 11 | 0,93 | 0,89 | 0,91 |
| 0.1 | 0.6 | sim | 85 | 6 | 11 | 0,93 | 0,89 | 0,91 |

Valores anteriores (T17) na calibração: precisão 0,98, recall 0,55, F1 0,71.

## Reservado (folds 4–5)

Respiratório × não respiratório: TP 62, FP 2, FN 2, TN 94; **precisão 0,97, recall 0,97, F1 0,97**.

| Classe ESC-50 | Grupo | Clipes | Detectados como respiratório | Recall | Rótulo esperado | Precisão da classe | Rótulos do AST |
|---|---|---|---|---|---|---|---|
| breathing | positivo | 16 | 16 | 1,00 | 16 | 0,73 | Gasp 16 |
| coughing | positivo | 16 | 15 | 0,94 | 15 | 0,65 | Throat clearing 15, Cough 10 |
| sneezing | positivo | 16 | 15 | 0,94 | 13 | 1,00 | Sneeze 13, Throat clearing 8, Cough 3, Gasp 1 |
| snoring | positivo | 16 | 16 | 1,00 | 15 | 1,00 | Snoring 15, Gasp 3 |
| clock_tick | negativo | 16 | 0 | — | — | — | — |
| dog | negativo | 16 | 0 | — | — | — | — |
| door_wood_knock | negativo | 16 | 0 | — | — | — | — |
| keyboard_typing | negativo | 16 | 0 | — | — | — | — |
| laughing | negativo | 16 | 2 | — | — | — | Wheeze 1, Gasp 1 |
| rain | negativo | 16 | 0 | — | — | — | — |

Recall da classe: fração dos clipes detectados como respiratórios. Rótulo esperado: clipes em que apareceu o rótulo do AST correspondente (tosse: Cough ou Throat clearing; respiração: Breathing, Gasp, Pant ou Wheeze; ronco: Snoring; espirro: Sneeze). Precisão da classe: desses rótulos, a fração que veio da classe certa. Nas classes negativas, "detectados" são falsos alarmes.
