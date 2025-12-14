"""Startup Files which stores A HandleSetup Class."""

from typing import Optional, Tuple, Union

import time
import sys
import os

from bs4 import BeautifulSoup

import requests

from Helper import Utils, NexusLogging, NexusColor, config


class HandleSetup:
    """A class responsible for handling various setup tasks for the Token Joiner tool."""

    @staticmethod
    def fetch_user_agent() -> str:
        """Fetch user agent from the remote source."""
        try:
            response = requests.get(
                "https://quicklyy.fun/api/tools/user-agent",
                timeout=5,
            )
            data = response.json()
            return data.get("userAgent")
        except requests.RequestException as e:
            print(
                f"{NexusLogging.LC} {NexusColor.RED}Failed to fetch user agent: {e}{NexusColor.RESET}"
            )
            sys.exit(
                "Error fetching user agent. Exiting..."
            )

    @staticmethod
    def show_initial_title():
        """Display the initial title with an option to skip the animation."""
        Utils.new_title(
            "Token Joiner discord.gg/nexus-tools ┃ Press S to skip animation"
        )

    @staticmethod
    def setup_headers(discord, user_agent: str, xcontext: tuple = None):
        """Set up headers for the Discord instance."""
        print(
            f"{NexusLogging.LC} {NexusColor.LIGHTBLACK}Building Headers...{NexusColor.RESET}"
        )
        discord.fill_headers(token="", user_agent=user_agent, xcontext=xcontext)
        print(
            f"{NexusLogging.LC} {NexusColor.GREEN}Headers Built!{NexusColor.RESET}"
        )

    @staticmethod
    def handle_proxies(
        utils_instance,
    ) -> Optional[str]:
        """Handle proxy usage based on user input."""
        if utils_instance.load("Input/proxies.txt") != 0:
            if config["proxy"]["enabled"]:
                return config["proxy"]["mode"]

        return None

    @staticmethod
    def get_invite_link() -> str:
        """Get and sanitize the invite link from the user."""
        invite = input(
            f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Invite:{NexusColor.NEXUS} "
        ).strip()
        if ".gg/" in invite:
            return invite.split(".gg/")[1]
        if "invite/" in invite:
            return invite.split("invite/")[1]
        return invite

    @staticmethod
    def get_invite_links() -> list[str]:
        """Get invite links from file."""
        invite_file = input(
            f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Invite Links File (.txt):{NexusColor.NEXUS} "
        ).strip().replace('"', '')
        try: 
            with open(invite_file, "r", encoding="utf-8") as file:
                invites = [
                    invite.strip().split(".gg/")[1] if ".gg/" in invite else
                    invite.strip().split("invite/")[1] if "invite/" in invite else
                    invite.strip()
                    for invite in file.readlines()
                ]
                if not invites:
                    print(f"{NexusLogging.LC}{NexusColor.RED} Invites Failed to loas or file is empty!{NexusColor.NEXUS}")
                    sys.exit(1)
                print(f"{NexusLogging.LC}{NexusColor.GREEN} Successfully loaded invites list!{NexusColor.NEXUS}")
                return invites
        except FileNotFoundError:
            ValueError("File does not exist!")


    @staticmethod
    def validate_invite(invite: str):
        """Validate the Discord invite link."""
        url = f"https://discord.com/api/v9/invites/{invite}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(
                    f"{NexusLogging.LC} {NexusColor.LIGHTBLACK}Invite -> {NexusColor.GREEN}Valid{NexusColor.RESET}"
                )
            elif response.status_code == 429:
                print(
                    f"{NexusLogging.LC} {NexusColor.RED}Rate Limited. Continuing without checking.{NexusColor.RESET}"
                )
            else:
                print(
                    f"{NexusLogging.LC} {NexusColor.LIGHTBLACK}Invite -> {NexusColor.RED}Invalid{NexusColor.RESET}"
                )
                time.sleep(2)
                sys.exit("Invalid invite. Exiting...")
        except requests.RequestException as e:
            print(
                f"{NexusLogging.LC} {NexusColor.RED}Failed to validate invite: {e}{NexusColor.RESET}"
            )
            sys.exit("Error validating invite. Exiting...")

    @staticmethod
    def get_nickname() -> Optional[str]:
        """Prompt the user for a nickname."""
        if config["appearance"]["ask_in_ui"]:
            if (
                input(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Change Nick? (y/n):{NexusColor.NEXUS} "
                )
                .strip()
                .lower()
                == "y"
            ):
                nickname = input(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Nickname:{NexusColor.NEXUS} "
                ).strip()
                print(
                    f"{NexusLogging.LC} {NexusColor.LIGHTBLACK}Nickname -> {NexusColor.GREEN}{nickname}{NexusColor.RESET}"
                )
                return nickname
            return None
        
        if config["appearance"]["nickname_enabled"]:
            return config["appearance"]["nickname"]

    @staticmethod
    def get_delay() -> tuple[int, int] | tuple[None, None]:
        """Prompt the user for joining delay."""
        
        def delay_prompt(prompt: str) -> int:
            while True:
                try:
                    return int(input(prompt).strip())
                except ValueError:
                    print(f"{NexusLogging.LC}{NexusColor.RED} Invalid input. Please enter a valid integer.{NexusColor.RESET}")

        if config["delay"]["ask_in_ui"]:
            confirm = input(
                f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Join Delay? (y/n):{NexusColor.NEXUS} "
            ).strip().lower()

            if confirm == "y":
                delay_min = delay_prompt(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Minimum Delay (in seconds):{NexusColor.NEXUS} "
                )
                print(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Minimum Delay set to -> {NexusColor.GREEN}{delay_min}{NexusColor.RESET}"
                )

                delay_max = delay_prompt(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Maximum Delay (in seconds):{NexusColor.NEXUS} "
                )
                print(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Maximum Delay set to -> {NexusColor.GREEN}{delay_max}{NexusColor.RESET}"
                )

                return delay_min, delay_max

            return None, None

        if config["delay"]["enabled"]:
            return config["delay"]["min"], config["delay"]["max"]

        return None, None


        

    @staticmethod
    def get_vcjoin() -> int:
        
        confirm = input(
            f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Join VC? (y/n):{NexusColor.NEXUS} "
        ).strip().lower()
        
        if confirm == "y":
                channel_id = input(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Channel ID:{NexusColor.NEXUS} "
                ).strip()
                
                try:
                    channel_id = int(channel_id)
                    print(
                        f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Joining VC -> {NexusColor.GREEN}{channel_id}{NexusColor.RESET}"
                    )
                    return channel_id
                except ValueError:
                    print(
                        f"{NexusLogging.LC}{NexusColor.RED} Invalid input. Please enter a valid channel id.{NexusColor.RESET}"
                    )

    @staticmethod
    def get_image() -> str:
        """
        Prompt the user to input an image URL or file path, 
        then convert the image to a Base64 string.
        """
        while True:
            choice = input(
                f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Enter image source - URL (u) or Path (p): {NexusColor.NEXUS}"
            ).strip().lower()

            if choice == "u":
                image_url = input(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Enter Image URL: {NexusColor.NEXUS}"
                ).strip()
                
                if not image_url.startswith(("http://", "https://")):
                    print(
                        f"{NexusLogging.LC}{NexusColor.RED} Invalid URL. Please provide a valid URL.{NexusColor.RESET}"
                    )
                    continue

                try:
                    path = Utils.download_image(url=image_url)
                    return Utils.image_to_base64(image_path=path)
                except Exception as e:
                    print(
                        f"{NexusLogging.LC}{NexusColor.RED} Error: {e}{NexusColor.RESET}"
                    )

            elif choice == "p":
                image_path = input(
                    f"{NexusLogging.LC}{NexusColor.LIGHTBLACK} Enter Image Path (Drag & Drop): {NexusColor.NEXUS}"
                ).strip()

                if not os.path.isfile(image_path):
                    print(
                        f"{NexusLogging.LC}{NexusColor.RED} Invalid file path. Please provide a valid path.{NexusColor.RESET}"
                    )
                    continue

                try:
                    return Utils.image_to_base64(image_path=image_path)
                except Exception as e:
                    print(
                        f"{NexusLogging.LC}{NexusColor.RED} Error: {e}{NexusColor.RESET}"
                    )

            else:
                print(
                    f"{NexusLogging.LC}{NexusColor.RED} Invalid input. Please type 'u' for URL or 'p' for Path.{NexusColor.RESET}"
                )

