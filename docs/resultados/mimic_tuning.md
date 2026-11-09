# Ajuste do Isolation Forest para dados reais (T37, parte `validacao` do MIMIC)

Modelo `vitals_iforest_mimic` (treinado na `calibracao`; percentis dos scores na `validacao`). Z-score e NEWS2 com os valores de `config/thresholds.yaml` (T36). Recall: casos semissintéticos da validação; carga: alertas por paciente-dia nas séries originais, só detectores de vitais. Critério: maior recall, depois menor carga.

| IForest limiar | Persistência | Casos | TP | FN | Recall | Atraso mediano (min) | Alertas/paciente-dia (originais) |
|---|---|---|---|---|---|---|---|
| percentil 0,5 | 1 | 72 | 57 | 15 | 0,79 | 55 | 0,86 |
| percentil 0,5 | 2 | 72 | 57 | 15 | 0,79 | 55 | 0,86 |
| percentil 0,5 | 3 | 72 | 57 | 15 | 0,79 | 55 | 0,87 |
| percentil 0,1 | 1 | 72 | 57 | 15 | 0,79 | 55 | 0,87 |
| percentil 0,1 | 2 | 72 | 57 | 15 | 0,79 | 55 | 0,87 |
| percentil 0,1 | 3 | 72 | 57 | 15 | 0,79 | 55 | 0,87 |
| percentil 1 **(escolhida)** | 1 | 72 | 58 | 14 | 0,81 | 54 | 0,87 |
| percentil 1 | 2 | 72 | 57 | 15 | 0,79 | 55 | 0,86 |
| percentil 1 | 3 | 72 | 57 | 15 | 0,79 | 55 | 0,86 |
