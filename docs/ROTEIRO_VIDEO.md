# Roteiro da gravação do vídeo de entrega (T38)

> **Roteiro atual da apresentação: [`ROTEIRO_APRESENTACAO.md`](ROTEIRO_APRESENTACAO.md)** (ordem: pacientes, cadastro ao vivo pela API, Azure ao vivo, código de vídeo, som e sinais, estratégia e métricas). Este arquivo continua válido para a **preparação** (seção 1), o plano B e o checklist.

Meta: até 15 minutos (roteiro de ~14), mostrando os 4 itens que o enunciado exige: **(1)** exemplo prático de áudio e vídeo, **(2)** detecção e resposta a anomalias, **(3)** integração dos serviços Azure e **(4)** fluxo final do alerta à equipe médica.

## 1. Preparação (antes de gravar, fora do vídeo)

Nada abaixo mostra chaves na tela: rode em terminal separado e não abra o `.env`.

```bash
docker compose down -v                      # banco e Redis limpos
docker compose up -d --build                # models-init baixa os modelos; os workers esperam por ele
python scripts/seed.py                      # pacientes P-0001..P-0005
python scripts/train_vitals_iforest.py      # modelo de vitais em models/
python scripts/preflight_demo.py --send-test
```

O `preflight_demo.py` precisa terminar **sem ✗** (código 0). Em modo falso ele lista o que depende do humano (chaves Azure, Teams, e-mail, amostras). Só grave com tudo em ✓.

Amostras em `data/samples/` (ver `data/samples/README.md` e `docs/DATASETS.md`): `physio_squat_correct.mp4` (controle), `physio_squat_wrong.mp4` (os dois são recortes do REHAB24-6, CC BY-NC 4.0, de voluntários reservados, câmera 18; a referência do exercício vem da calibração), `bed_fall.mp4` (UR Fall `fall-12`; reservado na T37, desenvolvimento na T41), `consulta_p0001.wav` (gerada pela Azure, T37 passo 10), `laudo_p0002.txt`, `hello_ptbr.wav`, `cough.wav`, `breathing.wav`, `snoring.wav` (ESC-50 reservados). Pacientes MIMIC reservados para o trecho de dados reais: `M-10002495` e `M-10039831`.

**Opcional (T40):** com `run_demo.py --keraal`, o trecho de fisioterapia pode usar `physio_keraal_wrong.mp4` (minuto 375) no lugar do agachamento; dizer em voz alta que o clipe é de um voluntário **saudável reservado** do Keraal e que as anotações vêm de dois terapeutas, e que no conjunto reservado o sistema acusou quase tudo (ver `docs/resultados/physio_keraal.md`). O trecho substitui o do agachamento, não se soma, para caber nos 15 minutos.

Cuidados de gravação: 1080p a 30 fps, notificações do sistema desligadas, zoom do navegador a 110–125%, janelas do terminal com fonte grande, chaves e `.env` fora da tela.

## 2. Roteiro minuto a minuto

O cenário `demo` leva ~26 min reais; para filmar só o trecho útil use `--fast-until 355 --tail-speedup 12` (minutos 360–480 em ~10 min). Comece a gravar quando o simulador chegar ao minuto ~355.

| Minuto do vídeo | Trecho | Comando / ação | O que mostrar | Frases-chave |
|---|---|---|---|---|
| 0:00–1:30 | Abertura e arquitetura | — | `docs/arquitetura.md` (diagrama Mermaid): API, Redis Streams, workers, banco, dashboard | "Cinco modalidades entram pela mesma esteira de eventos e viram evidências; um motor de fusão calcula o risco de 0 a 100 por paciente." |
| 1:30–2:30 | Ambiente pronto | `python scripts/preflight_demo.py` | lista toda em ✓ (sem chaves) | "Antes de começar, a checagem confirma API, workers, Azure e canais de alerta." |
| 2:30–3:30 | Painel inicial | abrir o dashboard (`http://localhost:8501`) | 5 pacientes, risco baixo, sem alertas | "O painel se atualiza a cada 5 segundos." |
| 3:30–5:00 | **Item 2: vitais e anomalias** | `python scripts/run_demo.py --fast-until 355 --tail-speedup 12` | P-0001 sobe de risco (NEWS2, z-score, Isolation Forest); abrir a tela do paciente: vitais, evidências com explicação | "O risco mistura regras clínicas (NEWS2) e estatística em streaming; cada evidência explica o motivo." |
| 5:00–6:30 | **Item 1: áudio (consulta)** | automático no minuto 370 (`consulta_p0001.wav`) | transcrição da Azure Speech, termos críticos e entidades da Azure Language, evidências de voz | "A Azure transcreve a consulta e extrai termos críticos; o modelo acústico compara com a linha de base de voz." |
| 6:30–7:30 | **Item 1: sons respiratórios** | enviar `cough.wav` pela tela "Enviar mídia" | evento de tosse (AST) com score | "Reservado do ESC-50: precisão e recall 0,97 no conjunto reservado." |
| 7:30–9:00 | **Item 1: vídeo (fisioterapia)** | automático no minuto 365 (`physio_squat_wrong.mp4`) | vídeo anotado, contagem de repetições, `physio_pattern_deviation` com a probabilidade do modelo e as medidas que mais pesaram | "A pose YOLO vira um conjunto de medidas por repetição (amplitudes, DTW contra a referência, tronco) e uma regressão logística, escolhida por validação cruzada deixando um voluntário de fora, decide se a repetição está incorreta; este clipe é de um voluntário reservado do REHAB24-6. No reservado, o modelo pega 83% das repetições incorretas com 31% de falsos alarmes; as regras fixas pegavam 61% com 44%. Melhorou, mas ainda erra uma em cada três corretas." |
| 9:00–10:30 | **Item 1: vídeo (queda)** | automático no minuto 410 (`bed_fall.mp4`) | queda detectada (UR Fall `fall-12`) | "Esta queda é de um dataset público. Revisamos a regra com o UR Fall e a medimos num segundo dataset, o CAUCAFall, que nunca foi usado no ajuste: ela detecta 12 de 50 quedas (recall 0,24) sem nenhum falso alarme nas 50 atividades normais. Com a câmera no alto do canto a pessoa caída não parece deitada para uma regra 2D: mostramos o limite com honestidade." |
| 10:30–11:30 | **Item 2: dados reais reservados** | `python -m medwatch.simulator.replay --mimic-split reservado --fast` (ou captura gravada) | pacientes `M-10002495` e `M-10039831` do MIMIC com alertas | "Dados reais do MIMIC-IV Demo, parte reservada: recall semissintético de 0,87." |
| 11:30–13:00 | **Itens 3 e 4: alerta à equipe** | painel "Alertas abertos"; Teams e e-mail no outro monitor | cartão com **risco de pico** e **risco atual**; mensagem no Teams; e-mail pelo Logic App; escalonamento | "O alerta chega ao Teams e ao e-mail; sem confirmação em 5 minutos (`ALERT_ESCALATION_MINUTES`) ele escalona." |
| 13:00–13:40 | Confirmação | botão Confirmar com nota | alerta muda para confirmado; relatório PDF/HTML da sessão | "A equipe confirma e o relatório com evidências fica disponível." |
| 13:40–14:00 | Fechamento | — | resumo e pendências conhecidas | "Limites: vídeo de queda generaliza mal; vitais do MIMIC são horários." |

Observação sobre o risco: o cartão mostra "risco de pico" (máximo do alerta) e "risco atual" (valor de agora do paciente); os dois podem divergir depois de a situação melhorar, e isso é esperado.

## 3. Plano B por trecho

| Se falhar | Faça |
|---|---|
| Azure Speech/Language | Mostrar o trecho gravado antes (gravar a tela do trecho 5:00–6:30 num ensaio) e os logs do `worker-audio` (`docker compose logs worker-audio`) |
| Teams ou e-mail | Mostrar a mensagem de teste do ensaio e o `ConsoleChannel` nos logs do `worker-alerts` |
| YOLO lento ou sem GPU | Usar o vídeo anotado já gerado no ensaio (seção "Mídias" da tela do paciente) |
| Simulador adiantado ou atrasado | Reiniciar com `docker compose down -v` e refazer a preparação; não editar o banco à mão |
| Dashboard travado | Recarregar a página; os dados continuam no banco |

## 4. Checklist final

- [ ] `preflight_demo.py` todo em ✓ antes de gravar.
- [ ] Ensaio completo feito uma vez, com o trecho de plano B gravado.
- [ ] Vídeo exportado em 1080p/30 fps com até 15 min.
- [ ] Nenhuma chave, e-mail ou webhook visível (revisar o vídeo inteiro).
- [ ] Vídeo publicado no YouTube ou Vimeo como **não listado**.
- [ ] Link do vídeo no `README.md`.
