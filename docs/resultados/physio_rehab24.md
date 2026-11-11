# Fisioterapia com vídeo real: agachamento do REHAB24-6 (T39)

Dados: Ex6 (agachamento) do REHAB24-6, CC BY-NC 4.0 (ver `docs/DATASETS.md`). Divisão por voluntário (semente 42): 4 calibração, 2 validação, 3 reservado. Pose: YOLOv8n-pose a 10 quadros/s, vídeo reduzido a 960 px no maior lado. A análise roda por bloco de repetições com a mesma orientação (1 s de margem), como num clipe curto. Uma repetição é "sinalizada" se algum achado `physio_*` a cobre; o rótulo é o do fisioterapeuta.

## Escolha da câmera (só calibração)

| Câmera | Erro médio de contagem (repetições/bloco) | Orientação frontal | Meio perfil |
|---|---|---|---|
| 17 | 5.1 | 8.2 | 2.0 |
| 18 | 2.0 | 2.0 | 2.0 |

Escolhida: câmera 18 (a 18 fica ortogonal à 17: quando a pessoa está de frente para a 17, a 18 a vê de lado). Não há vista de perfil puro no agachamento; o ângulo do joelho em 2D perde amplitude em meio perfil.

## Limiares (calibração + validação)

Referência: 54 repetições corretas anotadas da calibração. Grade de 256 combinações em `physio_rehab24.json`.

Proporção de repetições incorretas (calibração + validação): 34,4%. Com os valores mantidos (`rom_min_ratio` 0.8, `asymmetry_max_deg` 15, `dtw_max` 15, `trunk_max_deg` 30), as duas partes somadas dão precisão 35,5%, recall 62,8% e falsos alarmes 59,8%. **Nenhuma combinação separou as classes**: a melhor precisão não passa, com IC de 95%, da proporção de incorretas (sinalizar tudo daria o mesmo). Os valores de `exercises.yaml` foram mantidos.

## Reservado (voluntários 1, 2 e 6; 70 repetições)

- Repetições incorretas: 18; corretas: 52.
- **Recall** de repetição incorreta: 11/18 = 61,1% (IC 95% de 39% a 80%).
- **Precisão**: 11/34 = 32,4% (IC 95% de 19% a 49%); a proporção de incorretas é 25,7%, então o sistema pouco supera sinalizar ao acaso.
- **Falsos alarmes** (corretas sinalizadas): 23/52 = 44,2%.

### Contagem de repetições

| Voluntário | Orientação | Anotadas | Detectadas |
|---|---|---|---|
| 1 | front | 17 | 16 |
| 1 | half-profile | 10 | 8 |
| 2 | front | 10 | 8 |
| 2 | half-profile | 12 | 10 |
| 6 | front | 5 | 3 |
| 6 | half-profile | 11 | 9 |

Erro absoluto médio por bloco: 1.8 repetições. A segmentação pico a pico tende a perder as repetições das pontas do bloco.

### Por voluntário

| Voluntário | Incorretas sinalizadas | Corretas sinalizadas |
|---|---|---|
| 1 | 4/6 | 5/21 |
| 2 | 0/1 | 12/21 |
| 6 | 7/11 | 6/10 |

### Achados que mais disparam

| Achado | Em repetições incorretas | Em corretas |
|---|---|---|
| `physio_asymmetry` | 8 | 16 |
| `physio_low_rom` | 4 | 13 |
| `physio_trunk_compensation` | 8 | 7 |

O dataset não diz qual foi o erro encenado em cada repetição incorreta, só que ela é incorreta; por isso não dá para checar se o achado coincide com o erro.

Limitações: 9 voluntários, 3 no reservado (ICs largos); marcadores de captura de movimento no corpo; vista frontal ou meio perfil, nunca perfil; pose em 2D; limiares de `exercises.yaml` não ajustados (nada separou as classes).
