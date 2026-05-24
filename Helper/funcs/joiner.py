"Main File to handle Joining and more."

import ctypes
import threading
import time
import random 
from typing import Optional
from queue import Queue

import curl_cffi.requests
import cloudscraper

from Helper import (
    Discord,
    Hsolver,
    Utils,
    config,
    fetch_session,
    intro,
    pink_gradient,
    NexusLogging,
    DetectBypass,
    OnboardingBypass,
    BypassRules,
    RestoreCordBypass,
    NexusColor,
    HandleSetup,
    get_session_id,
    keep_session_alive
)

class NexusStats:
    """Used to store stats for joining like: joined, failed, solved, .."""
    joined: list[str] = []
    failed: int = 0
    solved: int = 0
    start = None
    thread_running = threading.Event()
    
def title():
    """Function to show NexusStats on title."""
    while not NexusStats.thread_running.is_set():
        title = f"Nexus Token Joiner ┃ Joined: {len(NexusStats.joined)} ┃ Failed: {NexusStats.failed} ┃ Solved: {NexusStats.solved} ┃ Time: {round(time.time() - NexusStats.start, 2)}s "
        ctypes.windll.kernel32.SetConsoleTitleW(title)
        time.sleep(0.01) 
        
class NexusTokenJoiner:
    """Handles Discord token joining and nickname changing."""

    def __init__(
        self, nickname: str, _proxy: bool, useragent: str, filling: bool = False
    ) -> None:
        """
        Initializes the NexusTokenJoiner instance.

        Args:
            nickname (str): The nickname to set for the user.
            _proxy (bool): Whether to use proxies for requests.
            useragent (str): The User-Agent string for HTTP headers.
        """
        self.discord: callable = Discord()
        self.hsolver: callable = Hsolver()
        self.utils: callable = Utils()
        
        self.filling: bool = filling
        self.solver: bool = True
        self._proxy: bool = _proxy

        self.nickname: str = nickname
        self.useragent: str = useragent
        
        self.onboarding = None
        self.rules = None
        self.restorecord_detected = False
        self.client_id = None
        
        self.guild_id = None
        self.session_id: str = None

        self.lock = threading.Lock()
        
    def change_nick(
        self, guild_id: int, nick: str, token: str
    ) -> None:
        """
        Changes the nickname of a user in a specified Discord guild.

        Args:
            guild_id (int): The ID of the guild where the nickname is to be changed.
            nick (str): The new nickname to set.
            token (str): The Discord token for authentication.
        """
        headers = self.discord.fill_headers(
            token, self.useragent
        )
        session = curl_cffi.requests.Session(impersonate="chrome")
        session.headers.update(headers)
        session.cookies.update(
            self.discord.get_cookies(session)
        )
        if "{random}" in nick:
            random_number = random.randint(1111, 9999)
            nick = nick.replace("{random}", str(random_number))

        response = session.patch(
            f"https://discord.com/api/v9/guilds/{guild_id}/members/@me",
            json={"nick": nick},
            timeout=10
        )


        if response.status_code == 200:
            NexusLogging.print_status(
                token, "Nickname Changed", NexusColor.GREEN
            )
        elif response.status_code == 429:
            NexusLogging.print_status(
                token, "Ratelimit", NexusColor.RED
            )
        else:
            NexusLogging.print_error(
                token,
                "Error while changing Nickname",
                response,
            )

    def accept_invite(
        self, invite: str, token: str, proxy: str = None, session_id: str = None
    ) -> None:
        """
        Accepts a Discord server invite and optionally changes the user's nickname.

        Args:
            invite (str): The server invite code.
            token (str): The Discord token for authentication.
            proxy (str, optional): Proxy to use for the request. Defaults to None.
        """
        session = curl_cffi.requests.Session(impersonate="chrome")
        try:
            if not session_id:
                session_id = fetch_session(token)
                if session_id == "Invalid token":
                    NexusLogging.print_status(
                        token, "Invalid", NexusColor.RED
                    )
                    return

                if session_id == "429":
                    NexusLogging.print_status(
                        token,
                        "Cant Fetch Session -> 429",
                        NexusColor.RED,
                    )
                    return

            self.session_id = session_id
            payload = {"session_id": self.session_id}
            session.cookies.update(
                self.discord.get_cookies(session)
            )

            if self._proxy:
                session.proxies = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
                }

            response = session.post(
                f"https://discord.com/api/v9/invites/{invite}",
                json=payload,
                headers=self.discord.fill_headers(
                    token, self.useragent
                ),
                timeout=config()["join"]["timeout"]
            )

            if response.status_code == 200:
                self._handle_successful_invite(
                    token, response, self.nickname, proxy, invite
                )
                return True, f"Token joined {invite} successfully."
            
            elif response.status_code == 429:
                NexusLogging.print_status(
                    token, "Ratelimit", NexusColor.RED
                )
                with self.lock:
                    NexusStats.failed += 1
            elif (
                response.status_code == 401
                and response.json()["message"]
                == "401: Unauthorized"
            ):
                NexusLogging.print_status(
                    token, "Invalid", NexusColor.RED
                )
                with self.lock:
                    NexusStats.failed += 1
            elif (
                "You need to verify your account"
                in response.text
            ):
                NexusLogging.print_status(
                    token, "Locked", NexusColor.RED
                )
                with self.lock:
                    NexusStats.failed += 1
            elif "captcha_rqdata" in response.text:
                self._handle_captcha(
                    token,
                    response,
                    invite,
                    session,
                    proxy,
                )
            else:
                NexusLogging.print_error(
                    token, "Error while joining", response
                )
                
        except TimeoutError:
            NexusLogging.print_status(token, "Timeout", NexusColor.RED)
            with self.lock:
                NexusStats.failed += 1
        except KeyError as e:
            NexusLogging.print_status(token, f"Key Error: {e}", NexusColor.RED)
            with self.lock:
                NexusStats.failed += 1
        except Exception as e:
            error_message = str(e)
            if "curl: (28) Connection timed out" not in error_message:
                NexusLogging.print_status(token, f"Error While Trying to join: {error_message}", NexusColor.RED)
                with self.lock:
                    NexusStats.failed += 1

    def _handle_successful_invite(
        self, token, response, nickname, proxy, invite = None
    ):
        """
        Handles the logic for a successful server join.

        Args:
            token (str): The Discord token used for the request.
            response (requests.Response): The response object from the server.
            nickname (str): The nickname to set, if any.
        """
        with self.lock:
            NexusStats.joined.append(token)
            
        if self.filling:
            NexusLogging.print_status(
                token, f"Joined {NexusColor.LIGHTBLACK}- ({invite})", NexusColor.GREEN
            )
        
        else:
            NexusLogging.print_status(
                token, "Joined", NexusColor.GREEN
            )
            
        
        self.guild_id = response.json()["guild"]["id"]

        cfsess = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
                "mobile": False,
            }
        )
        bypasses = config()["join"]
        detect = DetectBypass(token=token, guildid=self.guild_id, useragent=self.useragent , proxy=proxy, cfsession=cfsess)
            
        self.onboarding = self.onboarding if self.onboarding is not None else detect.check_onboarding()
        self.rules = self.rules if self.rules is not None else detect.check_rules()
        
        if self.rules and bypasses["bypass_rules"]:
            NexusLogging.print_status(
                token=token,
                message="Detected Rules",
                color=NexusColor.LIGHTBLUE,
            )
            BypassRules(
                token=token, guild_id=self.guild_id, useragent=self.useragent, proxy=proxy
            ).bypass_rules()
            
        if self.onboarding and bypasses["bypass_onboarding"]:
            NexusLogging.print_status(
                token=token,
                message="Detected Onboarding",
                color=NexusColor.LIGHTBLUE,
            )
            OnboardingBypass(
                token=token, guildid=self.guild_id, useragent=self.useragent, proxy=proxy
            ).bypass_onboarding()
        
        if proxy and bypasses["bypass_restorecord"]:
            if not self.restorecord_detected:
                client_id = detect.check_restorecord()
                if client_id:
                    self.restorecord_detected = True
                    self.client_id = client_id
                else:
                    self.restorecord_detected = True  

            if self.client_id:
                NexusLogging.print_status(
                    token=token,
                    message="Detected Restorecord",
                    color=NexusColor.LIGHTBLUE,
                )
                RestoreCordBypass(
                    token=token,
                    guild_id=self.guild_id,
                    client_id=self.client_id,
                    useragent=self.useragent,
                    proxy=proxy,
                    cfsession=cfsess
                ).bypass()
                
        if nickname:
            self.change_nick(
                guild_id=self.guild_id,
                nick=nickname,
                token=token
            )

                    
            

    def _handle_captcha(
        self, token, response, invite, session, proxy_
    ):
        """
        Handles captcha challenges during the server joining process.

        Args:
            token (str): The Discord token used for the request.
            response (requests.Response): The response object from the server.
            invite (str): The server invite code.
            session (tls_client.Session): The current TLS session.
            proxy_ (str): Proxy used for the request.
        """
        if self.filling:
            if invite:
                NexusLogging.print_status(
                    token=token,
                    message=f"Hcaptcha {NexusColor.LIGHTBLACK}- ({invite})",
                    color=NexusColor.RED
                )
            else:
                NexusLogging.print_status(
                    token=token,
                    message="Hcaptcha (filling)",
                    color=NexusColor.RED
                )
        else:
            NexusLogging.print_status(
                token=token,
                message="Hcaptcha",
                color=NexusColor.RED
            )
        if (
            config()["captcha"]["api_key"]
            != None
            and
            config()["captcha"]["enabled"]
            and
            proxy_
        ):
            self._solve_captcha(
                token,
                response,
                invite,
                session,
                proxy_,
            )
        else:
            with self.lock:
                NexusStats.failed += 1

    def _solve_captcha(
        self, token, response, invite, session, proxy_
    ):
        """
        Attempts to solve a captcha challenge using an external service.

        Args:
            token (str): The Discord token used for the request.
            response (requests.Response): The response object from the server.
            invite (str): The server invite code.
            session (tls_client.Session): The current TLS session.
            proxy_ (str): Proxy used for the request.
        """
            
        if self.solver:
            NexusLogging.print_status(
                token=token[:45],
                message="Solving Captcha..",
                color=NexusColor.GREEN
            )
            site_key = response.json()["captcha_sitekey"]
            rqdata = response.json()["captcha_rqdata"]
            rqtoken = response.json()["captcha_rqtoken"]
            captcha_session_id = response.json()["captcha_session_id"]

            try:
                start_time = time.time()
                status, solution = self.hsolver.get_captcha_key(
                    rqdata=rqdata,
                    site_key=site_key,
                    website_url="https://discord.com/channels/@me",
                    proxy=proxy_,
                    api_key=config()["captcha"]["api_key"],
                )
                if status:
                    end_time = time.time()
                    NexusStats.solved += 1
                    NexusLogging.print_status(
                        token=solution,
                        message=f"{NexusColor.GREEN}Solved in {NexusColor.RESET}{end_time - start_time:.2f}s",
                        color=NexusColor.GREEN,
                        length=60
                    )
                    headers = self.discord.fill_headers(
                        token=token, 
                        user_agent=self.useragent,
                        xcaptcha=solution,
                        rqtoken=rqtoken,
                        session_id=captcha_session_id
                    )
                   
                    response = session.post(
                        f"https://discord.com/api/v9/invites/{invite}",
                        json={
                            "session_id": self.session_id
                        },
                        headers=headers,
                        timeout=config()["join"]["timeout"]
                    )
                    

                    if response.status_code == 200:
                        with self.lock:
                            NexusStats.joined.append(token)
                        
                        if not self.filling:
                            NexusLogging.print_status(
                                token,
                                "Joined",
                                NexusColor.GREEN,
                            )
                        else:
                            NexusLogging.print_status(
                                token,
                                f"Joined {NexusColor.LIGHTBLACK}- ({invite})",
                                NexusColor.GREEN,
                            )
                        if self.nickname:
                            guild_id = response.json()[
                                "guild"
                            ]["id"]
                            self.change_nick(
                                guild_id,
                                self.nickname,
                                token,
                            )
                    else:
                        NexusLogging.print_error(
                            token,
                            "Error while joining",
                            response,
                        )
                        with self.lock:
                            NexusStats.failed += 1
                else:
                    NexusLogging.print_status(
                        "Failed To Solve Captcha.",
                        solution,
                        NexusColor.RED
                    )
                    with self.lock:
                        NexusStats.failed += 1
                    return
            except (
                ConnectionError,
                TimeoutError,
            ) as conn_error:
                print(
                    f"Connection error occurred: {conn_error}"
                )
                with self.lock:
                    NexusStats.failed += 1
            except ValueError as val_error:
                print(
                    f"Value error in response: {val_error}"
                )
                with self.lock:
                    NexusStats.failed += 1
            except KeyError as key_error:
                print(
                    f"Key error when accessing response data: {key_error}"
                )
                with self.lock:
                    NexusStats.failed += 1
        else:
            with self.lock:
                NexusStats.failed += 1
                
class RunTokenJoiner:
    @staticmethod
    def run_joiner(
        utils: Utils,
        invite: str,
        nickname: Optional[str],
        proxy_mode: Optional[str],
        useragent: str,
        delay_min: Optional[int],
        delay_max: Optional[int],
    ) -> None:
        """Run the token joiner with the given configuration."""
        threads = []
        use_proxies = bool(proxy_mode)
        proxy = None

        nexus = NexusTokenJoiner(nickname=nickname, _proxy=use_proxies, useragent=useragent)
        NexusStats.start = time.time()
        threading.Thread(target=title, daemon=True).start()

        for token in utils.get_tokens(formatting=True):
            if use_proxies:
                proxy = utils.get_formatted_proxy("Input/proxies.txt")

            thread = threading.Thread(target=nexus.accept_invite, args=(invite, token, proxy))
            threads.append(thread)
            thread.start()

            if config()["delay"]["enabled"]:
                time.sleep(random.uniform(delay_min, delay_max))

        for thread in threads:
            thread.join()

        NexusStats.thread_running.set()
        RunTokenJoiner.save_results(invite)

        RunTokenJoiner.print_summary()
    @staticmethod
    def run_token_filling(
        invite_list: list[str],
        tokens_list: list[str],
        proxy_list: list[str],
        nickname: str,
        proxy_mode: Optional[str],
        useragent: str,
        delay_min: int,
        delay_max: int
    ) -> None:
        """Fill multiple invites using tokens from the frontend."""
        
        invite_queue = Queue()
        for inv in invite_list:
            invite_queue.put(inv)

        token_proxy_map = {}
        if proxy_mode == "per-token" and proxy_list:
            for i, token in enumerate(tokens_list):
                proxy = proxy_list[i % len(proxy_list)]
                token_proxy_map[token] = proxy

        NexusStats.start = time.time()
        threading.Thread(target=title, daemon=True).start()

        threads = []

        for token in tokens_list:
            proxy = token_proxy_map.get(token) if proxy_mode == "per-token" else (
                proxy_list[0] if (proxy_mode == "static" and proxy_list) else None
            )

            thread = threading.Thread(
                target=RunTokenJoiner.handle_token_invites,
                args=(token, invite_queue, nickname, proxy_mode, proxy, useragent, delay_min, delay_max, proxy_list),
                daemon=True
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        NexusStats.thread_running.set()


    @staticmethod
    def handle_token_invites(
        token: str,
        invite_queue: Queue,
        nickname: str,
        proxy_mode: Optional[str],
        static_proxy: Optional[str],
        useragent: str,
        delay_min: int,
        delay_max: int,
        proxy_list: Optional[list[str]] = None
    ) -> None:
        """Handle multiple invite joins for a single token using a queue."""

        session_id, ws, interval = get_session_id(token)
        if ws:
            print(f"{NexusColor.GREEN}Connected. Session ID: {session_id}")
            keep_session_alive(ws, interval)

        while not invite_queue.empty():
            try:
                invite = invite_queue.get_nowait()
            except:
                break

            if not invite or not isinstance(invite, str):
                continue

            proxy = None
            if proxy_mode == "rotating" and proxy_list:
                proxy = random.choice(proxy_list)
            elif proxy_mode in ("per-token", "static"):
                proxy = static_proxy
            proxy = proxy or ""
            useragent = useragent or ""
            nickname = nickname or ""

            nexus = NexusTokenJoiner(
                nickname=nickname,
                _proxy=proxy,
                useragent=useragent,
                filling=True
            )
            nexus.accept_invite(invite, token, proxy, session_id)

            if config()["delay"]["enabled"]:
                time.sleep(random.uniform(delay_min, delay_max))

            invite_queue.task_done()

    @staticmethod
    def save_results(invite: str) -> None:
        """Save successfully joined tokens to a file."""
        with open(f"Output/joined_{invite}.txt", "w", encoding="utf-8") as f:
            for token in NexusStats.joined:
                f.write(token + "\n")

    @staticmethod
    def print_summary() -> None:
        """Print a summary of the join operation."""
        print(
            f"{NexusLogging.LC} {NexusColor.LIGHTBLACK}Joined: {NexusColor.GREEN}{len(NexusStats.joined)}"
            f"{NexusColor.LIGHTBLACK} | Failed: {NexusColor.RED}{NexusStats.failed}"
            f"{NexusColor.LIGHTBLACK} | Total: {pink_gradient[2]}{len(NexusStats.joined) + NexusStats.failed}{NexusColor.RESET}"
        )
        input()

def main() -> None:
    """Main function to run the token joiner."""
    utils = Utils()
    discord = Discord()
    xcontext = None

    utils.clear()
    HandleSetup.show_initial_title()

    useragent = HandleSetup.fetch_user_agent()
    intro()

    proxy_mode = HandleSetup.handle_proxies(utils)

    if config()["join"]["token_filling"]:
        invite_list = HandleSetup.get_invite_links()

        HandleSetup.setup_headers(discord=discord, user_agent=useragent)
        nickname = HandleSetup.get_nickname()
        delay_min, delay_max = HandleSetup.get_delay()

        RunTokenJoiner.run_token_filling(
            invite_list, nickname, proxy_mode, useragent, delay_min, delay_max
        )
        return

    invite = HandleSetup.get_invite_link()
    HandleSetup.validate_invite(invite)

    location, guild_id, channel_id, type_ = utils.get_xcontext_values(
        invite=invite,
        token=utils.get_random_token(),
        proxie=proxy_mode
    )

    if guild_id:
        xcontext = (location, guild_id, channel_id, type_)

    HandleSetup.setup_headers(discord=discord, user_agent=useragent, xcontext=xcontext)

    nickname = HandleSetup.get_nickname()
    delay_min, delay_max = HandleSetup.get_delay()

    RunTokenJoiner.run_joiner(
        utils, invite, nickname, proxy_mode, useragent, delay_min, delay_max
    )

