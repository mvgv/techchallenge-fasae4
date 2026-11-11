# Linha de base de voz e falsos alarmes (Common Voice pt-BR, T37 passo 9)

Gerado por `scripts/evaluate_voice.py`. Os falantes foram divididos em calibração (linha de base) e reservado (nunca usado para ajustar nada). Todas as vozes são de pessoas que gravaram frases do Common Voice; nenhuma tem doença da fala conhecida, então só se mede **especificidade** (falsos alarmes), não sensibilidade.

Limiares em uso (`config/thresholds.yaml`, não alterados): {'speech_rate_wpm_min': 100, 'pause_ratio_max': 0.4, 'z_threshold': 2.0}.

## Falsos alarmes em vozes saudáveis

| Grupo | Falantes | Com algum alarme | Taxa | `voice_fatigue` | `voice_dysarthria_indicator` |
|---|---|---|---|---|---|
| Calibração (a própria linha de base; otimista) | 54 | 1 | 1.9% | 0 | 1 |
| **Reservado** | 27 | 2 | **7.4%** (IC 95%: 2% a 23%) | 2 | 0 |

Sinais que dispararam no reservado: {'slow_speech': 2, 'low_loudness': 1, 'many_pauses': 1}. Na calibração: {'jitter_high': 1, 'shimmer_high': 1}.

## Distribuição das medidas (média, percentis 5 e 95)

| Medida | Calibração | Reservado |
|---|---|---|
| `speech_rate_wpm` | 124.519 (70.819 a 167.598) | 118.699 (87.512 a 161.638) |
| `pause_ratio` | 0.116 (0.035 a 0.213) | 0.129 (0.027 a 0.291) |
| `jitter` | 0.025 (0.018 a 0.031) | 0.023 (0.016 a 0.033) |
| `shimmer_db` | 1.348 (1.087 a 1.566) | 1.264 (0.94 a 1.554) |
| `hnr` | 5.221 (3.104 a 8.28) | 5.766 (3.12 a 9.267) |
| `loudness` | 0.569 (0.34 a 0.83) | 0.556 (0.265 a 1.422) |
| `duration_s` | 30.02 (14.368 a 49.248) | 27.682 (14.656 a 38.472) |

## Limitações

1. **Poucas vozes reservadas** (27): cada falante pesa 3.7%; o intervalo de confiança é largo.
2. **Estilo de leitura, não conversa.** Os falantes leem frases curtas (às vezes uma palavra). Voluntários saudáveis ficam entre os percentis 5 e 95 da velocidade de fala acima, então o limiar fixo de 100 palavras por minuto marca como lentos muitos leitores saudáveis, e o limiar de pausas (0,40) fica bem acima do que esse material mostra. Esses dois limiares **não foram calibrados com estes dados** e precisam de conversas reais.
3. **Canal de gravação.** Os áudios são MP3 de microfones variados; jitter, shimmer e HNR dependem do canal. A linha de base só vale para áudio de qualidade parecida; gravações de consultas reais precisam de uma própria.
4. **População.** O recorte tem muito mais homens (cerca de 71% dos clipes) e quase só adultos de 20 a 40 anos.
5. **Sem vozes patológicas.** Detectar fadiga ou disartria de verdade exigiria fala patológica anotada (por exemplo, TORGO ou UA-Speech, com cadastro), que não foi usada.
