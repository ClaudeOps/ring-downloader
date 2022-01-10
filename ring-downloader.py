#!/usr/bin/env python3
"""
ring-downloader
Download doorbell videos from you Ring account.
NOTE: Currently Ring.com does not provide an official API so
      this code can break without warning.

Thanks to tchellomello for his python-ring-doorbell module
found here: https://github.com/tchellomello/python-ring-doorbell
"""

import configparser
import json
import os
import pickle
from pathlib import Path

import pytz
from oauthlib.oauth2 import MissingTokenError
from ring_doorbell import Ring, Auth

CONFIG_DIR = os.path.expandvars("$HOME/.config/ringdl/")
CONFIG_FILE = f"{CONFIG_DIR}/config.ini"
PICKLE_FILE = f"{CONFIG_DIR}/ring-events.pickle"
CACHE_FILE = Path(f"{CONFIG_DIR}/token.cache")

CONFIG = configparser.ConfigParser()
CONFIG.read(CONFIG_FILE)
DOWNLOADFOLDER = CONFIG["DEFAULT"]["video_directory"]
USERNAME = CONFIG["DEFAULT"]["user_name"]
PASSWORD = CONFIG["DEFAULT"]["password"]


def download(bell, evnt):
    """
        Download the current event from the given doorbell.
        If the video is already in the download history or
        successfully downloaded then return True otherwise False.
    """
    event_id = evnt.get("id")

    event_time = evnt.get("created_at")
    filename = "".join(
        (
            f"{DOWNLOADFOLDER}/",
            f"{bell.name}-",
            f'{event_time.strftime("%Y%m%d_%H%M%S")}-',
            f"{event_id}.mp4",
        )
    )
    filename = filename.replace(" ", "_")

    print(filename)
    status = evnt.get("recording", {}).get("status")

    if status == "ready":
        try:
            bell.recording_download(event_id, filename=filename)
            os.utime(
                filename, (event_time.timestamp(), event_time.timestamp())
            )
            return True
        except Exception as ex:  # pylint: disable=broad-except
            print(ex)
            return False
    else:
        print(f"Event: {event_id} is {status}")
        return False


def token_updated(token):
    """
        Cache updated token to token file for next run
    """
    CACHE_FILE.write_text(json.dumps(token))


def otp_callback():
    """
        Get 2FA code from user
    """
    auth_code = input("2FA code: ")
    return auth_code


def main():
    """ Main function """
    if CACHE_FILE.is_file():
        auth = Auth(
            "RDL/0.1", json.loads(CACHE_FILE.read_text()), token_updated
        )
    else:
        auth = Auth("RDL/0.1", None, token_updated)
        try:
            auth.fetch_token(USERNAME, PASSWORD)
        except MissingTokenError:
            auth.fetch_token(USERNAME, PASSWORD, otp_callback())

    myring = Ring(auth)
    myring.update_data()

    try:
        with open(PICKLE_FILE, "rb") as handle:
            download_history = pickle.loads(handle.read())
    except FileNotFoundError:
        print(
            "Download history file missing. No problem. ",
            "We'll create a new one when we're finished.",
        )
        download_history = []

    devices = myring.devices()
    for doorbell in devices["doorbots"]:
        dlcount = 0
        count = 0
        doorbot = doorbell.name
        timezone = doorbell.timezone
        if timezone not in pytz.all_timezones:
            print(
                f"Could not find time zone {timezone}. ",
                "Setting to default timezone.",
            )
            timezone = None
        for current_event in doorbell.history(
                limit=200, retry=10, timezone=timezone
        ):
            count += 1
            if current_event.get("id") not in download_history:
                if download(doorbell, current_event):
                    download_history.append(current_event.get("id"))
                    # dl_status = "Successful"
                    dlcount += 1
                else:
                    # dl_status = "Failed"
                    pass
            else:
                # dl_status = "Skipping previous download"
                pass
            # print(f"{current_event.get('id')}: {dl_status}")
        print(f"{doorbot} videos downloaded: {dlcount} out of {count}")

    # don't let the pickle file grow too big. clean out some entries.
    download_history.sort(reverse=True)
    with open(PICKLE_FILE, "wb") as handle:
        pickle.dump(download_history[0:1000], handle)


if __name__ == "__main__":
    main()
