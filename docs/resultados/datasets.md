# Datasets públicos: resultados nas partes reservadas (T37)

Resumo; os detalhes e as grades de calibração estão nos relatórios citados. Nenhum número abaixo ajustou parâmetros.

| Dataset | Componente | Reservado | Resultado | Relatório |
|---|---|---|---|---|
| MIMIC-IV Demo 2.2 | vitais (NEWS2 + z-score + IForest) | 20 pacientes, 107,7 paciente-dias | recall semissintético 0,87 (taquicardia curta 0,69); 1,09 alerta/paciente-dia só com vitais, 1,87 com prescrições | `mimic_results.md` |
| ESC-50 (10 classes) | sons respiratórios (AST) | folds 4–5, 160 clipes | precisão 0,97, recall 0,97 (respiratório × não respiratório) | `audio_events.md` |
| UR Fall (cam0) | queda (pose YOLOv8n + regra de quadril/aspecto) | quedas 11–30 e ADL 11–40 | precisão 0,67, recall 0,10 (calibração: recall 0,90, precisão 1,00); ADL sem alarme em 29 de 30 | `urfall_fall.md` |
| CAUCAFall (T41, reservado novo de queda) | queda (pose YOLOv8n + caixa do detector quando a pose some + regra de quadril/aspecto ajustada no UR Fall inteiro) | 100 vídeos, 10 voluntários (50 quedas, 50 ADL), câmera alta no canto | recall 0,24 (12 de 50; IC 95% de 0,14 a 0,37), precisão 1,00, nenhuma ADL com alarme; regra da T37 no mesmo reservado: recall 0,20. No desenvolvimento (UR Fall inteiro) a regra nova foi de 11 para 26 de 30 quedas com 1 falso alarme em 40 ADL | `fall_v2.md` |
| REHAB24-6 (Ex6, agachamento) | fisioterapia (pose YOLOv8n + ROM, assimetria, DTW, tronco) | 3 voluntários, 70 repetições (18 incorretas) | recall de repetição incorreta 0,61 (IC 95% de 0,39 a 0,80), precisão 0,32, falsos alarmes 44% (23 de 52); contagem: erro médio de 1,8 repetições por bloco | `physio_rehab24.md` |
| Keraal (grupos 1A e 2A: dor lombar e saudáveis; RTK, ELK, CTK) | fisioterapia com erro nomeado (pose YOLOv8n + ROM, assimetria, DTW, tronco) | 4 voluntários (R1, R6, S1, S6), 90 gravações anotadas | precisão 12% / 52% / 36% e recall 50% / 86% / 100% (RTK / ELK / CTK), falsos alarmes 75% a 100%: nada separou correto de incorreto melhor que sinalizar tudo; erro nomeado só no CTK (8 de 10, tempo coincidente) | `physio_keraal.md` |
| Common Voice pt-BR (recorte brasileiro) | voz saudável: linha de base e falsos alarmes | 27 falantes | 2 de 27 (7,4%; IC 95% de 2% a 23%) dispararam `voice_fatigue`; nenhum, disartria | `voice_baseline.md` |
| Consulta sintética (Azure) | fala → texto → termos | consulta de 38 s | separação de falantes correta nas 8 falas; 5 termos críticos, 1 falso por erro de reconhecimento | `azure_integracao.md` |

Voz: só se mede especificidade (falsos alarmes) com 27 falantes; os limiares de ritmo de fala e de pausas não foram calibrados com estes dados (leitura de frases curtas, não conversa).

Leitura: os dados reais mostram que o vídeo de queda generaliza mal (no UR Fall, clipes curtos e pose que falha no chão; no CAUCAFall, a T41 corrigiu isso no desenvolvimento, mas a câmera alta no canto deixa a caixa da pessoa deitada mais alta que larga e o recall fica em 0,24); o áudio e os vitais se sustentam nas partes reservadas, com a ressalva do MIMIC de que as leituras horárias limitam o atraso dos alertas.
