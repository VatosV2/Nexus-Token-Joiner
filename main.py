import time
import json
import threading
from queue import Queue
from typing import List, Dict, Optional

from flask import Flask, render_template, Response
import requests
import webview

from Helper.funcs.pfp_adder import PFPController
from Helper.funcs.server_leaver import LeaverController
from Helper.funcs.joiner import NexusTokenJoiner, RunTokenJoiner
from Helper.funcs.vcjoiner import VCController
from Helper.Utils.handle_startup import HandleSetup
from Helper.Utils.utils import Discord

app = Flask(__name__)
log_queue = Queue()

with open("config.json", "r") as f:
    config = json.load(f)



class WindowController:
    def __init__(self):
        self.logs: List[Dict] = []
        self.status_window: Optional[webview.Window] = None
        self.status_updates: Dict[str, int] = {
            'progress': 0,
            'current': 0,
            'total': 0,
            'successful': 0,
            'failed': 0,
            'pending': 0
        }

        self.vc_controller = VCController()
        self.leaver_controller: Optional[LeaverController] = None

        self._log_lock = threading.Lock()
        self._status_lock = threading.Lock()
        
        self.useragent = HandleSetup.fetch_user_agent()



    def log(self, message: str, log_type: str = "info"):
        """Add a message to the logs."""
        with self._log_lock:
            self.logs.append({"message": message, "type": log_type})

    def get_logs(self) -> List[Dict]:
        """Get and clear logs."""
        with self._log_lock:
            logs_copy = self.logs.copy()
            self.logs.clear()
        return logs_copy



    def update_status(self, **kwargs):
        """Update status metrics."""
        with self._status_lock:
            for key, value in kwargs.items():
                if key in self.status_updates:
                    self.status_updates[key] = value

    def get_status_updates(self) -> Dict[str, int]:
        """Return current status metrics."""
        with self._status_lock:
            return self.status_updates.copy()



    def update_config_json(self, settings: dict) -> dict:
        """Save settings to config.json"""
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return {"success": True}

    def load_config_json(self) -> dict:
        """Load config.json and return its contents."""
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Error: config.json is not valid JSON")
            return {}
        except Exception as e:
            print(f"Error loading config.json: {e}")
            return {}


    def prepare_headers(self) -> dict:
        """
        Prepares headers for future uses.
        Exposed to JS.
        """
        try:
            HandleSetup.setup_headers(
                discord=Discord(), 
                user_agent=self.useragent
                )
            return {"success": True, "message": "Headers built successfully", "headers": self.discord_headers}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_internet_connection(self) -> dict:
        """Check if the internet connection is working by pinging a URL."""
        try:
            r = requests.get("https://nexustools.store/", timeout=5)  
            if r.ok:
                return {"success": True, "message": "Internet connection is working."}
            else:
                return {"success": False, "message": f"Received status code {r.status_code}"}
        except requests.exceptions.RequestException as e:
            return {"success": False, "message": f"Internet check failed: {e}"}
        
    def create_status_window(self) -> bool:
        """Create the status window."""
        if not self.status_window or not self.status_window.exists():
            self.status_window = webview.create_window(
                title="Operation Status",
                url="/status",
                width=800,
                height=600,
                frameless=True,
                on_top=True
            )
            return True
        return False

    def close(self):
        """Close all windows."""
        for window in webview.windows:
            window.destroy()

    def minimize(self):
        """Minimize all windows."""
        for window in webview.windows:
            window.minimize()



    def join_server(self, token: str, invite_code: str, nickname: str, proxy: Optional[str], filling: dict) -> dict:
        """Join a Discord server using a token."""
        try:
            joiner = NexusTokenJoiner(
                nickname=nickname,
                _proxy=proxy,
                useragent=self.useragent,
                filling=filling
            )
            status, response = joiner.accept_invite(invite=invite_code, token=token, proxy=proxy)
            if status:
                return {"success": True, "message": response}
            return {"success": False, "error": response}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_token_filling(
        self,
        invite_list: List[str],
        tokens_list: List[str],
        proxy_list: List[str],
        nickname: str,
        proxy_mode: str,
        delay_min: int,
        delay_max: int
    ) -> dict:
        """Start token filling for multiple tokens."""
        try:
            RunTokenJoiner.run_token_filling(
                invite_list=invite_list,
                tokens_list=tokens_list,
                proxy_list=proxy_list,
                nickname=nickname,
                proxy_mode=proxy_mode,
                useragent=self.useragent,
                delay_min=delay_min,
                delay_max=delay_max
            )
            return {"success": True, "message": "Token filling completed"}
        except Exception as e:
            return {"success": False, "message": str(e)}



    def leaver_start(
        self,
        tokens: List[str],
        leave_all: bool,
        server_id: Optional[str],
        delay_enabled: bool,
        delay_min: int,
        delay_max: int,
        max_workers: int = 20,
        proxies: Optional[List[str]] = None
    ) -> dict:
        """Start server leaving process."""
        if not leave_all:
            try:
                server_id = int(server_id)
            except Exception:
                return {"success": False, "error": "Invalid server ID"}

        if self.leaver_controller and self.leaver_controller._running:
            return {"success": False, "error": "Leaver already running"}

        proxy_list = proxies if isinstance(proxies, list) else ([proxies] if proxies else [])

        self.leaver_controller = LeaverController(
            useragent=self.useragent,
            proxy=proxy_list
        )

        return self.leaver_controller.start(
            tokens,
            bool(leave_all),
            server_id,
            bool(delay_enabled),
            int(delay_min),
            int(delay_max),
            int(max_workers),
        )

    def leaver_stop(self) -> dict:
        """Stop the leaver if running."""
        if not self.leaver_controller:
            return {"success": False, "error": "No leaver running"}
        return self.leaver_controller.stop()



    def update_pfp_multi(
        self,
        tokens: List[str],
        images: List[str],
        delay_enabled: bool,
        delay_min: int,
        delay_max: int,
        proxies: Optional[List[str]] = None
    ) -> dict:
        """Update multiple PFPs."""
        return PFPController().update_pfp_multi(tokens, images, delay_enabled, delay_min, delay_max, proxies=proxies)

    def stop_pfp(self) -> dict:
        """Stop PFP updating."""
        PFPController().stop()
        return {"success": True, "message": "PFP update stopped"}



    def leave_vc(self, token: str, guild_id: str, channel_id: str) -> dict:
        try:
            return self.vc_controller.leave_vc(token, int(guild_id), int(channel_id))
        except Exception as e:
            return {"success": False, "error": str(e)}

    def leave_vc_multi(self, tokens: List[str], guild_id: str, channel_id: str) -> dict:
        try:
            return self.vc_controller.leave_vc_multi(tokens, int(guild_id), int(channel_id))
        except Exception as e:
            return {"success": False, "error": str(e)}

    def join_vc_multi(self, tokens: List[str], guild_id: str, channel_id: str, options: Optional[dict] = None) -> dict:
        try:
            self.vc_controller.join_vc_multi(tokens, int(guild_id), int(channel_id), options or {})
            return {"success": True, "message": "Joining VC(s) started"}
        except Exception as e:
            return {"success": False, "error": str(e)}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/status')
def status():
    return render_template('index.html')


@app.route('/events')
def events():
    """Server-Sent Events endpoint for live updates"""
    def event_stream():
        controller = webview.windows[0]._js_api
        last_status = {}

        while True:
            try:
                for log in controller.get_logs():
                    yield f"data: {json.dumps(log)}\n\n"

                current_status = controller.get_status_updates()
                if current_status != last_status:
                    yield f"data: {json.dumps(current_status)}\n\n"
                    last_status = current_status

                time.sleep(0.1)
            except Exception:
                break

    return Response(event_stream(), mimetype="text/event-stream")


def run_flask():
    app.run(debug=False, port=5000, use_reloader=False)


if __name__ == '__main__':
    controller = WindowController()

    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(1)

    main_window = webview.create_window(
        title="Nexus Joiner",
        url="http://127.0.0.1:5000",
        js_api=controller,
        width=1000,
        height=600,
        frameless=True
        )

    webview.start(debug=False)
