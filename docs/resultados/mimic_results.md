# Vitais com dados reais do MIMIC-IV Demo (T37)

Gerado por `scripts/evaluate_mimic.py`. A parte `validacao` foi usada para escolher o limiar do Isolation Forest (`mimic_tuning.md`); a parte `reservado` não ajustou nada.

## Carga de alarmes em dados reais (sem rótulos)

Cada internação (lacuna de mais de 12 h entre vitais separa internações) passa pelo `AnomalyWorker` e pelo `FusionEngine`; um alerta abre com nível `warning` ou mais e fecha após 60 min seguidos com risco abaixo de 20 (mesma regra da T36). Isolation Forest: `vitals_iforest_mimic`.

| Divisão | Pacientes | Internações | Paciente-dias | Leituras | NEWS2 ≥ 5 | NEWS2 ≥ 7 (alto) |
|---|---|---|---|---|---|---|
| validacao | 20 | 26 | 66,3 | 1894 | 18,1% | 3,9% |
| reservado | 20 | 27 | 107,7 | 3433 | 15,5% | 2,9% |

| Divisão | Configuração | Alertas | Alertas/paciente-dia | Crítico | Aviso | Internações com alerta |
|---|---|---|---|---|---|---|
| validacao | NEWS2 | 37 | 0,56 | 36 | 1 | 13/26 |
| validacao | NEWS2 + z-score | 58 | 0,87 | 35 | 23 | 16/26 |
| validacao | NEWS2 + z-score + IForest | 58 | 0,87 | 35 | 23 | 16/26 |
| validacao | Todos (vitais + prescrições) | 153 | 2,31 | 43 | 110 | 24/26 |
| reservado | NEWS2 | 52 | 0,48 | 52 | 0 | 16/27 |
| reservado | NEWS2 + z-score | 107 | 0,99 | 52 | 55 | 20/27 |
| reservado | NEWS2 + z-score + IForest | 117 | 1,09 | 57 | 60 | 21/27 |
| reservado | Todos (vitais + prescrições) | 202 | 1,87 | 65 | 137 | 25/27 |

Evidências por tipo:

- validacao: `rx_high_alert_start` 293, `news2_medium` 268, `rx_dose_change` 247, `vital_zscore` 117, `rx_change_burst` 115, `news2_low_medium` 99, `rx_interaction` 92, `rx_duplicate_class` 82, `news2_high` 73, `vital_iforest` 14
- reservado: `news2_medium` 404, `rx_dose_change` 351, `rx_high_alert_start` 311, `vital_zscore` 280, `news2_low_medium` 216, `rx_change_burst` 165, `news2_high` 92, `rx_duplicate_class` 87, `rx_interaction` 53, `vital_iforest` 29

Exemplos (configuração completa):

- validacao, `M-10037861` (internação 0): alerta `critical` com 237,0 h de internação, risco de pico 99, duração 6,2 h; evidências principais: news2_high, vital_iforest, rx_interaction; na abertura: HR 158, SBP 81, SPO2 79, RR 30.
- validacao, `M-10022041` (internação 0): alerta `warning` com 2,5 h de internação, risco de pico 70, duração 1,4 h; evidências principais: rx_interaction, rx_dose_change, rx_high_alert_start; na abertura: HR 65, SBP 127, SPO2 100, RR 16, TEMP 37,2.
- validacao, `M-10008454` (internação 0): alerta `critical` com 71,7 h de internação, risco de pico 77, duração 5,1 h; evidências principais: rx_dose_change, news2_medium, vital_zscore; na abertura: HR 89, SBP 137, SPO2 94, RR 20.
- reservado, `M-10002495` (internação 0): alerta `critical` com 20,7 h de internação, risco de pico 98, duração 5,3 h; evidências principais: news2_high, vital_iforest, vital_zscore; na abertura: HR 106, SBP 88, SPO2 93, RR 27.
- reservado, `M-10039831` (internação 0): alerta `warning` com 15,7 h de internação, risco de pico 70, duração 1,4 h; evidências principais: vital_iforest, news2_medium, rx_change_burst; na abertura: HR 119, SBP 142, SPO2 92, RR 24.
- reservado, `M-10006053` (internação 0): alerta `critical` com 41,0 h de internação, risco de pico 84, duração 0,0 h; evidências principais: rx_interaction, rx_dose_change, vital_zscore; na abertura: HR 36, RR 0.

## Recall com dados semissintéticos (cenários injetados sobre o MIMIC)

Em cada internação com 12 h ou mais, cada cenário é injetado uma vez (série separada), num instante sorteado com semente fixa entre 6 h após o início e 6 h antes do fim, fora de alertas já abertos na série original (só NEWS2). Magnitudes iguais às do gerador sintético, somadas ao valor real: insuficiência respiratória em 60 min (SpO₂ −10, FR +13, FC +40, O₂ suplementar após 40 min); hipotensão em 45 min (PAS até 82, FC +25); taquicardia de 3 min a 155 bpm (como as leituras são horárias, uma leitura extra do monitor é acrescentada no início). TP: alerta aberto em `[início, fim + 30 min]`; os demais alertas da série contam como FP, inclusive os causados por eventos reais do paciente (por isso a precisão é um limite inferior).

| Divisão | Casos | TP | FN | Recall | Precisão (limite inferior) | Atraso mediano (min) |
|---|---|---|---|---|---|---|
| validacao | 72 | 58 | 14 | 0,81 | 0,39 | 54 |
| reservado | 78 | 68 | 10 | 0,87 | 0,24 | 52 |

| Divisão | Cenário | TP | FN | Recall | Atraso mediano (min) |
|---|---|---|---|---|---|
| validacao | `respiratory_deterioration` | 24 | 0 | 1,00 | 50 |
| validacao | `hypotension` | 22 | 2 | 0,92 | 93 |
| validacao | `tachy_spike` | 12 | 12 | 0,50 | 0 |
| reservado | `respiratory_deterioration` | 26 | 0 | 1,00 | 51 |
| reservado | `hypotension` | 24 | 2 | 0,92 | 84 |
| reservado | `tachy_spike` | 18 | 8 | 0,69 | 0 |
