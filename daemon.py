################################ Libraries ############################################
## Standard libraries 
import os
import time
import sys
from sys import exit, argv
from time import localtime, strftime
import subprocess   
import math
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import urllib2
from decimal import Decimal
from openpyxl import Workbook, load_workbook   
from openpyxl.styles import Font, Fill
import json # requests
from shutil import copyfile # to copy files

## Custom libraries 
from telegramlib import telegram                                # library to work with Telegram messemger
from sqltools import query_lastrow_id, query            # proper requests to sqlite db
from loglib import logfile                                              # logging
import platformlib as platform                                      # detecting the OS and assigning proper folders 
from coinigylib import coinigy                                      # library to work with coinigy 

coinigy = coinigy()

# Universal functions for all exchanges, custom built       
from exchange_func import getticker, getopenorders, cancel, getorderhistory, getorder, getbalance, selllimit, getorderbook, buylimit, getbalances

# Platform
platform = platform.platformlib()
platform_run, cmd_init, cmd_init_buy = platform.initialise() 
 
#################### For Telegram integration ###############################################################
chat = telegram()

comm_method = 'chat' # 'mail' or 'chat', chat is preferable for the smooth experience 
send_messages = True

######################################################################################
############################## MONITORING BOT ######################################
#####################################################################################

# A few commonly used functions             
def telegram_buy(wf_id = None):  
    global platform_run, cmd_init_buy, chat
    print cmd_init_buy 
    
    reply_string = 'Specify the parameters: mode exchange source_currency-buy_currency [total_in_source currency] [price] [time limit for the price in minutes].'\
    '\nExchanges: btrx / bina / bmex (abbreviations for bittrex, binance, bitmex). Some examples:\n'
    reply_string += '4h bmex usd-btc 0.05\n'
    reply_string += 'now bmex XRPH18 -0.1\n'
    reply_string += 'brk btrx btc-powr 0.5 0.000095\n'
    reply_string += 'Modes: reg/brk/now/reg-s/brk/4h/fullta, add -s (reg-s) for simulation' 
    chat.send(reply_string) 

    # Wait for a response
    msg_text = chat.get_response()

    try:
        # Starting a new process with a new task 
        msg_text_split = msg_text.split()
        # Processing params - should all be entered
        buy_mode = msg_text_split[0].lower()
        buy_exchange = msg_text_split[1].lower()
        
        buy_market = msg_text_split[2].upper()
        try:
            buy_trade, buy_currency = buy_market.split('-')
        except: 
            buy_trade = buy_market  # if only one market vs BTC is provided - e.g. XRPH18 on bitmex  
            buy_currency = 'BTC'
        
        try: 
            buy_total = msg_text_split[3]
        except: 
            buy_total = '' 
        
        try: 
            buy_price = msg_text_split[4]
        except: 
            buy_price = ''
        
        try:
            buy_time_limit = msg_text_split[5]
        except: 
            buy_time_limit = '' 
        
        if wf_id is not None: 
            sql_string = "UPDATE workflow SET market = '{}', trade = '{}', currency = '{}', exchange = '{}' WHERE wf_id = {}".format(buy_market, buy_trade, buy_currency, buy_exchange, wf_id) 
            job_id, rows = query_lastrow_id(sql_string)
            
        # Run depending on the platform
        if platform_run == 'Windows': 
            cmd_str = cmd_init_buy + ' '.join([buy_mode, buy_exchange, buy_market, buy_total, buy_price, buy_time_limit])
            # for Win, cmd_init_buy is 'start cmd /K python robot.py '
        else: 
            # Nix
            cmd_str = cmd_init_buy + ' '.join([buy_mode, buy_exchange, buy_market, buy_total, buy_price, buy_time_limit]) + '"'
            # for *Nix, cmd_init_buy is 'gnome-terminal --tab --profile Active -e "python /home/illi4/Robot/robot.py'   # we will also need to add params and close with "
        
        os.system(cmd_str)
        chat.send('Buy task requested')
        print ">>> Started a new buy job: ", cmd_str 
        
    except: 
        chat.send('Not all the mandatory parameters are specified')    
                
def telegram_sell(wf_id = None): 
    global platform_run, cmd_init, chat

    reply_string = 'Specify the parameters: mode exchange basic_currency-traded_currency entry_price take_profit_price stop_loss_price [limit_of_amount_to_sell] [sell_portion]'\
    '\nExchanges: btrx / bina / bmex (abbreviations for bittrex, binance, bitmex). Some examples:\n'
    reply_string += 'r bina btc-ltc 0.015 0.019 0.013 22\n'
    reply_string += 'r bmex usd-btc 15000 16700 14000\n'
    reply_string += 'brk btrx btc-powr 0.5 0.000095\n'
    reply_string += 'Modes: s/r/sns/rns/rnts\n'
    chat.send(reply_string)
        
    # Wait for a response
    msg_text = chat.get_response()

    # Starting a new process with a new task 
    msg_text_split = msg_text.split()
    
    # Processing params - should all be entered
    try: 
        run_simulation_param = msg_text_split[0].lower()
        run_exchange = msg_text_split[1].lower()   
        
        run_market = msg_text_split[2].upper()
        try:
            run_trade, run_currency = run_market.split('-')
        except: 
            run_trade = run_market  # if only one market vs BTC is provided - e.g. XRPH18 on bitmex  
            run_currency = 'BTC'
            
        run_price_curr = msg_text_split[3]
        run_tp = msg_text_split[4]
        run_sl = msg_text_split[5]
        
        try:
            run_limit_sell_amount = msg_text_split[6]
        except: 
            run_limit_sell_amount = ''
        try:
            run_sell_portion = msg_text_split[7]
        except: 
            run_sell_portion = ''

        # Run depending on the platform
        if platform_run == 'Windows': 
            cmd_str = cmd_init + ' '.join([run_simulation_param, run_exchange, run_market, run_price_curr, run_tp, run_sl, run_limit_sell_amount, run_sell_portion])
        else: 
            # Nix
            cmd_str = cmd_init + ' '.join([run_simulation_param, run_exchange, run_market, run_price_curr, run_tp, run_sl, run_limit_sell_amount, run_sell_portion]) + '"'
        os.system(cmd_str)
        
        # Check if launched  
        chat.send('Launching, hold on...')
        time.sleep(30)
        sql_string = "SELECT job_id FROM jobs WHERE market = '{}'".format(run_market.upper())
        rows = query(sql_string)

        try: 
            launched_confirmation = rows[0][0]   # first result if existing 
            print '>>> Started a new job on the market {}. Simulation mode: {}'.format(run_market.upper(), run_simulation_param)
            chat.send('Launched a new bot with these parameters')
        except:
            chat.send('The job was not launched')
    
    except: 
        chat.send('Not all the mandatory parameters are specified')

def telegram_long(): 
    chat.send('Enter information: exchange basic_curr altcoin entry_price quantity \nExample: btrx BTC QTUM 0.032 50')
    # Wait for a response
    msg_text = chat.get_response()

    # Starting a new process with a new task 
    msg_text_split = msg_text.split()
    # Processing params - should all be entered
    try: 
        long_exchange = msg_text_split[0].lower()
        long_trade = msg_text_split[1].upper()
        long_currency = msg_text_split[2].upper()
        long_ep = float(msg_text_split[3])
        long_quantity = float(msg_text_split[4])
        long_market = '{0}-{1}'.format(long_trade, long_currency)
        try:
            sql_string = "INSERT INTO longs(market, ep, quantity, exchange) VALUES ('{}', {}, {}, '{}')".format(long_market, long_ep, long_quantity, long_exchange)
            rows = query_lastrow_id(sql_string)
            chat.send('Inserted a record successfully')
        except: 
            chat.send('Error when inserting into DB')
    except: 
        chat.send('Not all the mandatory parameters are specified')
        
###################################### Starting the daemon #############################################
print '------------------------------------- \nWaiting for new instructions from Telegram.\n' 

while True:
    try:
        msg_text = chat.get_response()
    
        ###### Displaying help
        if msg_text.find('help') >= 0: 
            msg = "Start a new task: 'new' \nCheck running tasks: 'status' \nCancel tasks: 'abort'\n" + \
            "Check balances: 'balance' \nSell now: 'sellnow' \nSmart buy: 'buy' \n" + \
            "Cancel buy: 'stopbuy' \nStop monitoring: 'stop listener' "
            chat.send(msg)
            msg = 'Buy modes: reg/brk/now/reg-s/brk-s/4h/4h-s/fullta/fullta-s \nreg - buy at fixed price \nbrk - buy on breakout (above the specified price)\n'\
            'options with -s mean simulation mode \n'\
            '4h buys based on 4h price action \n'\
            'now buys immediately in real mode (or in simulation if there is simulation workflow) \n\n'\
            'fullta buys based on price action when lower time interval and higher time intervals are in line'
            chat.send(msg)
            msg = 'Job (task) modes: s/r/sns/rns/rnts \ns - simulation with stops \nr - real mode with stops and take profit \n'\
            'sns - simulation without stops \nrns - real mode with no stops (careful!) \n'\
            'rnts - real mode without trailing stops \n' 
            chat.send(msg)
            
        ###### Terminating
        elif msg_text.find('stoplistener') >= 0: 
            chat.send('Stopped message monitoring')
            exit(0)
        
        ####### Status 
        elif msg_text.find('status') >= 0: 
            no_profit_tasks = False 
            no_buy_tasks = False 
            no_longs = False 
            no_bb_tasks = False
            
            reply_string = '' 
            # Info from the DB - profit jobs
            # DB: id, market, tp, sl, simulation, mooning, selling, price_curr, percent_of, abort_flag
            reply_string_profit = '>> JOBS\n' 
            
            sql_string = "SELECT * FROM jobs"
            rows = query(sql_string)

            if rows == []: 
                no_profit_tasks = True
            else:
                for row in rows:
                    re_market = row[1]
                    re_tp = row[2]
                    re_sl = row[3]
                    # Direction of the trade
                    if float(re_tp) > float(re_sl): 
                        re_direction = '(L)' 
                    else: 
                        re_direction = '(S)' 
                        
                    re_simulation = row[4]
                    stop_loss = row[10]
                    
                    if bool(re_simulation) == True: 
                        if bool(stop_loss) == True: 
                            re_simulation = '(Simulation, SL)'
                        else: 
                            re_simulation = '(Simulation, no SL)'
                    else:
                        if bool(stop_loss) == True: 
                            re_simulation = '(Real, SL)'
                        else: 
                            re_simulation = '(Real, no SL)'
                            
                    re_mooning = row[5]
                    if bool(re_mooning) == 1:
                        descr_price = '% higher than original TP'
                    else:
                        descr_price = '% of EP'
                        
                    re_selling = row[6]
                    re_price_curr = row[7]
                    re_percent_of = row[8]
                    re_exchange = row[15]
                    
                    if bool(stop_loss) == True: 
                        reply_string_profit += "Running ({}) {}: {} {} {} {} \nTP: {} | SL: {}\nCurrent price: {}\n\n".format(re_exchange, re_market, re_percent_of, descr_price, re_simulation, re_direction, re_tp, re_sl, re_price_curr)
                    else: 
                        reply_string_profit += "Running ({}) {}: {} {} {} \nTP: {} \nCurrent price: {}\n\n".format(re_exchange, re_market, re_percent_of, descr_price, re_simulation, re_tp, re_price_curr)
                 
                
            # Info from the DB - buy jobs
            # DB: id, market, price_fixed, price, abort_flag
            reply_string_buy = '>> BUY\n' 
            
            sql_string = "SELECT * FROM buys"
            rows = query(sql_string)

            if rows == []: 
                no_buy_tasks = True
            else: 
                for row in rows:
                    re_b_market = row[1]
                    re_b_fixed = row[2]
                    re_b_price = row[3]
                    re_b_position = row[5]
                    if float(re_b_position) > 0: 
                        re_b_direction = '(L)' 
                    else: 
                        re_b_direction = '(S)' 
                    re_b_mode = row[6]
                    re_b_exchange = row[7]
                    if re_b_fixed == 0: 
                        price_descr = 'Floating'
                    else: 
                        price_descr = 'Fixed'
                    reply_string_buy += "Buying ({}) {} {}. {} price {}, mode {}. Total of: {}\n".format(re_b_exchange, re_b_direction, re_b_market, price_descr, re_b_price, re_b_mode, re_b_position)
            reply_string_buy += '\n'

            # Info from the DB - buybacks
            # DB: id, market, trade_price
            reply_string_bb = '>> BUYBACK\n' 
            sql_string = "SELECT * FROM bback"
            rows = query(sql_string)
            if rows == []: 
                no_bb_tasks = True
            else: 
                for row in rows:
                    bb_market = row[1]
                    bb_price = '{0:.6f}'.format(float(row[2])) # row[2] # 
                    bb_curr_price = '{0:.6f}'.format(float(row[3])) # row[3] #
                    bb_trade_price = row[4]
                    bb_exchange= row[6]
                    reply_string_bb += "{}: BB@ {}, current {}, trade of {} ({})\n".format(bb_market, bb_price, bb_curr_price, round(bb_trade_price, 3), bb_exchange)
            reply_string_bb += '\n'
            
            # Info from the DB - long-term holds
            # DB: id, market, EP, quantity
            reply_string_long = '>> HOLD\n' 
            
            sql_string = "SELECT * FROM longs"
            rows = query(sql_string)

            if rows == []: 
                no_longs = True
            else: 
                for row in rows:
                    re_l_market = row[1]
                    re_l_price = row[2]
                    re_l_q = row[3]
                    re_l_exchange = row[4]
                    if re_l_exchange == 'bina': 
                        re_l_exchange = 'binance' 
                    elif re_l_exchange == 'btrx': 
                        re_l_exchange = 'bittrex' 
                    re_l_curr_price = float(getticker(re_l_exchange, re_l_market))   
 
                    re_price_prop = round((re_l_curr_price/re_l_price)*100, 1)
                    reply_string_long += "{} ({}), current price: {} % of EP, Q: {}\n".format(re_l_market, re_l_exchange, re_price_prop, re_l_q)
            
            if (no_profit_tasks != True): 
                reply_string = reply_string + reply_string_profit
            if (no_buy_tasks != True): 
                reply_string = reply_string + reply_string_buy
            if (no_bb_tasks  != True): 
                reply_string = reply_string + reply_string_bb
            if (no_longs != True): 
                reply_string = reply_string + reply_string_long
                
            if reply_string == '': 
                reply_string = 'No active jobs'
            chat.send(reply_string)
        
        ########## Balances info
        elif msg_text.find('balance') >= 0: 
            # May not work if there are too many requests 
            retry = True 
            while retry: 
                try: 
                    str_balance = coinigy.balances()
                    chat.send(str_balance) 
                    retry = False 
                except: 
                    print "Seems like too many requests, retrying"
                    time.sleep(0.5)
            
        ########### Aborting tasks
        elif msg_text.find('abort') >= 0: 
            reply_string = 'Termination options (specify id):\n'
            
            sql_string = "SELECT * FROM jobs"
            rows = query(sql_string)

            if rows == []: 
                chat.send('No active tasks to abort')
            else:     
                for row in rows:
                    reply_string += str(row[0]) + ': ' + row[1] + ', EP ' + str(row[3]) + ', Simulation: ' + str(bool(row[4])) + '\n'
                reply_string += 'all\n\nReply anything else to cancel the termination request'                    
                chat.send(reply_string)
                
                msg_text = chat.get_response()
                
                # If not all were requested
                if msg_text.find('all') < 0: 
                    try: 
                        sql_string = "UPDATE jobs SET abort_flag = 1 WHERE job_id = {}".format(msg_text)    #flagging for cancellation
                        rows = query(sql_string)
                        chat.send('Job ' + msg_text.upper() + ' flagged for cancelling')
                    except:
                        chat.send('Incorrect task name')
                # Terminating all if requested
                else:
                    chat.send('Aborting all tasks')
                    sql_string = "UPDATE jobs SET abort_flag = 1"
                    rows = query(sql_string)

        ########### Aborting tasks
        elif msg_text.find('sellnow') >= 0: 
            reply_string = 'Sell options (specify id):\n'
            
            sql_string = "SELECT * FROM jobs"
            rows = query(sql_string)

            if rows == []: 
                chat.send('No active tasks')
            else:     
                for row in rows:
                    reply_string += str(row[0]) + ': ' + row[1] + ', EP ' + str(row[3]) + ', Simulation: ' + str(bool(row[4])) + '\n'
                reply_string += 'all\n\nReply anything else to cancel the sell request'                    
                chat.send(reply_string)
                
                msg_text = chat.get_response()
                
                # If not all were requested
                if msg_text.find('all') < 0: 
                    try: 
                        sql_string = "UPDATE jobs SET selling = 1 WHERE job_id = {}".format(msg_text)    #flagging for cancellation
                        rows = query(sql_string)
                        chat.send('Job ' + msg_text.upper() + ' flagged for selling')
                    except:
                        chat.send('Incorrect task name')
                # Terminating all if requested
                else:
                    chat.send('Marked everything for selling')
                    sql_string = "UPDATE jobs SET selling = 1"
                    rows = query(sql_string)
        
        ############### Cancel buy
        elif msg_text.find('stopbuy') >= 0: 
            reply_string = 'Options (reply with id):\n'
            rows = query("SELECT * FROM buys")

            if rows == []: 
                chat.send('No active tasks to abort')
            else: 
                for row in rows:
                    reply_string += str(row[0]) + ': ' + row[1] + ', mode ' + str(row[6]) + '\n'
                reply_string += 'all\n\nReply anything else to cancel the termination request'                    
                chat.send(reply_string)
                msg_text = chat.get_response()
                
                # If not all were requested
                if msg_text.find('all') < 0: 
                    try: 
                        sql_string = "UPDATE buys SET abort_flag = 1 WHERE job_id = {}".format(msg_text)    #flagging for cancellation
                        rows = query(sql_string)
                        chat.send('Buy ' + msg_text.upper() + ' flagged for cancelling')
                    except:
                        chat.send('Incorrect task name')
                # Terminating all if requested
                else:
                    chat.send('Aborting all tasks')
                    sql_string = "UPDATE buys SET abort_flag = 1"
                    rows = query(sql_string)

        ############### Cancel buyback
        elif msg_text.find('stopbback') >= 0: 
            reply_string = 'Options (reply with id):\n'
            rows = query("SELECT * FROM bback")

            if rows == []: 
                chat.send('No active tasks to abort')
            else: 
                for row in rows:
                    reply_string += str(row[0]) + ': ' + row[1] + ', bb_price ' + str(row[2]) + '\n'
                reply_string += 'all\n\nReply anything else to cancel the termination request'                    
                chat.send(reply_string)
                msg_text = chat.get_response()
                
                # If not all were requested
                if msg_text.find('all') < 0: 
                    try: 
                        sql_string = "UPDATE bback SET abort_flag = 1 WHERE id = {}".format(msg_text)    #flagging for cancellation
                        rows = query(sql_string)
                        chat.send('Buyback ' + msg_text.upper() + ' flagged for cancelling')
                    except:
                        chat.send('Incorrect task name')
                # Terminating all if requested
                else:
                    chat.send('Aborting all tasks')
                    sql_string = "UPDATE bback SET abort_flag = 1"
                    rows = query(sql_string)
                    
        ############## Setting input parameters if a new task is requested
        elif msg_text.find('new') >= 0:  
            telegram_sell()
            
        ############## Setting input parameters if a smart buy
        elif msg_text.find('buy') >= 0:  
            telegram_buy()

        ############## Entering a long record
        elif msg_text.find('nlong') >= 0:  
            telegram_long()

        ########### Removing longs
        elif msg_text.find('rmlong') >= 0: 
            reply_string = 'Current longs (specify id):\n'
            
            sql_string = "SELECT * FROM longs"
            rows = query(sql_string)

            if rows == []: 
                chat.send('No active longs to remove')
            else:     
                for row in rows:
                    reply_string += str(row[0]) + ': ' + row[1] + ', EP ' + str(row[2]) + ', Quantity: ' + str(row[3]) + '\n'
                reply_string += 'all\n\nReply anything else to cancel the request'                    
                chat.send(reply_string)
                
                msg_text = chat.get_response()

                # If not all were requested
                if msg_text.find('all') < 0: 
                    try: 
                        sql_string = "DELETE FROM longs WHERE long_id = {}".format(msg_text)
                        rows = query(sql_string)
                        chat.send('Removed the record')
                    except:
                        chat.send('Incorrect response')
                # Removing all if requested
                else:
                    sql_string = "DELETE FROM longs"
                    rows = query(sql_string)        
                
        ############## Setting input parameters if this is a buy&sell (workflow) job
        elif msg_text.find('workflow') >= 0:  
        
            chat.send('Specify mode (s/r/sns/rns/rnts), exchange, TP, SL, [sell_portion (amount)] for further reference')
            msg_text = chat.get_response()
            
            # Getting parameters
            msg_text_split = msg_text.split()
            # Processing params - should all be entered
            try: 
                wf_run_mode = msg_text_split[0]
                if wf_run_mode not in ['s','r','sns','rns', 'rnts']: 
                    chat.send('Incorrect run mode specified')
                else:
                    wf_exchange = msg_text_split[1]
                    if wf_exchange not in ['btrx', 'bina', 'bmex']: 
                        print 'Incorrect exchange specified (should be btrx, bina, bmex)\n\n'
                        chat.send('Incorrect exchange specified (should be btrx, bina, bmex)')
                    else: 
                        # if ok 
                        wf_tp = msg_text_split[2]
                        wf_sl = msg_text_split[3]
                        try: 
                            wf_sell_portion = msg_text_split[4]
                        except: 
                            wf_sell_portion = 0 
                        # Insert a record in the db 
                        sql_string = "INSERT INTO workflow(tp, sl, sell_portion, run_mode, exchange) VALUES ({}, {}, {}, '{}', '{}')".format(float(wf_tp), float(wf_sl), float(wf_sell_portion), wf_run_mode, wf_exchange)
                        wf_id, rows = query_lastrow_id(sql_string)                               
                        # Start the buy job
                        telegram_buy(wf_id)  
            except:
                chat.send('Not all the parameters are specified')

    except KeyboardInterrupt:
        exit(0)
