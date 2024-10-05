from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from pathlib import Path
import mimetypes
import urllib.parse
import socket
import logging
from pymongo import MongoClient

uri = "mongodb://mongodb_service:27017"
BASE_DIR = Path(__file__).parent
HTTPServer_Port = 3000
UDP_IP = '127.0.0.1'
UDP_PORT = 5000


class HttpGetHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        data = self.rfile.read(int(self.headers['Content-Length']))
        send_data_to_socket(data)
        self.send_response(302)
        self.send_header('Location', '/')
        self.end_headers()

    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path).path
        match pr_url:
            case '/':
                self.send_html_file('index.html')
            case '/message.html':
                self.send_html_file('message.html')
            case _:
                file = BASE_DIR.joinpath(pr_url[1:])
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html_file('error.html', 404)

    def send_html_file(self, filename:str, status=200):
        try:
            self.send_response(status)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            with open(filename, 'rb') as fd:
                self.wfile.write(fd.read())
        except Exception as e:
            logging.error(f"Unexpected error on send_html_file: {e}")

    def send_static(self, filename:str, status=200):
        try:
            self.send_response(status)
            mt = mimetypes.guess_type(str(filename))
            if mt:
                self.send_header("Content-type", mt[0])
            else:
                self.send_header("Content-type", 'text/plain')
            self.end_headers()
            with open(filename, 'rb') as file:
                self.wfile.write(file.read())
        except Exception as e:
            logging.error(f"Unexpected error on send_static: {e}")


def run_http_server(server_class=HTTPServer, handler_class=HttpGetHandler):
    try:
        server_address = ('0.0.0.0', HTTPServer_Port)
        http = server_class(server_address, handler_class)
        logging.info(f'Starting HTTP server on port {HTTPServer_Port}')
        http.serve_forever()
    except KeyboardInterrupt:
        logging.info('Shutdown server')
    except Exception as e:
        logging.error(f"Unexpected error on http server run: {e}")
    finally:
        http.server_close()


def send_data_to_socket(data:bytes):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server = UDP_IP, UDP_PORT
        logging.info(f'Connection established {server}')
        sock.sendto(data, server)
        response, address = sock.recvfrom(1024)
        logging.info(f'Saved data: {response.decode()} from address: {address}')
        sock.close()
        logging.info(f'Data transfer completed')
    except Exception as e:
        logging.error(f"Unexpected error on socket client send: {e}")


def save_data(data:bytes) -> dict:
    client = MongoClient(uri)
    try:
        db = client.socket_db
        data_parse = urllib.parse.unquote_plus(data.decode())
        data_dict = {key: value for key, value in [el.split('=') for el in data_parse.split('&')]}
        data_dict['date'] = str(datetime.now())
        logging.info(f'Data to be written to db: {data_dict}')
        db.messages.insert_one(data_dict)
        return data_dict
    except Exception as e:
        logging.error(f"Unexpected error while data saving: {e}")
    finally:
        if client:
            logging.info("Database connection closed")
            client.close()


def run_socket_server(ip: str, port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = ip, port
    sock.bind(server)
    logging.info(f'Socket server started at {server}')
    try:
        while True:
            data, address = sock.recvfrom(1024)
            logging.info(f'Received data: {data.decode()} from: {address}')
            save_data(data)
            sock.sendto(data, address)
            logging.info(f'Send data: {data.decode()} to: {address}')

    except KeyboardInterrupt:
        logging.info('Shutting down socket server')
    finally:
        sock.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(threadName)s %(message)s')

    http_server_process = Process(target=run_http_server)
    http_server_process.start()

    socket_server_process = Process(target=run_socket_server, args=(UDP_IP, UDP_PORT))
    socket_server_process.start()
