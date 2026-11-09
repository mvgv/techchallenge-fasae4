# Avaliação dos vitais (30 pacientes sintéticos, seeds 100–129, 24 h)

| Configuração | TP | FP | FN | Precisão | Recall | F1 | Atraso mediano (min) | FP/paciente-dia |
|---|---|---|---|---|---|---|---|---|
| NEWS2 | 15 | 557 | 0 | 0.03 | 1.00 | 0.05 | 24.0 | 18.57 |
| NEWS2 + z-score | 15 | 2011 | 0 | 0.01 | 1.00 | 0.01 | 0.0 | 67.03 |
| NEWS2 + z-score + IForest | 15 | 2632 | 0 | 0.01 | 1.00 | 0.01 | 0.0 | 87.73 |

Critério: detecção dentro de `[ts_start, ts_end + 30 min]` de um rótulo positivo (respiratory_deterioration, hypotension, tachy_spike) conta como um TP por rótulo; detecções fora dessas janelas são FP (inclui as causadas por `sensor_artifact`); rótulos sem detecção são FN.

Leitura: o gerador mantém o estado alterado até o fim do dia e o worker repete alertas NEWS2 médio/alto a cada `repeat_minutes`; essas repetições após a janela do rótulo contam como FP. O z-score também dispara em pacientes normais (limiar/cooldown da `thresholds.yaml`).
