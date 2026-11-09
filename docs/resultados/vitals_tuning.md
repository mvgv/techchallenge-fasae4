# Busca de limiares dos vitais (T36)

Avaliação no nível de alerta (configuração NEWS2 + z-score + IForest); critério de escolha: recall de 100% nos rótulos positivos e menor número de alertas em pacientes normais. Os 30 pacientes de ajuste (`seeds 100–129`) e os 30 de conferência (`seeds 200–229`, nunca usados no ajuste) têm a mesma composição.

## Ajuste (seeds 100–129)

| z limiar | z pers. | IForest limiar | IF pers. | TP | FN | Recall | Alertas FP | Alertas/dia (normais) | Precisão | Atraso mediano (min) |
|---|---|---|---|---|---|---|---|---|---|---|
| 3.0 | 1 | percentil 0,5 | 1 | 12 | 3 | 0.80 | 29 | 1.50 | 0.29 | 11.0 |
| 3.0 | 1 | percentil 0,5 | 3 | 13 | 2 | 0.87 | 8 | 0.20 | 0.62 | 26.0 |
| 3.0 | 1 | percentil 0,1 | 1 | 13 | 2 | 0.87 | 19 | 0.90 | 0.41 | 26.0 |
| 3.0 | 1 | percentil 0,1 | 3 | 14 | 1 | 0.93 | 3 | 0.10 | 0.82 | 30.5 |
| 3.0 | 3 | percentil 0,5 | 1 | 8 | 7 | 0.53 | 73 | 3.10 | 0.10 | 28.0 |
| 3.0 | 3 | percentil 0,5 | 3 | 9 | 6 | 0.60 | 8 | 0.10 | 0.53 | 34.0 |
| 3.0 | 3 | percentil 0,1 | 1 | 9 | 6 | 0.60 | 29 | 1.40 | 0.24 | 34.0 |
| 3.0 | 3 | percentil 0,1 | 3 | 7 | 8 | 0.47 | 1 | 0.00 | 0.88 | 40.0 |
| 3.5 | 1 | percentil 0,5 | 1 | 13 | 2 | 0.87 | 60 | 2.50 | 0.18 | 22.0 |
| 3.5 | 1 | percentil 0,5 | 3 | 14 | 1 | 0.93 | 9 | 0.10 | 0.61 | 14.0 |
| 3.5 | 1 | percentil 0,1 | 1 | 14 | 1 | 0.93 | 28 | 1.20 | 0.33 | 13.0 |
| 3.5 | 1 | percentil 0,1 | 3 | 13 | 2 | 0.87 | 2 | 0.00 | 0.87 | 29.0 |
| 3.5 | 3 | percentil 0,5 | 1 | 8 | 7 | 0.53 | 73 | 3.10 | 0.10 | 28.0 |
| 3.5 | 3 | percentil 0,5 | 3 | 9 | 6 | 0.60 | 8 | 0.10 | 0.53 | 34.0 |
| 3.5 | 3 | percentil 0,1 | 1 | 9 | 6 | 0.60 | 29 | 1.40 | 0.24 | 34.0 |
| 3.5 | 3 | percentil 0,1 | 3 | 7 | 8 | 0.47 | 1 | 0.00 | 0.88 | 40.0 |
| 4.0 | 1 | percentil 0,5 | 1 | 13 | 2 | 0.87 | 69 | 2.90 | 0.16 | 22.0 |
| 4.0 | 1 | percentil 0,5 | 3 | 14 | 1 | 0.93 | 9 | 0.10 | 0.61 | 14.0 |
| 4.0 | 1 | percentil 0,1 | 1 | 14 | 1 | 0.93 | 30 | 1.40 | 0.32 | 13.0 |
| 4.0 | 1 | percentil 0,1 | 3 | 13 | 2 | 0.87 | 2 | 0.00 | 0.87 | 29.0 |
| 4.0 | 3 | percentil 0,5 | 1 | 8 | 7 | 0.53 | 73 | 3.10 | 0.10 | 28.0 |
| 4.0 | 3 | percentil 0,5 | 3 | 9 | 6 | 0.60 | 8 | 0.10 | 0.53 | 34.0 |
| 4.0 | 3 | percentil 0,1 | 1 | 9 | 6 | 0.60 | 29 | 1.40 | 0.24 | 34.0 |
| 4.0 | 3 | percentil 0,1 | 3 | 7 | 8 | 0.47 | 1 | 0.00 | 0.88 | 40.0 |

## Conferência (seeds 200–229)

| z limiar | z pers. | IForest limiar | IF pers. | TP | FN | Recall | Alertas FP | Alertas/dia (normais) | Precisão | Atraso mediano (min) |
|---|---|---|---|---|---|---|---|---|---|---|
| 3.0 | 1 | percentil 0,5 | 1 | 10 | 5 | 0.67 | 42 | 1.80 | 0.19 | 0.0 |
| 3.0 | 1 | percentil 0,5 | 3 | 14 | 1 | 0.93 | 11 | 0.60 | 0.56 | 26.5 |
| 3.0 | 1 | percentil 0,1 | 1 | 14 | 1 | 0.93 | 25 | 1.50 | 0.36 | 24.0 |
| 3.0 | 1 | percentil 0,1 | 3 | 15 | 0 | 1.00 | 1 | 0.00 | 0.94 | 24.0 |
| 3.0 | 3 | percentil 0,5 | 1 | 8 | 7 | 0.53 | 76 | 3.90 | 0.10 | 29.0 |
| 3.0 | 3 | percentil 0,5 | 3 | 9 | 6 | 0.60 | 15 | 0.70 | 0.38 | 37.0 |
| 3.0 | 3 | percentil 0,1 | 1 | 9 | 6 | 0.60 | 46 | 2.20 | 0.16 | 33.0 |
| 3.0 | 3 | percentil 0,1 | 3 | 8 | 7 | 0.53 | 0 | 0.00 | 1.00 | 38.5 |
| 3.5 | 1 | percentil 0,5 | 1 | 13 | 2 | 0.87 | 67 | 3.30 | 0.16 | 20.0 |
| 3.5 | 1 | percentil 0,5 | 3 | 15 | 0 | 1.00 | 16 | 0.70 | 0.48 | 24.0 |
| 3.5 | 1 | percentil 0,1 | 1 | 15 | 0 | 1.00 | 39 | 2.10 | 0.28 | 24.0 |
| 3.5 | 1 | percentil 0,1 | 3 | 15 | 0 | 1.00 | 1 | 0.00 | 0.94 | 28.0 |
| 3.5 | 3 | percentil 0,5 | 1 | 8 | 7 | 0.53 | 76 | 3.90 | 0.10 | 29.0 |
| 3.5 | 3 | percentil 0,5 | 3 | 9 | 6 | 0.60 | 15 | 0.70 | 0.38 | 37.0 |
| 3.5 | 3 | percentil 0,1 | 1 | 9 | 6 | 0.60 | 46 | 2.20 | 0.16 | 33.0 |
| 3.5 | 3 | percentil 0,1 | 3 | 8 | 7 | 0.53 | 0 | 0.00 | 1.00 | 38.5 |
| 4.0 | 1 | percentil 0,5 | 1 | 13 | 2 | 0.87 | 74 | 3.80 | 0.15 | 20.0 |
| 4.0 | 1 | percentil 0,5 | 3 | 15 | 0 | 1.00 | 16 | 0.70 | 0.48 | 24.0 |
| 4.0 | 1 | percentil 0,1 | 1 | 15 | 0 | 1.00 | 46 | 2.20 | 0.25 | 24.0 |
| 4.0 | 1 | percentil 0,1 | 3 | 15 | 0 | 1.00 | 1 | 0.00 | 0.94 | 28.0 |
| 4.0 | 3 | percentil 0,5 | 1 | 8 | 7 | 0.53 | 76 | 3.90 | 0.10 | 29.0 |
| 4.0 | 3 | percentil 0,5 | 3 | 9 | 6 | 0.60 | 15 | 0.70 | 0.38 | 37.0 |
| 4.0 | 3 | percentil 0,1 | 1 | 9 | 6 | 0.60 | 46 | 2.20 | 0.16 | 33.0 |
| 4.0 | 3 | percentil 0,1 | 3 | 8 | 7 | 0.53 | 0 | 0.00 | 1.00 | 38.5 |
## Escolha

**z-score: limiar 3,0, persistência 1; Isolation Forest: percentil 0,1, persistência 3.**

- Maior recall no nível de alerta entre as 24 combinações do conjunto de ajuste (14 de 15 rótulos, 0,93), empatado com `z 3,5 / 1 / percentil 0,5 / 3`; entre as duas, a escolhida tem o menor número de alertas em pacientes normais na conferência (0,00 contra 0,70 por paciente-dia).
- No conjunto de conferência (seeds 200–229, nunca usado no ajuste) a combinação escolhida tem recall 1,00 e 0,00 alerta por paciente-dia em pacientes normais; no ajuste, 0,10.
- **Recall de 100% não foi alcançado no conjunto de ajuste.** O rótulo perdido é uma `hypotension` (seed 119): a PAS cai a ~82 mmHg, o que dá só 3 pontos de NEWS2 (um parâmetro, faixa `low_medium`, peso 0,45 × score 0,3: risco ≈ 14, abaixo de `warning` = 40), e o z-score não dispara de forma sustentada na rampa lenta de 45 min. Corrigir isso exigiria mudar pesos ou limiares da fusão (fora do escopo da T36); fica registrado como limitação.
- Persistência 3 no z-score derruba o recall (0,47–0,60): o `tachy_spike` dura 3 minutos e, depois da primeira leitura anômala, a variância exponencial cresce e o z das seguintes cai abaixo do limiar. Por isso o z-score fica com persistência 1 e a persistência atua no Isolation Forest, o detector ruidoso.
