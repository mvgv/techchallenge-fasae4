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

## Consulta sintética pela Azure (passo 10)

Gerada por `python scripts/synthesize_consulta.py` (precisa de `AZURE_SPEECH_KEY` e `USE_FAKE_AZURE=false`; ESC-50 baixado para as tosses). Gera `data/samples/consulta_p0001.wav` e `hello_ptbr.wav`, fora do Git.

| Item | Valor |
|---|---|
| Roteiro | Seção 7.2 do plano: médica e paciente "seu João", 6 falas, 38 s |
| Vozes | Azure neurais pt-BR: médica `pt-BR-FranciscaNeural`, paciente `pt-BR-AntonioNeural` (ritmo -20% a -25% e pausas depois das vírgulas) |
| Tosses | 2 tosses **reais** de clipes reservados do ESC-50 (folds 4–5, ordenados pelo nome: `4-152995-A-24.wav` e `4-154443-A-24.wav`), inseridas depois da fala em que o paciente diz que tosse |
| Formato | WAV 16 kHz mono PCM 16 bits |
| Licença das tosses | ESC-50, CC BY-NC; citar o autor do clipe no vídeo, se aparecer |

**Limitação, a dizer no vídeo:** numa voz sintética, a análise de fadiga e de alteração da fala (jitter, pausas, F0) não tem sentido clínico. Essa análise é demonstrada com vozes reais (Common Voice, passo 9). A transcrição, os termos críticos, o sentimento, as entidades de saúde e os sons respiratórios valem normalmente. Resultados da execução real: `docs/resultados/azure_integracao.md`.

## Common Voice pt-BR, recorte brasileiro (passo 9)

| Campo | Valor |
|---|---|
| Fonte | Mozilla Data Collective, "Common Voice Scripted Speech 26.0 - Brazilian Portuguese" (MDC Curators), <https://mozilladatacollective.com/datasets/cmruxo9ew00d3md07veethj6k> |
| Licença | CC0-1.0. Uso proibido: tentar determinar a identidade dos falantes. (O pacote completo de 27.0 também proíbe re-hospedar e recompartilhar.) |
| Obtido em | 2026-11-10, baixado à mão pelo humano (conta no site e aceite dos termos); arquivo `1784654835483-pt-BR.tar.gz`, 122,2 MB, extraído em `data/datasets/commonvoice/extracted/pt-BR/` (fora do Git) |
| Conteúdo | 5.051 clipes MP3 de 202 falantes: `train.tsv` (3.762), `dev.tsv` (862) e `test.tsv` (427). Só áudio validado (pelo menos 1 voto a favor e nenhum contra) de falantes de sotaque brasileiro. Colunas: `client_id`, `path`, `sentence`, `up_votes`, `down_votes`, `age`, `gender`, `accents`, `variant`, entre outras |
| Por que o recorte | O pacote completo de português (27.0) tem 4,85 GB; o recorte brasileiro tem 122 MB e basta para a linha de base |
| Seleção | 81 falantes com 10 ou mais clipes; de cada um, os 10 primeiros clipes (por nome), com o silêncio das pontas aparado e concatenados num trecho contínuo de 15 a 50 s. O limite por falante evita que um deles, com 658 clipes, domine a linha de base |
| Divisão | Por falante, semente 42: 54 de calibração e 27 reservados (`config/splits.yaml`, seção `voice`, só o prefixo de 16 caracteres do `client_id`) |
| Uso | A linha de base de voz saudável (`data/references/voice_baseline.json`, fora do Git) vem só da calibração; os falsos alarmes são medidos no reservado, com `python scripts/evaluate_voice.py` |
| Resultado | 2 de 27 vozes reservadas (7,4%; IC 95% de 2% a 23%) dispararam `voice_fatigue`: ver `docs/resultados/voice_baseline.md` |

Os áudios ficam só em `data/`. O recorte tem cerca de 71% de clipes de vozes masculinas e quase só adultos de 20 a 40 anos; isso e o fato de serem leituras de frases curtas, e não conversas, limitam o que a linha de base representa.

## REHAB24-6, fisioterapia (T39)

| Item | Valor |
|---|---|
| Fonte | Zenodo, <https://zenodo.org/records/13305826>, DOI `10.5281/zenodo.13305826`, v1, acesso aberto sem cadastro |
| Licença | **CC BY-NC 4.0**: só pesquisa acadêmica, não comercial. Citar: Černek, A., Sedmidubsky, J., Budikova, P., "REHAB24-6: Physical Therapy Dataset for Analyzing Pose Estimation Methods", SISAP 2024 |
| Baixado | 2026-11-11, `python scripts/download_datasets.py --rehab24` (`videos.zip` 2,65 GB, `Segmentation.csv`, `Segmentation.txt`, `joints_names.txt`; md5 conferidos); só o Ex6 foi extraído para `data/datasets/rehab24/videos/Ex6/` |
| Colunas de `Segmentation.csv` (separador `;`) | `video_id`, `repetition_number`, `exercise_id`, `person_id`, `first_frame`, `last_frame` (quadros a 30 fps), `cam17_orientation` (`front`, `half-profile`, `profile`), `mocap_erroneous`, `exercise_subtype`, `lights_on`, `extra_person_in_cam17`, `extra_person_in_cam18`, `correctness` (1 certa, 0 incorreta) |
| Vídeos | Um par por voluntário e exercício: `PM_xxx-Camera17-30fps.mp4` (1920x1080) e `PM_xxx-Camera18-30fps-transposed.mp4` (1080x1920, retrato), ambos a 30 fps. A câmera 18 fica ortogonal à 17: se a pessoa está de frente para a 17, está de lado para a 18 |
| Agachamento (Ex6) | 195 repetições (134 certas, 61 incorretas) em **9 voluntários** (`person_id` 1 a 9; um vídeo cada: PM_008, 022, 029, 038, 043, 105, 126, 113, 118), não 10 como a página sugere. Por voluntário (incorretas/certas): 1: 6/21, 2: 1/21, 3: 10/10, 4: 3/17, 5: 10/10, 6: 11/10, 7: 10/10, 8: 5/17, 9: 5/18 |
| Orientação | No agachamento só há `front` (98 repetições) e `half-profile` (97); **não há `profile`**. A orientação muda dentro do mesmo vídeo (blocos de cerca de 10 repetições), então a câmera adequada (a 18 quando a pessoa está de frente para a 17) depende do trecho |
| Divisão | Por voluntário, semente 42 (`config/splits.yaml`, seção `rehab24`): calibração 4, 5, 7, 8; validação 3, 9; reservado 1, 2, 6 |
| Uso de cada parte | Calibração: escolha da câmera (18) e referência do exercício (`data/references/squat.json`, 54 repetições corretas). Calibração + validação: grade de limiares (nada separou as classes; valores mantidos). Reservado: só o número final (`python scripts/evaluate_physio.py final`) e os clipes da demonstração |
| Resultado | Reservado, 70 repetições: recall de repetição incorreta 11/18 (61%; IC 95% de 39% a 80%), precisão 11/34 (32%), falsos alarmes 23/52 (44%); contagem com erro médio de 1,8 repetições por bloco: `docs/resultados/physio_rehab24.md` |
| Clipes da demonstração | `physio_squat_wrong.mp4` (voluntário 1, `PM_008` câmera 18, 155–172 s, 5 repetições incorretas) e `physio_squat_correct.mp4` (voluntário 2, `PM_022` câmera 18, 3–31 s, 7 corretas), por `scripts/pick_demo_clips.py` |
| Limitações | Voluntários com marcadores de captura de movimento; sem vista lateral pura, então o ângulo do joelho em 2D perde amplitude; só 9 voluntários, e com divisão por voluntário o reservado terá poucos |

## Keraal, fisioterapia com erros nomeados (T40, inspeção parcial)

- **Fonte:** <https://keraal.enstb.org/data/>; licença CC BY-NC-SA. **Dados clínicos de pacientes (grupo 1A): nunca vão para o Git nem para o painel público.** A demonstração usa só saudáveis (grupo 2A).
- **Estado em 2026-11-11:** `group2A.tar.xz` (338 MB) e `readme_files_format.txt` baixados; o 2A foi extraído em `data/datasets/keraal/g2a/` (fora do Git). `group1A.tar.xz` (1,4 GB) **não** foi baixado: o servidor entrega ~25 KB/s na VPS (bloqueio humano no `PROGRESSO.md`).
- **Estrutura do 2A:** `annotatorA/`, `annotatorB/` (`.anvil`), `videos/` (MP4), `openpose/`, `blazepose/`, `kinect/`. Nome: `G2A-<exercício>-S<voluntário>-<local>-<id>`; exercícios `RTK`, `ELK`, `CTK`. 51 gravações de 6 voluntários (S1 a S6), cada uma com anotação A e B.
- **Formato do `.anvil`:** XML em **UTF-16**; `<el start end>` com tempos em **segundos**. Trilhas: `Global evaluation` (`evaluation`: Correct, Incorrect, Incomplete, Motionless), `Global error` e `Temporal error` (`type` Error1 a Error3, Other ou none; `bodyPart` BothArms, RightArm ou Spine; `Evaluation` SmallError ou LargeError).
- **Contagens (A e B somados, 102 avaliações globais):** Correct 72, Incorrect 21, Incomplete 7, Motionless 2; 12 erros temporais com intervalo.
- **Acordo A × B no rótulo global (2A):** 47 de 51 gravações (92%); kappa e tipo de erro ficam para o passo 2.
- **Pendente:** grupo 1A (pacientes), `prepare_keraal.py`, divisão e avaliação. `scripts/inspect_keraal.py` reproduz as contagens.
