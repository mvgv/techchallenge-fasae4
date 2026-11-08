# Ambiente remoto para o agente executor

Como rodar o Claude Code fora deste desktop para executar o `PLANO_IMPLEMENTACAO.md`. Há dois caminhos; ambos consomem o mesmo limite de uso do seu plano Claude, a diferença está em onde o código e o Docker rodam.

## Qual escolher

| | Opção 1: sessões na nuvem do Claude Code | Opção 2: VPS própria via SSH |
|---|---|---|
| Custo extra | Nenhum (a VM está incluída no plano) | Mensalidade do provedor (ordem de US$ 20–40/mês para 4 vCPU e 16 GB) |
| Máquina | Ubuntu 24.04, 4 vCPU, 16 GB de RAM, 30 GB de disco, Docker e Compose instalados | Você escolhe; recomendado 4 vCPU, 16 GB, 80 GB |
| Estado entre sessões | VM recriada quando fica ociosa: só o que está no Git sobrevive | Persistente: imagem Docker, banco, modelos e `.env` ficam no disco |
| Manutenção | Nenhuma | Atualizações, firewall e segurança por sua conta |
| Ver o dashboard (porta 8501) | Não há acesso direto às portas da VM | Túnel SSH para `localhost:8501` |
| Continua com o desktop desligado | Sim | Sim (a tarefa pode parar se o login expirar) |

**Recomendação:** comece pela **opção 1**. O projeto já foi preparado para ela: o estado do trabalho fica no Git (`PROGRESSO.md`, commits `[wip]`), então a VM ser recriada não perde nada. Mude para a **opção 2** quando precisar do ambiente completo ligado o tempo todo (T27 em diante, para ver o dashboard e os alertas em funcionamento, e para gravar o vídeo da entrega).

---

## Opção 1: sessões na nuvem

### 1. Conectar o GitHub

1. Abra [claude.ai/code](https://claude.ai/code) e siga a configuração inicial.
2. Autorize o **Claude GitHub App** e instale-o no repositório `mvgv/techchallenge-fasae4`.

### 2. Criar o ambiente `medwatch`

Crie um ambiente de nuvem (pela página de ambientes em claude.ai/code ou pelo seletor de ambiente do app, em **Cloud**) com:

**Rede:** nível **Custom**, marcando **Also include default list of common package managers**, e acrescentando estes domínios (um por linha). A lista padrão já cobre PyPI, Docker Hub, GitHub e os repositórios do Ubuntu; estes são os que o projeto usa além dela:

```text
download.pytorch.org
huggingface.co
*.huggingface.co
*.hf.co
deb.debian.org
security.debian.org
physionet.org
*.cognitiveservices.azure.com
*.api.cognitive.microsoft.com
*.speech.microsoft.com
*.blob.core.windows.net
```

| Domínio | Para quê |
|---|---|
| `download.pytorch.org` | Torch CPU (T01 e `Dockerfile`) |
| `huggingface.co`, `*.huggingface.co`, `*.hf.co` | Modelo AST de sons respiratórios (T17) |
| `deb.debian.org`, `security.debian.org` | `apt-get` dentro do build da imagem Docker |
| `physionet.org` | MIMIC-IV Demo (T07, opcional) |
| `*.cognitiveservices.azure.com`, `*.api.cognitive.microsoft.com`, `*.speech.microsoft.com`, `*.blob.core.windows.net` | Azure AI Speech, Language e Blob, se forem usadas chaves reais |

**Variáveis de ambiente** (formato `.env`):

```dotenv
USE_FAKE_AZURE=true
BASH_DEFAULT_TIMEOUT_MS=600000
BASH_MAX_TIMEOUT_MS=1800000
```

- `USE_FAKE_AZURE=true` deixa o projeto funcionar sem chaves. As variáveis deste ambiente ficam visíveis dentro da sessão; por isso a recomendação é **não** colocar as chaves Azure aqui e fazer a verificação real (`scripts/check_azure.py`) numa máquina sua ou na VPS.
- Os dois `BASH_*` dão mais tempo para `pip install`, `docker compose build` e testes lentos.

**Script de configuração** (roda uma vez como root; se terminar em ~5 minutos, o resultado fica em cache para as próximas sessões):

```bash
#!/bin/bash
set -e
uv python install 3.11
docker pull timescale/timescaledb:latest-pg16
docker pull redis:7-alpine
docker pull python:3.11-slim-bookworm
```

Não coloque o `docker compose build` aqui: com o Torch ele passa de 5 minutos e o cache deixa de funcionar.

### 3. Trabalhar nas sessões

1. No app, abra o seletor de ambiente, escolha **Cloud → medwatch** e o repositório `mvgv/techchallenge-fasae4`.
2. Escolha o modelo **Claude Sonnet 5.5** no seletor de modelo (ou digite `/model sonnet` na sessão). Veja a seção 0.2 do plano para quando trocar para o Opus 5.5.
3. Mensagem inicial sugerida:

   > Leia o CLAUDE.md e continue o trabalho a partir do PROGRESSO.md. Trabalhe na branch `dev` (crie a partir da `main` se não existir), faça push nela a cada commit e não abra pull request. Neste ambiente, use `uv venv --python 3.11 .venv` no lugar de `python -m venv`.

4. Para continuar outro dia, inicie uma sessão nova com a mesma mensagem ou reabra a sessão anterior em claude.ai/code. A VM é recriada, mas o trabalho está na branch `dev`.
5. De tempos em tempos, faça o merge de `dev` na `main` pelo GitHub.

**Importante:** todas as sessões precisam trabalhar na **mesma branch**, senão cada sessão começa sem o progresso das outras. Se o ambiente não deixar a sessão dar push na `dev`, peça que ela abra um pull request da branch dela para a `dev` e faça o merge no GitHub antes de iniciar a próxima sessão.

### Limitações desta opção

- Cada VM nova reconstrói a imagem Docker (10–20 minutos) quando a tarefa precisa dela. Até a T30, quase todo o trabalho roda com `pytest` e clientes falsos, sem a imagem; para banco e Redis basta `docker compose up -d db redis`, que usa as imagens já baixadas pelo script.
- Processos em segundo plano (Compose, simulador) não sobrevivem à VM. Suba de novo em cada sessão.
- Não há acesso às portas da VM, então você não abre o dashboard no seu navegador. O agente consegue testar a API e o Streamlit por `curl` dentro da VM.

---

## Opção 2: VPS própria via SSH

O app do Claude conecta na VPS por SSH, instala o Claude Code lá automaticamente e roda a sessão na VPS. Seu desktop só mostra a conversa.

### Especificação recomendada

- Ubuntu 24.04 LTS, x86_64, IPv4 público.
- 4 vCPU, **16 GB de RAM**, 80 GB de SSD. Sem GPU.
- Provedores com bom custo para esse perfil: Hetzner, DigitalOcean, Contabo, entre outros. Uma VM equivalente na Azure custa bem mais e consumiria rapidamente os créditos de estudante, que é melhor reservar para Speech e Language.

### 1. Criar a chave SSH no Windows (PowerShell)

```powershell
ssh-keygen -t ed25519 -C "medwatch-vps"
```

O app precisa entrar na VPS sem digitar senha. Se você colocar uma senha na chave, carregue-a no agente SSH do Windows (o primeiro comando pede PowerShell como administrador):

```powershell
Get-Service ssh-agent | Set-Service -StartupType Automatic
```
```powershell
Start-Service ssh-agent
```
```powershell
ssh-add $HOME\.ssh\id_ed25519
```

### 2. Criar a VPS

No painel do provedor, crie a máquina com Ubuntu 24.04 e cole o conteúdo de `$HOME\.ssh\id_ed25519.pub` como chave SSH do root.

### 3. Preparar a VPS com o script do repositório

Entre como root e rode o [`scripts/setup_vps.sh`](../scripts/setup_vps.sh). Ele cria o usuário `medwatch` com a mesma chave do root, instala Docker, Compose, Git, GitHub CLI, ffmpeg, tmux e uv com Python 3.11, cria 4 GB de swap, ativa o firewall (só SSH aberto) e desliga o login por senha e o login direto como root.

```bash
ssh root@IP_DA_VPS
```
```bash
curl -fsSL https://raw.githubusercontent.com/mvgv/techchallenge-fasae4/main/scripts/setup_vps.sh -o setup_vps.sh
```
```bash
bash setup_vps.sh medwatch
```

**Antes de fechar a sessão como root**, abra outro terminal e confirme que o novo usuário entra e usa o Docker:

```bash
ssh medwatch@IP_DA_VPS
```
```bash
docker run --rm hello-world
```

Ainda como root, defina uma senha para o `sudo` do usuário:

```bash
passwd medwatch
```

### 4. Atalhos SSH no Windows

Acrescente ao arquivo `$HOME\.ssh\config`:

```text
Host medwatch-vps
  HostName IP_DA_VPS
  User medwatch
  IdentityFile ~/.ssh/id_ed25519

Host medwatch-tunnel
  HostName IP_DA_VPS
  User medwatch
  IdentityFile ~/.ssh/id_ed25519
  LocalForward 8501 localhost:8501
  LocalForward 8000 localhost:8000
```

`medwatch-vps` é usado pelo app; `medwatch-tunnel` serve só para abrir o dashboard (passo 7). Ficam separados para o túnel não disputar portas com as conexões do app.

### 5. Preparar o repositório na VPS

```bash
ssh medwatch-vps
```
```bash
git config --global user.name "mvgv"
```
```bash
git config --global user.email "mvgv1989@gmail.com"
```
```bash
gh auth login
```
```bash
mkdir -p ~/workspace && cd ~/workspace && git clone https://github.com/mvgv/techchallenge-fasae4.git
```
```bash
cd techchallenge-fasae4 && cp .env.example .env
```

O `gh auth login` abre um código para você confirmar no navegador do seu computador e configura o Git para fazer push. Depois, preencha as chaves Azure no `.env` da VPS (ou mantenha `USE_FAKE_AZURE=true`).

### 6. Conectar o app do Claude

1. No app, abra o seletor de ambiente embaixo da caixa de mensagem e escolha **New environment**.
2. Na aba **SSH**, em **Host**, escolha **Add SSH connection…**: nome `medwatch-vps`, host `medwatch-vps`. Deixe porta e chave em branco (o app usa o `~/.ssh/config`).
3. Escolha a pasta `~/workspace/techchallenge-fasae4` e clique em **Create environment**.
4. Escolha o modelo **Claude Sonnet 5.5** e envie: "Leia o CLAUDE.md e continue o trabalho a partir do PROGRESSO.md."

Na primeira conexão, o app instala o Claude Code em `~/.claude/remote/` na VPS (cerca de 1 GB).

### 7. Ver o dashboard e a API

Com o ambiente rodando na VPS, abra o túnel num terminal do Windows e deixe-o aberto:

```bash
ssh -N medwatch-tunnel
```

Depois acesse `http://localhost:8501` (dashboard) e `http://localhost:8000/docs` (API) no seu navegador. O banco e o Redis nunca ficam expostos: o Compose publica as portas só em `127.0.0.1` (seção 9.3 do plano).

### Limitações e cuidados desta opção

- Nas sessões por SSH, o painel de navegador do app não abre o projeto; use o túnel.
- Uma tarefa longa pode parar se o login da conta Claude expirar enquanto o app está desconectado.
- Se o app foi instalado pela Microsoft Store, ele usa um cliente SSH próprio, que funciona com chave simples como a deste guia.
- A VPS é cobrada enquanto existir. Se ficar dias sem uso, desligue ou faça um snapshot e exclua.
- Espaço em disco: rode `docker system prune` de vez em quando.
