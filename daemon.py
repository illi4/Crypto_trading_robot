### Daemon script for commands processing
# add --userid=NNNNNN when starting, otherwise the admin account from config will be used 

################################ Libraries ############################################
## Standard libraries 
import os
import time
from sys import exit
import argparse
import re
from datetime import datetime
# Data manipulation
import pandas as pd
import numpy as np
import sqlite3  # for sqlite connection in pandas df_sql

## Custom libraries 
from libs.telegramlib import telegram 
import libs.sqltools as sqltools
sql = sqltools.sql()

import libs.platformlib as platform                                  # detecting the OS and setting proper folders
from libs.coinigylib import coinigy                                      # library to work with coinigy

import config

# Python telegram bot 
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import telegram as telegram_python_bot # for bare wrapper to send files 

# Threading for v3
import _thread


import logging
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


# Create the EventHandler and pass it your bot's token.
updater = Updater(config.telegram_token)
# Get the dispatcher to register handlers
dp = updater.dispatcher

# Parse custom params if there are any
parser = argparse.ArgumentParser()
parser.add_argument('--userid', type=int, help="User id (telegram")
# One to ignore admin (so that admin can debug on testnet locally) and for admin only
parser.add_argument('--ignore_admin', type=int, help="Ignore admin (0/1)")
parser.add_argument('--only_admin', type=int, help="Only admin (0/1)")

args, unknown = parser.parse_known_args()
user_id = getattr(args, 'userid')
if user_id is None:
    user_id = config.telegram_chat_id     # my id

ignore_admin = bool(getattr(args, 'ignore_admin'))  # 1 to ignore
only_admin = bool(getattr(args, 'only_admin'))  # 1 to enable admin only mode

coinigy = coinigy(user_id)    # replace with a proper user

# Universal functions for all exchanges, custom built       
import exch_api

# Auxiliary function to check which strategy is active for chat
# different keys may be used depending on the strategy
def which_strategy(user_to):
    sql_string = "SELECT active_strategy FROM user_info WHERE userid = '{}'".format(user_to)
    rows = sql.query(sql_string)
    try:
        strategy_name = rows[0][0]  # first result
        return strategy_name
    except:
        return 'standard'

strategy_name = which_strategy(user_id)
e_api_to = exch_api.api(user_id, strategy = strategy_name)

# Platform
platform = platform.platformlib()
platform_run, cmd_init = platform.initialise()

#################### For Telegram integration ###############################################################
chat = telegram(user_id, start_override = True)

comm_method = 'chat' # 'mail' or 'chat', chat is preferable for the smooth experience 
send_messages = True

# Dataframes for responses type, response 1, response 2 (when needed)
responses_df = pd.DataFrame(data=np.array([['none']]),
                  index=['none'],
                  columns=['type'])

responses_df_1 = pd.DataFrame(data=np.array([['none']]),
                  index=['none'],
                  columns=['type'])

responses_df_2 = pd.DataFrame(data=np.array([['none']]),
                  index=['none'],
                  columns=['type'])

responses_param_wf = pd.DataFrame(data=np.array([['none']]),
                  index=['none'],
                  columns=['type'])

responses_param_auto = pd.DataFrame(data=np.array([['none']]),
                  index=['none'],
                  columns=['type'])

# Streaming responses
responses_stream = pd.DataFrame(data=np.array([['none']]),
                  index=['none'],
                  columns=['type'])
strategy_exchange_stream = {}



######################################################################################
############################## MONITORING BOT ######################################
#####################################################################################

# Response sanitisation
def sanitise(line):
    line = re.sub('[!@#$]', '', line)
    for word in ['drop', 'insert', 'select', 'update']:
        line = re.sub(word, '', line)
    return line

########## Sending in a thread
def send_chat_message(user_to, text):
    bot.send_message(
        chat_id = user_to,
        text = text
    )


########## Close position
def telegram_close_position(user_to):

    reply_string = 'Close options (specify id):\n'
    sql_string = "SELECT * FROM jobs WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)
    if rows == []:
        send_chat_message('No active tasks')
        #send_chat_message(user_to, 'No active tasks')
    else:
        for row in rows:
            if bool(row[4]):
                simulation_str = '(simulation)'
            else:
                simulation_str = ''
            reply_string += '{}: {}, EP {} {}, strategy "{}"\n'.format(row[0], row[1], row[3], simulation_str, row[18])
        reply_string += 'all\n\nReply anything else to cancel the request'
        send_chat_message(user_to, reply_string)
    responses_df.loc[user_to] = 'close_position'

def telegram_close_position_execute(user_to, value):

    msg_text = sanitise(value)

    # If not all were requested
    if msg_text.find('all') < 0:
        try:
            sql_string = "UPDATE jobs SET selling = 1 " \
                "WHERE job_id = {} AND userid = {}".format(msg_text,
                                                                                                user_to)  # flagging for cancellation
            sql.query(sql_string)
            send_chat_message(user_to, 'Job ' + msg_text.upper() + ' flagged for closing')
        except:
            send_chat_message(user_to, 'Incorrect task name')
    # Terminating all if requested
    else:
        send_chat_message(user_to, 'Marked everything for closing')
        sql_string = "UPDATE jobs SET selling = 1 WHERE userid = {}".format(user_to)
        sql.query(sql_string)

    responses_df.loc[user_to] = None

########## Balances info
def telegram_balance(user_to, exchange = None, strategy = None):

    balance_available = None

    if exchange is not None and strategy is not None:
        e_api_to = exch_api.api(user_to, strategy = strategy)
        balance = e_api_to.getbalance(exchange)
        print("Balance for the user {} on the strategy {}: {}".format(user_to, strategy, balance))
        if balance is not None:
            balance_available = round(balance['Available'], 4)
            balance_str = 'Available for opening new positions on {} ({} strategy): {}'.format(exchange, strategy, balance_available)
            send_chat_message(user_to, balance_str)
        else:
            balance_available = None
            send_chat_message(user_to, 'Cannot get the balance. API keys are inactive or incorrect')
    else:
        sql_string = "SELECT strategy, exchange FROM keys WHERE user = '{}'".format(user_to)
        rows = sql.query(sql_string)

        if rows != []:
            for row in rows:
                retry_continue = True
                retry_count = 0
                strategy = row[0]
                exchange = row[1]
                #print 'Checking', strategy, exchange
                while retry_count < 10 and retry_continue:
                    try:
                        e_api_to = exch_api.api(user_to, strategy = strategy)
                        balance = e_api_to.getbalance(exchange)
                        balance_available = round(balance['Available'], 4)
                        balance_str = 'Available for opening new positions on {} strategy: {}'.format(strategy, balance_available)
                        retry_continue = False
                    except:
                        retry_count += 1
                        print("Seems like too many requests now, retrying")
                        time.sleep(0.2)
                # Return the result
                if retry_count == 10:
                    send_chat_message(user_to, 'Cannot get the balance for {} ({}): API keys are inactive or incorrect'.format(exchange, strategy))
                else:
                    send_chat_message(user_to, balance_str)

    return balance_available


### 'New'
def telegram_new_sell(user_to):
    # New instances for threading

    msg = """ 
This will launch a trading task when you already (!) have an open position on the market. If you do not know what you are doing, please reply something random and then use the /auto option.

To start, answer with a message with the following parameters:
> mode market entry_price  

Modes: 's' (simulation), 'r' (real mode)

Example: r btc/usd 6000
^ this will launch a job (long) on btc/usd in regular mode where you entered at 6000 

Note that your stops will be automatically reconfigured by the bot. The direction will be detected automatically based on your position. 
    """
    send_chat_message(user_to, msg)
    send_chat_message(user_to, available_markets_generator())

    responses_df.loc[user_to] = 'new_sell'


def telegram_new_sell_execute(user_to, value):
    global platform_run, cmd_init

    exchange, strategy_name = strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1]
    exchange = exchange_name_convert(exchange) # abbreviation

    msg_text = sanitise(value)

    # Starting a new process with a new task
    msg_text_split = msg_text.split()

    # Processing params - should all be entered
    try:
        run_simulation_param = msg_text_split[0].lower()
        run_exchange = exchange #msg_text_split[1].lower()

        run_market = msg_text_split[1].upper()
        try:
            run_trade, run_currency = run_market.split('-')
        except:
            run_trade = run_market  # if only one market vs BTC is provided - e.g. XRPH18 on bitmex
            run_currency = 'BTC'

        run_price_curr = msg_text_split[2]

        # Deprecated
        '''
        run_tp = msg_text_split[3]
        run_sl = msg_text_split[4]
        try:
            run_limit_sell_amount = msg_text_split[5]
        except:
            run_limit_sell_amount = ''
        try:
            run_sell_portion = msg_text_split[6]
        except:
            run_sell_portion = ''
        '''
        
        # Run depending on the platform
        user_id_str = '--userid={}'.format(user_to)
        strategy_str = '--core_strategy={}'.format(strategy_name)
        try: 
            entry_price_str = '--entry_cutoff_price={}'.format(run_price_curr)
        except: 
            entry_price_str = ''
        if platform_run == 'Windows':
            cmd_str = cmd_init + ' '.join(['process', run_simulation_param, run_exchange, run_market,
                                           run_price_curr, user_id_str, entry_price_str, strategy_str])
        else:
            # Nix
            cmd_str = cmd_init + ' '.join(['process', run_simulation_param, run_exchange, run_market,
                                           run_price_curr, user_id_str, entry_price_str, strategy_str]) + '"'
        os.system(cmd_str)

        # Check if launched

        send_chat_message(user_to, 'Launching under the strategy {}, hold on...'.format(strategy_name))
        time.sleep(30)
        sql_string = "SELECT job_id FROM jobs WHERE market = '{}' " \
            "AND userid = {} AND core_strategy='{}'".format(run_market.upper(), user_to, strategy_name)
        rows = sql.query(sql_string)

        try:
            launched_confirmation = rows[0][0]  # first result if existing
            print('>>> Started a new job on the market {}. Simulation mode: {}'.format(run_market.upper(),
                                                                                       run_simulation_param))
            send_chat_message(user_to, 'Launched a new bot with these parameters')
        except:
            send_chat_message(user_to, 'The job was not launched')

    except:
        send_chat_message(user_to, 'Incorrect response format, please select a new command or start again')

    responses_df.loc[user_to] = None

def exchange_name_convert(name):
    if name == 'bitmex':
        name = 'bmex'
    elif name == 'oanda':
        name = 'oanda'
    return name

### Auto
def telegram_auto(user_to):
    # Real mode on bitmex with fullta: r bmex
    wf_run_mode = 'r'
    wf_exchange = 'bmex'

    exchange, strategy = strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1]
    wf_exchange = exchange_name_convert(exchange) # abbreviation 

    # Insert a record in the db, using just dummy values for tp and sl
    # Market, trade, currency will be updated with proper values in telegram buy
    sql_string = "INSERT INTO workflow(run_mode, exchange, userid, core_strategy) " \
        "VALUES ('{}', '{}', '{}', '{}')".format(wf_run_mode, wf_exchange, user_to, strategy)
    wf_id, rows = sql.query_lastrow_id(sql_string)
    # Start the buy job
    telegram_initiate_position(user_to, wf_id, True)

### For workflows 
def telegram_workflow(user_to):

    send_chat_message(user_to, 'Specify mode "r" (real mode) or "s" (simulation) for further reference.')
    responses_df.loc[user_to] = 'workflow'

def telegram_workflow_launch(user_to, value):

    exchange, strategy = strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1]
    wf_exchange = exchange_name_convert(exchange) # abbreviation

    msg_text = sanitise(value)

    responses_df.loc[user_to] = None    # will be starting a new one anyway

    # Getting parameters
    msg_text_split = msg_text.split()
    # Processing params - should all be entered
    try:
        wf_run_mode = msg_text_split[0]
        if wf_run_mode not in ['s', 'r']:
            send_chat_message(user_to, 'Incorrect run mode specified')
            responses_df.loc[user_to] = None
        else:
            if wf_exchange not in config.exch_supported:
                send_chat_message(user_to, 'Incorrect exchange specified')
            else:
                # Insert a record in the db
                sql_string = "INSERT INTO workflow(run_mode, exchange, userid, core_strategy) " \
                    "VALUES ('{}', '{}', {}, '{}')".format(
                        wf_run_mode, wf_exchange, user_to, strategy_name)
                wf_id, rows = sql.query_lastrow_id(sql_string)
                # Start the buy job
                telegram_initiate_position(user_to, wf_id)
    except:
        send_chat_message(user_to, 'Incorrect response format, please select a new command or start again')

### My positions
def telegram_mypositions(user_to):

    exchange, strategy_name = strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1]

    e_api_to = exch_api.api(user_to, strategy = strategy_name)

    reply_str = 'Positions opened on the exchange:\n'
    send_chat_message(user_to, 'Checking your positions, hold on...')

    user_positions = e_api_to.getpositions(exchange, None)
    if user_positions != []:
        for position in user_positions:
            reply_str += '{}\n'.format(position)
        send_chat_message(user_to, reply_str)
    else:
        send_chat_message(user_to, 'No positions')


### 'Initiate_position'
def telegram_initiate_position(user_to, wf_id = None, exch_fullta_mode = False):

    if exch_fullta_mode:
        msg = """ 
This will launch a fully automated process of searching entries and profitable exits, and your position sizes will be adjusted automatically. To launch, reply with the contract name and the position size in BTC. Here are some examples:

btc/usd 0.3
^ Bitcoin perpetual contract, entry amounted in 0.3 bitcoin

If you just want to use your whole balance and you roughly know the amount, you could specify a larger number and the maximum available balance will be used automatically.
        """
        send_chat_message(user_to, msg)
        send_chat_message(user_to, available_markets_generator())

        responses_df.loc[user_to] = 'initiate'
        responses_param_wf[user_to] = wf_id
        responses_param_auto[user_to] = True
    else:
        msg = """ 
Specify the parameters: 
mode source_currency-buy_currency [total_in_source currency] [price] [time limit for the price in minutes]
 
Modes: now/fullta. Add -s (now-s) for simulation. 

After opening a position, the task will be finished (!). If you want to launch fully automated trading, use /auto instead. Some examples:

fullta btc/usd 0.05
^ initiate (open) a long position automatically for the amount of 0.05 btc. 

now btc/usd -0.1
^ initiate a short on Ripple immediately for the amount of 0.1 btc.
        """
        send_chat_message(user_to, msg)
        send_chat_message(user_to, available_markets_generator())

        responses_df.loc[user_to] = 'initiate'
        responses_param_wf[user_to] = wf_id
        responses_param_auto[user_to] = False

def telegram_initiate_execute(user_to, value):
    global platform_run

    if user_to in list(strategy_exchange_stream.keys()):
        exchange, strategy_name = strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1]
        exchange = exchange_name_convert(exchange) # abbreviation

    msg_text = sanitise(value)

    wf_id = responses_param_wf[user_to].values[0]
    exch_fullta_mode = responses_param_auto[user_to].values[0]

    try:
        # Starting a new process with a new task
        msg_text_split = msg_text.split()

        # Checking if exch_fullta_mode is used
        if exch_fullta_mode:
            buy_mode = 'fullta'
            buy_exchange = exchange
            buy_market = msg_text_split[0].upper()
            buy_total = msg_text_split[1]
            buy_price = ''
            buy_time_limit = ''
        else:
            buy_mode = msg_text_split[0].lower()
            buy_exchange = exchange  #msg_text_split[1].lower()
            buy_market = msg_text_split[1].upper()
            try:
                buy_total = msg_text_split[2]
            except:
                buy_total = ''
            try:
                buy_price = msg_text_split[3]
            except:
                buy_price = ''
            try:
                buy_time_limit = msg_text_split[4]
            except:
                buy_time_limit = ''

                # Checking the market
        try:
            buy_trade, buy_currency = buy_market.split('-')
        except:
            buy_trade = buy_market  # if only one market vs BTC is provided - e.g. XRPH18 on bitmex
            buy_currency = 'BTC'

        # Check if the buy for the same user and market is running
        sql_string = "SELECT * FROM buys WHERE market = '{}' AND userid = {} " \
            "AND core_strategy = '{}'".format(buy_market, user_to, strategy_name)
        rows = sql.query(sql_string)
        try:
            exists = rows[0][0]  # first result
            send_chat_message(user_to,
                'Warning: another buy on the same market is running. One of them may be redundant, please check after launch.')
        except:
            pass

        # Updating the db
        if wf_id is not None:
            sql_string = "UPDATE workflow SET market = '{}', trade = '{}', currency = '{}', " \
                         "exchange = '{}' WHERE wf_id = {} AND userid = {} AND core_strategy='{}'".format(
                            buy_market, buy_trade, buy_currency,
                            buy_exchange, wf_id, user_to, strategy_name)
            job_id, rows = sql.query_lastrow_id(sql_string)

        # Run depending on the platform
        user_id_str = '--userid={}'.format(user_to)
        strategy_str = '--core_strategy={}'.format(strategy_name)
        if platform_run == 'Windows':
            cmd_str = cmd_init + ' '.join(
                ['initiate', buy_mode, buy_exchange, buy_market, buy_total, buy_price, buy_time_limit, user_id_str, strategy_str])

        else:
            # Nix
            cmd_str = cmd_init + ' '.join(
                ['initiate', buy_mode, buy_exchange, buy_market, buy_total, buy_price, buy_time_limit,
                 user_id_str, strategy_str]) + '"'

        os.system(cmd_str)
        send_chat_message(user_to, 'New task requested successfully (strategy: {}). Please allow for a few minutes for this task to launch.'.format(strategy_name))
        print("Started a new buy job: ", cmd_str)

    except:
        send_chat_message(user_to, 'Incorrect response format, please select a new command or start again')

    responses_df.loc[user_to] = None
    responses_param_wf.loc[user_to] = None
    responses_param_auto.loc[user_to] = None

########## Clean DB
def telegram_clean_my_db(user_to):
    global responses_df

    msg_resp = "❗\n\nThis will: \n- stop all your tasks \n- clean all your jobs and workflow database records " \
               "\n\nRespond 'yes' to confirm or anything else to cancel."
    send_chat_message(user_to, msg_resp)
    responses_df.loc[user_to] = 'db_clean'

def telegram_db_clean_execute(user_to, value):
    global responses_df

    if value.lower().find('yes') >= 0:
        send_chat_message(user_to, "Aborting all tasks, hold on for a few minutes...")
        for tbl_name in ['buys', 'jobs', 'bback', 'buy_hold']:
            sql_string = "UPDATE {} SET abort_flag=1 WHERE userid = {}".format(tbl_name, user_to)
            sql.query(sql_string)

        time.sleep(90)
        send_chat_message(user_to, "Cleaning the database...")

        for tbl_name in ['jobs', 'workflow', 'buys', 'bback', 'buy_hold']:
            sql_string = "DELETE from {} WHERE userid = {}".format(tbl_name, user_to)
            sql.query(sql_string)
        send_chat_message(user_to, "Database cleaned")
    else:
        send_chat_message(user_to, "Does not look like yes. Cancelled the request.")

    responses_df.loc[user_to] = None

########## Margin change, needs a df update for monitoring
def telegram_margin_change_r(user_to):
    exchange, strategy_name = strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1]

    # Getting the current margin value
    sql_string = "SELECT param_val FROM user_params WHERE userid = {} " \
        "AND param_name = 'margin' AND core_strategy='{}'".format(user_to, strategy_name)
    rows = sql.query(sql_string)

    if rows != []:
        margin_level = rows[0][0]
        reply_string = 'Your current margin level on strategy "{}": {}.\n\n'.format(strategy_name, margin_level)
    else:
        sql_string = "INSERT INTO user_params(userid, param_name, param_val, core_strategy) " \
            "VALUES ({}, '{}', {}, '{}')".format(user_to, 'margin', 5, strategy_name)
        rows = sql.query(sql_string)
        reply_string = 'Your current margin level on strategy "{}": 5\n'.format(strategy_name)

    reply_string += 'Choose one of the options below to change your margin level ' \
        '(10 is extreme and recommended for traditional markets only). ' \
        '\n\nIf you are not sure what this means, please go to bitmex and read about margin trading. '

    keyboard = [[
        InlineKeyboardButton("1", callback_data='margin:1'),
        InlineKeyboardButton("2", callback_data='margin:2'),
        InlineKeyboardButton("3", callback_data='margin:3'), 
        InlineKeyboardButton("5", callback_data='margin:5'), 
        InlineKeyboardButton("10", callback_data='margin:10')
        ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    bot.send_message(
        chat_id=user_to, 
        text = reply_string,  
        reply_markup=reply_markup
    )


############################################################################################################
### Using the whole balance always
def telegram_use_all_balance(user_to):
    global responses_df

    # Getting the current param value
    sql_string = "SELECT param_val FROM user_params WHERE userid = {} " \
        "AND param_name = 'use_all_balance'".format(user_to)
    rows = sql.query(sql_string)

    if rows != []:
        use_all_balance = bool(int(rows[0][0]))
        reply_string = 'Current value: {}'.format(use_all_balance)
    else:
        sql_string = "INSERT INTO user_params(userid, param_name, param_val) " \
            "VALUES ({}, '{}', {})".format(user_to, 'use_all_balance', 0)
        rows = sql.query(sql_string)
        reply_string = 'Current value: False'

    # Monitoring further
    responses_df.loc[user_to] = 'use_all_balance'
    send_chat_message(user_to, reply_string)
    reply_string = 'Reply T (True) or F (False) to enable or disable the option. Reply anything random to cancel the request'
    send_chat_message(user_to, reply_string)

###  Updating the value
def telegram_use_all_balance_execute(user_to, value):

    msg_text = sanitise(value).lower()
    value_upd = None

    if msg_text == 't' or msg_text == 'true':
        value_upd = 1
    if msg_text == 'f' or msg_text == 'false':
        value_upd = 0

    if value_upd is not None:
        sql_string = "UPDATE user_params SET param_val = {} WHERE param_name = 'use_all_balance' " \
            "AND userid = {} ".format(value_upd, user_to)
        sql.query(sql_string)
        send_chat_message(user_to, 'Parameter updated and will be applied when opening new positions')
        responses_df.loc[user_to] = None

    responses_df.loc[user_to] = None

################################################################################
### Traditional market signals subscription
def telegram_traditional_markets_overview(user_to):
    global responses_df

    # Getting the current param value
    sql_string = "SELECT param_val FROM user_params WHERE userid = {} " \
        "AND param_name = 'traditional_markets_overview'".format(user_to)
    rows = sql.query(sql_string)

    if rows != []:
        use_all_balance = bool(int(rows[0][0]))
        reply_string = 'Current value: {}'.format(use_all_balance)
    else:
        sql_string = "INSERT INTO user_params(userid, param_name, param_val) " \
            "VALUES ({}, '{}', {})".format(user_to, 'traditional_markets_overview', 0)
        rows = sql.query(sql_string)
        reply_string = 'Current value: False'

    # Monitoring further
    responses_df.loc[user_to] = 'traditional_markets_overview'
    send_chat_message(user_to, reply_string)
    reply_string = 'Reply T (True) or F (False) to enable or disable the option. Reply anything random to cancel the request'
    send_chat_message(user_to, reply_string)

###  Updating the value
def telegram_traditional_markets_overview_execute(user_to, value):

    msg_text = sanitise(value).lower()
    value_upd = None
 
    if (msg_text == 't' or msg_text == 'true'):
        value_upd = 1
    if (msg_text == 'f' or msg_text == 'false'):
        value_upd = 0

    if value_upd is not None:
        sql_string = "UPDATE user_params SET param_val = {} WHERE param_name = 'traditional_markets_overview' " \
            "AND userid = {} ".format(value_upd, user_to)
        sql.query(sql_string)
        if value_upd == 1:
            send_chat_message(user_to, 'You will start receiving daily reports with traditional market signals from now on. You can always unsubscribe using the same command.')
        else:
            send_chat_message(user_to, 'You were successfully unsubscribed.')
        responses_df.loc[user_to] = None

    responses_df.loc[user_to] = None

#############################################################################################################

### Strategy status
def telegram_strategy_status(user_to):

    response = 'Available strategies:'

    sql_string = "SELECT name, description FROM strategies"
    rows = sql.query(sql_string)

    for row in rows:
        add_str = '\n- {}: {}'.format(row[0], row[1])
        response += add_str

    send_chat_message(user_to, response)

## Trades hist
def telegram_trades(user_to):
    global responses_df

    sql_string = "SELECT start_timestamp, end_timestamp, trade_outcome, trade_commissions, " \
        "trade_funding, earned_ratio, percent_gained, core_strategy " \
        "FROM trade_log WHERE userid = {} ORDER BY end_timestamp DESC LIMIT 3".format(user_id)
    rows = sql.query(sql_string)

    reply_string = 'Your last 3 trades:\n\n'

    if rows != []:
        for row in rows:
            time_utc = datetime.utcfromtimestamp(row[0]).strftime('%m/%d/%Y %H:%M')
            reply_string += 'Timestamp (UTC): {} \nOutcome (BTC): {} \nCommissions: {} \nFunding: {} ' \
            '\nResult (no margin): {}% \nResult (on margin): {}% \nStrategy: {}\n\n'.format(
                time_utc, row[2], row[3], row[4], row[5], row[6], row[7]
            )
    else:
        reply_string = 'No trade history available'
    send_chat_message(user_to, reply_string)
    
    # Also collecting and sending the full history 
    filename = 'temp/trades_{}.csv'.format(user_to)
    conn = sqlite3.connect("workflow.db")
    df = pd.read_sql('select * from trade_log where userid={}'.format(user_to), conn)
    df.drop('id', axis=1, inplace=True)
    df.to_csv(filename)
    conn.commit()
    conn.close()
    
    bot.send_document(
        chat_id=user_to, 
        caption= 'Full history of trades performed by bot on your account', 
        document=open(filename, 'rb')
    )

## Select the strategy
def telegram_e_strategy_select(user_to, stream_name = None):

    keyboard_arr = config.strategies
    keyboard_arr_transformed = []
    keyboard = []
    for elem, value in keyboard_arr.items():
        keyboard_arr_transformed.append(
            InlineKeyboardButton(str(elem), callback_data='input_platform:{}'.format(elem))
        )
    # An option to repeat the last one
    if user_to in list(strategy_exchange_stream.keys()):
        keyboard_arr_transformed.append(
            InlineKeyboardButton('Last selected', callback_data='input_platform:LASTVAL')
        )

    keyboard.append(keyboard_arr_transformed)
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(
        chat_id=user_to,
        text = 'Select your platform',
        reply_markup=reply_markup
    )
    responses_stream.loc[user_to] = stream_name

def telegram_e_strategy_select_f(user_to, platform):
    items_pre = config.strategies
    keyboard_arr_transformed = []
    keyboard = []

    if platform == 'LASTVAL':
        stream_process(user_to, None, None)
    else:
        keyboard_arr = dict((key,value) for key, value in items_pre.items() if key == platform)
        for elem, value in keyboard_arr.items():
            for strategy_name in value:
                keyboard_arr_transformed.append(
                    InlineKeyboardButton(str(strategy_name), callback_data='input_strategy:{}_{}'.format(platform, strategy_name))
                )
        keyboard.append(keyboard_arr_transformed)
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.send_message(
            chat_id=user_to,
            text = 'Available strategies',
            reply_markup=reply_markup
        )


### Handling callbacks ######
def callback_handle(bot, update):
    sql.query_data = update.callback_query 
    callback_response = sql.query_data.data
    user_to = sql.query_data.message.chat_id
    message_id=sql.query_data.message.message_id

    if user_to in list(strategy_exchange_stream.keys()):
        exchange, strategy = strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1]
    
    # Check what
    if 'margin:' in callback_response:
        margin_level = int(callback_response.replace("margin:", ""))
        sql_string = "UPDATE user_params SET param_val = {} WHERE param_name = 'margin' " \
            "AND userid = {} AND core_strategy='{}'".format(
                margin_level, user_to, strategy)
        sql.query(sql_string)
        bot.edit_message_text(
            text="Margin level updated and will be applied when opening new positions",
            chat_id=user_to,
            message_id=message_id)

    elif 'keys:' in callback_response:
        exchange_to_use = callback_response.replace('keys:', '')
        bot.edit_message_text(
            text="Updating keys for {}".format(exchange_to_use),
            chat_id=user_to,
            message_id=message_id)

        # Strategy selection
        if exchange_to_use == 'oanda':
            reply_string = 'Please choose the platform to change keys for'

            keyboard = [[
                InlineKeyboardButton("bitmex", callback_data='keys:bitmex'),
                InlineKeyboardButton("oanda", callback_data='keys:oanda')
                ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            bot.send_message(
                chat_id=user_to,
                text = reply_string,
                reply_markup=reply_markup
            )

    elif 'abort:' in callback_response:
        option = int(callback_response.replace("abort:", ""))
        telegram_abort_execute(user_to, option)
        bot.edit_message_text(
            text="Abort requested",
            chat_id=user_to,
            message_id=message_id)

    elif 'input_platform:' in callback_response:
        selected_platform = callback_response.replace("input_platform:", "")

        if selected_platform != 'LASTVAL':
            text_upd = "Select strategy for the platform {}".format(selected_platform)
        else:
            text_upd = "Using last values: {} {}".format(strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1])

        bot.edit_message_text(
            text=text_upd,
            chat_id=user_to,
            message_id=message_id)
        telegram_e_strategy_select_f(user_to, selected_platform)

    elif 'input_strategy:' in callback_response:
        selected_all = callback_response.replace("input_strategy:", "")
        selected_arr = selected_all.split('_')
        selected_exchange, selected_strategy = selected_arr[0], selected_arr[1]

        bot.edit_message_text(
            text="Selected platform: {}, strategy: {}".format(selected_exchange, selected_strategy),
            chat_id=user_to,
            message_id=message_id)
        # End of selection for the stream
        stream_process(user_to, selected_exchange, selected_strategy)

### Process stream: important milestone
def stream_process(user_to, exchange, strategy):
    if exchange is not None and strategy is not None:
        strategy_exchange_stream[user_to] = [exchange, strategy]

    if (responses_stream.loc[user_to] == 'keys_update').bool():
        telegram_keys_set(user_to)
    elif (responses_stream.loc[user_to] == 'margin_change').bool():
       telegram_margin_change_r(user_to)
    elif (responses_stream.loc[user_to] == 'auto_job').bool():
       telegram_auto(user_to)
    elif (responses_stream.loc[user_to] == 'initiate_position').bool():
       telegram_initiate_position(user_to)
    elif (responses_stream.loc[user_to] == 'new_sell').bool():
       telegram_new_sell(user_to)
    elif (responses_stream.loc[user_to] == 'telegram_workflow').bool():
       telegram_workflow(user_to)
    elif (responses_stream.loc[user_to] == 'telegram_mypositions').bool():
       telegram_mypositions(user_to)

    responses_stream.loc[user_to] = None


########## Admin add user
def telegram_add_user(user_to):
    global responses_df

    send_chat_message(user_to, "User name:")

    # Monitoring further
    responses_df.loc[user_to] = 'add_user_step_1'

def telegram_add_user_1(user_to, value):
    global responses_df
    global responses_df_1

    responses_df_1.loc[user_to] = value

    send_chat_message(user_to, "User id:")

    # Monitoring further
    responses_df.loc[user_to] = 'add_user_step_2'

def telegram_add_user_2(user_to, value):
    global responses_df
    global responses_df_1
    global responses_df_2

    responses_df_2.loc[user_to] = value

    # Add the user
    add_name = str(responses_df_1.loc[user_to].values[0])
    add_id = int(responses_df_2.loc[user_to])

    sql_string = "INSERT INTO user_info(userid, name) VALUES ({}, '{}')".format(add_id, add_name)
    sql.query(sql_string)

    sql_string = "INSERT INTO user_params(userid, param_name, param_val) VALUES ({}, '{}', {})".format(add_id,
                                                                                                       'margin', 5)  # default recommended margin
    sql.query(sql_string)
    send_chat_message(user_to, 'User added')

    # Cleanup
    responses_df.loc[user_to], responses_df_1.loc[user_to], responses_df_2.loc[user_to] = None, None, None

########## Keys update
def telegram_keys_set(user_to):
    global responses_df

    reply_string = "What is your key id (not secret key)? Reply 'cancel' if you would like to cancel the request."
    send_chat_message(user_to, reply_string)
    responses_df.loc[user_to] = 'keys_step_1'

def telegram_keys_set_1(user_to, value):
    global responses_df, responses_df_1
    responses_df_1.loc[user_to] = value

    if value.lower().find('cancel') < 0:
        reply_string = "What is your secret key?"
        send_chat_message(user_to, reply_string)
        responses_df.loc[user_to] = 'keys_step_2'
    else:
        responses_df.loc[user_to], responses_df_1.loc[user_to] = None, None
        send_chat_message(user_to, 'Request cancelled')

def telegram_keys_set_2(user_to, value):
    global responses_df, responses_df_1, responses_df_2

    responses_df_2.loc[user_to] = value

    # Getting info on what strategy and exchange to use
    exchange, strategy = strategy_exchange_stream[user_to][0], strategy_exchange_stream[user_to][1]

    # Keys check
    key_id = sanitise(str(responses_df_1.loc[user_to].values[0]))
    key_secret = sanitise(str(responses_df_2.loc[user_to].values[0]))

    # Check if the key exists
    user_id = user_to
    sql_string = "SELECT id FROM keys WHERE user = {} AND strategy='{}' AND exchange = '{}' ".format(user_id, strategy, exchange)
    rows = sql.query(sql_string)

    if rows != []:
        # Existing - updating
        key_row_id = rows[0][0]
        sql_string = "UPDATE keys SET key_id = '{}', key_secret = '{}' WHERE id = {} and exchange = '{}' ".format(
            key_id, key_secret, key_row_id, exchange)
        sql.query(sql_string)
    else:
        # New - inserting
        sql_string = "INSERT INTO keys(user, key_id, key_secret, strategy, exchange) VALUES ({}, '{}', '{}', '{}', '{}')".format(
            user_id, key_id, key_secret, strategy, exchange)
        sql.query(sql_string)

    # Checking balance to ensure that the keys are correct   #finish
    send_chat_message(user_to, 'Validating the keys...')
    api_validate = telegram_balance(user_id, exchange = exchange, strategy = strategy)
    if api_validate is not None:
        send_chat_message(user_to, 'Keys checked for correctness and saved')
    else:
        send_chat_message(user_to, 'Keys do not seem to work')

    # Cleanup
    responses_df.loc[user_to], responses_df_1.loc[user_to], responses_df_2.loc[user_to] = None, None, None


### Available markets
def available_markets_generator():
    sql_string = "SELECT * FROM markets WHERE enabled=1"
    rows = sql.query(sql_string)

    markets_description = 'Available markets:\n'

    if rows != []:
        for row in rows:
            market = row[1]
            description = row[2]
            markets_description += "{}: {}\n".format(market, description)
    else:
        markets_description = 'None'

    return markets_description


def available_markets(user_to):
    send_chat_message(user_to, available_markets_generator())
    
#### Status
def telegram_status(user_to):   # fix short flag
    no_profit_tasks = False
    no_buy_tasks = False
    no_longs = False
    no_bb_tasks = False

    # Markets set to give info on the markets
    markets_status = set()

    reply_string = ''
    # Info from the DB - profit jobs
    # DB: id, market, tp, sl, simulation, mooning, selling, price_curr, percent_of, abort_flag
    reply_string_profit = 'ℹ Positions\n'

    sql_string = "SELECT * FROM jobs WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)

    if rows == []:
        no_profit_tasks = True
    else:
        for row in rows:
            re_market = row[1]
            markets_status.add(re_market)

            if re_market == 'btc/usd':
                round_num = 2
            else:
                round_num=10
            
            re_simulation = row[4]
            stop_loss = row[10]

            if bool(re_simulation) == True:
                re_simulation = '(simulation)'
            else:
                re_simulation = ''

            re_mooning = row[5]
            if bool(re_mooning) == 1:
                descr_price = '% higher than original take profit'

            re_selling = row[6]
            re_price_curr = round(row[7], round_num)
            re_percent_of = round(float(row[8]), 2)
            re_exchange = row[15]
            if row[17] is not None:
                re_stop_cutoff = round(row[17], round_num)
            else:
                re_stop_cutoff = None
            re_strategy = row[18]
            re_entry = round(row[11], round_num)
            re_position_type = row[19]
            
            if re_position_type == 0:  
                re_direction = '(long)'
            else: 
                re_direction = '(short)'  
            
            if re_percent_of >= 100:
                re_percent_of -= 100
                descr_price = 'Price: (^) up {0:.2f}% from entry'.format(re_percent_of) 
            else:
                re_percent_of = 100 - re_percent_of
                descr_price = 'Price: (v) down {0:.2f}% from entry'.format(re_percent_of) 

            if re_strategy in ['standard', 'traditional']:
                reply_string_profit += "\n{} {} - {} {} {}\n{} \nEntry: {} \n" \
                    "Current price: {}\n".format(
                    re_market, re_strategy, re_exchange.title(), re_direction, re_simulation,
                    descr_price, re_entry, re_price_curr)
            else:
                reply_string_profit += "\n{} {} - {} {} {}\n{} \nEntry: {} \nCurrent price: {}\n".format(
                    re_market, re_strategy, re_exchange.title(), re_direction, re_simulation,
                    descr_price, re_entry, re_price_curr)
        reply_string_profit += '\n'

    # Info from the DB - buy jobs
    # DB: id, market, price_fixed, price, abort_flag
    reply_string_buy = '⏳ Looking for entries\n'

    sql_string = "SELECT * FROM buys WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)

    if rows == []:
        no_buy_tasks = True
    else:
        for row in rows:
            re_b_market = row[1]
            markets_status.add(re_b_market)

            # Deprecate
            '''
            if re_b_market == 'btc/usd':
                round_num = 2
            else:
                round_num=10
            '''
            round_num = 2

            re_b_fixed = row[2]
            if row[3] is not None:
                re_b_price = round(row[3], round_num)
            else:
                re_b_price = None
            re_b_position = row[5]
            if float(re_b_position) > 0:
                re_b_direction = '(long)'
            else:
                re_b_direction = '(short)'
            re_b_mode = row[6]
            re_b_exchange = row[7]
            re_b_strategy = row[9]
            if re_b_fixed == 0:
                price_descr = 'Floating'
            else:
                price_descr = 'Fixed'
            # For reply purposes
            if re_b_price == 0:
                re_b_price = "(auto)"
            reply_string_buy += "\n{} {} - {}. \nTotal position amount (on margin): {}\n".format(
                re_b_market, re_b_strategy, re_b_exchange.title(),
                re_b_position)
        reply_string_buy += '\n'

    # Info from the DB - buybacks
    # DB: id, market, trade_price
    reply_string_bb = '⏳ Looking for re-entries\n'
    sql_string = "SELECT * FROM bback WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)
    if rows == []:
        no_bb_tasks = True
    else:
        for row in rows:
            bb_market = row[1]
            markets_status.add(bb_market)

            if bb_market == 'btc/usd':
                round_num = 2
            else:
                round_num=10

            if row[2] is not None:
                bb_price = round(float(row[2]), round_num)
            else:
                bb_price = None
            if row[3] is not None:
                bb_curr_price = round(float(row[3]), round_num)
            else:
                bb_curr_price = None
            bb_trade_price = row[9]     # for how much value is buyback planned
            if row[9] is not None:
                bb_trade_price = round(float(row[9]), 5)
            else:
                bb_trade_price = None
            bb_exchange = row[6]
            bb_strategy = row[8]
            reply_string_bb += "\n{} {} - {}: stopped @ {}, current {}. Total position (on margin): {}\n".format(
                bb_market, bb_strategy,
                bb_exchange.title(), bb_price,
                bb_curr_price,
                round(bb_trade_price, 3)
                )
        reply_string_bb += '\n\n'

    # Info from the DB - long-term holds
    # DB: id, market, EP, quantity
    reply_string_long = 'Hodl\n'

    sql_string = "SELECT * FROM longs WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)

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
            re_l_curr_price = float(e_api.getticker(re_l_exchange, re_l_market))

            re_price_prop = round((re_l_curr_price / re_l_price) * 100, 1)
            reply_string_long += "\n{} ({}), current price: {} % of EP, Q: {}\n".format(re_l_market, re_l_exchange,
                                                                                        re_price_prop, re_l_q)

    if (no_profit_tasks != True):
        reply_string = reply_string + reply_string_profit
    if (no_buy_tasks != True):
        reply_string = reply_string + reply_string_buy
    if (no_bb_tasks != True):
        reply_string = reply_string + reply_string_bb
    if (no_longs != True):
        reply_string = reply_string + reply_string_long

    if reply_string == '':
        reply_string = 'No active jobs'


    else:
        reply_string += '📊 Market status\n\n'
        for market in markets_status:

            # Always 2
            round_num = 2
            '''
            if market == 'btc/usd':
                round_num = 2
            else:
                round_num=10
            '''

            # Jobs
            sql_string = "SELECT prediction, probability, " \
                         "price FROM market_info WHERE market = '{}'".format(market)
            print(sql_string)

            rows = sql.query(sql_string)
            if rows != []:
                for row in rows:
                    market_stat_str = "{}: {} ({:.0%} confidence) \nPrice: {}\n\n".format(
                        market, row[0], row[1], round(row[2], round_num)
                    )
                    reply_string += market_stat_str

    send_chat_message(user_to, reply_string)

### Abort
def telegram_abort(user_to):
    global responses_df, tmp_list

    # To add a keyboard
    keyboard_arr = []

    # Fill a temporary list
    counter = 0
    reply_string = ''
    tmp_list = []

    # Jobs
    sql_string = "SELECT * FROM jobs WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)
    if rows != []:
        reply_string += 'Listing your active tasks. \n\nTrading jobs running:\n'
        for row in rows:
            tmp_list.append([counter, 'jobs', row[0]])
            keyboard_arr.append(str(counter))
            reply_string += str(counter) + ': ' + row[1] + ', EP ' + str(row[3]) + ', Simulation: ' + str(
                bool(row[4])) + ', Strategy: ' + row[18] + '\n'
            counter += 1
    # Buys
    sql_string = "SELECT * FROM buys WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)
    if rows != []:
        reply_string += '\nLooking for entries and opening a position:\n'
        for row in rows:
            tmp_list.append([counter, 'buys', row[0]])
            keyboard_arr.append(str(counter))
            reply_string += str(counter) + ': ' + row[1] + ', mode ' + str(row[6]) + ', strategy: ' + row[9] + '\n'
            counter += 1
    # Buybacks
    sql_string = "SELECT * FROM bback WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)
    if rows != []:
        reply_string += '\nMonitoring for the next entries:\n'
        for row in rows:
            tmp_list.append([counter, 'bback', row[0]])
            keyboard_arr.append(str(counter))
            #reply_string += str(counter) + ': ' + row[1] + ', bb_price ' + str(row[2]) + ', strategy: ' + row[8] + '\n'
            reply_string = "{}{}: {}\n".format(reply_string, counter, row[1])
            counter += 1
    # Buy queue on hold
    sql_string = "SELECT * FROM buy_hold WHERE userid = {}".format(user_to)
    rows = sql.query(sql_string)
    if rows != []:
        reply_string += '\nBuys on hold (waiting for positions to be closed first):\n'
        for row in rows:
            tmp_list.append([counter, 'buy_hold', row[0]])
            keyboard_arr.append(str(counter))
            #reply_string += str(counter) + ': ' + row[1] + ', mode ' + str(row[6])  + ', strategy: ' + row[9] + '\n'
            reply_string = "{}{}: {}\n".format(reply_string, counter, row[1])
            counter += 1

    reply_string += '\nChoose the option to abort or ignore to do nothing.'

    keyboard_arr_transformed = []
    keyboard = []
    for elem in keyboard_arr:
        keyboard_arr_transformed.append(
            InlineKeyboardButton(str(elem), callback_data='abort:{}'.format(elem))
        )
    keyboard.append(keyboard_arr_transformed)
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(
        chat_id=user_to,
        text = reply_string,
        reply_markup=reply_markup
    )


def telegram_abort_execute(user_to, value):
    global tmp_list

    msg_text = value #sanitise(value)
    user_to = user_to

    id = tmp_list[int(msg_text)][2]
    print("Stopping id as requested:", id, "which is the id:", tmp_list[int(msg_text)][1])
    if tmp_list[int(msg_text)][1] == 'jobs':
        sql_string = "UPDATE jobs SET abort_flag = 1 WHERE job_id = {} AND userid = {}".format(id,
                                                                                               user_to)  # flagging for cancellation
        sql.query(sql_string)
        reply = 'Job {} flagged for cancelling'.format(msg_text)
        send_chat_message(user_to, reply)
    if tmp_list[int(msg_text)][1] == 'buys':
        sql_string = "UPDATE buys SET abort_flag = 1 WHERE job_id = {} AND userid = {}".format(id,
                                                                                               user_to)  # flagging for cancellation
        sql.query(sql_string)
        reply = 'Buy {} flagged for cancelling'.format(msg_text)
        send_chat_message(user_to, reply)
    if tmp_list[int(msg_text)][1] == 'bback':
        sql_string = "UPDATE bback SET abort_flag = 1 WHERE id = {} AND userid = {}".format(id,
                                                                                            user_to)  # flagging for cancellation
        sql.query(sql_string)
        reply = 'Reentry {} flagged for cancelling'.format(msg_text)
        send_chat_message(user_to, reply)
    if tmp_list[int(msg_text)][1] == 'buy_hold':
        sql_string = "UPDATE buy_hold SET abort_flag = 1 WHERE job_id = {} AND userid = {}".format(id,
                                                                                                   user_to)  # flagging for cancellation
        sql.query(sql_string)
        reply = 'Buy on hold {} flagged for cancelling'.format(msg_text)
        send_chat_message(user_to, reply)


####################################################################################################
###################################### Starting the daemon #############################################

### Updating the legit users list 
def legit_users_update(): 
    rows = sql.query("SELECT userid FROM user_info")
    legit_users = []
    for row in rows:
        if ignore_admin:
            if row[0] != config.telegram_chat_id:
                legit_users.append(row[0])
        else:
            legit_users.append(row[0])
    # Rewrite if admin-only
    if only_admin:
        legit_users = [config.telegram_chat_id] 
    return legit_users
    
def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"', update, error)

def echo(bot, update):
    # Processing 2nd and 3rd answers
    text = update.message.text
    requestor = update.message.chat_id
    if requestor in responses_df.index:
        if (responses_df.loc[requestor] == 'db_clean').bool():
            _thread.start_new_thread( telegram_db_clean_execute, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'add_user_step_1').bool():
            _thread.start_new_thread( telegram_add_user_1, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'add_user_step_2').bool():
            _thread.start_new_thread( telegram_add_user_2, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'keys_step_1').bool():
            _thread.start_new_thread( telegram_keys_set_1, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'keys_step_2').bool():
            _thread.start_new_thread( telegram_keys_set_2, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'abort').bool():
            _thread.start_new_thread( telegram_abort_execute, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'new_sell').bool():
            _thread.start_new_thread( telegram_new_sell_execute, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'initiate').bool():
            _thread.start_new_thread( telegram_initiate_execute, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'close_position').bool():
            _thread.start_new_thread( telegram_close_position_execute, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'workflow').bool():
            _thread.start_new_thread( telegram_workflow_launch, (requestor, text, ) )

        if (responses_df.loc[requestor] == 'use_all_balance').bool():
            _thread.start_new_thread( telegram_use_all_balance_execute, (requestor, text, ) )


## Functions to handle commands
def startbot(bot, update):
    requestor = update.message.chat_id
    print("> Start request from", requestor)
    msg = """ 
Welcome to the lambobot. Please read Q&A available by this link: https://goo.gl/S4BC2e
 
Note that you will not receive response to any commands until your access is enabled by the bot admin. 
    """
    send_chat_message(requestor, msg)


def help(bot, update):
    requestor = update.message.chat_id
    print("> Request from", requestor)
    if int(requestor) in legit_users:
        msg = """ 
Brief guide on what to use when.

1. You want to update margin level or keys: To update keys, run /keys_update and to update margin run /margin_change. 

2. You do not have any positions open on bitmex for the desirable market (e.g. btc/usd): 
a. Launch /auto for fully automated job which will open positions and close them. Note that all jobs are launched on the active strategy and related account. You could check your active strategy using /strategy_info.
b. Lauch /initiate_position to open a position now or based on TA (fullta mode). 

3. You have open positions on bitmex: 
a. Launch /new to start a trading job. You would need to specify entry price, desired exit price, other parameters on launch. 
b. Launch /auto to launch automated job which will be on hold until you close your positions.  

4. You launched /auto and a job is currently running. 
a. Launch /abort to stop any of the running tasks (looking for entries, buybacks, trading jobs). 
(!) This will not close your open positions on the exchange.
b. Launch /close_position when an active trading job is in process after opening some positions. This will close your positions and will stop the task. 

Remember that the typical flow for an automated job is: 
Looking for entries -> Entering -> Handling positions -> Exiting -> Looking for reentries -> Entering -> ...
        """
        send_chat_message(requestor, msg)

        msg = """ 
Description of commands:

Start a new automatic job: /auto 
Check running tasks: /status 
Cancel tasks: /abort
Check balance: /balance 
Close a position now: /close_position 
Change your margin level: /margin_change
Update your keys: /keys_update
Initiate a position: /initiate_position
Start a trading task: /new (including simulations)
Names of contracts available in the bot: /markets 

For /initiate_position mode, initiation modes are: now/now-s/fullta/fullta-s 
options with -s mean simulation mode 
now buys immediately in real mode (or in simulation if there is simulation workflow) 
fullta buys based on price action when lower time interval and higher time intervals are in line

Job (/new) modes: s/r/sns/rns/rnts
s - simulation with stops 
r - real mode with stops and take profit 
sns - simulation without stops \nrns - real mode with no stops (careful!)
rnts - real mode without trailing stops
        """
        send_chat_message(requestor, msg)
 
def margin_change(bot, update):
    requestor = update.message.chat_id
    print("> margin_change:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_e_strategy_select, (requestor, 'margin_change', ) )
    
def keys_update(bot, update):
    requestor = update.message.chat_id
    print("> keys_update:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_e_strategy_select, (requestor, 'keys_update', ) )

def status(bot, update):
    requestor = update.message.chat_id
    print("> status:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_status, (requestor, ) )

def balance(bot, update):
    requestor = update.message.chat_id
    print("> balance:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_balance, (requestor, ) )

def markets(bot, update):
    requestor = update.message.chat_id
    print("> markets:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( available_markets, (requestor, ) )

def abort(bot, update):
    requestor = update.message.chat_id
    print("> abort:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_abort, (requestor, ) )

def new(bot, update):
    requestor = update.message.chat_id
    print("> new:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_e_strategy_select, (requestor, 'new_sell', ) )

def initiate_position(bot, update):
    requestor = update.message.chat_id
    print("> initiate_position:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_e_strategy_select, (requestor, 'initiate_position', ) )

def auto(bot, update):
    requestor = update.message.chat_id
    print("> auto:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_e_strategy_select, (requestor, 'auto_job', ) )

def close_position(bot, update):
    requestor = update.message.chat_id
    print("> close_position:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_close_position, (requestor, ) )

def workflow(bot, update):
    requestor = update.message.chat_id
    print("> workflow:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_e_strategy_select, (requestor, 'telegram_workflow', ) )

def my_positions(bot, update):
    requestor = update.message.chat_id
    print("> my_positions:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_e_strategy_select, (requestor, 'telegram_mypositions', ) )

def strategy_info(bot, update):
    requestor = update.message.chat_id
    print("> strategy_info:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_strategy_status, (requestor, ) )

def my_trades(bot, update):
    requestor = update.message.chat_id
    print("> my_trades:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_trades, (requestor, ) )

def stoplistener(bot, update):
    requestor = update.message.chat_id
    print("> stoplistener:", requestor)
    if requestor == config.telegram_chat_id:
        updater.idle()
        exit(0)

def add_user(bot, update):
    requestor = update.message.chat_id
    print("> add_user:", requestor)
    if requestor == config.telegram_chat_id:
        _thread.start_new_thread( telegram_add_user, (requestor, ) )

def clean_my_db(bot, update):
    requestor = update.message.chat_id
    print("> clean_my_db:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_clean_my_db, (requestor, ) )

def use_all_balance(bot, update):
    requestor = update.message.chat_id
    print("> use_all_balance:", requestor)
    if int(requestor) in legit_users:
        _thread.start_new_thread( telegram_use_all_balance, (requestor, ) )


# Answer to different commands 
dp.add_handler(CommandHandler("help", help))
dp.add_handler(CommandHandler("start", startbot))
dp.add_handler(CommandHandler("margin_change", margin_change))
dp.add_handler(CommandHandler("keys_update", keys_update))
dp.add_handler(CommandHandler("status", status))
dp.add_handler(CommandHandler("balance", balance))
dp.add_handler(CommandHandler("markets", markets))
dp.add_handler(CommandHandler("abort", abort))
dp.add_handler(CommandHandler("new", new))
dp.add_handler(CommandHandler("initiate_position", initiate_position))
dp.add_handler(CommandHandler("auto", auto))
dp.add_handler(CommandHandler("close_position", close_position))
dp.add_handler(CommandHandler("workflow", workflow))
dp.add_handler(CommandHandler("my_positions", my_positions))
dp.add_handler(CommandHandler("strategy_info", strategy_info))
dp.add_handler(CommandHandler("my_trades", my_trades))
dp.add_handler(CommandHandler("stoplistener", stoplistener))
dp.add_handler(CommandHandler("add_user", add_user))
dp.add_handler(CommandHandler("clean_my_db", clean_my_db))
dp.add_handler(CommandHandler("use_all_balance", use_all_balance))

# process messages 
dp.add_handler(MessageHandler(Filters.text, echo))

# process callbacks 
updater.dispatcher.add_handler(CallbackQueryHandler(callback_handle))

# log all errors
dp.add_error_handler(error)

# The bare bot 
bot = telegram_python_bot.Bot(config.telegram_token)

# Start the Bot
legit_users = legit_users_update() 
print('Waiting for new instructions from Telegram.\n')
updater.start_polling()

# Update status and legit users periodically
while True: 
    legit_users = legit_users_update()

    chat.status_report()

    time.sleep(300)
