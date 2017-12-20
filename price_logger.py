## Standard libraries 
import json
import urllib2

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

## Custom libraries 
# Universal functions for all the exchanges 
from exchange_func import getticker, getopenorders, cancel, getorderhistory, getorder, getbalance, selllimit, getorderbook, buylimit, getbalances  
from telegramlib import telegram # my lib to work with Telegram   
import platformlib as platform  # detecting the OS and assigning proper folders 
from coinigylib import coinigy

coinigy = coinigy()
chat = telegram()
    
def append_line(data, filename):    
    with open(filename, 'ab') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(data)    
    
# List of cryptos to monitor   
markets_dict = {
'USDT-USD': 'KRKN', 
'USDT-BTC' : 'BTRX', 
'USDT-BTC' : 'BINA', 
'BTC-LTC' : 'BTRX', 
'BTC-DASH' : 'BTRX', 
'BTC-MUSIC' : 'BTRX', 
'BTC-XMR' : 'BTRX', 
'BTC-NEO' : 'BTRX', 
'BTC-ETH' : 'BTRX', 
'BTC-POWR' : 'BTRX',
'BTC-CTR' : 'BINA', 
'BTC-MUSIC' : 'BTRX', 
'XBT-USD' : 'BMEX'   
}

usdt_exchanges_list = ['btrx', 'bnc']   # exchanges list 

markets = []
usdt_arr_min = []   # min for minute
file_dict = {} 
failed_attempts_dict = {}   # failed attempts 
time_failed = {} 

for elem, exch_use in markets_dict.iteritems():
    filename = 'price_log/' + elem + '_' + exch_use.lower() + '.csv'
    file_dict[elem] = filename  
    failed_attempts_dict[elem] = 0 

usdt_count = 0 
usdt_price_arr = np.ones(15) #15 1-min values 
usdt_collapse = False 

# Failed timer milestone 
for elem, exch_use in markets_dict.iteritems(): 
    time_failed[elem] =  time.time()
    # print "Orig time milestone", time_failed[elem] 

while True: # Logging the prices and checking what is up with USDT 
    
    # Timers on the start
    start_time = time.time()
    
    # Updating crypto prices 
    for elem, exch_use in markets_dict.iteritems(): 
    
        elem_ticker = elem.replace('-', '/') 
        try: 
            price = coinigy.price(elem_ticker, exch_use)
        except: 
            price = None 
        timestamp = time.time()
        date_time = datetime.fromtimestamp(timestamp)
        
        if price is not None: 
            print date_time, ':', elem, price 
            # Appending to the file 
            if elem <> 'USDT-USD': 
                append_line([timestamp, price], file_dict[elem])

            # Specifically for USDT 
            if elem == 'USDT-USD': 
                usdt_arr_min.append(float(price))
                usdt_count += 1    
                if usdt_count > 2:  # total 1 min
                    usdt_min_max = max(usdt_arr_min)
                    usdt_count = 0
                    usdt_arr_min = []
                    # appending and deleting so that we have a continuous price array 
                    usdt_price_arr = np.append(usdt_price_arr, usdt_min_max)
                    usdt_price_arr = np.delete(usdt_price_arr, [0])
                    print date_time, ':', 'USDT', usdt_min_max 
                    print '> USDT price array', usdt_price_arr
                
                # Checking for a collapse of USDT 
                if (usdt_price_arr.min() < 0.93) and (usdt_collapse == False): 
                    chat.send("Alarm: USDT-USD price has been below 0.93 for more than 15 minutes")
                    usdt_collapse = True 

                    # Getting BTC for the whole balance in a case of collapse 
                    # Buy depending on the platform 
                    for usdt_exch_abbr in usdt_exchanges_list: 
                        # USDT balance
                        if usdt_exch_abbr == 'btrx': 
                            exchange_usdt = 'bittrex'
                            comission_rate = 0.003
                        elif usdt_exch_abbr == 'bnc': 
                            exchange_usdt = 'binance'
                            comission_rate = 0.001
                        
                        balance = getbalance(exchange_usdt, 'USDT')
                        balance_avail = balance['Available'] * (1.0 - comission_rate)    
                    
                        if platform_run == 'Windows': 
                            cmd_str = cmd_init_buy + ' '.join(['now', usdt_exch_abbr, 'USDT', 'BTC', str(balance_avail)])     
                            # cmd_init_buy is 'start cmd /K python robot.py '
                        else: 
                            # Nix
                            cmd_str = cmd_init_buy + ' '.join(['now', usdt_exch_abbr, 'USDT', 'BTC', str(balance_avail)]) + '"'     
                        os.system(cmd_str)
        
        # If there are issues with getting the price 
        else: 
            # Notification about errors and logging to see what's up 
            print date_time, ':', elem, 'failed to get the price' 
            failed_attempts_dict[elem] += 1
            # Logging issues 
            append_line([date_time, elem, exch_use], 'price_log_issues.csv')
               
            if failed_attempts_dict[elem] >= 5: 
                time_failed_diff = time_failed[elem] - time.time()
                if time_failed_diff < 600:        
                    chat.send("Cannot get the price of " + elem + " for 10 minutes and 5 times in a row")
                    failed_attempts_dict[elem] = 0 
                    time_failed[elem] = time.time()
    # Timer 
    time_now = time.time() 
    time_diff = (math.ceil(time_now - start_time)) 
    # print "Cycle run time", time_diff
    if time_diff > 20: 
        time_sleep = 0 
    else: 
        time_sleep = 20 - time_diff     # as we will be measuring USDT per minute and then comparing 15-min intervals 
    
    time.sleep(time_sleep)  # so that the difference for usdt intervals is around a minute. There is ~ a sec per each element request 
