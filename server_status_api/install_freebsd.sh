#!/bin/sh

set -eu

APP_NAME="server_status_api"
APP_DIR="/usr/local/${APP_NAME}"
SERVICE_FILE="/usr/local/etc/rc.d/${APP_NAME}"

if [ "$(id -u)" -ne 0 ]; then
    echo "Execute como root."
    echo "Exemplo: su - root"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python3 nao encontrado. Instalando..."
    pkg install -y python
fi

mkdir -p "${APP_DIR}"
cp app.py config.xml README.md "${APP_DIR}/"
mkdir -p "${APP_DIR}/freebsd"
cp freebsd/server_status_api "${APP_DIR}/freebsd/"

cp freebsd/server_status_api "${SERVICE_FILE}"
chmod +x "${SERVICE_FILE}"

sysrc server_status_api_enable=YES

echo "Instalacao concluida."
echo "Para iniciar: service server_status_api start"
echo "Para testar: fetch -qo- http://127.0.0.1:8000/hello"
