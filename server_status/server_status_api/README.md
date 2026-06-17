# Server Status API

API simples para informar se o servidor da API esta rodando e ha quanto tempo.

## Como rodar

```sh
python app.py
```

Por padrao, a API sobe em:

```text
http://0.0.0.0:8000
```

A porta e o host ficam no arquivo `config.xml`:

```xml
<?xml version='1.0' encoding='utf-8'?>
<config>
    <server>
        <host>0.0.0.0</host>
        <port>8000</port>
    </server>
</config>
```

Use `0.0.0.0` para aceitar conexoes de outras maquinas. Use `127.0.0.1` se quiser aceitar apenas conexoes locais.

Em outra maquina da rede, acesse usando o IP do servidor:

```text
http://IP_DO_SERVIDOR:8000/health
```

## Endpoints

```text
GET /
GET /hello
GET /health
GET /uptime
GET /server/status
```

Resposta do `/hello`:

```json
{
  "message": "hello",
  "version": "1.0-BETA"
}
```

Resposta de exemplo:

```json
{
  "status": "running",
  "started_at": "2026-06-13T16:20:00.000000+00:00",
  "checked_at": "2026-06-13T16:25:30.000000+00:00",
  "uptime_seconds": 330,
  "uptime": "5m 30s"
}
```

Resposta resumida do `/server/status`:

```json
{
  "status": "running",
  "hostname": "web",
  "boot": {
    "uptime": "3d 4h 20m"
  },
  "cpu": {
    "model": "Intel(R) Xeon(R)",
    "cores": 2
  },
  "memory": {
    "used_percent": 42.5,
    "used_gb": 1.2,
    "total_gb": 4.0
  },
  "disk": {
    "items": []
  },
  "dmesg": {
    "lines": []
  }
}
```

## FreeBSD

Na VM FreeBSD, copie a pasta `server_status_api`.

Se precisar instalar Python:

```sh
pkg install python
```

Instalacao automatica:

```sh
cd server_status_api
sh install_freebsd.sh
service server_status_api start
```

Para testar manualmente:

```sh
cd server_status_api
python3 app.py
```

Se quiser deixar rodando como servico do FreeBSD, copie o projeto para `/usr/local/server_status_api`:

```sh
mkdir -p /usr/local/server_status_api
cp -R server_status_api/* /usr/local/server_status_api/
```

Instale o script de servico:

```sh
cp /usr/local/server_status_api/freebsd/server_status_api /usr/local/etc/rc.d/server_status_api
chmod +x /usr/local/etc/rc.d/server_status_api
```

Ative e inicie:

```sh
sysrc server_status_api_enable=YES
service server_status_api start
```

Verifique:

```sh
service server_status_api status
tail -f /var/log/server_status_api.log
```

Se quiser deixar acessivel fora da VM, confirme se a porta configurada no `config.xml` esta liberada no firewall.

Exemplo de acesso de outra maquina:

```text
http://IP_DA_VM:8000/hello
http://IP_DA_VM:8000/health
```
