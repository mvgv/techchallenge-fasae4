# Amostras de mídia (`data/samples/`)

Os arquivos desta pasta **não vão para o Git** (só este README). Eles são fornecidos pelo grupo
(passos [HUMANO] da seção 6 do `PLANO_IMPLEMENTACAO.md`). Nunca coloque aqui dados reais de
pacientes: use gravações encenadas ou datasets públicos, respeitando as licenças.

| Arquivo | Conteúdo | Origem | Usado por |
|---|---|---|---|
| `physio_squat_correct.mp4` | Agachamento executado corretamente, câmera lateral, corpo inteiro visível | Gravado pelo grupo ou trecho do KIMORE / UI-PRMD | `scripts/build_exercise_reference.py` (referência do exercício) |
| `physio_squat_wrong.mp4` | Agachamento incorreto: amplitude reduzida e joelho valgo | Gravado pelo grupo ou trecho do KIMORE / UI-PRMD | `run_demo.py`, P-0003, minuto 365 |
| `bed_fall.mp4` | Queda do leito / do plano para o chão | Le2i Fall Detection ou UR Fall Detection (verificar a licença) | `run_demo.py`, P-0004, minuto 410 |
| `consulta_p0001.wav` | Consulta em pt-BR, 38 s, dois falantes, seguindo o roteiro da seção 7.2 do plano (com tosse e fala pausada) | Gerada por `scripts/synthesize_consulta.py` (voz da Azure + tosses reservadas do ESC-50); ver `docs/DATASETS.md` | `run_demo.py`, P-0001, minuto 370 |
| `cough.wav` | Trecho curto de tosse | AudioSet / Freesound com licença livre (CC0 ou CC-BY, citar o autor) | teste manual do detector de sons respiratórios (T17) |
| `laudo_p0002.txt` | Laudo/evolução em texto (UTF-8) citando heparina, cetorolaco, ajuste de insulina e algum termo crítico (ex.: "sangramento") | Escrito pelo grupo (fictício) | `run_demo.py`, P-0002, minuto 385 |
| `hello_ptbr.wav` | Frase curta em pt-BR ("Olá, este é um teste do MedWatch") | Gerada por `scripts/synthesize_consulta.py --only hello` | `scripts/check_azure.py` (verificação do Azure Speech) |
| `voice_healthy/*.wav` | 5–10 leituras de voz saudável (mesmo texto, 20–30 s cada) | Gravado pelo grupo | `scripts/build_voice_baseline.py` (linha de base de voz) |
| `video_annotations.csv` | Colunas `video, t_start, t_end, type` (segundos) com os eventos reais dos vídeos | Preenchido pelo grupo | `scripts/evaluate_video.py` |

Formatos aceitos pela API: vídeo `.mp4 .mov .avi .mkv`; áudio `.wav .mp3 .m4a .ogg`
(convertido para WAV 16 kHz mono); documento `.txt .md`.

## Rodar a demonstração

Com o ambiente no ar (seção 9.7 do plano: banco, Redis, API e workers) e as amostras acima:

```bash
python scripts/run_demo.py                       # inicia o simulador como subprocesso
python scripts/run_demo.py --external-simulator  # e, em outro terminal:
docker compose --profile demo up simulator
```

O script cria os pacientes, inicia o cenário `demo` e envia cada amostra quando `sim:clock`
atinge o minuto da tabela 7.1, com `recorded_at` igual ao tempo simulado. Amostras ausentes
são puladas com aviso. São cerca de 26 minutos reais (6 min de histórico a 60x + 20 min a 6x).
