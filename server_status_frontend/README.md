# Server Status Frontend

Frontend estatico para consultar a API em `/api/`.

## Arquivos

```text
index.html
styles.css
app.js
```

## Nginx

Copie esta pasta para, por exemplo:

```text
/usr/local/www/server_status_frontend
```

Exemplo de configuracao:

```nginx
server {
    listen 80;
    server_name seu-dominio.com;

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
}
```

Depois:

```sh
nginx -t
service nginx reload
```
