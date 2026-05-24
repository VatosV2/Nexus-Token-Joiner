import random
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import curl_cffi.requests
import webview

from Helper import (
    NexusColor,
    NexusLogging,
    Discord,
    fetch_session,
)


def _js_safe_eval(js: str):
    try:
        window = webview.windows[0]
        window.evaluate_js(js)
    except Exception:
        pass


def _push_stats(stats: dict):
    try:
        window = webview.windows[0]
        js = f"window.leaverUpdateStats({json.dumps(stats)});"
        window.evaluate_js(js)
    except Exception:
        pass


def _notify_done():
    _js_safe_eval("window.leaverDone();")


class ServerLeaver:
    """
    Thin HTTP client for Discord "leave guild" operations.
    One instance is cheap; create per worker to avoid cross-thread sharing.
    """

    def __init__(self, useragent: str, proxy: str | None = None):
        self.useragent = useragent
        self.session = curl_cffi.requests.Session(impersonate="chrome")
        if proxy:
            self.session.proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}

    def _headers(self, token: str):
        return Discord.fill_headers(token=token, user_agent=self.useragent)

    def list_guilds(self, token: str, timeout: float = 15.0) -> tuple[bool, str, list[dict]]:
        """Return (ok, message, guilds) where guilds is a list of dicts {id, name}."""
        try:
            fetch_session(token)
            r = self.session.get(
                "https://discord.com/api/v9/users/@me/guilds",
                headers=self._headers(token),
                timeout=timeout,
            )
        except Exception as e:
            return False, f"request error: {e}", []

        if not r.ok:
            NexusLogging.print_error(token, "Failed to fetch guilds", r)
            return False, f"HTTP {r.status_code}", []

        try:
            data = r.json()
            gids = [{"id": g["id"], "name": g.get("name", "Unknown")} for g in data if "id" in g]
            return True, "ok", gids
        except Exception as e:
            return False, f"json error: {e}", []


    def leave_server(self, token: str, guild_id: str | int, timeout: float = 15.0) -> tuple[bool, str]:
        """Return (ok, message)."""
        try:
            fetch_session(token)
            r = self.session.delete(
                f"https://discord.com/api/v9/users/@me/guilds/{guild_id}",
                json={"lurking": False},
                headers=self._headers(token),
                timeout=timeout,
            )
        except Exception as e:
            return False, f"request error: {e}"

        if r.ok:
            return True, "left"
        if r.status_code == 429:
            try:
                retry = r.json().get("retry_after", 1)
            except Exception:
                retry = 1
            NexusLogging.print_status(token, f"Ratelimited, retry after {retry}s", NexusColor.RED)
            time.sleep(retry)
            return False, "ratelimit"
        NexusLogging.print_error(token, "Error while leaving server", r)
        return False, f"HTTP {r.status_code}"


class LeaverController:
    """
    Threaded manager for multi-token leave with JS stat updates.
    No UI logs from Python; only NexusLogging + stats to JS.
    """

    def __init__(self, useragent: str, proxy: str | list[str] | None = None):
        self.useragent = useragent
        self.proxies = proxy if isinstance(proxy, list) else ([proxy] if proxy else [])

        self._lock = threading.Lock()
        self._running = False
        self._executor: ThreadPoolExecutor | None = None
        self._futures = []

        self.stats = {
            "successful": 0,
            "failed": 0,
            "pending": 0,
            "total": 0,
            "current": 0,
        }

    def start(
        self,
        tokens: list[str],
        leave_all: bool,
        server_id: str | int | None,
        delay_enabled: bool,
        delay_min: int,
        delay_max: int,
        max_workers: int = 20,
        per_leave_sleep: float = 1,
        timeout: float = 15.0,
    ):
        if self._running:
            return {"success": False, "error": "Already running"}

        self._running = True
        self.stats = {
            "successful": 0,
            "failed": 0,
            "pending": len(tokens),
            "total": len(tokens),
            "current": 0,
        }
        _push_stats(self.stats)

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers if max_workers and max_workers > 0 else None
        )
        self._futures.clear()

        def worker(token: str) -> tuple[bool, str]:
            if not self._running:
                return False, "stopped"

            try:
                if delay_enabled:
                    time.sleep(random.uniform(delay_min, delay_max))

                proxy = random.choice(self.proxies) if self.proxies else None
                client = ServerLeaver(self.useragent, proxy)

                if leave_all:
                    ok, msg, guilds = client.list_guilds(token, timeout=timeout)
                    if not ok:
                        return False, f"list_guilds: {msg}"

                    left_guilds = []

                    for g in guilds:
                        if not self._running:
                            break
                        gid = g["id"]
                        gname = g.get("name", "Unknown")

                        for attempt in range(3):
                            ok, leave_msg = client.leave_server(token, gid, timeout=timeout)
                            if ok:
                                NexusLogging.print_status(token, f"Left server: {gname} ({gid})", NexusColor.GREEN)
                                left_guilds.append(gname)
                                break
                            elif leave_msg == "ratelimit":
                                time.sleep(2)
                            else:
                                NexusLogging.print_error(token, f"Failed to leave {gname} ({gid}): {leave_msg}")
                                break

                        if not proxy:
                            time.sleep(random.uniform(per_leave_sleep, per_leave_sleep * 2))

                    return True, f"Left {len(left_guilds)} server(s): {', '.join(left_guilds)}"

                else:
                    if not server_id:
                        return False, "missing server_id"
                    ok, msg = client.leave_server(token, server_id, timeout=timeout)
                    if not proxy:
                        time.sleep(random.uniform(per_leave_sleep, per_leave_sleep * 2))
                    return (True, msg) if ok else (False, msg)

            except Exception as e:
                return False, f"exception: {e}"

        for token in tokens:
            fut = self._executor.submit(worker, token)
            fut.add_done_callback(lambda f: self._after_one(f))
            self._futures.append(fut)

        return {"success": True}

    def _after_one(self, fut):
        success = False
        try:
            success, _note = fut.result()
        except Exception:
            success = False

        with self._lock:
            if success:
                self.stats["successful"] += 1
            else:
                self.stats["failed"] += 1

            self.stats["current"] += 1
            self.stats["pending"] = max(0, self.stats["total"] - self.stats["current"])
            _push_stats(self.stats)

            if self._running and self.stats["current"] >= self.stats["total"]:
                self._finish()

    def _finish(self):
        self._running = False
        try:
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        _notify_done()

    def stop(self):
        """Stop processing (in-flight tasks will wind down)."""
        self._running = False
        try:
            if self._executor:
                self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        _notify_done()
        return {"success": True, "message": "Stopping leaver"}
