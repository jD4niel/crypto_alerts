import hmac
import json
import hashlib
import time
import argparse
import urllib.request
import logging
from datetime import datetime, date, timedelta
import os, requests

logging.basicConfig(level=logging.INFO)

###### TELEGRAM KEYS ######
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
TOKEN = os.environ.get('TELEGRAM_TOKEN')

if not(CHAT_ID or TOKEN):
    logging.error(" === NOT TELEGRAM CHAT_ID OR TOKEN  ===")
    #sys.exit()

def send_message(message, not_send_message):
    if not_send_message:
        print(message)
        return message

    url =  "https://api.telegram.org/bot" + TOKEN
    if message:
        send_message = f"/sendMessage?chat_id={CHAT_ID}&text={message}"
        base_url = url + send_message
        return requests.get(base_url)

def get_server_time():
    url = "https://fapi.binance.com/fapi/v1/time"
    response = urllib.request.urlopen(url).read()
    return json.loads(response.decode())["serverTime"]


def get_klines(symbol, interval, limit):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = f"?symbol={symbol}&interval={interval}&limit={limit}"
    response = urllib.request.urlopen(url + params).read()
    klines = json.loads(response.decode())
    return [[float(x) for x in line] for line in klines]


def get_rsi(symbol, interval, period):
    klines = get_klines(symbol, interval, period + 1)
    closes = [line[4] for line in klines]
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    if avg_loss == 0:
        return f"Error on calculation - {avg_loss}"
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)


def get_all_symbols():
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    response = urllib.request.urlopen(url).read()
    exchange_info = json.loads(response.decode())
    symbols = [symbol["symbol"] for symbol in exchange_info["symbols"] if symbol["contractType"] == "PERPETUAL" and symbol["quoteAsset"] == "BUSD"]
    return symbols


def parse_interval(interval):
    """
    Converts the interval string in the format of '1m', '3m', '5m', '15m', '30m', '1h'
    into a timedelta object representing the interval in minutes.
    """
    if interval.endswith('m'):
        minutes = int(interval[:-1])
        return timedelta(minutes=minutes)
    elif interval.endswith('h'):
        hours = int(interval[:-1])
        return timedelta(hours=hours)
    else:
        raise ValueError(f"Invalid interval format: {interval}")


def main(interval, up, down, show_logs, not_send_message):
    interval_td = parse_interval(interval)
    while True:
        symbols = get_all_symbols()
        message = ""
        for symbol in symbols:
            try:
                rsi = get_rsi(symbol, interval, 14)
                if not show_logs:
                    logging.info(f"{datetime.now().strftime('%H:%M:%S %d-%m-%Y')} - {symbol} RSI: {rsi} ")
                if isinstance(rsi, float):
                    if rsi > up:
                        message += f"{symbol} RSI-{ interval } { rsi } above {up} SHORT\n"
                    elif rsi < down:
                        message += f"{symbol} RSI { interval } { rsi } below {down} LONG\n"

            except Exception as e:
                message += f"Error getting RSI { interval } { rsi } for {symbol}: {e}\n"
                logging.error(message)

        if message:
            logging.info(message)
            send_message(message, not_send_message)
        else:
            logging.error("\n\n- - -   NOT TRADE OPPORTUNITIES :C     -  -  -\n\n")
        
        # Calculate the amount of time until the next scheduled run
        now = datetime.now()
        next_run = (now + interval_td) \
                    .replace(second=0, microsecond=0) # Round to nearest minute
        sleep_time = (next_run - now).total_seconds()
        logging.info(f"sleep_time: {sleep_time} ")
        # Sleep until the next scheduled run
        time.sleep(sleep_time)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("interval", default="1m", nargs="?", help="Kline interval (default: %(default)s)")
    parser.add_argument("up", type=float, default=90, nargs="?", help="Upper RSI threshold (default: %(default)s)")
    parser.add_argument("down", type=float, default=10, nargs="?", help="Lower RSI threshold (default: %(default)s)")
    parser.add_argument('--no_show_logs', action='store_true', help='Prevent show all currency logs')
    parser.add_argument('--not_send_message', action='store_true', help='Prevent send telegram message')
    parser.add_argument("--h", action="store_true", help="Show help message")
    args = parser.parse_args()

    if args.h:
        print("""
==========================================================================
                BINANCE MULTI-ALERTS
==========================================================================
This script uses Binance's fapi API to go through all BUSD futures currency.
Alert when the RSI goes above the up parameter or below the down parameter. 
Usage: python script_name.py [interval] [up] [down] [--h] 
Arguments: 
interval   Kline interval (default: 1m) 
up         Upper RSI threshold (default: 90) 
down       Lower RSI threshold (default: 10)
==========================================================================
""")
    else:
        main(args.interval, args.up, args.down, args.no_show_logs, args.not_send_message)

