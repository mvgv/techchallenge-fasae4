#!/usr/bin/env bash
# Executa o plano em ciclos. Cada ciclo é uma sessão nova do Claude que retoma pelo PROGRESSO.md.
#
#   Iniciar (dentro do tmux):  bash scripts/run_agent.sh
#   Parar:                     touch ~/STOP_AGENT   (termina o ciclo atual e para)
#
# Diferenças em relação à primeira versão:
#   - limite de uso do plano: lê no aviso a hora em que renova e espera até lá, sem contar como falha;
#   - só ciclos que terminam bem contam como "repetição" da mesma tarefa;
#   - falhas que não são limite de uso (6 seguidas) param o script para revisão.
#
# Variáveis opcionais: REPO (pasta do projeto), LOG (arquivo de log), MAX_REPEAT (padrão 8).

REPO="${REPO:-$HOME/workspace/techchallenge-fasae4}"
LOG="${LOG:-$HOME/agent.log}"
MAX_REPEAT="${MAX_REPEAT:-8}"
STOP_FILE="$HOME/STOP_AGENT"

cd "$REPO" || { echo "pasta $REPO não existe" >&2; exit 1; }

PROMPT="Neste modo automático, rode comandos longos (build, instalação, testes) em primeiro plano até terminarem; não agende verificações nem deixe processos em segundo plano. O ambiente Python 3.11 já está pronto em .venv: use .venv/bin/python, .venv/bin/pytest e .venv/bin/ruff, sem docker run e sem criar outro venv. Leia o CLAUDE.md e siga o protocolo de início de sessão. Trabalhe na tarefa atual do PROGRESSO.md até concluí-la, com commit e push a cada passo. Ao concluir, atualize o PROGRESSO.md, faça o commit final com push e encerre. Se a tarefa depender de um passo humano, registre o bloqueio e avance para a próxima tarefa possível."

# Imprime quantos segundos esperar até o limite renovar ("... resets 2:20pm (America/Sao_Paulo)").
# Sem hora reconhecível, espera 30 minutos. Nunca passa de 6 horas.
wait_for_reset() {
  local out="$1" txt zone alvo agora espera
  txt=$(grep -oiE "resets [0-9]{1,2}(:[0-9]{2})? ?(am|pm)" "$out" | head -1 | sed -E 's/^resets //I')
  zone=$(grep -oE "\(America/[A-Za-z_]+\)" "$out" | head -1 | tr -d '()')
  if [ -z "$txt" ]; then echo 1800; return; fi
  alvo=$(TZ="${zone:-America/Sao_Paulo}" date -d "$txt" +%s 2>/dev/null) || { echo 1800; return; }
  agora=$(date +%s)
  [ "$alvo" -le "$agora" ] && alvo=$((alvo + 86400))
  espera=$((alvo - agora + 180))   # 3 minutos de folga
  [ "$espera" -gt 21600 ] && espera=21600
  echo "$espera"
}

LAST=""; REPEAT=0; FAILS=0

while [ ! -f "$STOP_FILE" ]; do
  git pull --ff-only -q
  TASK=$(grep -m1 'Tarefa atual:' PROGRESSO.md | grep -o 'T[0-9][0-9]' | head -1)
  if [ -z "$TASK" ]; then
    echo "=== $(date '+%F %T') sem tarefa atual; parando ===" >> "$LOG"
    break
  fi
  case "$TASK" in
    T24|T26|T30|T32|T35) MODEL=claude-opus-5-5 ;;
    *) MODEL=claude-sonnet-5-5 ;;
  esac

  echo "=== $(date '+%F %T') tarefa=$TASK modelo=$MODEL ===" >> "$LOG"
  OUT=$(mktemp)
  claude -p "$PROMPT" --model "$MODEL" > "$OUT" 2>&1
  RC=$?
  cat "$OUT" >> "$LOG"

  if grep -qiE "hit your .*limit|usage limit" "$OUT"; then
    ESPERA=$(wait_for_reset "$OUT")
    echo "--- $(date '+%F %T') limite de uso atingido; aguardando $((ESPERA / 60)) min até renovar" >> "$LOG"
    rm -f "$OUT"
    sleep "$ESPERA"
    continue
  fi
  rm -f "$OUT"

  if [ "$RC" -eq 0 ]; then
    FAILS=0
    if [ "$TASK" = "$LAST" ]; then REPEAT=$((REPEAT + 1)); else REPEAT=0; LAST="$TASK"; fi
    if [ "$REPEAT" -ge "$MAX_REPEAT" ]; then
      echo "=== $TASK repetiu $MAX_REPEAT ciclos concluídos; parando para revisão ===" >> "$LOG"
      break
    fi
    sleep 60
  else
    FAILS=$((FAILS + 1))
    if [ "$FAILS" -ge 6 ]; then
      echo "=== 6 falhas seguidas que não são limite de uso; parando para revisão ===" >> "$LOG"
      break
    fi
    echo "--- ciclo falhou (erro, não é limite de uso); nova tentativa em 30 min" >> "$LOG"
    sleep 1800
  fi
done
