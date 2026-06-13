# Deploy via Git no FreeBSD

Fluxo recomendado:

```sh
pkg install git python nginx
git clone https://github.com/rochinel2/python-projects.git /usr/local/src/python_projects
cd /usr/local/src/python_projects
sh deploy/freebsd_update.sh
```

Depois de novas alteracoes no Windows:

```sh
git add .
git commit -m "Atualiza server status"
git push
```

Na VM FreeBSD:

```sh
cd /usr/local/src/python_projects
git pull
sh deploy/freebsd_update.sh
```

O script instala/atualiza:

```text
/usr/local/server_status_api
/usr/local/www/server_status_frontend
/usr/local/etc/rc.d/server_status_api
```

O arquivo da API `/usr/local/server_status_api/config.xml` e preservado se ja existir, para nao sobrescrever porta/host configurados na VM.

Um exemplo de configuracao Nginx esta em:

```text
deploy/nginx_server_status.conf.example
```
