import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from huaqi_src.core.db_storage import LocalDBStorage
from huaqi_src.core.event import Event
from huaqi_src.core.config_manager import ConfigManager

class WeChatWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/webhook/wechat':
            config = ConfigManager()
            if not config.is_enabled("wechat"):
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "WeChat module is disabled in config"}')
                return
                
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                actor = data.get("actor", "Unknown")
                content = data.get("content", "")
                context_id = data.get("context_id", "")
                
                if not content:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b'{"status": "error", "message": "Content cannot be empty"}')
                    return
                    
                db = LocalDBStorage()
                event = Event(
                    timestamp=int(time.time()),
                    source="wechat",
                    actor=actor,
                    content=content,
                    context_id=context_id
                )
                db.insert_event(event)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"status": "success", "message": "Event recorded"}')
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(host='127.0.0.1', port=8080):
    server_address = (host, port)
    httpd = HTTPServer(server_address, WeChatWebhookHandler)
    httpd.serve_forever()

if __name__ == '__main__':
    run_server()
