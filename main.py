import asyncio
import json
import logging
import os
import urllib
from datetime import datetime

import requests
import websockets
from dateutil.parser import parse as date_parse
from google.cloud import pubsub_v1

from secret_manager_utils import SecretsManagerUtils

PROJECT_ID = os.environ.get("GCP_PROJECT", "projectoceanis")
TOPIC = "options_events"

secret_manager_client = SecretsManagerUtils(PROJECT_ID)
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC)


async def publish(message):
    logging.info("publishing message...")
    data = message.encode('utf-8')
    future = publisher.publish(topic_path, data=data)
    logging.info(f"{future.result()}")


def unix_time_millis(dt):
    # Grab the starting point, so time '0'.
    epoch = datetime.utcfromtimestamp(0)
    return (dt - epoch).total_seconds() * 1000.0


def get_options_ids(symbol):
    uri = "https://api.tdameritrade.com/v1/marketdata/chains"
    querystring = {"apikey": "OMNIUSR@AMER.OAUTHAP", "symbol": symbol}
    response = requests.request("GET", uri, params=querystring).json()

    put_contracts = []
    call_contracts = []

    for contract_by_price in response["putExpDateMap"].values():
        for contract_data in contract_by_price.values():
            put_contracts.append(contract_data[0]["symbol"])

    for contract_by_price in response["callExpDateMap"].values():
        for contract_data in contract_by_price.values():
            call_contracts.append(contract_data[0]["symbol"])

    return put_contracts + call_contracts


def build_credentials(user_principals):
    # We need to get the timestamp in order to make our next request, but it needs to be parsed.
    token_timestamp = user_principals['streamerInfo']['tokenTimestamp']
    date = date_parse(token_timestamp, ignoretz=True)
    token_timestamp_ms = unix_time_millis(date)
    return {
        "userid": user_principals['accounts'][0]['accountId'],
        "token": user_principals['streamerInfo']['token'],
        "company": user_principals['accounts'][0]['company'],
        "segment": user_principals['accounts'][0]['segment'],
        "cddomain": user_principals['accounts'][0]['accountCdDomainId'],
        "usergroup": user_principals['streamerInfo']['userGroup'],
        "accesslevel": user_principals['streamerInfo']['accessLevel'],
        "authorized": "Y",
        "timestamp": int(token_timestamp_ms),
        "appid": user_principals['streamerInfo']['appId'],
        "acl": user_principals['streamerInfo']['acl']
    }


def build_login_request(user_principals):
    return {
        "requests": [
            {
                "service": "ADMIN",
                "requestid": "0",
                "command": "LOGIN",
                "account": user_principals['accounts'][0]['accountId'],
                "source": user_principals['streamerInfo']['appId'],
                "parameters": {
                    "credential": urllib.parse.urlencode(build_credentials(user_principals)),
                    "token": user_principals['streamerInfo']['token'],
                    "version": "1.0"
                }
            }
        ]
    }


def build_data_request(user_principals, symbols):
    return {
        "requests": [
            {
                "service": "OPTION",
                "requestid": "1",
                "command": "SUBS",
                "account": user_principals['accounts'][0]['accountId'],
                "source": user_principals['streamerInfo']['appId'],
                "parameters": {
                    "keys": ",".join(symbols),
                    "fields":
                        "0,1,2,3,4,5,6,7,8,9",
                }
            }
        ]
    }


def get_user_principals():
    url = "https://api.tdameritrade.com/v1/userprincipals"
    querystring = {"fields": "streamerSubscriptionKeys,streamerConnectionInfo"}
    access_token = secret_manager_client.get_secret_version("access_token")

    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.request("GET", url, headers=headers, params=querystring)

    return response.json()


class WebSocketClient:

    def __init__(self, user_principals):
        self.user_principals = user_principals

    async def connect(self):
        """
            Connecting to webSocket server
            websockets.client.connect returns a WebSocketClientProtocol, which is used to send and receive messages
        """
        # define the URI of the data stream, and connect to it.
        # uri = "ws://localhost:4001"
        uri = f"wss://{self.user_principals['streamerInfo']['streamerSocketUrl']}/ws"
        connection = await websockets.client.connect(uri)

        # if all goes well, let the user know.
        if connection.open:
            logging.info("Connection established. Client correctly connected.")
            return connection

    async def send_message(self, connection, message):
        """
            Sending message to webSocket server
        """
        await connection.send(message)

    async def receive_message(self, connection):
        """
            Receiving all server messages and handle them
        """
        while True:
            try:
                message = await connection.recv()
                message_decoded = json.loads(message)
                logging.info("_" * 100)
                logging.info(f"Received message from server.")

                if "data" in message_decoded and "cusip" not in message_decoded["data"][0]["content"][0]:
                    await publish(message)
                else:
                    logging.info(f"Message ignored: {message_decoded}")
                logging.info("_" * 100 + "\n")

            except websockets.exceptions.ConnectionClosed:
                logging.error("Connection with server closed.")
                break

            except Exception as err:
                logging.error(f"Unhandled error: {err}")
                pass


if __name__ == '__main__':
    symbol = "NVDA"
    user_principals = get_user_principals()
    option_ids = get_options_ids(symbol)
    login_request = json.dumps(build_login_request(user_principals))
    data_request = json.dumps(build_data_request(user_principals, option_ids))

    ws_client = WebSocketClient(user_principals)

    loop = asyncio.get_event_loop()

    # Start connection and get client connection protocol
    connection = loop.run_until_complete(ws_client.connect())
    loop.run_until_complete(ws_client.send_message(connection, login_request))
    loop.run_until_complete(ws_client.send_message(connection, data_request))

    loop.run_until_complete(asyncio.wait([
        ws_client.receive_message(connection),
        ws_client.receive_message(connection)
    ]))
