#!/usr/bin/env bash
set -euo pipefail

NEW_USER="dorjoo"
NEW_USER_PASSWORD="Mongolian123!"     # ЗААВАЛ ажиллуулахын өмнө солих
SSH_PORT="22"
CORE_VPS_IP="103.143.40.57"           # core/web/admin байрлаж буй үндсэн VPS
XYP_PORT="8088"
TIMEZONE="Asia/Ulaanbaatar"

if [[ $EUID -ne 0 ]]; then
  echo "Root-оор ажиллуул: sudo ./xyp-vps-setup.sh" >&2
  exit 1
fi

echo "==> 1/10 Систем шинэчлэх"
apt update && apt upgrade -y
apt install -y ca-certificates curl gnupg ufw fail2ban unattended-upgrades \
  python3 python3-venv python3-pip build-essential libxml2-dev libxslt-dev python3-dev git

echo "==> 2/10 Timezone/NTP"
timedatectl set-timezone "$TIMEZONE"
timedatectl set-ntp true

echo "==> 3/10 Sudo хэрэглэгч үүсгэх"
if ! id -u "$NEW_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$NEW_USER"
  usermod -aG sudo "$NEW_USER"
  usermod --password "$(openssl passwd -6 "$NEW_USER_PASSWORD")" "$NEW_USER"
  mkdir -p "/home/$NEW_USER/.ssh"
  if [[ -f /root/.ssh/authorized_keys ]]; then
    cp /root/.ssh/authorized_keys "/home/$NEW_USER/.ssh/authorized_keys"
  else
    echo "!!! /root/.ssh/authorized_keys алга — та root-оор ЭХЛЭЭД key-ээ гараар байрлуулаагүй бол"
    echo "    доор SSH hardening хийгдэхээс өмнө өөрийн public key-г"
    echo "    /home/$NEW_USER/.ssh/authorized_keys дотор гараар нэмээрэй (Ctrl+C одоо)."
  fi
  chown -R "$NEW_USER:$NEW_USER" "/home/$NEW_USER/.ssh"
  chmod 700 "/home/$NEW_USER/.ssh"
  chmod 600 "/home/$NEW_USER/.ssh/authorized_keys" 2>/dev/null || true
fi

echo "==> 4/10 SSH hardening"
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<EOF
Port ${SSH_PORT}
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers ${NEW_USER}
MaxAuthTries 3
LoginGraceTime 20
X11Forwarding no
EOF
sshd -t
systemctl reload ssh || systemctl reload sshd

echo "==> 5/10 UFW — зөвхөн SSH + core VPS-с ${XYP_PORT} рүү"
ufw default deny incoming
ufw default allow outgoing
ufw allow "${SSH_PORT}/tcp"
ufw allow from "${CORE_VPS_IP}" to any port "${XYP_PORT}" proto tcp
ufw --force enable

echo "==> 6/10 sysctl network hardening"
cat > /etc/sysctl.d/99-hardening.conf <<'EOF'
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.conf.all.log_martians = 1
EOF
sysctl --system >/dev/null

echo "==> 7/10 fail2ban (SSH)"
cat > /etc/fail2ban/jail.d/sshd.local <<EOF
[sshd]
enabled = true
port = ${SSH_PORT}
maxretry = 5
bantime = 1h
findtime = 10m
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

echo "==> 8/10 unattended-upgrades"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
systemctl enable --now unattended-upgrades

echo "==> 9/10 /opt/xyp folder бэлдэх"
mkdir -p /opt/xyp
chown "$NEW_USER:$NEW_USER" /opt/xyp

echo "==> 10/10 дууслаа"
cat <<EOF

============================================================
Шинэ terminal-аар шалга (одоогийн session-оо бүү хаа):
  ssh -p ${SSH_PORT} ${NEW_USER}@<xyp-vps-ip>

Амжилттай орсны дараа:
  passwd ${NEW_USER}   # түр password солих

Дараа нь өмнөх алхмуудаар (git clone, venv, app.py, systemd) үргэлжлүүл.
============================================================
EOF