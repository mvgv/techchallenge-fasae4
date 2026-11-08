# Decisões

Uma linha por decisão tomada onde o `PLANO_IMPLEMENTACAO.md` era ambíguo ou precisou mudar.

| Data | Tarefa | Decisão | Motivo |
|---|---|---|---|
| 2026-11-08 | T02 | `Modality` e `Severity` usam `enum.StrEnum` em vez de `(str, Enum)` | ruff UP042; mesmo valor serializado |
| 2026-11-08 | T07 | `pyarrow>=15,<18` adicionado às dependências (parquet do MIMIC); `test_mimic.py` pula se o pyarrow não importar | o pyarrow 26 da `.venv` exige NumPy 2, incompatível com `numpy<2`; reinstalar com `pip install "pyarrow<18"` para rodar o teste |
| 2026-11-08 | T07 | Linha de base de spo2 do simulador limitada a [96, 100] (plano: só teto 100); `demo_timeline()` separa o cenário demo | garante o critério "normal mantém spo2 >= 94 em 99%" para qualquer seed |
| 2026-11-08 | T12 | Horário noturno do `MovementMonitor` usa `ts` em UTC (um hospital real usaria o fuso local) | demo sintética em UTC; conforme o plano |
| 2026-11-08 | T13 | Limiar de z-score 3,0 do plano gera `vital_zscore` esporádicos em séries sintéticas normais; mantido. Teste de `sensor_artifact` só exige que nenhum z-score venha dos pontos inválidos | o ruído sintético tem variância baixa; a fusão (T25) deve dar peso baixo a `vital_zscore` |
| 2026-11-08 | T17 | `Breathing` só vira evento com `max_score >= 0.6` (filtro em `detect`); `clf` injetável no construtor para testes | respiração normal não é anomalia; permite testar sem baixar o AST |
| 2026-11-08 | T16 | Se o openSMILE não importar (ex.: pyarrow incompatível na `.venv`), `extract_features` devolve `None` nas features eGeMAPS em vez de falhar | a fadiga (pausa e velocidade) continua funcionando; plano já prevê `None` para colunas ausentes |
| 2026-11-08 | T24 | Worker de vídeo usa duas passagens sem guardar frames em memória: a passagem 1 grava os frames com a anotação do Ultralytics num AVI MJPG temporário; a passagem 2 relê esse arquivo e sobrepõe zonas, tempo e achados (sem rodar os modelos de novo), para vídeos de qualquer duração | memória constante e implementação única; evita o corte de 2 min |
| 2026-11-08 | T24 | Payload das evidências de vídeo é completado com os nomes do catálogo (`ref_rom`, `joint_pair`, `threshold`, `trunk_deg`, `zone/people/max`, `cls/seconds`, `start_count/end_count`, `frame_key`, `rep`) mantendo os campos originais; `people` da intrusão é aproximado por `max+1`; textos no vídeo anotado sem acentos (fonte Hershey do OpenCV) | contratos da seção 4 sem alterar as funções de análise já testadas |
