## Standard libraries 
import decimal
from decimal import Decimal
import math 

import time
from time import localtime, strftime
import pandas as pd 
import numpy as np
import csv
from datetime import datetime
import sys
from sys import exit, argv
import os
import urllib2
import json

## Custom libraries 
# Universal functions for all the exchanges 
from exchange_func import getticker, getopenorders, cancel, getorderhistory, getorder, getbalance, selllimit, detect_exchange, getorderbook, buylimit, getbalances
from telegramlib import telegram # my lib to work with Telegram
import platformlib as platform  # detecting the OS and assigning proper folders 

# Platform
platform = platform.platformlib()
platform_run, cmd_init, cmd_init_buy = platform.initialise() 

chat = telegram()


####  Getting prices 
def get_price(market): 
    try: 
        price = getticker(exchange, market) 
    except: 
        price = None 
    return price


def append_line(data, filename):     
    with open(filename, 'ab') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(data)

##### Getting prices and writing into CSV 
exchange = 'bittrex'        # at least for now 

# Prices for several cryptos 
markets_list = ['USDT-BTC', 'BTC-LTC', 'BTC-DASH', 'BTC-XMR', 'BTC-NEO', 'BTC-ETH', 'BTC-POWR']
markets = []
usdt_arr_min = []   # min for minute

for elem in markets_list: 
    filename = 'price_log/' + elem + '.csv'
    markets_dict = {'crypto' : elem, 'file': filename} 
    markets.append(markets_dict )

usdt_count = 0 
    
while True: # Logging the prices  
    # Updating crypto prices 
    for elem in markets:         
        price = get_price(elem['crypto'])
        timestamp = time.time()
        date_time = datetime.fromtimestamp(timestamp)
        if price is not None: 
            print date_time, ':', elem['crypto'], price 
            # Appending to the file 
            append_line([timestamp, price], elem['file'])
            time.sleep(1)  # just not to bombard the exchange with requests
        else: 
            print date_time, ':', elem['crypto'], 'failed to get the price' 
        
    time.sleep(20) # sleeping  

