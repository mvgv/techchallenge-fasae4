# Datasets públicos: resultados nas partes reservadas (T37)

Resumo; os detalhes e as grades de calibração estão nos relatórios citados. Nenhum número abaixo ajustou parâmetros.

| Dataset | Componente | Reservado | Resultado | Relatório |
|---|---|---|---|---|
| MIMIC-IV Demo 2.2 | vitais (NEWS2 + z-score + IForest) | 20 pacientes, 107,7 paciente-dias | recall semissintético 0,87 (taquicardia curta 0,69); 1,09 alerta/paciente-dia só com vitais, 1,87 com prescrições | `mimic_results.md` |
| ESC-50 (10 classes) | sons respiratórios (AST) | folds 4–5, 160 clipes | precisão 0,97, recall 0,97 (respiratório × não respiratório) | `audio_events.md` |
| UR Fall (cam0) | queda (pose YOLOv8n + regra de quadril/aspecto) | quedas 11–30 e ADL 11–40 | precisão 0,67, recall 0,10 (calibração: recall 0,90, precisão 1,00); ADL sem alarme em 29 de 30 | `urfall_fall.md` |
| Common Voice pt-BR (recorte brasileiro) | voz saudável: linha de base e falsos alarmes | 27 falantes | 2 de 27 (7,4%; IC 95% de 2% a 23%) dispararam `voice_fatigue`; nenhum, disartria | `voice_baseline.md` |
| Consulta sintética (Azure) | fala → texto → termos | consulta de 38 s | separação de falantes correta nas 8 falas; 5 termos críticos, 1 falso por erro de reconhecimento | `azure_integracao.md` |

Voz: só se mede especificidade (falsos alarmes) com 27 falantes; os limiares de ritmo de fala e de pausas não foram calibrados com estes dados (leitura de frases curtas, não conversa).

Leitura: os dados reais mostram que o vídeo de queda generaliza mal (clipes curtos que terminam logo após deitar, pose falha no chão); o áudio e os vitais se sustentam nas partes reservadas, com a ressalva do MIMIC de que as leituras horárias limitam o atraso dos alertas.
