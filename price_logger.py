################################ Libraries ############################################
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

# Universal functions for all the exchanges 
from exchange_func import getticker, getopenorders, cancel, getorderhistory, getorder, getbalance, selllimit, getorderbook, buylimit, getbalances  
from telegramlib import telegram # my lib to work with Telegram   
import platformlib as platform  # detecting the OS and assigning proper folders 
from coinigylib import coinigy

################################ Functions ############################################
def append_line(data, filename):    
    with open(filename, 'ab') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(data)    

################################ Config ############################################
coinigy = coinigy()
chat = telegram()
 
platform = platform.platformlib()
platform_run, cmd_init, cmd_init_buy = platform.initialise()     
        
# Directories to copy (if needed - I am using this for backing up data) 
dir_from = '/home/illi4/Robot/price_log'
dir_to = '/home/illi4/Dropbox/Exchange/price_log'

# List of cryptos   
markets_list = [
    ['BTC-CTR' , 'BINA'], 
    ['BTC-MUSIC' , 'BTRX'], 
    ['USDT-USD', 'KRKN'], 
    ['USDT-BTC', 'BTRX'], 
    ['XBT-USD' , 'BMEX'], 
    ['XRPH18', 'BMEX'], 
    ['ETHH18', 'BMEX'], 
    ['BCHF18', 'BMEX'], 
    ['DASHH18', 'BMEX'], 
    ['ETC7D', 'BMEX'], 
    ['LTCH18', 'BMEX'], 
    ['XMRH18', 'BMEX'], 
    ['ZECH18', 'BMEX']    
]

################################ Code ############################################

usdt_exchanges_list = ['btrx', 'bina']   # exchanges list where you hold USDT - if it collapses, USDT is sold immediately

markets = []
usdt_arr_min = []   # min for minute
file_dict = {} 
failed_attempts_dict = {}   # failed attempts 
time_failed = {} 

for elem in markets_list:
    # There is an exception for bitmex and the naming there
    if elem[0] == 'XBT-USD' and elem[1] == 'BMEX': 
        name_id = 'USD-BTC_bmex'
        filename = 'price_log/' + name_id + '.csv'
        file_dict['XBT-USD_bmex'] = filename  
    else:     
        name_id = elem[0] + '_' + elem[1].lower()
        filename = 'price_log/' + name_id + '.csv'
        file_dict[name_id] = filename  
    failed_attempts_dict[elem[0]] = 0 
 
usdt_count = 0 
usdt_price_arr = np.ones(15) #15 1-min values 
usdt_collapse = False 

# Failed timer milestone 
for elem in markets_list: 
    time_failed[elem[0]] =  time.time()    

# For directories copying (remove if you do not need this)  
start_time_dir_copy = time.time()

# Logging the prices and checking what is up with USDT 
while True: 
    # Timers on the start
    start_time = time.time()
    
    # Copy files to dropbox if needed (price data) every hour 
    if (start_time - start_time_dir_copy) > 3600: 
        start_time_dir_copy = start_time
        os.system('cp -R ' + dir_from + ' ' + dir_to)
    
    # Updating crypto prices 
    for elem in markets_list: 
        name_id = elem[0] + '_' + elem[1].lower()
        elem_ticker = elem[0].replace('-', '/') 
        try: 
            price = coinigy.price(elem[1], elem_ticker)
        except: 
            price = None 
        timestamp = time.time()
        date_time = datetime.fromtimestamp(timestamp)
        print date_time, ':', elem[0], elem[1], price 
        
        if price is not None: 
            # Appending to the file 
            if elem[0] <> 'USDT-USD': 
                append_line([timestamp, price], file_dict[name_id])
                #print "Folder:", file_dict[name_id]

            # Specifically for USDT 
            if elem[0] == 'USDT-USD': 
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
                        if platform_run == 'Windows': 
                            cmd_str = cmd_init_buy + ' '.join(['now', usdt_exch_abbr, 'USDT', 'BTC' ])       # buying for the whole balance     
                            # cmd_init_buy is 'start cmd /K python robot.py '
                        else: 
                            # Nix
                            cmd_str = cmd_init_buy + ' '.join(['now', usdt_exch_abbr, 'USDT', 'BTC' ]) + '"'     # buying for the whole balance     
                        os.system(cmd_str)
        
        # If there are issues with getting the price 
        else: 
            # Notification about errors and logging to see what's up 
            print date_time, ':', elem[0], 'failed to get the price' 
            failed_attempts_dict[elem[0]] += 1
            # Logging issues 
            append_line([date_time, elem[0], elem[1]], 'price_log_issues.csv')
               
            if failed_attempts_dict[elem[0]] >= 5: 
                time_failed_diff = time_failed[elem[0]] - time.time()
                if time_failed_diff < 600:        
                    chat.send("Cannot get the price of " + elem[0] + " for 10 minutes and 5 times in a row")
                    failed_attempts_dict[elem[0]] = 0 
                    time_failed[elem[0]] = time.time()
        # Sleep for just a bit 
        time.sleep(0.2) 
    # Timer 
    time_now = time.time() 
    time_diff = (math.ceil(time_now - start_time)) 
    # print "Cycle run time", time_diff
    if time_diff > 20: 
        time_sleep = 0 
    else: 
        time_sleep = 20 - time_diff     # as we will be measuring USDT per minute and then comparing 15-min intervals 
    
    time.sleep(time_sleep)  # so that the difference for usdt intervals is around a minute. There is ~ a sec per each element request 
