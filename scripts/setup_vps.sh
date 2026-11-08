#!/usr/bin/env bash
# Prepara uma VPS Ubuntu 24.04 (x86_64) para o MedWatch e para o Claude Code via SSH.
#
# Uso, como root, uma única vez:
#   bash setup_vps.sh <usuario> ["<chave-publica-ssh>"]
#
# Sem a chave, o script copia as chaves de /root/.ssh/authorized_keys (as que o
# provedor da VPS instalou) para o novo usuário.
#
# O que faz: cria o usuário com sudo e acesso ao Docker; instala Docker Engine,
# Compose, Git, GitHub CLI, ffmpeg, tmux e uv com Python 3.11; cria swap de 4 GB;
# ativa atualizações de segurança automáticas, firewall (só SSH) e fail2ban;
# desliga login por senha e login direto como root.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Rode como root." >&2
  exit 1
fi

USER_NAME="${1:?Informe o nome do usuário. Ex.: bash setup_vps.sh medwatch}"
PUBKEY="${2:-}"

if [[ -z "$PUBKEY" ]]; then
  if [[ -s /root/.ssh/authorized_keys ]]; then
    KEYS_SOURCE=/root/.ssh/authorized_keys
  else
    echo "Nenhuma chave informada e /root/.ssh/authorized_keys está vazio." >&2
    echo "Passe a chave pública como segundo argumento." >&2
    exit 1
  fi
else
  if ! [[ "$PUBKEY" =~ ^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521))\  ]]; then
    echo "A chave informada não parece uma chave pública SSH (ssh-ed25519 ..., ssh-rsa ...)." >&2
    exit 1
  fi
fi

export DEBIAN_FRONTEND=noninteractive
ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"

echo "==> Pacotes do sistema"
apt-get update
apt-get -y upgrade
apt-get install -y ca-certificates curl gnupg git tmux ufw fail2ban unattended-upgrades ffmpeg
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Usuário $USER_NAME"
if ! id "$USER_NAME" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$USER_NAME"
fi
usermod -aG sudo "$USER_NAME"
install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "/home/$USER_NAME/.ssh"
AUTH="/home/$USER_NAME/.ssh/authorized_keys"
touch "$AUTH"
if [[ -n "$PUBKEY" ]]; then
  grep -qxF "$PUBKEY" "$AUTH" || echo "$PUBKEY" >> "$AUTH"
else
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    grep -qxF "$line" "$AUTH" || echo "$line" >> "$AUTH"
  done < "$KEYS_SOURCE"
fi
chown "$USER_NAME:$USER_NAME" "$AUTH"
chmod 600 "$AUTH"

echo "==> Docker Engine e Compose (repositório oficial)"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $CODENAME stable" \
  > /etc/apt/sources.list.d/docker.list

echo "==> GitHub CLI (repositório oficial)"
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  -o /etc/apt/keyrings/githubcli-archive-keyring.gpg
chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$ARCH signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  > /etc/apt/sources.list.d/github-cli.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin gh
usermod -aG docker "$USER_NAME"
systemctl enable --now docker

echo "==> uv e Python 3.11 para $USER_NAME"
sudo -u "$USER_NAME" -H bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u "$USER_NAME" -H bash -c '"$HOME/.local/bin/uv" python install 3.11'

echo "==> Swap de 4 GB"
if ! swapon --show | grep -q '/swapfile'; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> Firewall: só SSH"
ufw allow OpenSSH
ufw --force enable
systemctl enable --now fail2ban

echo "==> SSH: sem senha e sem login direto como root"
cat > /etc/ssh/sshd_config.d/99-medwatch.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
grep -Eq '^\s*Subsystem\s+sftp' /etc/ssh/sshd_config || echo 'Subsystem sftp /usr/lib/openssh/sftp-server' >> /etc/ssh/sshd_config
sshd -t
systemctl reload ssh

cat <<EOF

Pronto.

ANTES de fechar esta sessão como root, teste em outro terminal:
  ssh $USER_NAME@<IP_DA_VPS>
  docker run --rm hello-world

Depois, ainda como root, defina a senha do sudo:
  passwd $USER_NAME

A partir de agora o login direto como root está desligado.
Próximos passos: docs/AMBIENTE_REMOTO.md, passo 4.
EOF
