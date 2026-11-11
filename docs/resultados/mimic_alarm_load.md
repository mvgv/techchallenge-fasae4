## Carga de alarmes em dados reais (sem rótulos)

Cada internação (lacuna de mais de 12 h entre vitais separa internações) passa pelo `AnomalyWorker` e pelo `FusionEngine`; um alerta abre com nível `warning` ou mais e fecha após 60 min seguidos com risco abaixo de 20 (mesma regra da T36). Isolation Forest: `vitals_iforest_mimic`.

| Divisão | Pacientes | Internações | Paciente-dias | Leituras | NEWS2 ≥ 5 | NEWS2 ≥ 7 (alto) |
|---|---|---|---|---|---|---|
| validacao | 20 | 26 | 66,3 | 1894 | 18,1% | 3,9% |

| Divisão | Configuração | Alertas | Alertas/paciente-dia | Crítico | Aviso | Internações com alerta |
|---|---|---|---|---|---|---|
| validacao | NEWS2 | 37 | 0,56 | 36 | 1 | 13/26 |
| validacao | NEWS2 + z-score | 58 | 0,87 | 35 | 23 | 16/26 |
| validacao | NEWS2 + z-score + IForest | 58 | 0,87 | 35 | 23 | 16/26 |
| validacao | Todos (vitais + prescrições) | 154 | 2,32 | 42 | 112 | 24/26 |

Evidências por tipo:

- validacao: `rx_high_alert_start` 293, `news2_medium` 268, `rx_dose_change` 247, `vital_zscore` 117, `rx_change_burst` 115, `news2_low_medium` 99, `rx_interaction` 92, `rx_duplicate_class` 82, `news2_high` 73

Exemplos (configuração completa):

- validacao, `M-10037861` (internação 0): alerta `critical` com 237,0 h de internação, risco de pico 99, duração 5,2 h; evidências principais: news2_high, rx_interaction, vital_zscore; na abertura: HR 158, SBP 81, SPO2 79, RR 30.
- validacao, `M-10022041` (internação 0): alerta `warning` com 2,5 h de internação, risco de pico 70, duração 1,4 h; evidências principais: rx_interaction, rx_dose_change, rx_high_alert_start; na abertura: HR 65, SBP 127, SPO2 100, RR 16, TEMP 37,2.
- validacao, `M-10008454` (internação 0): alerta `critical` com 71,7 h de internação, risco de pico 77, duração 5,1 h; evidências principais: rx_dose_change, news2_medium, vital_zscore; na abertura: HR 89, SBP 137, SPO2 94, RR 20.
