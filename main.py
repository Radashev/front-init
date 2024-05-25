import mimetypes
import urllib.parse
import json
import logging
import socket
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from datetime import datetime

BASE_DIR = Path(__file__).parent
BUFFER_SIZE = 1024
HTTP_PORT = 3000
HTTP_HOST = '0.0.0.0'
SOCKET_HOST = '127.0.0.1'
SOCKET_PORT = 5000

logging.basicConfig(level=logging.DEBUG, format='%(threadName)s %(message)s')


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        route = urllib.parse.urlparse(self.path).path
        match route:
            case '/':
                self.send_html('index.html')
            case '/message':
                self.send_html('message.html')
            case _:
                file = BASE_DIR / route[1:]
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html('error.html', 404)

    def do_POST(self):
        if self.path == '/message':
            size = int(self.headers.get('Content-Length'))
            data = self.rfile.read(size)
            parsed_data = urllib.parse.parse_qs(data.decode())
            formatted_data = {key: value[0] for key, value in parsed_data.items()}

            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.sendto(json.dumps(formatted_data).encode(), (SOCKET_HOST, SOCKET_PORT))
            client_socket.close()

            self.send_response(302)
            self.send_header('Location', '/message')
            self.end_headers()
        else:
            self.send_html('error.html', 404)

    def send_html(self, filename, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        try:
            with open(BASE_DIR / 'templates' / filename, 'rb') as file:
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_error(404, 'Файл не знайдено: {}'.format(filename))

    def send_static(self, filename, status_code=200):
        self.send_response(status_code)
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            self.send_header('Content-Type', mime_type)
        else:
            self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        try:
            with open(filename, 'rb') as file:
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_error(404, 'Файл не знайдено: {}'.format(filename))


def save_data_from_form(data):
    timestamp = datetime.now().isoformat()

    storage_dir = BASE_DIR / 'storage'
    storage_dir.mkdir(parents=True, exist_ok=True)

    data_file = storage_dir / 'data.json'
    if not data_file.exists():
        data_file.write_text('{}', encoding='utf-8')

    try:
        with open(data_file, 'r+', encoding='utf-8') as file:
            try:
                content = json.load(file)
            except json.JSONDecodeError:
                content = {}
            content[timestamp] = data
            file.seek(0)
            json.dump(content, file, ensure_ascii=False, indent=4)
            file.truncate()
    except Exception as e:
        logging.error(f"Не вдалося зберегти дані: {e}")


def run_socket_server(host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((host, port))
    logging.info("Запуск серверу сокетів")
    try:
        while True:
            msg, address = server_socket.recvfrom(BUFFER_SIZE)
            logging.info(f"Сокет отримав {address}: {msg}")
            data = json.loads(msg.decode())
            save_data_from_form(data)
    except KeyboardInterrupt:
        pass
    finally:
        server_socket.close()


def run_http_server(host, port):
    address = (host, port)
    http_server = HTTPServer(address, SimpleHTTPRequestHandler)
    logging.info("Запуск HTTP серверу")
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http_server.server_close()


if __name__ == '__main__':
    http_thread = Thread(target=run_http_server, args=(HTTP_HOST, HTTP_PORT))
    http_thread.start()

    socket_thread = Thread(target=run_socket_server, args=(SOCKET_HOST, SOCKET_PORT))
    socket_thread.start()

    http_thread.join()
    socket_thread.join()
