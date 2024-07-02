
from datetime import datetime
from threading import Thread, Event
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import json
import socket
import logging
import mimetypes
import urllib.parse


logging.basicConfig(
    level=logging.INFO,
    format='   %(name)s - - %(asctime)s "%(levelname)s / %(message)s"',
    datefmt='[%d/%b/%Y %H:%M:%S]'
)

#функцією create_handler обгортаємо клас HttpHandler з методами
def create_handler(udp_ip: str, udp_port: int):

    class HttpHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            data = self.rfile.read(int(self.headers['Content-Length']))
            data_parsed = urllib.parse.unquote_plus(data.decode())
            data_list = [el.split('=') for el in data_parsed.split('&')]
            data_dict = {key: val for key, val in data_list}
            logging.debug("Message: %r", data_dict)
            run_socket_client(data_dict, udp_ip, udp_port)
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()

        def do_GET(self):
            pr_url = urllib.parse.urlparse(self.path)
            match pr_url.path:
                case '/':
                    self.send_html_file('static_resources/index.html')
                case '/message.html':
                    self.send_html_file('static_resources/message.html')
                case '/logo.png':
                    self.send_html_file('static_resources/logo.png')
                case '/style.css':
                    self.send_html_file('static_resources/style.css')
                case _:
                    self.send_html_file('static_resources/error.html', 404)

        def send_html_file(self, filename, status=200):
            self.send_response(status)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            with open(filename, 'rb') as fd:
                self.wfile.write(fd.read())

        def send_static(self):
            self.send_response(200)
            mt = mimetypes.guess_type(self.path)
            if mt:
                self.send_header("Content-type", mt[0])
            else:
                self.send_header("Content-type", "text/plain")
            self.end_headers()
            with open(f'.{self.path}', 'rb') as file:
                self.wfile.write(file.read())
    return HttpHandler

# сервер http
def run_http_server(stop_ev: object, ip: str, port: int, handler_class: callable, server_class=HTTPServer):
    server_address = (ip, port)
    http = server_class(server_address, handler_class)
    while not stop_ev.is_set():
        http.serve_forever()

    http.server_close()

#сокет клієнта
def run_socket_client(message: dict, ip: str, port: int):

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = ip, port
    data = json.dumps(message).encode('utf-8')
    sock.sendto(data, server)
    logging.debug(f'Send data: {data.decode()} to server: {server}')

    sock.close()

#сокет сервера
def run_socket_server(stop_ev: object, data_file: str, ip: str, port: int):

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = ip, port
    print(f'Connection established with Server - (ip address: {ip}, port: {port})')
    sock.bind(server)
    while not stop_ev.is_set():
        sock.settimeout(1)
        try:
            data, address = sock.recvfrom(1024)
            logging.debug("Received data: %r from: %s", data, address)
            storage_handler(data, data_file)
        except socket.timeout:
            continue
        except socket.error:
            break
        print(f'Socket connection closed {address}')
    sock.close()

#функція обробки отриманих даних від клієнта
def storage_handler(data: dict, file_path: str):
    message = json.loads(data.decode('utf-8'))
    formatted_msg = {str(datetime.now()): message}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            file_dict = json.loads(file.read())
    else:
        file_dict = {}
    file_dict.update(formatted_msg)
    file_data = json.dumps(file_dict, indent=2, ensure_ascii=False)
    with open(file_path, 'w+', encoding='utf-8') as file:
        file.write(file_data)

if __name__ == '__main__':
    HTTP_IP = '127.0.0.1'
    HTTP_PORT = 5000
    UDP_IP = '127.0.0.1'
    UDP_PORT = 3000
    STORAGE = 'storage/data.json'

    stop_event = Event()

    # параметри HTTP сервера
    http_thread = Thread(target=run_http_server, args=(stop_event, HTTP_IP, HTTP_PORT, create_handler(UDP_IP, UDP_PORT)))

    # параметри Socket сервера
    socket_thread = Thread(target=run_socket_server, args=(stop_event, STORAGE, UDP_IP, UDP_PORT))

    http_thread.start()
    socket_thread.start()

    try:
        http_thread.join()
    except KeyboardInterrupt:
        stop_event.set()
        socket_thread.join()
        logging.info("Server finished work")