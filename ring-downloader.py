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
    if event_id in downloaded_events:
        return True

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


if CACHE_FILE.is_file():
    AUTH = Auth("RDL/0.1", json.loads(CACHE_FILE.read_text()), token_updated)
else:
    AUTH = Auth("RDL/0.1", None, token_updated)
    try:
        AUTH.fetch_token(USERNAME, PASSWORD)
    except MissingTokenError:
        AUTH.fetch_token(USERNAME, PASSWORD, otp_callback())

myring = Ring(AUTH)  # pylint: disable=invalid-name
myring.update_data()

try:
    with open(PICKLE_FILE, "rb") as handle:
        downloaded_events = pickle.loads(handle.read())
except FileNotFoundError:
    print(
        "Download history file missing. No problem. ",
        "We'll create a new one when we're finished.",
    )
    downloaded_events = []

DEVICES = myring.devices()
for doorbell in DEVICES["doorbots"]:
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
    for event in doorbell.history(limit=100, retry=10, timezone=timezone):
        count += 1
        if event.get("id") not in downloaded_events:
            if download(doorbell, event):
                downloaded_events.append(event.get("id"))
                dlStatus = "Successful"
                dlcount += 1
            else:
                dlStatus = "Failed"
        else:
            dlStatus = "Skipping previous download"

    print(f"{doorbot} videos downloaded: {dlcount} out of {count}")
# don't let the pickle file grow too big. clean out some entries.
downloaded_events.sort(reverse=True)
with open(PICKLE_FILE, "wb") as handle:
    pickle.dump(downloaded_events[0:1000], handle)
