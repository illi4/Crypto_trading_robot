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

# For kraken 
import urllib2
import json

## Custom libraries 
# Universal functions for all the exchanges 
from exchange_func import getticker, getopenorders, cancel, getorderhistory, getorder, getbalance, selllimit, getorderbook, buylimit, getbalances
from telegramlib import telegram # my lib to work with Telegram
import platformlib as platform  # detecting the OS and assigning proper folders 

# Platform
platform = platform.platformlib()
platform_run, cmd_init, cmd_init_buy = platform.initialise() 

chat = telegram()

usdt_price_arr = np.ones(15) #15 1-min values 
usdt_collapse = False 
kraken_attempts = 0 


####  Getting prices 
def get_price(market, exch_use): 
    try: 
        price = getticker(exch_use, market) 
    except: 
        price = None 
    return price

 
def append_line(data, filename):    # data = ['Timestamp', 'Price']
    with open(filename, 'ab') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(data)

##### Getting prices and writing into CSV 

exchange = 'bittrex'  # the main exchange for price monitoring 
usdt_exchanges_list = ['btrx', 'bnc']   # exchanges list 

# Prices for several cryptos 
markets_dict = {
'USDT-BTC' : 'bittrex', 
'BTC-LTC' : 'bittrex', 
'BTC-DASH' : 'bittrex', 
'BTC-XMR' : 'bittrex', 
'BTC-NEO' : 'bittrex', 
'BTC-ETH' : 'bittrex', 
'BTC-POWR' : 'bittrex',
'BTC-CTR' : 'binance'
}

markets = []
usdt_arr_min = []   # min for minute
file_dict = {} 
failed_attempts_dict = {}   # failed attempts 

for elem, exch_use in markets_dict.iteritems():
    filename = 'price_log/' + elem + '.csv'
    file_dict[elem] = filename  
    failed_attempts_dict[elem] = 0 

usdt_count = 0 
    
while True: # Logging the prices and checking what is up with USDT 

    # Updating crypto prices 
    for elem, exch_use in markets_dict.iteritems(): 
        price = get_price(elem, exch_use)
        timestamp = time.time()
        date_time = datetime.fromtimestamp(timestamp)
        if price is not None: 
            print date_time, ':', elem, price 
            # Appending to the file 
            append_line([timestamp, price], file_dict[elem])
            time.sleep(1)  # just not to bombard the exchange with requests
        else: 
            # Notification about errors 
            print date_time, ':', elem, 'failed to get the price' 
            failed_attempts_dict[elem] += 1
            if failed_attempts_dict[elem] >= 5: 
                chat.send("Cannot get the price of " + elem + " for several minutes")
                failed_attempts_dict[elem] = 0 
            
        
    time.sleep(14) 
