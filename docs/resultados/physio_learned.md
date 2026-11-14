# Fisioterapia com aprendizado (T41, parte B)

Duas técnicas clássicas de detecção de anomalias, comparadas com as regras fixas da T39/T40 sobre as mesmas medidas da pose 2D (`physio_features.py`: amplitude e DTW por articulação, assimetria, tronco, razão ombros/quadris, cotovelo, duração, curva da articulação principal):

- **sem supervisão**: aprende só o movimento correto e mede a distância até ele (Mahalanobis com covariância encolhida de Ledoit-Wolf; IsolationForest). O limiar é o percentil das corretas de treino que, na validação cruzada, dá no máximo 20% de falsos alarmes;
- **supervisionado**: aprende a fronteira entre corretas e incorretas (regressão logística com padronização e classes balanceadas; árvore rasa; GradientBoosting pequeno). Limiar 0,5.

Seleção por **validação cruzada deixando um voluntário de fora**, em calibração + validação (com 6 a 8 voluntários, uma validação de 2 pessoas seria ruído); a referência do DTW é refeita em cada dobra sem o voluntário de fora. Um modelo só **vence** as regras se, na validação cruzada, tiver F1 acima das regras e de sinalizar tudo, respeitar o teto de falsos alarmes (sem supervisão) e tiver AUC com IC 95% por voluntário acima de 0,5. O reservado foi medido uma única vez, depois da escolha.

## Agachamento (REHAB24-6)

Calibração + validação: 82 corretas e 43 incorretas, 6 voluntários.

### Validação cruzada (um voluntário de fora)

| Método | AUC [IC 95% por voluntário] | Precisão | Recall [IC 95%] | Falsos alarmes [IC 95%] | F1 |
|---|---|---|---|---|---|
| Regras (T39/T40) | 0.52 [0.44; 0.63] | 0.36 | 0.63 [0.48; 0.76] | 0.60 [0.49; 0.70] | 0.45 |
| Sinalizar tudo (base) | — | 0.34 | 1.00 [0.92; 1.00] | 1.00 [0.96; 1.00] | 0.51 |
| Mahalanobis (só corretas) (p95) | 0.55 [0.38; 0.67] | 0.40 | 0.79 [0.65; 0.89] | 0.61 [0.50; 0.71] | 0.54 |
| IsolationForest (só corretas) (p95) | 0.55 [0.41; 0.71] | 0.50 | 0.28 [0.17; 0.43] | 0.15 [0.09; 0.24] | 0.36 |
| Regressão logística | 0.71 [0.62; 0.84] | 0.48 | 0.56 [0.41; 0.70] | 0.32 [0.23; 0.42] | 0.52 |
| Árvore rasa | 0.50 [0.37; 0.65] | 0.59 | 0.37 [0.24; 0.52] | 0.13 [0.08; 0.22] | 0.46 |
| GradientBoosting pequeno | 0.65 [0.47; 0.84] | 0.49 | 0.49 [0.35; 0.63] | 0.27 [0.18; 0.37] | 0.49 |

Vencedor na validação cruzada: **Regressão logística**.

### Reservado (voluntários 1, 2, 6; 18 incorretas, 52 corretas)

| Método | AUC [IC 95% por voluntário] | Precisão | Recall [IC 95%] | Falsos alarmes [IC 95%] | F1 |
|---|---|---|---|---|---|
| Regras (T39/T40) | 0.58 [0.21; 0.71] | 0.32 | 0.61 [0.39; 0.80] | 0.44 [0.32; 0.58] | 0.42 |
| Regras + achados da T41 | 0.58 [0.21; 0.71] | 0.32 | 0.61 [0.39; 0.80] | 0.44 [0.32; 0.58] | 0.42 |
| Sinalizar tudo (base) | 0.50 [0.50; 0.50] | 0.26 | 1.00 [0.82; 1.00] | 1.00 [0.93; 1.00] | 0.41 |
| Mahalanobis (só corretas) | 0.80 [0.38; 0.95] | 0.45 | 0.78 [0.55; 0.91] | 0.33 [0.22; 0.46] | 0.57 |
| IsolationForest (só corretas) | 0.76 [0.33; 0.90] | 0.50 | 0.33 [0.16; 0.56] | 0.12 [0.05; 0.23] | 0.40 |
| Regressão logística | 0.85 [0.76; 0.92] | 0.48 | 0.83 [0.61; 0.94] | 0.31 [0.20; 0.44] | 0.61 |
| Árvore rasa | 0.68 [0.64; 0.86] | 0.34 | 0.72 [0.49; 0.88] | 0.48 [0.35; 0.61] | 0.46 |
| GradientBoosting pequeno | 0.71 [0.49; 0.89] | 0.38 | 0.67 [0.44; 0.84] | 0.38 [0.26; 0.52] | 0.48 |

## Esconder o rosto (Keraal CTK)

Calibração + validação: 31 corretas e 26 incorretas, 7 voluntários.

### Validação cruzada (um voluntário de fora)

| Método | AUC [IC 95% por voluntário] | Precisão | Recall [IC 95%] | Falsos alarmes [IC 95%] | F1 |
|---|---|---|---|---|---|
| Regras (T39/T40) | 0.59 [0.46; 0.67] | 0.51 | 0.88 [0.71; 0.96] | 0.71 [0.53; 0.84] | 0.65 |
| Sinalizar tudo (base) | — | 0.46 | 1.00 [0.87; 1.00] | 1.00 [0.89; 1.00] | 0.63 |
| Mahalanobis (só corretas) (p95) | 0.46 [0.28; 0.61] | 0.46 | 1.00 [0.87; 1.00] | 0.97 [0.84; 0.99] | 0.63 |
| IsolationForest (só corretas) (p95) | 0.50 [0.37; 0.63] | 0.57 | 0.15 [0.06; 0.34] | 0.10 [0.03; 0.25] | 0.24 |
| Regressão logística | 0.71 [0.57; 0.88] | 0.55 | 0.65 [0.46; 0.81] | 0.45 [0.29; 0.62] | 0.60 |
| Árvore rasa | 0.56 [0.30; 0.75] | 0.52 | 0.62 [0.43; 0.78] | 0.48 [0.32; 0.65] | 0.56 |
| GradientBoosting pequeno | 0.57 [0.47; 0.67] | 0.54 | 0.50 [0.32; 0.68] | 0.35 [0.21; 0.53] | 0.52 |

Vencedor na validação cruzada: **nenhum**.

### Reservado (voluntários R1, R6, S1; 10 incorretas, 24 corretas)

| Método | AUC [IC 95% por voluntário] | Precisão | Recall [IC 95%] | Falsos alarmes [IC 95%] | F1 |
|---|---|---|---|---|---|
| Regras (T39/T40) | 0.62 [0.50; 0.72] | 0.36 | 1.00 [0.72; 1.00] | 0.75 [0.55; 0.88] | 0.53 |
| Regras + achados da T41 | 0.62 [0.50; 0.72] | 0.36 | 1.00 [0.72; 1.00] | 0.75 [0.55; 0.88] | 0.53 |
| Sinalizar tudo (base) | 0.50 [0.50; 0.50] | 0.29 | 1.00 [0.72; 1.00] | 1.00 [0.86; 1.00] | 0.45 |
| Mahalanobis (só corretas) | 0.50 [0.33; 0.56] | 0.30 | 1.00 [0.72; 1.00] | 0.96 [0.80; 0.99] | 0.47 |
| IsolationForest (só corretas) | 0.86 [0.56; 0.89] | 0.83 | 0.50 [0.24; 0.76] | 0.04 [0.01; 0.20] | 0.62 |
| Regressão logística | 0.87 [0.50; 1.00] | 0.50 | 0.90 [0.60; 0.98] | 0.38 [0.21; 0.57] | 0.64 |
| Árvore rasa | 0.52 [0.11; 0.53] | 0.30 | 0.80 [0.49; 0.94] | 0.79 [0.60; 0.91] | 0.43 |
| GradientBoosting pequeno | 0.75 [0.56; 1.00] | 0.37 | 0.70 [0.40; 0.89] | 0.50 [0.31; 0.69] | 0.48 |

### Erro nomeado no reservado

Regressão logística multiclasse treinada com as incorretas de Error1 e Error3 fora do reservado (na validação cruzada: acerto 0.48 em 25). Linhas: erro anotado; colunas: erro previsto.

| Anotado | Error1 | Error3 | Achado da regra (T40) |
|---|---|---|---|
| Error1 | 3 | 4 | `physio_low_rom` |
| Error2 | 1 | 0 | `physio_low_rom` |
| Error3 | 2 | 0 | `physio_low_rom` |

Acerto do modelo: 0.30 (10 gravações). As regras "nomeiam" o erro em 8 de 10, mas usam o mesmo achado (`physio_low_rom`) para os três erros: não distinguem um do outro.

## Alongamento lateral (Keraal ELK)

Sem dados para aprender: 4 corretas e 27 incorretas fora do reservado (o mínimo é 10 de cada). Só as regras foram medidas.

| Método | AUC [IC 95% por voluntário] | Precisão | Recall [IC 95%] | Falsos alarmes [IC 95%] | F1 |
|---|---|---|---|---|---|
| Regras (T39/T40) | 0.43 [0.00; 0.46] | 0.52 | 0.86 [0.60; 0.96] | 1.00 [0.74; 1.00] | 0.65 |
| Regras + achados da T41 | 0.46 [0.00; 0.50] | 0.54 | 0.93 [0.69; 0.99] | 1.00 [0.74; 1.00] | 0.68 |
| Sinalizar tudo (base) | 0.50 [0.50; 0.50] | 0.56 | 1.00 [0.78; 1.00] | 1.00 [0.74; 1.00] | 0.72 |

## Rotação de tronco (Keraal RTK)

Sem dados para aprender: 28 corretas e 5 incorretas fora do reservado (o mínimo é 10 de cada). Só as regras foram medidas.

| Método | AUC [IC 95% por voluntário] | Precisão | Recall [IC 95%] | Falsos alarmes [IC 95%] | F1 |
|---|---|---|---|---|---|
| Regras (T39/T40) | 0.29 [0.17; 0.42] | 0.12 | 0.50 [0.19; 0.81] | 0.92 [0.75; 0.98] | 0.19 |
| Regras + achados da T41 | 0.29 [0.17; 0.42] | 0.12 | 0.50 [0.19; 0.81] | 0.92 [0.75; 0.98] | 0.19 |
| Sinalizar tudo (base) | 0.50 [0.50; 0.50] | 0.19 | 1.00 [0.61; 1.00] | 1.00 [0.87; 1.00] | 0.32 |

## Achados novos (passo B4)

Limiares tirados das gravações corretas fora do reservado (`train_physio_model.calibrate_new_findings`); a conferência abaixo também é fora do reservado.

| Exercício | Limiar | Valor | Corretas sinalizadas | Casos-alvo sinalizados |
|---|---|---|---|---|
| Esconder o rosto (Keraal CTK) | `incomplete_rom_min_deg` | 68.9 | 8/36 | 2/2 (incompletas/paradas) |
| Alongamento lateral (Keraal ELK) | `incomplete_rom_min_deg` | 81.5 | 0/22 | 2/9 (incompletas/paradas) |
| Alongamento lateral (Keraal ELK) | `trunk_min_expected_deg` | 6.2 | 4/22 | 5/28 (Error2 (tronco pouco inclinado)) |
| Rotação de tronco (Keraal RTK) | `incomplete_rom_min_deg` | 45.1 | 3/41 | 0/16 (incompletas/paradas) |
| Rotação de tronco (Keraal RTK) | `rotation_ratio_range_min` | 0.09 | 5/41 | 1/2 (Error2 (pouca rotação)) |

No reservado (gravações sem incerteza; incompletas incluídas):

| Exercício | Achado | Grupo | Disparou |
|---|---|---|---|
| Esconder o rosto (Keraal CTK) | `physio_incomplete` | corretas | 0/24 |
| Esconder o rosto (Keraal CTK) | `physio_incomplete` | incompletas | 0/1 |
| Esconder o rosto (Keraal CTK) | `physio_incomplete` | incorretas Error1 | 0/7 |
| Esconder o rosto (Keraal CTK) | `physio_incomplete` | incorretas Error2 | 0/1 |
| Esconder o rosto (Keraal CTK) | `physio_incomplete` | incorretas Error3 | 0/2 |
| Alongamento lateral (Keraal ELK) | `physio_incomplete` | corretas | 1/11 |
| Alongamento lateral (Keraal ELK) | `physio_incomplete` | incompletas | 2/4 |
| Alongamento lateral (Keraal ELK) | `physio_incomplete` | incorretas Error2 | 0/14 |
| Alongamento lateral (Keraal ELK) | `physio_trunk_insufficient` | corretas | 1/11 |
| Alongamento lateral (Keraal ELK) | `physio_trunk_insufficient` | incompletas | 0/4 |
| Alongamento lateral (Keraal ELK) | `physio_trunk_insufficient` | incorretas Error2 | 6/14 |
| Rotação de tronco (Keraal RTK) | `physio_incomplete` | corretas | 0/25 |
| Rotação de tronco (Keraal RTK) | `physio_incomplete` | incompletas | 0/1 |
| Rotação de tronco (Keraal RTK) | `physio_incomplete` | incorretas Error1 | 0/2 |
| Rotação de tronco (Keraal RTK) | `physio_incomplete` | incorretas Error2 | 0/3 |
| Rotação de tronco (Keraal RTK) | `physio_incomplete` | incorretas Other | 0/1 |
| Rotação de tronco (Keraal RTK) | `physio_rotation_low` | corretas | 0/25 |
| Rotação de tronco (Keraal RTK) | `physio_rotation_low` | incompletas | 0/1 |
| Rotação de tronco (Keraal RTK) | `physio_rotation_low` | incorretas Error1 | 0/2 |
| Rotação de tronco (Keraal RTK) | `physio_rotation_low` | incorretas Error2 | 0/3 |
| Rotação de tronco (Keraal RTK) | `physio_rotation_low` | incorretas Other | 0/1 |

## Leitura

- **Agachamento (REHAB24-6):** a regressão logística venceu as regras na validação cruzada (AUC 0.71) e, no reservado, ficou com AUC 0.85 (IC 0.76–0.92), recall 0.83, precisão 0.48 e 31% de falsos alarmes, contra recall 0.61, precisão 0.32 e 44% das regras. Foi integrada (passo B6).
- **Esconder o rosto (Keraal CTK):** nenhum modelo venceu na validação cruzada, então o sistema fica com as regras. No reservado a regressão logística pareceu melhor (F1 0.64 contra 0.53), mas o reservado não escolhe modelo: com 3 voluntários, essa diferença não autoriza trocar.
- **Erro nomeado (Esconder o rosto (Keraal CTK)):** acerto 0.30 no reservado e 0.48 na validação cruzada, perto do acaso: as medidas 2D não distinguem os tipos de erro.
- **Alongamento lateral (Keraal ELK):** 4 corretas e 27 incorretas fora do reservado; sem modelo.
- **Rotação de tronco (Keraal RTK):** 28 corretas e 5 incorretas fora do reservado; sem modelo.
- **Achados novos:** separam pouco. O mais útil é o tronco insuficiente no alongamento lateral; o "incompleto" pega gravações paradas, mas não as incompletas da rotação de tronco, em que o ombro se move normalmente.
- Os intervalos são largos (3 a 4 voluntários no reservado). A seleção por validação cruzada usa os mesmos dados para escolher hiperparâmetros e estimar o desempenho, então os números da validação são otimistas; o do reservado não é.
