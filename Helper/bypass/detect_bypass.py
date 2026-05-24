"""Python File Which Contains a class to detect bypasses."""
from typing import Dict, Optional

import curl_cffi.requests

from bs4 import BeautifulSoup

from Helper.Utils.logging import NexusLogging
from Helper.NexusColors.color import NexusColor
from Helper.Utils.utils import config, Discord


class DetectBypass:
    """Class For detection Bypasses."""
    def __init__(
        self,
        token: str,
        guildid: int,
        useragent: str,
        cfsession,
        proxy: str | None = None,
    ) -> None:
        """Initializes the class DetectBypass class."""
        self.session = curl_cffi.requests.Session(impersonate="chrome")

        self.cfsession = cfsession
        
        self.proxy: str = proxy
        self.token: str = token
        self.guildid: int = guildid
        self.headers: Dict[str, str] = self.build_detect_headers(
            useragent=useragent, token=token
        )
        
        if self.proxy:
            self.session.proxies = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
            }

    def build_detect_headers(self, useragent: str, token: str) -> Dict[str, str]:
        version = Discord.extract_version(useragent)
        return {
            "authority": "discord.com",
            "accept": "*/*",
            "accept-language": "en-US",
            "authorization": token,
            "content-type": "application/json",
            "origin": "https://discord.com",
            "priority": "u=1, i",
            "referer": "https://discord.com/channels/@me",
            "sec-ch-ua": f'"Google Chrome";v="{version}", "Chromium";v="{version}", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": useragent,
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "en-US",
            "x-discord-timezone": "Europe/Berlin",
            "x-super-properties": Discord.build_properties(user_agent=useragent)
        }
        

    def check_onboarding(self) -> Optional[bool]:
        """Check if the guild has onboarding."""
        response = self.session.get(
            f"https://discord.com/api/v9/guilds/{self.guildid}/onboarding",
            headers=self.headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("enabled"):
                return True
            return False

        return None

    def check_rules(self) -> Optional[bool]:
        """Check if the guild has check rules."""
        response = self.session.get(
            f"https://discord.com/api/v9/guilds/{self.guildid}/member-verification?with_guild=false&invite_code=",
            headers=self.headers,
            timeout=10
        )

        if response.status_code == 200:
            return True
        if response.status_code == 403:
            return False
        return None

    def extract_clientid(self, text: str) -> Optional[str]:
        """Extracts client id for restorecord bypass."""
        try:
            soup = BeautifulSoup(text, "html.parser")
            verify_link = soup.find(
                "a", href=True, text="Verify"
            )

            client_id = None
            if verify_link:
                href = verify_link["href"]
                if "client_id=" in href:
                    client_id = href.split("client_id=")[
                        1
                    ].split("&")[0]

            return client_id
        except Exception as e:
            NexusLogging.print_status(
                token=self.token,
                message=f"Error: {e}",
                color=NexusColor.RED,
            )
            return None

    def check_restorecord(self) -> Optional[int]:
        """Check if the guild has restorecord."""
        if not self.proxy:
            return False

        proxies = {
            "http": f"http://{self.proxy}",
            "https": f"http://{self.proxy}",
        }

        captcha_encounters = 0

        for attempt in range(5):
            response = self.cfsession.get(
                f"https://restorecord.com/verify/{self.guildid}",
                proxies=proxies
                )

            if response.status_code in [307, 200]:
                client_id = self.extract_clientid(
                    response.text
                )
                return client_id

            if (
                "Please complete the captcha to continue"
                in response.text
            ):
                captcha_encounters += 1
                if config()["debug"]:
                    NexusLogging.print_status(
                        token=self.token,
                        message=f"Error encountered while attempting to detect Restorecord: {NexusColor.LIGHTBLACK}Cloudflare",
                        color=NexusColor.RED,
                    )
            else:
                NexusLogging.print_error(
                    token=self.token,
                    message=f"Unexpected error on attempt {attempt + 1} while detecting Restorecord",
                    response=response,
                )
                break
                

        if captcha_encounters == 5:
            NexusLogging.print_status(
                token=self.token,
                message=f"Error encountered while attempting to detect Restorecord: {NexusColor.LIGHTBLACK}Cloudflare",
                color=NexusColor.RED,
            )
            return False
