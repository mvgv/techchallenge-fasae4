# Datasets públicos (T37)

Nada baixado vai para o Git (`data/` é ignorado). Vão para o Git só o código, os IDs das divisões (`config/splits.yaml`) e os resultados agregados (`docs/resultados/datasets.md`).

Regra geral: cada dataset tem uma parte **reservada**, nunca usada para ajustar limiares, modelos ou parâmetros. Ela serve para o número final do relatório e para a demonstração.

## MIMIC-IV Clinical Database Demo (PhysioNet)

| Campo | Valor |
|---|---|
| Fonte | <https://physionet.org/content/mimic-iv-demo/2.2/> |
| Versão | 2.2 |
| Licença | Open Data Commons Open Database License v1.0 (ODbL); acesso aberto, sem credenciamento |
| Baixado em | 2026-11-09, com `python scripts/download_datasets.py --mimic` |
| Arquivos usados | `icu/chartevents.csv.gz` (5,5 MB) e `hosp/prescriptions.csv.gz` (0,6 MB) |
| Preparação | `scripts/prepare_mimic.py` → `data/mimic/vitals.parquet` e `prescriptions.parquet` |
| Pacientes | 100 (`patient_id` = `M-<subject_id>`) |
| Linhas de vitais | 15.546 (média por grade de 5 min, uma linha por paciente e instante) |
| Prescrições | 18.087 |
| Tempo coberto | 503 paciente-dias, contando só os trechos com observações (lacunas maiores que 12 h separam internações) |

**Variáveis (itemid):** FC 220045, PAS/PAD não invasiva 220179/220180 com a arterial invasiva 220050/220051 preenchendo as lacunas, SpO₂ 220277, FR 220210, temperatura 223762 (°C) ou 223761 (°F convertida). Preenchimento: FC, FR, PA e SpO₂ em 86% a 89% das linhas; temperatura em 24% (é medida a cada 4 h, em média).

**Intervalo entre observações.** O intervalo mediano entre observações consecutivas do mesmo paciente é **60 minutos** (quartis de 30 e 60 min); por paciente, a mediana fica entre 20 e 60 min e é 60 min em mais de 75% deles. O simulador publica uma leitura por **minuto**. Consequências:

- detectores que olham "as últimas N leituras" (z-score EWMA, features do Isolation Forest) cobrem um intervalo de tempo ~60 vezes maior no MIMIC;
- por isso o Isolation Forest para dados reais é um modelo separado, treinado com o próprio MIMIC (passo 4 da T37);
- um alerta não pode ter atraso menor que o intervalo até a próxima medição.

**Datas.** O MIMIC desloca as datas para o futuro (anos de 2110 a 2201), de forma independente por paciente. O `load_mimic(..., rebase_start=...)` desloca cada paciente para começar numa data escolhida, mantendo os intervalos.
