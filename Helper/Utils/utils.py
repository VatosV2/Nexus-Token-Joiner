"""Util File for Nexus Token Joiner V2"""

import base64
import uuid
import json
import os
import random
import re
import time
import tempfile
import threading

from typing import (
    Dict,
    Any,
    List,
    Optional,
    TypedDict,
    Tuple,
)

from Helper.Utils.logging import NexusLogging
from Helper.NexusColors.color import NexusColor

import requests
import websocket
import orjson


config = json.load(open("config.json"))


class BuildProperties(TypedDict, total=False):
    os: str
    browser: str
    device: str
    system_locale: str
    browser_user_agent: str
    browser_version: str
    os_version: str
    referrer: str
    referring_domain: str
    referrer_current: str
    referring_domain_current: str
    release_channel: str
    client_build_number: int
    native_build_number: int
    client_event_source: Optional[None]


class Discord:
    """
    Utility class for fetching build numbers, building super-properties, and managing Discord-related information.
    Provides methods to get the current build version, format headers, and manage cookies and user agents.
    """

    saved_headers: List[Dict[str, str]] = []
    saved_properties: Dict[str, str] = {}

    @staticmethod
    def context(value: str, guild_id, channel_id, type) -> str:
        """
        Encodes a value into a base64-encoded string representing the context.

        Args:
            value (str): The value to be encoded.

        Returns:
            str: The base64-encoded string representing the context.
        """
        return base64.b64encode(
            orjson.dumps({"location":value,"location_guild_id":guild_id,"location_channel_id":channel_id,"location_channel_type": type})
        ).decode()

    @staticmethod
    def _native() -> int:
        """
        Fetches the native build number from Discord's update manifest.

        Returns:
            int: The native build number of Discord.
        """
        response = requests.get(
            "https://updates.discord.com/distributions/app/manifests/latest",
            params={
                "install_id": "0",
                "channel": "stable",
                "platform": "win",
                "arch": "x86",
            },
            headers={
                "user-agent": "Discord-Updater/1",
                "accept-encoding": "gzip",
            },
            timeout=10,
        ).json()
        return int(response["metadata_version"])

    @staticmethod
    def _main() -> str:
        """
        Fetches the main build number of Discord from the official Discord API.

        Returns:
            str: The main build number as a string.
        """
        response = requests.get(
            "https://discord.com/api/downloads/distributions/app/installers/latest",
            params={
                "channel": "stable",
                "platform": "win",
                "arch": "x86",
            },
            allow_redirects=False,
            timeout=10,
        ).text
        return re.search(r"x86/(.*?)/", response).group(1)

    @staticmethod
    def _build() -> int:
        """
        Fetches the build number of Discord from the website's assets.

        Returns:
            int: The build number of Discord, or -1 if the build number cannot be found.
        """
        page = requests.get(
            "https://discord.com/app", timeout=10
        ).text
        assets = re.findall(r'src="/assets/([^"]+)"', page)

        for asset in reversed(assets):
            js = requests.get(
                f"https://discord.com/assets/{asset}",
                timeout=10,
            ).text
            if "buildNumber:" in js:
                return int(
                    js.split('buildNumber:"')[1].split('"')[
                        0
                    ]
                )

        return -1

    def build_numbers(self) -> Tuple[int, str, int]:
        """
        Returns the build numbers from the different methods (`_build`, `_main`, and `_native`).

        Returns:
            Tuple[int, str, int]: A tuple containing the client build number, main build number, and native build number.
        """
        return (self._build(), self._main(), self._native())

    @staticmethod
    def extract_version(user_agent: str) -> str:
        """
        Extracts the browser version from the provided user-agent string.

        Args:
            user_agent (str): The user-agent string from which the version will be extracted.

        Returns:
            str: The browser version extracted from the user-agent string, or "Unknown" if no version is found.
        """
        patterns = {
            "Chrome": r"Chrome/([\d.]+)",
            "Firefox": r"Firefox/([\d.]+)",
            "Safari": r"Version/([\d.]+).*Safari",
            "Opera": r"Opera/([\d.]+)",
            "Edge": r"Edg/([\d.]+)",
            "IE": r"MSIE ([\d.]+);",
        }
        for pattern in patterns.values():
            if match := re.search(pattern, user_agent):
                return match.group(1)
        return "Unknown"

    @classmethod
    def build_properties(
        cls, user_agent: str, extra: Dict[str, Any] = None
    ) -> str:
        """
        Builds the super-properties string for Discord using the provided user-agent and additional data.

        Args:
            user_agent (str): The user-agent string to be used for extracting the browser version.
            extra (Dict[str, Any]): Additional properties to be included in the super-properties.

        Returns:
            str: A base64-encoded string representing the super-properties JSON object.
        """
        if user_agent in cls.saved_properties:
            return cls.saved_properties[user_agent]  

        if extra is None:
            extra = {}

        client, main, native = cls().build_numbers()
        version = cls.extract_version(user_agent)

        properties: Dict[str, Any] = {
            "os": "Windows",
            "browser": "Chrome",
            "device": "",
            "system_locale": "en-US",
            "browser_user_agent": user_agent,
            "browser_version": version,
            "os_version": "10",
            "referrer": "",
            "referring_domain": "",
            "referrer_current": "",
            "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": client,
            "client_event_source": None,
            "has_client_mods": False,
            "client_launch_id": str(uuid.uuid4()),
            "launch_signature": str(uuid.uuid4()),
            "client_heartbeat_session_id": str(uuid.uuid4()),
            "client_app_state": "focused",
            **extra,
        }

        encoded_properties = base64.b64encode(orjson.dumps(properties)).decode()
        cls.saved_properties[user_agent] = encoded_properties  
        return encoded_properties


    @staticmethod
    def fill_headers(
        token: str,
        user_agent: str,
        extra: Dict[str, Any] = None,
        xcaptcha: str = None,
        rqtoken: str = None,
        xcontext: tuple = None,
        session_id: str = None,
        force_new: bool = False
    ) -> Dict[str, str]:
        """
        Fills the headers with the provided token and user-agent, and returns the updated headers.

        Args:
            token (str): The authorization token to be included in the headers.
            user_agent (str): The user-agent string to be included in the headers.
            extra (Dict[str, Any]): Additional properties to be included in the super-properties.
            xcaptcha (str): The X-Captcha-Key value to be included if provided.
            rqtoken (str): The X-Captcha-Rqtoken value to be included if provided.

        Returns:
            Dict[str, str]: The headers dictionary with the updated authorization and other properties.
        """
        version = Discord.extract_version(user_agent)
        
        if not xcaptcha and not xcontext and not force_new:
            for headers in Discord.saved_headers:
                if headers.get("user-agent") == user_agent:
                    headers["authorization"] = token
                    return headers

        headers = {
            "authority": "discord.com",
            "accept": "*/*",
            "accept-language": "en-US",
            "authorization": token,
            "content-type": "application/json",
            "origin": "https://discord.com",
            "referer": "https://discord.com/channels/@me",
            "sec-ch-ua": f'"Not/A)Brand";v="8", "Chromium";v="{version}", "Google Chrome";v="{version}"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": user_agent,
        }

        if xcaptcha and rqtoken:
            headers.update({
                "x-captcha-key": xcaptcha or "",
                "x-captcha-rqtoken": rqtoken or "",
                "x-captcha-session-id": session_id or "",
                })
            
        if xcontext:
            location, guild_id, channel_id, type_ = xcontext
            xcontextprops = Discord.context(
                value=location, 
                guild_id=guild_id, 
                channel_id=channel_id, 
                type=type_)
            
            headers.update({"x-context-properties": xcontextprops})

        headers.update({
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "en-US",
            "x-super-properties": Discord.build_properties(user_agent, extra),
        })

        if not xcaptcha:
            Discord.saved_headers.append(headers)
            return headers

        return headers


    @staticmethod
    def get_cookies(session) -> Dict[str, str]:
        """
        Retrieves cookies from a Discord session.

        Args:
            session: The session object used to make the request.

        Returns:
            Dict[str, str]: A dictionary containing cookies from the session.
        """
        cookies = {}
        try:
            response = session.get("https://discord.com", timeout=10)
            for cookie_name, cookie_value in response.cookies.items():
                if cookie_name.startswith("__") and cookie_name.endswith("uid"):
                    cookies[cookie_name] = cookie_value
            return cookies
        except requests.RequestException as e:
            print(f"Failed to obtain cookies (RequestException: {e})")
        except KeyError as e:
            print(f"Failed to extract cookies (KeyError: {e})")
        except TypeError as e:
            print(f"Failed to process cookies (TypeError: {e})")
        return cookies

class IdentifyPayload(TypedDict):
    """
    TypedDict for the structure of the payload used in the IDENTIFY operation.

    Attributes:
        op (int): The operation code. For IDENTIFY, it's 2.
        d (Dict[str, Any]): The data payload containing token and properties.
    """
    op: int
    d: Dict[str, Any]


def fetch_session(token: str) -> str:
    """
    Connects to the Discord Gateway WebSocket and retrieves the session ID using the provided token.

    Args:
        token (str): The Discord bot token used for authentication.

    Returns:
        str: The session ID if the connection is successful and the READY event is received,
             or an error message if the token is invalid, rate-limited (429), or another error occurs.

    Exceptions:
        websocket.WebSocketException: Raised if there is an error with the WebSocket connection.
        json.JSONDecodeError: Raised if there is an error decoding the received JSON data.
    """
    ws = websocket.WebSocket()
    try:
        ws.connect(
            "wss://gateway.discord.gg/?v=9&encoding=json"
        )
        recv = json.loads(ws.recv())

        payload = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {"$os": "Windows"},
            },
        }

        ws.send(json.dumps(payload))
        result = json.loads(ws.recv())

        if result.get("t") == "READY":
            return result["d"]["session_id"]
        if result.get("op") == 9:
            return "Invalid token"
        if result.get("op") == 429:
            return "429"
        return "An unknown error occurred"

    except websocket.WebSocketException as e:
        return f"WebSocket error: {e}"
    except json.JSONDecodeError as e:
        return f"JSON error: {e}"

def get_session_id(token):
    ws = websocket.WebSocket()
    try:
        ws.connect("wss://gateway.discord.gg/?v=9&encoding=json")

        hello = json.loads(ws.recv())
        heartbeat_interval = hello["d"]["heartbeat_interval"] / 1000

        payload = {
            "op": 2,
            "d": {
                "token": token,
                "properties": {"$os": "Windows"},
            },
        }

        ws.send(json.dumps(payload))

        while True:
            response = json.loads(ws.recv())

            if response.get("t") == "READY":
                session_id = response["d"]["session_id"]
                return session_id, ws, heartbeat_interval

            if response.get("op") == 9:
                return "Invalid token", None, None
            if response.get("op") == 429:
                return "Rate limited", None, None

    except websocket.WebSocketException as e:
        return f"WebSocket error: {e}", None, None
    except json.JSONDecodeError as e:
        return f"JSON error: {e}", None, None


def keep_session_alive(ws, heartbeat_interval):
    def heartbeat():
        while True:
            try:
                ws.send(json.dumps({"op": 1, "d": None}))
                time.sleep(heartbeat_interval)
            except Exception:
                break 

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()

class Hsolver:
    """
    Class to handle captcha solving using external services.
    Provides methods to interact with captcha solving APIs and get solutions.
    """

    @staticmethod
    def get_captcha_key(
        rqdata: str,
        site_key: str,
        website_url: str,
        proxy: str,
        api_key: str,
    ) -> Dict[bool, str]:
        """
        Solves an hCaptcha using an external solver service.

        This method communicates with the captcha solving service, using the provided
        data (such as the `site_key`, `website_url`, `proxy`, and `rqdata`) along
        with an `api_key` for authentication to solve the captcha.

        The process continues to retry until the captcha is successfully solved.

        Args:
            rqdata (str): The required data for the captcha request (often specific to the captcha instance).
            site_key (str): The site key for the hCaptcha challenge (provided by the website hosting the captcha).
            website_url (str): The URL of the website where the captcha is located.
            proxy (str): The proxy to use for making the request (if any).
            api_key (str): The API key for the captcha solving service to authenticate the request.

        Returns:
            str: The solution for the captcha if successfully solved.

        Raises:
            Exception: If the captcha cannot be solved after repeated attempts (not handled here, but can be customized).
        """
        
        
        if config["captcha"]["service"] == "24captcha":
            json = {
                "key": api_key,
                "sitekey": site_key,
                "pageurl": website_url,
                "json": 1,
                "proxy": proxy,
                "rqdata": rqdata,
                "enterprise": True
            }
            
            r = requests.post("https://24captcha.online/in.php", json=json)
            task_id = r.json()["request"]
            json = {
                "key": api_key,
                "action": "get",
                "id": task_id,
                "json": 1
            }
            
            for _ in range(config["captcha"]["timeout"]):
                r = requests.get(f"https://24captcha.online/res.php", json=json)
                if r.json()["status"] == 1:
                    return True, r.json()["request"]
                
                if r.json()["request"] == "ERROR_CAPTCHA_UNSOLVABLE":
                    return False, r.json()["request"]
                
                time.sleep(1)
            
            return False, "Captcha Timeout"

        if config["captcha"]["service"] == "razorcap":
            json = {
                'key': api_key, 
                'type': "hcaptcha_enterprise",
                'data': {
                    'sitekey': site_key,
                    'siteurl': "discord.com",
                    'proxy': f"http://{proxy}",
                    'rqdata': rqdata
                }
            }
            r = requests.post("https://api.razorcap.me/create_task", json=json)
            if r.ok:
                task_id = r.json()["task_id"]

            for _ in range(45):
                r = requests.get(f"https://api.razorcap.me/get_result/{task_id}")
                if r.json()["status"] == "solved":
                    return True, r.json()["response_key"]
                
                if r.json()["status"] == "error":
                    return False, r.json()["message"]
                
                time.sleep(1)
            
            return False, "Captcha Timeout"

        if config["captcha"]["service"] == "teamai":
            json_data = {
            "site_key": site_key,
            "site_url": website_url,
            "rqd": rqdata,
            "proxy": proxy,
            "key": api_key,
            }

            r = requests.post("http://captcha.aiclientz.com:1234/solve", json=json_data)
            try:
                data = r.json()
            except ValueError:
                return False, r.text

            if r.status_code == 201 or str(data.get("code")) == "201" or "captcha" in data:
                return True, data.get("captcha")
        


class Utils:
    """Utility class containing common methods for working with tokens, proxies, and system operations."""

    @staticmethod
    def get_tokens(formatting: bool) -> List[str]:
        """
        Reads the 'tokens.txt' file located in the 'Input' directory and returns a list of tokens.

        The method reads all the lines from the file, strips leading/trailing spaces, and optionally formats the tokens.

        Args:
            formatting (bool): If True, extracts the third segment of tokens delimited by ':'.

        Returns:
            List[str]: A list of token strings read from the 'tokens.txt' file, or an empty list if the file doesn't exist.
        """
        try:
            with open("Input/tokens.txt", "r", encoding="utf-8") as file:
                tokens = [
                    token.split(":")[2].strip() if formatting and ":" in token else token.strip()
                    for token in file.readlines()
                ]
            return tokens
        except FileNotFoundError:
            return []

    @staticmethod
    def get_formatted_proxy(filename: str) -> str:
        """
        Reads a random proxy from the specified file and formats it correctly.

        The method selects a random proxy from the provided file, checks its format, and returns it in a standardized
        format (e.g., 'username:password@host:port') if necessary. If the proxy doesn't already include authentication
        or the proper delimiter, it is adjusted accordingly.

        Args:
            filename (str): The path to the file containing proxy addresses.

        Returns:
            str: A formatted proxy string.
        """
            
        proxy = random.choice(
            open(filename, encoding="cp437")
            .read()
            .splitlines()
        ).strip()
        
        proxy = re.sub(r'^http?://', '', proxy, flags=re.IGNORECASE)
        
        if "@" in proxy:
            return proxy
        if len(proxy.split(":")) == 2:
            return proxy

        if "." in proxy.split(":")[0]:
            return (
                ":".join(proxy.split(":")[2:])
                + "@"
                + ":".join(proxy.split(":")[:2])
            )

        return (
            ":".join(proxy.split(":")[:2])
            + "@"
            + ":".join(proxy.split(":")[2:])
        )

    @staticmethod
    def new_title(title: str) -> None:
        """
        Changes the terminal or command prompt window title.

        The method changes the title of the terminal window to the provided title string. It works differently based
        on the operating system: for Windows, it uses the `title` command, and for Unix-based systems (Linux/macOS),
        it uses ANSI escape codes to set the window title.

        Args:
            title (str): The title to set for the terminal window.
        """
        os.system(
            f"title {title}"
            if os.name == "nt"
            else f"echo -ne '\033]0;{title}\007'"
        )
    

    @staticmethod
    def clear() -> None:
        """
        Clears the terminal or command prompt screen.

        The method clears the terminal screen. On Windows, it uses the `cls` command, while on Unix-based systems
        (Linux/macOS), it uses the `clear` command.

        """
        os.system("cls" if os.name == "nt" else "clear")

    @staticmethod
    def load(filename: str) -> List[str]:
        """Returns Linecount of a file."""
        with open(filename, 'r', encoding="utf-8") as file:
            line_count = sum(1 for line in file)
        return line_count

    @staticmethod
    def change_window_size(width: int, height: int) -> None:
        """
        Changes the terminal or command prompt window size.

        The method changes the window size of the terminal or command prompt. On Windows, it uses the `mode` command,
        and on Unix-based systems (Linux/macOS), it attempts to use the `resize` command if available.

        Args:
            width (int): The width of the terminal window in characters.
            height (int): The height of the terminal window in lines.
        """
        if os.name == "nt":
            os.system(f"mode con: cols={width} lines={height}")
        else:
            os.system(f"resize -s {height} {width}")

    @staticmethod
    def download_image(url: str) -> str:
        """
        Downloads an image from a URL and saves it to a temporary file.

        Args:
            url (str): The URL of the image to download.

        Returns:
            str: The file path of the downloaded image.

        Raises:
            ValueError: If the URL is invalid or the image cannot be downloaded.
            IOError: If the file cannot be written to the disk.
        """
        try:
            response = requests.get(url, stream=True)

            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                raise ValueError("URL does not point to a valid image.")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                for chunk in response.iter_content(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file_path = temp_file.name

            return temp_file_path

        except requests.exceptions.RequestException as e:
            raise ValueError(f"Failed to download image: {e}")
        except IOError as e:
            raise IOError(f"Failed to write image to disk: {e}")

    @staticmethod
    def image_to_base64(image_path) -> str:
        """Converts a image to a base64 encoded string"

        Args:
            image_path (str): Path of the image that gets converted.

        Returns:
            str: The encoded string of the image.
        """
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(
                image_file.read()
            ).decode("utf-8")
        return encoded_string
    
    @staticmethod
    def get_xcontext_values(
        invite: str, token: str, proxie: Optional[str] = None
    ) -> Optional[Tuple[str, int, int, str]]:
        try:
            if proxie:
                proxie = Utils.get_formatted_proxy("Input/proxies.txt")
                
            headers = {"Authorization": token}
            proxies = (
                {"http": f"http://{proxie}"}
                if proxie
                else None
            )
                        
            response = requests.get(
                f"https://discord.com/api/v9/invites/{invite}",
                headers=headers,
                proxies=proxies,
            )
            
            if response.ok:
                data = response.json()
                return "Join Guild", data["guild"]["id"], data["channel"]["id"], data.get("type", "unknown")
            
        except KeyError as e:
            print(f"{NexusColor.RED}Unexpected response structure: Missing key {e}")
        
        return None, None, None, None
    
    @staticmethod
    def get_random_token(max_attempts=10):
        """
        Fetches a random token from Utils and validates it by making requests to Discord API.

        Args:
            max_attempts (int): Maximum number of attempts to find a valid token.

        Returns:
            str: A valid token if found, else None.
        """
        tokens = Utils.get_tokens(formatting=True)

        if not tokens:
            return None

        for _ in range(max_attempts):
            token = random.choice(tokens)
            
            user_response = requests.get(
                "https://discord.com/api/v9/users/@me",
                headers={"Authorization": token}
            )

            if user_response.status_code == 200:
                settings_response = requests.get(
                    "https://discord.com/api/v9/users/@me/settings",
                    headers={"Authorization": token}
                )

                if settings_response.status_code == 200:
                    return token
                else:
                    pass
            else:
                pass

        return None

    @staticmethod
    def change_window_size(width: int, height: int) -> None:
        """
        Changes the terminal or command prompt window size.

        The method changes the window size of the terminal or command prompt. On Windows, it uses the `mode` command,
        and on Unix-based systems (Linux/macOS), it attempts to use the `resize` command if available.

        Args:
            width (int): The width of the terminal window in characters.
            height (int): The height of the terminal window in lines.
        """
        if os.name == "nt":
            os.system(f"mode con: cols={width} lines={height}")
        else:

            os.system(f"resize -s {height} {width}")
