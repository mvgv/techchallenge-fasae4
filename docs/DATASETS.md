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

## UR Fall Detection Dataset (Universidade de Rzeszów)

| Campo | Valor |
|---|---|
| Fonte | <https://fenix.ur.edu.pl/~mkepski/ds/uf.html> |
| Termos | uso acadêmico/pesquisa, citando Kwolek e Kepski, "Human fall detection on embedded platform using depth maps and wireless accelerometer", Computer Methods and Programs in Biomedicine, 117(3), 2014 |
| Baixado em | 2026-11-10, com `python scripts/download_datasets.py --urfall` |
| Conteúdo | câmera frontal `cam0`: 30 quedas (`fall-01`…`30`) e 40 ADL (`adl-01`…`40`); MP4 do site (profundidade e RGB lado a lado) com a metade RGB recortada para `data/datasets/urfall/video/` (H.264 640×480, 30 fps, 23 MB) |
| Rótulos | `urfall-cam0-{falls,adls}.csv`: por quadro, -1 em pé/normal, 0 caindo, 1 deitado |
| Divisão | quedas 01–10 e ADL 01–10 calibração; quedas 11–30 e ADL 11–40 reservadas (`config/splits.yaml`, seção `urfall`) |
| Avaliação | `python scripts/evaluate_urfall.py` → `docs/resultados/urfall_fall.md`; anotações em `data/datasets/urfall/video_annotations.csv` |

Limite importante: os clipes de queda são curtos (1–5 s) e muitos terminam logo depois de a pessoa deitar, e a pose do YOLO falha com a pessoa no chão; a regra de queda passou a tolerar lacunas de pose (`LYING_GAP_S`). A câmera `ur_fall` em `config/zones.yaml` não tem leito. Resultado no reservado: ver `docs/resultados/urfall_fall.md` (recall baixo, discutido lá).

## Material para a demonstração (passo 11)

Gerado por `python scripts/pick_demo_clips.py` em `data/samples/` (fora do Git). Todos vêm das partes **reservadas**:

| Arquivo | Origem | Motivo |
|---|---|---|
| `cough.wav` | ESC-50 `4-155650-A-24.wav` (tosse, fold 4–5) | maior score de "Cough" do AST entre as tosses reservadas (0,46) |
| `breathing.wav` | ESC-50 `5-235593-A-23.wav` (respiração) | maior score de "Gasp" entre as respirações reservadas (0,81) |
| `snoring.wav` | ESC-50 `4-197454-A-28.wav` (ronco) | maior score de "Snoring" (0,97) |
| `bed_fall.mp4` | UR Fall `fall-12` (cam0, reservado) | uma das 2 quedas reservadas que a regra calibrada detecta (recall reservado 0,10: dizer isso no vídeo, sem esconder as outras 18) |
| pacientes MIMIC | `M-10002495` (alerta crítico, risco de pico 98, NEWS2 alto + IForest + z-score, 20,7 h de internação) e `M-10039831` (alerta de aviso com IForest e NEWS2 médio, 15,7 h) | reservados, com alertas de vitais legíveis para mostrar no painel (`replay --mimic-split reservado`) |

`consulta_p0001.wav` (passo 10) depende da Azure e segue bloqueado.
