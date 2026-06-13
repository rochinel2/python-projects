import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import xml.etree.ElementTree as ET


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.xml")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
API_VERSION = "1.0-BETA"
STARTED_AT = datetime.now(timezone.utc)


def create_default_config():
    root = ET.Element("config")
    server = ET.SubElement(root, "server")
    ET.SubElement(server, "host").text = DEFAULT_HOST
    ET.SubElement(server, "port").text = str(DEFAULT_PORT)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(CONFIG_FILE, encoding="utf-8", xml_declaration=True)


def load_config():
    if not os.path.exists(CONFIG_FILE):
        create_default_config()
        return DEFAULT_HOST, DEFAULT_PORT

    try:
        root = ET.parse(CONFIG_FILE).getroot()
        host = root.findtext("server/host", default=DEFAULT_HOST).strip() or DEFAULT_HOST
        port_text = root.findtext("server/port", default=str(DEFAULT_PORT)).strip()
        port = int(port_text)
    except (ET.ParseError, ValueError):
        print(f"Arquivo {CONFIG_FILE} invalido. Usando configuracao padrao.")
        return DEFAULT_HOST, DEFAULT_PORT

    return host, port


def format_duration(total_seconds):
    total_seconds = int(total_seconds)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or parts:
        parts.append(f"{hours}h")
    if minutes or parts:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def status_payload():
    now = datetime.now(timezone.utc)
    uptime_seconds = (now - STARTED_AT).total_seconds()

    return {
        "status": "running",
        "started_at": STARTED_AT.isoformat(),
        "checked_at": now.isoformat(),
        "uptime_seconds": int(uptime_seconds),
        "uptime": format_duration(uptime_seconds),
    }


def hello_payload():
    return {
        "message": "hello",
        "version": API_VERSION,
    }


def run_command(command, timeout=5):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return None, str(error)

    output = result.stdout.strip()
    error = result.stderr.strip()

    if result.returncode != 0:
        return None, error or f"Comando retornou codigo {result.returncode}"

    return output, None


def sysctl_value(name):
    output, _ = run_command(["sysctl", "-n", name])
    return output


def bytes_to_gb(value):
    if value is None:
        return None

    return round(value / 1024 / 1024 / 1024, 2)


def parse_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def server_boot_time():
    output, _ = run_command(["sysctl", "-n", "kern.boottime"])
    if not output:
        return None

    match = re.search(r"sec = (\d+)", output)
    if not match:
        return None

    return datetime.fromtimestamp(int(match.group(1)), timezone.utc)


def memory_payload():
    page_size = parse_int(sysctl_value("hw.pagesize"))
    total_pages = parse_int(sysctl_value("vm.stats.vm.v_page_count"))
    free_pages = parse_int(sysctl_value("vm.stats.vm.v_free_count")) or 0
    inactive_pages = parse_int(sysctl_value("vm.stats.vm.v_inactive_count")) or 0
    cache_pages = parse_int(sysctl_value("vm.stats.vm.v_cache_count")) or 0
    total_bytes = parse_int(sysctl_value("hw.physmem"))

    if page_size and total_pages:
        total_bytes = total_pages * page_size

    available_bytes = None
    used_bytes = None
    used_percent = None

    if page_size and total_bytes:
        available_pages = free_pages + inactive_pages + cache_pages
        available_bytes = available_pages * page_size
        used_bytes = max(total_bytes - available_bytes, 0)
        used_percent = round((used_bytes / total_bytes) * 100, 1)

    return {
        "total_bytes": total_bytes,
        "used_bytes": used_bytes,
        "available_bytes": available_bytes,
        "total_gb": bytes_to_gb(total_bytes),
        "used_gb": bytes_to_gb(used_bytes),
        "available_gb": bytes_to_gb(available_bytes),
        "used_percent": used_percent,
        "note": "Uso calculado como total menos paginas livres/inativas/cache.",
    }


def disk_payload():
    output, error = run_command(["df", "-k"])
    if error or not output:
        return {"items": [], "error": error}

    items = []
    lines = output.splitlines()[1:]
    for line in lines:
        parts = line.split()
        if len(parts) < 6:
            continue

        filesystem, blocks, used, available, capacity, mountpoint = parts[:6]
        items.append({
            "filesystem": filesystem,
            "mountpoint": mountpoint,
            "size_gb": round(int(blocks) / 1024 / 1024, 2),
            "used_gb": round(int(used) / 1024 / 1024, 2),
            "available_gb": round(int(available) / 1024 / 1024, 2),
            "used_percent": capacity,
        })

    return {"items": items}


def dmesg_payload(limit=25):
    output, error = run_command(["dmesg"], timeout=8)
    if error or not output:
        return {"lines": [], "error": error}

    return {"lines": output.splitlines()[-limit:]}


def server_status_payload():
    now = datetime.now(timezone.utc)
    boot_time = server_boot_time()
    uptime_seconds = None

    if boot_time:
        uptime_seconds = int((now - boot_time).total_seconds())

    load_average = None
    try:
        load_average = os.getloadavg()
    except (AttributeError, OSError):
        pass

    return {
        "status": "running",
        "checked_at": now.isoformat(),
        "hostname": platform.node(),
        "system": {
            "name": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        },
        "boot": {
            "started_at": boot_time.isoformat() if boot_time else None,
            "uptime_seconds": uptime_seconds,
            "uptime": format_duration(uptime_seconds) if uptime_seconds is not None else None,
        },
        "cpu": {
            "model": sysctl_value("hw.model") or platform.processor() or None,
            "cores": parse_int(sysctl_value("hw.ncpu")) or os.cpu_count(),
            "load_average": {
                "1m": load_average[0],
                "5m": load_average[1],
                "15m": load_average[2],
            } if load_average else None,
        },
        "memory": memory_payload(),
        "disk": disk_payload(),
        "dmesg": dmesg_payload(),
    }


class ApiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/hello":
            self.send_json(hello_payload())
            return

        if path in ("/", "/health", "/uptime"):
            self.send_json(status_payload())
            return

        if path in ("/server", "/server/status"):
            self.send_json(server_status_payload())
            return

        self.send_json({"error": "not_found"}, status=404)

    def send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")


def main():
    host, port = load_config()
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"API rodando em http://{host}:{port}")
    print("Endpoints: /hello, /health, /uptime e /server/status")
    server.serve_forever()


if __name__ == "__main__":
    main()
