#!/bin/sh

set -eu

APP_NAME="server_status_api"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_SRC="${REPO_DIR}/server_status_api"
FRONTEND_SRC="${REPO_DIR}/server_status_frontend"

API_DIR="/usr/local/${APP_NAME}"
FRONTEND_DIR="/usr/local/www/server_status_frontend"
SERVICE_FILE="/usr/local/etc/rc.d/${APP_NAME}"
NGINX_CONF_EXAMPLE="${REPO_DIR}/deploy/nginx_server_status.conf.example"

if [ "$(id -u)" -ne 0 ]; then
    echo "Execute como root."
    echo "Exemplo: su - root"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python3 nao encontrado. Instalando..."
    pkg install -y python
fi

if [ ! -d "${API_SRC}" ]; then
    echo "Diretorio da API nao encontrado: ${API_SRC}"
    exit 1
fi

if [ ! -d "${FRONTEND_SRC}" ]; then
    echo "Diretorio do frontend nao encontrado: ${FRONTEND_SRC}"
    exit 1
fi

echo "Atualizando API em ${API_DIR}..."
mkdir -p "${API_DIR}"
cp "${API_SRC}/app.py" "${API_DIR}/app.py"
cp "${API_SRC}/README.md" "${API_DIR}/README.md"

if [ ! -f "${API_DIR}/config.xml" ]; then
    cp "${API_SRC}/config.xml" "${API_DIR}/config.xml"
    echo "config.xml criado com valores padrao."
else
    echo "config.xml existente preservado."
fi

mkdir -p "${API_DIR}/freebsd"
cp "${API_SRC}/freebsd/server_status_api" "${API_DIR}/freebsd/server_status_api"
cp "${API_SRC}/freebsd/server_status_api" "${SERVICE_FILE}"
chmod +x "${SERVICE_FILE}"

touch /var/log/${APP_NAME}.log
chown www:wheel /var/log/${APP_NAME}.log
chmod 640 /var/log/${APP_NAME}.log

mkdir -p /var/run/${APP_NAME}
chown www:wheel /var/run/${APP_NAME}
chmod 755 /var/run/${APP_NAME}

sysrc server_status_api_enable=YES >/dev/null

echo "Atualizando frontend em ${FRONTEND_DIR}..."
mkdir -p "${FRONTEND_DIR}"
cp "${FRONTEND_SRC}/index.html" "${FRONTEND_DIR}/index.html"
cp "${FRONTEND_SRC}/styles.css" "${FRONTEND_DIR}/styles.css"
cp "${FRONTEND_SRC}/app.js" "${FRONTEND_DIR}/app.js"
cp "${FRONTEND_SRC}/README.md" "${FRONTEND_DIR}/README.md"

echo "Reiniciando API..."
if service server_status_api status >/dev/null 2>&1; then
    service server_status_api restart
else
    service server_status_api start
fi

if command -v nginx >/dev/null 2>&1; then
    if nginx -t; then
        service nginx reload || service nginx restart
    else
        echo "nginx -t falhou. Confira a configuracao do Nginx."
        echo "Exemplo disponivel em: ${NGINX_CONF_EXAMPLE}"
    fi
else
    echo "Nginx nao encontrado. Instale/configure manualmente se desejar servir o frontend."
fi

echo "Deploy finalizado."
echo "API local: http://127.0.0.1:8000/hello"
echo "Frontend: ${FRONTEND_DIR}"
