import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


class ApiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/hello":
            self.send_json(hello_payload())
            return

        if self.path in ("/", "/health", "/uptime"):
            self.send_json(status_payload())
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
    print("Endpoints: /hello, /health e /uptime")
    server.serve_forever()


if __name__ == "__main__":
    main()
