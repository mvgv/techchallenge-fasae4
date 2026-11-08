# MedWatch — instruções para o agente

Projeto do Tech Challenge IADT Fase 4: monitoramento multimodal de pacientes (Python + Azure AI).

## Em toda sessão, antes de qualquer coisa

1. Leia `PROGRESSO.md`. Ele diz qual tarefa está em andamento e qual é o próximo passo exato.
2. Siga o **protocolo de início de sessão** da seção 0.1 do `PLANO_IMPLEMENTACAO.md`.
3. No `PLANO_IMPLEMENTACAO.md`, leia só a seção 0 (regras), a tarefa atual e as seções que ela referencia. Não releia o plano inteiro.

## Regras essenciais (o plano é a referência completa)

- Uma tarefa por vez, na ordem numérica, respeitando as dependências.
- A sessão pode acabar a qualquer momento. A cada passo concluído:
  atualize `PROGRESSO.md` → `git add` (arquivos do passo + `PROGRESSO.md`) → commit `T<NN> [wip]: <passo>` → `git push`.
- Commit final da tarefa: `T<NN>: <título>`, só com `pytest -q` e `ruff check .` passando.
- Nunca acumule mais de ~5 arquivos ou ~30 minutos de trabalho sem commit.
- Ao perceber que a sessão vai terminar, siga o **protocolo de encerramento** (seção 0.1).
- Nunca descarte mudanças sem commit sem antes guardá-las com `git stash push -u -m "<motivo>"`.
- Passos **[HUMANO]** pendentes vão para a tabela de bloqueios do `PROGRESSO.md`; conclua o que der com `USE_FAKE_AZURE=true` e siga.
- Nunca commite `.env`, `data/` ou `models/`. Nunca invente identidade do Git nem credenciais: peça ao humano.
- Decisões não previstas no plano: uma linha em `docs/DECISOES.md`.
- Modelo: Sonnet 5.5 por padrão. Em T24, T26, T30, T32 ou após 2 tentativas falhas no mesmo erro, registre `recomendação: trocar para Opus 5.5` no `PROGRESSO.md` e avise o humano (seção 0.2).
- Rodando numa sessão na nuvem ou numa VPS: veja `docs/AMBIENTE_REMOTO.md`.

## Ambiente

- Windows: se `git` não estiver no PATH, use `"C:\Program Files\Git\cmd\git.exe"`.
- Containers: seção 9 do plano. Suba só os serviços já implementados (tabela 9.6).
- Testes: `pytest -q` local ou `docker compose run --rm api pytest -q`.
