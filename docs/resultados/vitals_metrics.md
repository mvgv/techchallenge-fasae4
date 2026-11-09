# Avaliação dos vitais (30 pacientes sintéticos, seeds 100–129, 24 h)

Limiares em uso: z-score 3.0 com persistência 1; Isolation Forest `p0_1` com persistência 3 (`config/thresholds.yaml`).

## 1. Por alerta (número principal: o que a equipe médica veria)

Evidências de cada paciente passam pelo `FusionEngine` (`config/fusion.yaml`); um alerta abre quando o nível chega a `warning` ou mais e fecha quando o risco fica abaixo de 20 por 60 minutos seguidos. TP: alerta aberto em `[ts_start, ts_end + 30 min]` de um rótulo positivo; os demais alertas são FP (inclui os causados por `sensor_artifact`).

| Configuração | TP | FP | FN | Precisão | Recall | Atraso mediano (min) | Alertas/dia em pacientes normais |
|---|---|---|---|---|---|---|---|
| NEWS2 | 6 | 1 | 9 | 0.86 | 0.40 | 40.0 | 0.00 |
| NEWS2 + z-score | 13 | 3 | 2 | 0.81 | 0.87 | 37.0 | 0.10 |
| NEWS2 + z-score + IForest | 14 | 3 | 1 | 0.82 | 0.93 | 30.5 | 0.10 |

## 2. Por episódio

TP: ao menos uma detecção em `[ts_start, ts_end + 30 min]`. Fora das janelas, detecções do mesmo tipo com menos de 30 min entre si formam um episódio, e cada episódio é um FP. Coluna final: episódios falsos por paciente-dia nos pacientes `normal`.

| Configuração | TP | FP | FN | Precisão | Recall | Atraso mediano (min) | Episódios FP/dia em normais |
|---|---|---|---|---|---|---|---|
| NEWS2 | 15 | 51 | 0 | 0.23 | 1.00 | 24.0 | 2.30 |
| NEWS2 + z-score | 15 | 508 | 0 | 0.03 | 1.00 | 0.0 | 21.10 |
| NEWS2 + z-score + IForest | 15 | 508 | 0 | 0.03 | 1.00 | 0.0 | 21.10 |

## 3. Por evidência (método da T31, para comparação)

Cada detecção fora das janelas de rótulo é um FP (repetições incluídas).

| Configuração | TP | FP | FN | Precisão | Recall | F1 | Atraso mediano (min) | FP/paciente-dia |
|---|---|---|---|---|---|---|---|---|
| NEWS2 | 15 | 196 | 0 | 0.07 | 1.00 | 0.13 | 24.0 | 6.53 |
| NEWS2 + z-score | 15 | 1485 | 0 | 0.01 | 1.00 | 0.02 | 0.0 | 49.50 |
| NEWS2 + z-score + IForest | 15 | 1485 | 0 | 0.01 | 1.00 | 0.02 | 0.0 | 49.50 |

Rótulos: `respiratory_deterioration` e `hypotension` vão até o fim da série (o estado alterado persiste); `tachy_spike` dura 3 minutos.
