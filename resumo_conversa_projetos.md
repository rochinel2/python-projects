# Resumo da Conversa e Projetos

Este arquivo resume os projetos criados e ajustados durante a conversa.

## Projeto 1: Script Clinux

Arquivo principal:

```text
baixar_versao_clinux.py
```

Objetivo: baixar uma versão do Clinux de um servidor HTTP/FTP, extrair o ZIP, localizar `clinux.exe`, renomear para `clinux_<versao>.exe` e lidar com arquivos duplicados.

Funcionalidades implementadas:

- Le e salva o ultimo diretorio em `ultimo_diretorio.txt`.
- Le credenciais em `config_clinux.xml`.
- Se o XML nao existir, pede usuario/senha e cria o arquivo.
- Baixa `clinux_<versao>.zip`.
- Extrai o ZIP.
- Renomeia `clinux.exe` para `clinux_<versao>.exe`.
- Se o arquivo final ja existir:
  - `s`: sobrescreve;
  - `n`: cancela;
  - `r`: renomeia o arquivo antigo para `_1`, `_2`, etc., e coloca o novo no nome principal.
- Pergunta se deseja baixar outra versao apos sucesso.
- Pergunta se deseja tentar novamente apos erro.
- Mantem a janela aberta com `Pressione Enter para fechar...`.
- Foi compilado com PyInstaller para:

```text
dist/baixar_versao_clinux.exe
```

Arquivos sensiveis e gerados foram colocados no `.gitignore`.

## Projeto 2: API Server Status

Pasta:

```text
server_status_api/
```

Arquivos principais:

```text
server_status_api/app.py
server_status_api/config.xml
server_status_api/freebsd/server_status_api
server_status_api/install_freebsd.sh
```

Objetivo: API simples para rodar em FreeBSD e informar se o servidor esta executando e ha quanto tempo.

A API usa apenas biblioteca padrao do Python:

```python
http.server
```

Sem FastAPI e sem dependencias externas.

Endpoints:

```text
GET /
GET /hello
GET /health
GET /uptime
```

`/hello` retorna:

```json
{
  "message": "hello",
  "version": "1.0-BETA"
}
```

`/health` e `/uptime` retornam:

```json
{
  "status": "running",
  "started_at": "...",
  "checked_at": "...",
  "uptime_seconds": 123,
  "uptime": "2m 3s"
}
```

Configuracao da API:

```text
server_status_api/config.xml
```

Exemplo:

```xml
<?xml version='1.0' encoding='utf-8'?>
<config>
    <server>
        <host>0.0.0.0</host>
        <port>8000</port>
    </server>
</config>
```

A API roda por padrao em:

```text
0.0.0.0:8000
```

No FreeBSD, houve ajustes no servico `rc.d`:

- O servico roda com `daemon`.
- Foi removido `-u www` porque causava erro:

```text
daemon: failed to set user environment
```

- Foi ajustado o PID file para ficar em:

```text
/var/run/server_status_api/server_status_api.pid
```

- Foi removido temporariamente o restart automatico `-r -R 5`.
- O servico usa log em:

```text
/var/log/server_status_api.log
```

## Projeto 3: Frontend Server Status

Pasta:

```text
server_status_frontend/
```

Arquivos:

```text
server_status_frontend/index.html
server_status_frontend/styles.css
server_status_frontend/app.js
server_status_frontend/README.md
```

Objetivo: frontend estatico servido pelo Nginx para mostrar os dados da API.

O frontend consulta:

```text
/api/hello
/api/health
```

Mostra:

- status online/offline;
- versao da API;
- uptime;
- horario de inicio;
- ultima leitura;
- JSON bruto;
- botao atualizar;
- atualizacao automatica a cada 10 segundos.

Constante no JS:

```js
const API_BASE = "/api";
```

## Deploy via Git

Foi criado:

```text
deploy/freebsd_update.sh
deploy/nginx_server_status.conf.example
deploy/README.md
.gitattributes
.gitignore
```

Repositorio remoto:

```text
https://github.com/rochinel2/python-projects.git
```

Fluxo no Windows:

```bash
git add .
git commit -m "mensagem"
git push origin main
```

Fluxo na VM FreeBSD:

```sh
cd /usr/local/src/python_projects
git pull
sh deploy/freebsd_update.sh
```

Primeiro clone na VM:

```sh
pkg install git python nginx
git clone https://github.com/rochinel2/python-projects.git /usr/local/src/python_projects
cd /usr/local/src/python_projects
sh deploy/freebsd_update.sh
```

O script copia:

```text
server_status_api -> /usr/local/server_status_api
server_status_frontend -> /usr/local/www/server_status_frontend
rc.d service -> /usr/local/etc/rc.d/server_status_api
```

Ele preserva o `config.xml` existente da VM.

## Nginx

A API esta funcionando via Nginx em `/api/`.

Configuracao recomendada dentro de um bloco `server { ... }`:

```nginx
server {
    listen 9090;
    server_name localhost;

    root /usr/local/www/server_status_frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ^~ /api/ {
        rewrite ^/api/(.*)$ /$1 break;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $http_host;
    }

    error_page 500 502 503 504 /50x.html;

    location = /50x.html {
        root /usr/local/www/server_status_frontend;
    }
}
```

Problema encontrado:

```text
"location" directive is not allowed here
```

Causa: havia blocos `location` fora de `server { ... }`.

Tambem foi apontado que isto esta errado:

```nginx
location ^~/pacs {
```

Correto:

```nginx
location ^~ /pacs {
```

Todo `location` precisa estar dentro de um bloco `server`.

## Estado Atual

- API voltou a funcionar normalmente no FreeBSD.
- O frontend foi criado e esta sendo ajustado no Nginx.
- O problema atual do Nginx foi causado por blocos `location` duplicados ou fora do `server`.
- Proximo passo provavel: corrigir o `nginx.conf`, validar com:

```sh
nginx -t
service nginx restart
```

E acessar:

```text
http://IP_DA_VM:9090/
http://IP_DA_VM:9090/api/hello
http://IP_DA_VM:9090/api/health
```
