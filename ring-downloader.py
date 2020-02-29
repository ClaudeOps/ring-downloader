#!/usr/bin/env python3

import configparser
import json
import os
import pickle
from pathlib import Path
import pytz
from oauthlib.oauth2 import MissingTokenError
from ring_doorbell import Ring, Auth

CONFIG_DIR = os.path.expandvars("$HOME/.ringdl/")
CONFIG_FILE = f'{CONFIG_DIR}/config.ini'
PICKLE_FILE = f'{CONFIG_DIR}/ring-events.pickle'
CACHE_FILE = Path('token.cache')


def download(doorbell, event):
    eventId = event.get('id')
    if eventId in downloaded_events:
        return True

    doorbot = doorbell.name
    eventTime = event.get('created_at')
    filename = ''.join((f'{downloadFolder}/',
                        f'{doorbot}-',
                        f'{eventTime.strftime("%Y%m%d_%H%M%S")}-',
                        f'{eventId}.mp4'))
    filename = filename.replace(' ', '_')

    print(filename)
    status = event.get('recording', {}).get('status')

    if status == 'ready':
        try:
            doorbell.recording_download(eventId, filename=filename)
            os.utime(
                filename,
                (eventTime.timestamp(), eventTime.timestamp())
            )
            return True
        except Exception as ex:
            print(ex)
            return False
    else:
        print(f'Event: {eventId} is {status}')
        return False


def token_updated(token):
    CACHE_FILE.write_text(json.dumps(token))


def otp_callback():
    auth_code = input("2FA code: ")
    return auth_code


config = configparser.ConfigParser()
config.read(CONFIG_FILE)

if CACHE_FILE.is_file():
    auth = Auth("RDL/0.1", json.loads(CACHE_FILE.read_text()), token_updated)
else:
    USERNAME = config['DEFAULT']['user_name']
    PASSWORD = config['DEFAULT']['password']
    auth = Auth("RDL/0.1", None, token_updated)
    try:
        auth.fetch_token(USERNAME, PASSWORD)
    except MissingTokenError:
        auth.fetch_token(USERNAME, PASSWORD, otp_callback())

myring = Ring(auth)
myring.update_data()
downloadFolder = config['DEFAULT']['video_directory']

try:
    with open(PICKLE_FILE, 'rb') as handle:
        downloaded_events = pickle.loads(handle.read())
except Exception as ex:
    print(f'Error opening pickle file')
    print(ex)
    downloaded_events = []

devices = myring.devices()

# output = ''
for doorbell in devices['doorbots']:
    dlcount = 0
    count = 0
    doorbot = doorbell.name
    timezone = doorbell.timezone
    if timezone not in pytz.all_timezones:
        print(
            f'Could not find time zone {timezone}. ',
            'Setting to default timezone.'
        )
        timezone = None
    for event in doorbell.history(limit=300, retry=10, timezone=timezone):
        count += 1
        if event.get('id') not in downloaded_events:
            if download(doorbell, event):
                downloaded_events.append(event.get("id"))
                dlStatus = "Successful"
                dlcount += 1
            else:
                dlStatus = "Failed"
        else:
            dlStatus = 'Skipping previous download'

    print(f'{doorbot} videos downloaded: {dlcount} out of {count}')

with open(PICKLE_FILE, 'wb') as handle:
    pickle.dump(downloaded_events, handle)
