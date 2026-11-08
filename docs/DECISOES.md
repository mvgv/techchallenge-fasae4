# Decisões

Uma linha por decisão tomada onde o `PLANO_IMPLEMENTACAO.md` era ambíguo ou precisou mudar.

| Data | Tarefa | Decisão | Motivo |
|---|---|---|---|
| 2026-11-08 | T02 | `Modality` e `Severity` usam `enum.StrEnum` em vez de `(str, Enum)` | ruff UP042; mesmo valor serializado |
| 2026-11-08 | T07 | Linha de base de spo2 do simulador limitada a [96, 100] (plano: só teto 100); `demo_timeline()` separa o cenário demo | garante o critério "normal mantém spo2 >= 94 em 99%" para qualquer seed |
