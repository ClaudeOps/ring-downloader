#!/usr/bin/env python3

from ring_doorbell import Ring
import os
import pytz
import pickle
import datetime
import configparser
CONFIG_DIR = os.path.expandvars("$HOME/.ringdl/")
CONFIG_FILE = f'{CONFIG_DIR}/config.ini'
PICKLE_FILE = f'{CONFIG_DIR}/ring-events.pickle'


def download(doorbell, event):
    eventId = event.get('id')
    if eventId in downloaded_events:
        return True
    else:
        doorbot = doorbell.name
        eventTime = event.get('created_at')
        filename = f'{downloadFolder}/{doorbot}-{eventTime.strftime("%Y%m%d_%H%M%S")}-{eventId}.mp4'
        filename = filename.replace(' ', '_')

        print(filename)
        status = event.get('recording', {}).get('status')

        if status == 'ready':
            try:
                doorbell.recording_download(eventId, filename=filename)
                os.utime(filename, (eventTime.timestamp(), eventTime.timestamp()))
                return True
            except Exception as ex:
                print(ex)
                return False
        else:
            print(f'Event: {eventId} is {status}')
            return False


config = configparser.ConfigParser()
config.read(CONFIG_FILE)

myring = Ring(config['DEFAULT']['user_name'], config['DEFAULT']['password'])
downloadFolder = config['DEFAULT']['video_directory']

try:
    with open(PICKLE_FILE, 'rb') as handle:
        downloaded_events = pickle.loads(handle.read())
except:
    print(f'Error opening pickle file')
    downloaded_events = []

# output = ''
for doorbell in myring.doorbells:
    dlcount = 0
    count = 0
    doorbot = doorbell.name
    timezone = doorbell.timezone
    if timezone not in pytz.all_timezones:
        print(f'Could not find time zone {timezone}. Setting to default timezone.')
        timezone = None
    for event in doorbell.history(limit=30, retry=10, timezone=timezone):
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
        # output += f'Doorbot:  {doorbot}-{count}\n'
        # output += f'ID:       {event.get("id")}\n'
        # output += f'Kind:     {event.get("kind")}\n'
        # output += f'When:     {event.get("created_at")}\n'
        # output += f'Download: {dlStatus}\n'
        # output += '--' * 50
        # output += '\n'

    print(f'{doorbot} videos downloaded: {dlcount} out of {count}')

#  print(output)
with open(PICKLE_FILE, 'wb') as handle:
    pickle.dump(downloaded_events, handle)
