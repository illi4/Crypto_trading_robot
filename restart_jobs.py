from libs.telegramlib import telegram
from sys import exit, argv
import config

import libs.sqltools as sqltools
sql = sqltools.sql()

import libs.platformlib as platform                                  # detecting the OS and setting proper folders
import argparse
import os
import time

from sys import exit

# 126501560, 45764410, 166079360

def start_command(command, start=False, testmode=False):
    global cmd_init
    if platform_run == 'Windows':
        cmd_str = cmd_init + ' ' + command
    else:
        # Nix
        cmd_str = cmd_init + ' ' + command + '"'
    print(cmd_str)
    if start:
        os.system(cmd_str)
    if not testmode:
        time.sleep(4)

# Parse custom params if there are any
parser = argparse.ArgumentParser()
parser.add_argument('--userid', type=int, help="User id (telegram")
parser.add_argument('--restart', type=int, help="User id (telegram")

args, unknown = parser.parse_known_args()
user_id = getattr(args, 'userid')
if user_id is None:
    user_id = config.telegram_chat_id     # my id

do_restart = bool(getattr(args, 'restart'))

# Platform
platform = platform.platformlib()
platform_run, cmd_init = platform.initialise()

# Get user margin params for jobs relaunch
user_margins = {}
user_margins['traditional'] = {}
user_margins['standard'] = {}

for margin_type in ['traditional', 'standard']:
    sql_string = "SELECT userid, param_val FROM user_params WHERE param_name = 'margin' and core_strategy = '{}'".format(margin_type)
    rows = sql.query(sql_string)
    if rows != []:
        for row in rows:
            user_identifier = row[0]
            user_margin = row[1]
            user_margins[margin_type][user_identifier] = user_margin

start_arr = []


sql_string = "SELECT * FROM jobs" 
rows = sql.query(sql_string)

if rows != []:
    for row in rows:
        market = row[1] # market
        usr = row[16]  
        entry = row[11]

        exch = row[15]

        if exch == 'bitmex':
            exch = 'bmex'
        else:
            exch = 'oanda'

        strategy = row[18]
        position_type =  row[19]
            
        str = 'process r {} {} {} --is_restart=1 --userid={}  --core_strategy={}'.format(exch, market, entry, usr, strategy)
        start_arr.append(str)
 

sql_string = "SELECT * FROM buys"
rows = sql.query(sql_string)

if rows != []:
    for row in rows:
        strategy = row[9]
        usr = row[8] # user
        exch = row[7]

        if exch == 'bitmex':
            exch = 'bmex'
        else:
            exch = 'oanda'

        try: 
            margin_divider = user_margins[strategy][usr]
        except: 
            margin_divider = 5 # default 
        market = row[1] # market
        val = row[5]/float(margin_divider)  

        str = 'initiate full_cycle {} {} {} --is_restart=1 --userid={} --core_strategy={}'.format(exch, market, val, usr, strategy)
        start_arr.append(str)

sql_string = "SELECT * FROM bback"
rows = sql.query(sql_string)

if rows != []:
    for row in rows:
        val = row[4]   # should not divide by margin because the amount is normal anyway
        market = row[1] # market
        usr = row[7] # user
        strategy = row[8]

        exch = row[6]
        if exch == 'bitmex':
            exch = 'bmex'
        else:
            exch = 'oanda'

        str = 'initiate full_cycle {} {} {} --is_restart=1 --userid={} --core_strategy={}'.format(exch, market, val, usr, strategy)
        start_arr.append(str)
        
        
# Check
if not do_restart:
    print("Testmode. Run with --restart=1 to actually restart. Commands:")
    for command in start_arr:
        start_command(command, testmode=True)
    exit(0)

# Restarting 

print('(!) Now close the windows with user tasks. All jobs will be deleted from the DB and commands will be relaunched.')
time.sleep(60)

# Deleting tasks
for elem in ['workflow', 'bback', 'buys', 'buy_hold', 'jobs']:
    request = "DELETE FROM {}".format(elem)
    print('Delete:', request)
    sql.query(request)

# Now starting
for command in start_arr:
    start_command(command, start=True)

