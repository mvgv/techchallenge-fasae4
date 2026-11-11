# Datasets públicos: resultados nas partes reservadas (T37)

Resumo; os detalhes e as grades de calibração estão nos relatórios citados. Nenhum número abaixo ajustou parâmetros.

| Dataset | Componente | Reservado | Resultado | Relatório |
|---|---|---|---|---|
| MIMIC-IV Demo 2.2 | vitais (NEWS2 + z-score + IForest) | 20 pacientes, 107,7 paciente-dias | recall semissintético 0,87 (taquicardia curta 0,69); 1,09 alerta/paciente-dia só com vitais, 1,87 com prescrições | `mimic_results.md` |
| ESC-50 (10 classes) | sons respiratórios (AST) | folds 4–5, 160 clipes | precisão 0,97, recall 0,97 (respiratório × não respiratório) | `audio_events.md` |
| UR Fall (cam0) | queda (pose YOLOv8n + regra de quadril/aspecto) | quedas 11–30 e ADL 11–40 | precisão 0,67, recall 0,10 (calibração: recall 0,90, precisão 1,00); ADL sem alarme em 29 de 30 | `urfall_fall.md` |
| Common Voice (pt) | voz saudável | — | pendente: termos no site [HUMANO] | — |
| Consulta sintética (Azure) | fala → texto → termos | — | pendente: chaves Azure [HUMANO] | — |

Leitura: os dados reais mostram que o vídeo de queda generaliza mal (clipes curtos que terminam logo após deitar, pose falha no chão); o áudio e os vitais se sustentam nas partes reservadas, com a ressalva do MIMIC de que as leituras horárias limitam o atraso dos alertas.
