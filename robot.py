################# Use examples #############
# > python robot.py initiate now bmex btc/usd 0.005
# > python robot.py initiate full_cycle bmex btc/usd 0.005
# > python robot.py process r bmex btc/usd 6398
# > python robot.py initiate now oanda usd_jpy 11 --core_strategy=traditional
# > python robot.py initiate now oanda nas100_usd 1500 --core_strategy=traditional
# > python robot.py initiate full_cycle oanda usd_jpy 100 --core_strategy=traditional
################# Libraries ##################
# Standard libraries

from sys import argv
import math
import urllib.request, urllib.error, urllib.parse
import decimal
from decimal import Decimal
import traceback
import argparse

from datetime import datetime
import random

# For lulz
import safygiphy
g = safygiphy.Giphy()

# Decimal precision and rounding 
decimal.getcontext().prec = 25
decimal.getcontext().rounding = 'ROUND_DOWN'

## Custom libraries
import libs.sqltools as sqltools
sql = sqltools.sql()

import libs.platformlib as platform                                  # detecting the OS and setting proper folders
import libs.aux_functions as aux_functions  # various auxiliary functions
import libs.tdlib as tdlib    # Price analysis library - in threads
import robo_class  # class to store robot job constants and used variables

td_info = tdlib.tdlib()
aux_functions = aux_functions.aux_functions()

from libs.aux_functions import send_chat_message

################################ Config and imports - part I ############################################

import config   # Import a configuration file
import backtest     # Backtest import
b_test = backtest.backtesting()

import exch_api  # exchanges 

### Platform
platform = platform.platformlib()
platform_run, cmd_init = platform.initialise()
print("Initialising...")

# Parse custom params if there are any (on early stages)
parser = argparse.ArgumentParser()
parser.add_argument('--userid', type=int, help="User id (telegram")
parser.add_argument("--core_strategy", type=str, help="Core strategy name (blank is standard)")   # strategy (standard / micro)  # deprecate this
parser.add_argument('--is_restart', type=int, help="Restart indicator (1 or 0)")
args, unknown = parser.parse_known_args()
user_id = getattr(args, 'userid')

if user_id is None:
    user_id = config.telegram_chat_id     # my id

is_restart = getattr(args, 'is_restart')
if is_restart is not None:  # restart indicator
    is_restart = True
else:
    is_restart = False

# Using coinigy to get prices so that there are no stringent restrictions on api request rates (frequency)
from libs.coinigylib import coinigy 

'''# Telegram integration:using aux_functions now
#import telegram as telegram_python_bot  # for bare wrapper to send files
#bot = telegram_python_bot.Bot(config.telegram_token)
 '''

### Default values
no_input = False 
trailing_stop_flag = True  # default mode is to have trailing stop

###################################################################################
############################## Auxiliary functions   #####################################
###################################################################################

### Send message: now using aux_functions
'''
def send_chat_message(user_to, text):
    try:
        if not config.backtesting_enabled:
            bot.send_message(
                chat_id=user_to,
                text=text,
                timeout=30
            )
    except:
        err_msg = traceback.format_exc()
        print("\n(i) Note: Failed to send telegram message. Reason: {}". format(err_msg))
'''


### Notify admin about issues
def issue_notify(robot_instance, error, only_admin = False):
    admin_id = config.telegram_chat_id
    user = robot_instance.user_id

    admin_string = 'Error for the user {}. Reason: {}. Check the scripts.'.format(user, error)
    comm_string = 'An error occured in the {} job. The admin was notified and is looking into it.'.format(robot.exchange)
    robot_instance.logger.lprint([admin_string])
    if not only_admin:
        send_chat_message(robot.user_id, comm_string)
    send_chat_message(admin_id, admin_string)

### Function to get original value
def original_value(robot, exchange, market, e_api):
    try:
        if not robot.simulation and not b_test.backtesting:
            if exchange == 'bitmex':
                all_positions = e_api.getpositions(exchange, market)
                if all_positions != [{}]:
                    position = e_api.getpositions(exchange, market)[0]
                    # For the btc market
                    if robot.market in config.primary_calc_markets:
                        robot.value_original = position['contracts']/robot.price_entry
                    # For the other  markets
                    else:
                        position = e_api.getpositions(exchange, market)[0]
                        robot.value_original = robot.price_entry*position['contracts_no']
                else:
                    robot.value_original = None
            elif exchange == 'oanda':
                all_positions = e_api.getpositions(exchange, market)
                if all_positions != [{}]:
                    position = e_api.getpositions(exchange, market)[0]
                    if robot.forex_pair:
                        robot.value_original = position['contracts']  # in usd
                    else:
                        robot.value_original = position['contracts']*position['entryprice']  # in usd
            else:
                robot.logger.lprint([ "Other exchanges are not supported yet"])
                send_chat_message(robot.user_id, 'Exchange is not supported')
                robot.terminate()
        # In simulation
        else:
            robot.value_original = robot.simulation_balance*robot.margin_level
    except:
        robot.logger.lprint([ "API keys error when checking value"])
        send_chat_message(robot.user_id, 'API keys error when checking value')
        robot.terminate()

### Checking for positions # do this for oanda?
def buyer_check_positions(robot, e_api):
    buy_terminate = False
    hold_id = None

    ### If we are in the real mode and there are open positions on bitmex (e.g. we have set a stop manually) - postpone the execution
    if (robot.wf_run_mode != 's') and config.postpone_entries:
        positions = e_api.getpositions(robot.exchange, robot.market)

        try:    # if positions open, insert a record in holds
            contracts_check = positions[0]['contracts']
            retry = True
            robot.logger.lprint(['Positions are open on the exchange, holding on until ready...'])
            send_chat_message(robot.user_id, 'Positions are open on the exchange - waiting until they are closed')
            ### Inserting in the sqlite db if started fine
            sql_string = "INSERT INTO buy_hold(market, abort_flag, price_fixed, price, source_position, mode, exchange, userid, core_strategy) " \
                         "VALUES ('{}', 0, {}, {}, {}, '{}', '{}', {}, '{}')".format(
                robot.market, int(robot.fixed_price_flag), robot.fixed_price,
                robot.source_position, robot.mode, robot.exchange, robot.user_id, robot.core_strategy)
            hold_id, rows = sql.query_lastrow_id(sql_string)
        except:
            retry = False

        # Retry until the positions are OK to go
        while retry:
            # Checking if there are contracts returned
            try:
                # If cancellation requested
                approved_flag = sql.check_cancel_flag(robot, hold_id, 'buy_hold')
                if not approved_flag:
                    sql_string = "DELETE FROM buy_hold WHERE job_id = {} " \
                        "AND userid = {} AND core_strategy = '{}' ".format(
                            hold_id, robot.user_id, robot.core_strategy)
                    sql.query(sql_string)
                    robot.logger.lprint(['Cancelled holding out and a buy task. Restart if needed.'])
                    send_chat_message(robot.user_id, 'Cancelled holding out and a buy task. Restart if needed.')
                    buy_terminate = True
                    retry = False
                else:
                    positions = e_api.getpositions(robot.exchange, robot.market)
                    #print positions #TEST
                    contracts_check = positions[0]['contracts']
                    b_test.sleep(robot.sleep_buy_timer)
                    #print "Contracts check", contracts_check
            except:
                retry = False

        # Resume if the cycle finished
        if buy_terminate:
            proceed_decision = False
        else:
            proceed_decision = True
            robot.logger.lprint(['No positions open, ready to start'])
            if hold_id is not None:
                sql_string = "DELETE FROM buy_hold WHERE job_id = {} AND userid = {} " \
                    "AND core_strategy = '{}' ".format(
                        hold_id, robot.user_id, robot.core_strategy)
                sql.query(sql_string)

        return proceed_decision

    else: # implement for other exchanges
        return True

### Checking balance and changing the position size
def ensure_balance(robot, checked_price = None):

    result = True # default

    if robot.simulation or config.backtesting_enabled:
        return True
    else:
        # On bitmex, BTC only is used as collateral
        if robot.exchange == 'bitmex':
            check_token = 'BTC'
        else:
            check_token = robot.trade

        balance = e_api.getbalance(robot.exchange, check_token)
        #robot.logger.lprint(['Checking balance response:', balance])

        if balance is not None:
            balance_avail = balance['Available']
            robot.logger.lprint(['Available balance:', balance_avail])

            # Changing the available balance and changing the value if there is no enough funds
            if robot.exchange == 'bitmex':
                balance_avail = Decimal(balance_avail).quantize(Decimal('.0001'), rounding='ROUND_DOWN')
                balance_check = balance_avail * Decimal(0.99) * robot.margin_level

                if (balance_check < robot.source_position) and (balance_check > 0.001):   # changing position  if there is more than 0.001 on the balance
                    robot.source_position = balance_avail * robot.margin_level * Decimal(0.99)
                    robot.logger.lprint(['Corrected the position in ensure balance:', balance_avail ])
                    result = True
                if (balance_check < robot.source_position) and (balance_check <= 0.001):   # do not proceed it not enough balance (less than 0.001)
                    result = False
                if balance_check >= robot.source_position:
                    result = True

                # Need to ensure that requested amount is fine to proceed with the buy (specifics for alts)
                if (checked_price is not None) and robot.market not in config.primary_calc_markets:    # (robot.market <> 'btc/usd'):
                    ratio = float(robot.source_position * robot.margin_level)/float(checked_price)
                    if ratio < 1.0:
                        amount_required = (float(checked_price) / float(robot.margin_level))*1.01 # allowing for a slight deviation
                        status_msg = 'You cannot open one contract on this market for this amount. Minimum amount needed: {}'.format(amount_required)
                        robot.logger.lprint([status_msg])
                        send_chat_message(robot.user_id, status_msg)
                        result = False
                    else:
                        result = True
                return result

            elif robot.exchange == 'oanda': # For the other exchanges (potentially to reconsider)
                if Decimal(str(balance_avail * robot.margin_level)) < Decimal(str(robot.source_position)):
                    robot.source_position = Decimal(str(balance_avail * robot.margin_level))
                    robot.logger.lprint(['Corrected the position in ensure balance:', robot.source_position ])
                    return True
                else:
                    return True

        # If there is an api key issue
        else:
            robot.logger.lprint(['API keys issue'])
            return None


###################################################################################
############################## MAIN WORKFLOW FUNCTIONS   #########################
###################################################################################

###  Re-buy (buy back) wrapper
def buy_back_wrapper(robot, b_test):
    bb_price = robot.stopped_price  # from the exit

    # Starting buyback except for the cases when the task was aborted through telegram #Commented now - reconsidered that I still need this
    # if stopped_mode != 'telegram':
    robot.logger.lprint(["Buyback monitoring started:", robot.stopped_mode])

    if robot.exchange == 'bitmex':

        buy_trade_price = robot.value_original * (
                    1 + float(robot.earned_ratio * robot.margin_level) / 100) / robot.margin_level

        robot.logger.lprint(
            [">>> Sale outcomes: buy trade price (to use in buyback)", buy_trade_price, "main_curr_from_sale",
             robot.main_curr_from_sell,
             "margin", robot.margin_level, "earned ratio", robot.earned_ratio, "value original", robot.value_original])

    elif robot.exchange == 'oanda':

        if not robot.forex_pair:
            buy_trade_price = (robot.value_original / robot.margin_level) * (
                        1 + float(robot.earned_ratio * robot.margin_level) / 100)
        else:
            buy_trade_price = (robot.value_original) * (
                        1 + float(robot.earned_ratio * robot.margin_level) / 100)
            buy_trade_price = buy_trade_price / robot.margin_level

        usd_x_rate = usd_rate_value(robot, e_api)
             
        #print "USD RATE {} Buy trade price {}".format(usd_x_rate, buy_trade_price)   #DEBUG

        buy_trade_price = float(buy_trade_price)/float(usd_x_rate)

        robot.logger.lprint(
            [">>> OANDA sale outcomes: buy trade price (to use in buyback)", buy_trade_price, "main_curr_from_sale",
             robot.main_curr_from_sell,
             "margin", robot.margin_level, "earned ratio", robot.earned_ratio, "value original", robot.value_original])
    else:
        # commission depending on the exchange. If we do not have TD data
        buy_trade_price = float(robot.balance_start) * bb_price * (1 - robot.comission_rate)

    # Workaround if no orders
    if (robot.no_sell_orders) and robot.exchange in ['bitmex']:
        robot.terminate()
    else:
        # try:
        # Inserting into buyback information table
        sql_string = "INSERT INTO bback(market, bb_price, curr_price, trade_price, exchange, userid, core_strategy, bb_price_margin) " \
                     "VALUES ('{}', {}, {}, {}, '{}', {}, '{}', {})".format(
            robot.market, bb_price, bb_price, buy_trade_price,
            robot.exchange, robot.user_id, robot.core_strategy,
            buy_trade_price * robot.margin_level)
        robot.bb_id, rows = sql.query_lastrow_id(sql_string)

        time_bb_trigger = b_test.time()  # getting a snapshot of time for buyback so that we wait for at least an hour before starting buyback
        bb_flag, direction = buy_back(robot, bb_price, time_bb_trigger,
                                                            b_test=b_test)  # runs until a result is returned with a confirmation and a direction which defines the next step
        '''
        except:
            bb_flag = False # if there were issued with inserting / finding
            err_msg = traceback.format_exc()
            comm_string = '{} {}: Error when performing buyback: {}. Please notify the admin'.format(robot.market, robot.exchange, err_msg)
            robot.logger.lprint([comm_string])
            chat.send(comm_string)
        '''

        # If we have reached the target to initiate a buyback and there was no cancellation through Telegram
        if bb_flag:
            notification_text = 'Re-entry initiated for {} on {}. Direction: {}. Confidence: {:.0%}'.format(
                robot.market, robot.exchange, aux_functions.direction_name(direction), float(robot.prediction_probability))
            send_chat_message(robot.user_id, notification_text)
            robot.logger.lprint(["Re-entry in the direction:", aux_functions.direction_name(direction)])

            # Storing entry direction
            robot.entry_direction = direction

            # print "bb_price {}, tp {}, buy_delta {}, tp_price {}, sl_price {}".format(bb_price, tp, buy_delta, tp_price, sl_price) # DEBUG
            sql_string = "INSERT INTO workflow(run_mode, price_entry, exchange, userid, core_strategy) " \
                         "VALUES ('{}', {}, '{}', {}, '{}')".format(
                robot.simulation_param, float(bb_price),
                robot.exchange_abbr, robot.user_id, robot.core_strategy)
            robot.wf_id, rows = sql.query_lastrow_id(sql_string)

            if robot.wf_id is not None:
                reentry_market = robot.trade

                sql_string = "UPDATE workflow SET market = '{}', trade = '{}', currency = '{}', " \
                             "exchange = '{}' WHERE wf_id = {} AND userid = {} AND core_strategy = '{}' ".format(
                    robot.market, robot.trade, robot.currency, robot.exchange_abbr, robot.wf_id, robot.user_id,
                    robot.core_strategy)
                robot.job_id, rows = sql.query_lastrow_id(sql_string)

            mode_buy = 'now'

            sql_string = "DELETE FROM bback WHERE id = {} AND userid = {} " \
                         "AND core_strategy = '{}' ".format(
                robot.bb_id, robot.user_id, robot.core_strategy)  # deleting buyback from the table
            sql.query(sql_string)

            # Rewritten - call the function rather than launch: change the input, run the robot
            # Direction stored in entry direction now
            robot.input('_', 'initiate', mode_buy, robot.exchange_abbr, reentry_market, str(buy_trade_price))
            robot.logger.lprint([
                "Buy called parameters: initiate", mode_buy, robot.exchange_abbr, reentry_market, str(buy_trade_price)
            ])

            robot.run_program_mode = 'initiate'

        # If a buyback cancellation was requested
        else:
            send_chat_message(robot.user_id, 'Buy back cancelled for {} on {}'.format(robot.market, robot.exchange))
            # Delete buyback from the DB
            sql_string = "DELETE FROM bback WHERE id = {} " \
                         "AND userid = {} AND core_strategy = '{}' ".format(
                robot.bb_id, robot.user_id, robot.core_strategy)
            sql.query(sql_string)
            robot.terminate()

### Cycle to wait for the price feed. Ensure that we never get Nones in the current price
def get_price_feed(robot, b_test):
    price_update = None

    while price_update is None:
        price_update = coinigy.price(robot.exchange_abbr, robot.market, robot.logger, b_test)
        if price_update is None:
            robot.logger.lprint(["---- cannot get prices from the feed. sleeping..."])
            b_test.sleep(30)

    return price_update


### Main workflow: buy back aux function
def buy_back_comment(td_result, td_direction, comment = ''):
    if td_result:
        if td_direction == 'red':
            robot.logger.lprint(["---- TD buyback: short {}".format(comment)])
        if td_direction == 'green':
            robot.logger.lprint(["---- TD buyback: long {}".format(comment)])

###  Main workflow: Looking for rebuy points (buyback)
def buy_back(robot, price_base, time_bb_initiated, b_test = b_test):

    ### Greetings (for logs readability)
    robot.logger.lprint(["###################### CYCLE: BUY_BACK ###########################"])

    if config.run_testmode: #<TEST>
        td_result, td_direction, over_threshold = robot.predicted_action_direction()
        return True, td_direction   # testmode to <TEST>

    td_direction = None # to return information on the direction of the new detected trend
    td_result = False

    ## Checking the conditions
    while not (td_result and over_threshold):
        # Updating the candles
        stop_reconfigure(robot, 'buy_back', b_test = b_test)

        # Check if we are within market hours for traditional markets
        is_market_open = is_trading_hours(b_test, robot)
        if not is_market_open:
            robot.prediction = 0
            robot.prediction_probability = 1
            robot.logger.lprint(["--- market is closed or almost closed - setting flag to no positions"])

        curr_timing = b_test.strftime("%d-%m-%Y %H:%M")
        robot.logger.lprint([curr_timing, robot.user_name, '|', robot.exchange, robot.market, "|",
            "prediction: {}, confidence {:.0%}".format(
            robot.predicted_name(robot.prediction), float(robot.prediction_probability))])   # prediction

        # Check if we need to cancel
        if not b_test.backtesting:
            stop_bback = sql.check_bb_flag(robot)
            if stop_bback:
                break

        # Checking time elapsed from the start of buyback
        time_elapsed = (math.ceil(b_test.time() - time_bb_initiated ))/60
        robot.exit_h_elapsed = round(time_elapsed/60, 1)

        # Getting the current price and showing info on potential longs or potential shorts
        robot.price = get_price_feed(robot, b_test)

        # Updating DB
        if robot.bb_id is not None and not b_test.backtesting:
            sql_string = "UPDATE bback SET curr_price = {}, last_update={} WHERE id = {} AND userid = {} AND core_strategy = '{}'".format(
                robot.price, b_test.time(), robot.bb_id, robot.user_id, robot.core_strategy)
            sql.query(sql_string)

        # Predictions check  ML
        td_result, td_direction, over_threshold = robot.predicted_action_direction()
        robot.logger.lprint(['--- validating (re-entry): td_result {}, td_direction {}, over_threshold {}'.format(
            td_result, td_direction, over_threshold)])

        if td_result and over_threshold:
            buy_back_comment(td_result, td_direction, 'prediction')

        # No need to sleep if the buyback is confirmed
        if not (td_result and over_threshold):
            b_test.sleep(int(robot.sleep_timer_buyback/robot.speedrun))

    # Finishing up
    return td_result, td_direction

### Update information on performed orders, p1
def sell_orders_info(robot, b_test = None):

    # Earned ratio for further recalculation
    if not robot.short_flag:
        robot.earned_ratio = round((float(robot.price_exit) / float(robot.price_entry) - 1) * 100, 2)
        robot.earned_ratio_multiple = ((float(robot.price_exit) / float(robot.price_entry) - 1)*robot.margin_level) + 1
    else:
        robot.earned_ratio = round((float(robot.price_entry) / float(robot.price_exit) - 1) * 100, 2)
        robot.earned_ratio_multiple = ((float(robot.price_entry) / float(robot.price_exit) -1)*robot.margin_level) + 1

    try: # to handle errors
        if not robot.simulation and not config.backtesting_enabled:
            # Reset values if we are not simulating
            robot.main_curr_from_sell = 0
            robot.commission_total = 0


            # Wait to collect orders info
            b_test.sleep(10)

            # Getting information on _sell_ orders executed
            orders_opening_upd = e_api.getorderhistory(robot.exchange, robot.market, lastid=robot.oanda_last_trans_id)

            for elem in orders_opening_upd:
                robot.orders_new.add(elem['OrderUuid'])
            orders_executed = robot.orders_new.symmetric_difference(robot.orders_start)

            # DEBUG block
            '''
            print ("START", robot.orders_start, "\n\n")
            print ("ORD_UPD", orders_opening_upd, "\n\n")
            print ("orders_executed", orders_executed, "\n\n")
            '''

            # Info on executions
            if orders_executed == set([]):
                robot.logger.lprint(["No sell orders executed"])
                robot.no_sell_orders = True
            else:  # iterating through orders
                robot.logger.lprint(["New executed orders"])    # oanda can give no info on cancelled orders which is ok
                for elem in orders_executed:
                    order_info = e_api.getorder(robot.exchange, robot.market, elem)
                    ''' # The response from bitmex could be empty sometimes
                    if order_info is None:
                        notify_string = "Issue when getting order info for order {} and user {}".format(elem, robot.user_id)    # troubleshooting
                        robot.logger.lprint([notify_string])
                        chat.send(notify_string, to_overwrite = config.telegram_chat_id)
                    '''
                    if order_info is not None:
                        if robot.exchange != 'bitmex':
                            robot.main_curr_from_sell += order_info['Price']
                            robot.commission_total += order_info['CommissionPaid']
                            qty_sold = order_info['Quantity'] - order_info['QuantityRemaining']
                            #robot.alt_sold_total += qty_sold  #deprecated
                            robot.logger.lprint([">>", elem, "price", order_info['Price'], "quantity sold", qty_sold ]) #DEBUG
                        else:
                            #robot.price_exit = robot.bitmex_sell_avg
                            if robot.price_exit != 0:
                                if robot.market in config.primary_calc_markets: #robot.market == 'btc/usd':  #
                                    robot.main_curr_from_sell = robot.contracts_start/robot.price_exit
                                else:
                                    robot.main_curr_from_sell = robot.contracts_start*robot.price_exit
                                #print "DEBUG: contracts_start {}, price_exit {}, main_curr_from_sell {}".format(
                                #    robot.contracts_start, robot.price_exit, robot.main_curr_from_sell)
                    else:
                        robot.logger.lprint(["No orders to process"])

                # Deprecate
                robot.logger.lprint(["Total price", robot.main_curr_from_sell]) #DEBUG

        # Deprecated
        #else:
            # If the simulation is True - main_curr_from_sell will have simulated value and the commission would be zero. Updating quantity.
            #robot.alt_sold_total = robot.limit_sell_amount
            #robot.logger.lprint(['Robot contracts start', robot.contracts_start]) #DEBUG

        # For bitmex in simulation we are accounting for loss/profit. In real mode it is done when calculating contracts anyway
        if robot.exchange == 'bitmex' and robot.simulation:
            # Accounting for the loss or the profit
            robot.main_curr_from_sell = float(robot.value_original) * float(robot.earned_ratio_multiple) * robot.margin_level
        # In the real mode, accounting for:
        if robot.exchange == 'bitmex' and not robot.simulation:
            robot.main_curr_from_sell = float(robot.earned_ratio_multiple) * robot.main_curr_from_sell

    except:
        err_msg = traceback.format_exc()
        issue_notify(robot, err_msg)


### Update information on performed orders and outcomes, p2
def sell_results_process(e_api, robot, timestamp_from, timestamp_to, use_start_value = False):
    orders_result = e_api.results_over_time(
        robot.exchange, robot.market, timestamp_from, timestamp_to + 60, lastid=robot.oanda_last_trans_id)   # +60 sec for contingency
    robot.logger.lprint(['Entry / exit results', orders_result, "| original value", robot.value_original])
    trade_commissions = orders_result['commission']
    trade_funding = orders_result['funding']
    if use_start_value:
        if robot.short_flag:
            start_value = -abs(robot.value_original)
        else:
            start_value = abs(robot.value_original)    # signs related to output, see results_over_time ()
        trade_outcome_preliminary = orders_result['total_outcome']
        trade_outcome = float(start_value) + float(trade_outcome_preliminary)
    else:
        trade_outcome = orders_result['total_outcome']
    percent_gained = round(100*float(trade_outcome)/float(abs(robot.value_original/robot.margin_level)), 2)   # in %
    return trade_outcome, trade_commissions, trade_funding, percent_gained

def sell_orders_outcome(robot, b_test = None):

    emoji_text = ''

    if not robot.no_sell_orders:
        if robot.exchange not in ['bitmex', 'oanda']:
            robot.logger.lprint(['Exchange currently not supported'])
        else: # calculation for bitmex based on timestamps
            if not b_test.backtesting:
                if robot.exchange == 'bitmex':
                    # If we have both start and end timestamps
                    if robot.timestamp_start_initiate is not None and robot.timestamp_finish is not None:
                        trade_outcome, trade_commissions, trade_funding, percent_gained = sell_results_process(e_api, robot, robot.timestamp_start_initiate, robot.timestamp_finish)

                    # If start timestamp comes from process - need to consider original value to calc difference
                    if (robot.timestamp_start_initiate is None) and (robot.timestamp_start_process is not None) and (robot.timestamp_finish is not None):
                        trade_outcome, trade_commissions, trade_funding, percent_gained = sell_results_process(e_api, robot, robot.timestamp_start_process,
                            robot.timestamp_finish, use_start_value = True)

                elif robot.exchange == 'oanda': # OANDA just uses the last trade and return the actual result so no need to pass start value
                    # Check which timestamp to use as a start
                    if robot.timestamp_start_initiate is not None:
                        timestamp_from = robot.timestamp_start_initiate
                    else:
                        timestamp_from = robot.timestamp_start_process
                    trade_outcome, trade_commissions, trade_funding, percent_gained = sell_results_process(e_api, robot, timestamp_from, robot.timestamp_finish)

                    #print("!!!!", trade_outcome, trade_commissions, trade_funding, percent_gained )

                # For consistency
                robot.earned_ratio = percent_gained/robot.margin_level
            else: # in backtesting mode
                if not robot.short_flag:
                    robot.earned_ratio = round((float(robot.price_exit)/float(robot.price_entry) - 1)*100, 2)   # in %
                else:
                    robot.earned_ratio = round((float(robot.price_entry)/float(robot.price_exit) - 1)*100, 2)  # in %
                percent_gained = robot.earned_ratio * robot.margin_level   # percent gained and earned ratio > 0 mean profit

            # Processing and writing the results / communicating
            # Flag for losing / winning trade
            if robot.earned_ratio >= 0:
                robot.losing_trade_flag = False
            else:
                robot.losing_trade_flag = True

            robot.trade_time = b_test.strftime("%d-%m-%Y %H:%M")
            #robot.logger.lprint(['Total from all sales', robot.main_curr_from_sell, 'total commission', robot.commission_total])   #not using
            robot.logger.lprint(['Price entry', robot.price_entry, ', price exit', robot.price_exit])
            robot.logger.lprint(['Earned % (no margin)', robot.earned_ratio, '| Original value:', robot.value_original])

            # Backtesting results storage
            if config.backtesting_enabled:
                robot.backtest_results.append([robot.entry_time, robot.trade_time, robot.earned_ratio])
                robot.logger.lprint(['> Backtesting results so far (%)'])
                tmp_sum = 0
                tmp_str = '\n'
                for elem in robot.backtest_results:
                    tmp_str = str(elem[2]) + '\n'
                    tmp_sum += elem[2]
                    robot.logger.lprint([tmp_str])
                robot.logger.lprint(["Total", tmp_sum, '\n'])

                # Also updating a summary log
                # check and fix here. multiplier is still ok to look at though
                ##balance_summary = robot.value_original * (1 + float(robot.earned_ratio)/100)/robot.margin_level

                robot.logger.write_summary(robot.backtest_results, robot.value_original_snapshot ,
                    robot.start_date, robot.trade_time, robot.margin_level,
                    codename = robot.codename, params_info = robot.attr_string)

            # Emoji to use and descriptions
            if not b_test.backtesting:

                # GIFs and emoji
                if robot.earned_ratio < 0:
                    emoji_text = '👻'         # whoopsie
                    r = g.random(tag="poor")
                else:
                    emoji_text = '💵'        # dollar
                    r = g.random(tag="rich")
                # Getting the pic 
                gifdata = r['data']
                if gifdata != {}:
                    try:  # in case of api issues 
                        gifurl = r['data']['images']['downsized']['url']
                    except: 
                        gifurl = None 
                else: 
                    gifurl = None 
                    
                if not robot.short_flag:
                    trade_description = '(long)'
                else:
                    trade_description = '(short)'

                price_exit_msg = round(float(robot.price_exit), robot.round_num)

                msg_result = '{} {}: Entry price: {}, exit price: {} {}. \nOutcome: {}% ({}% on margin).'.format(
                    emoji_text, robot.market, robot.price_entry, price_exit_msg,
                    trade_description, round(robot.earned_ratio, 2),
                    round(robot.earned_ratio * robot.margin_level, 2))
                send_chat_message(robot.user_id, msg_result)

                if gifurl is not None:
                    try:
                        if not config.backtesting_enabled:
                            bot.sendDocument(robot.user_id, gifurl)
                    except:
                        robot.logger.lprint(["Cannot send gif"])

                # Updating twitter if enabled
                if (robot.lambobot is not None) and not robot.simulation:
                    comm_string_twitter = '{} {}: closed a position. Entry price: {}, ' \
                                          'exit price: {} {}. {}% made (multiplied by margin) ' \
                                          '{} #{} #{} #algotrading'.format(emoji_text, robot.market.upper(),
                                                                                                robot.price_entry, price_exit_msg,
                                                                                                trade_description, round(robot.earned_ratio, 2),
                                                                                                robot.twitter_comment, robot.trade, robot.currency)
                    if gifurl is not None: 
                        try: # just in case if this returns an error
                            robot.lambobot.post_image(gifurl, comm_string_twitter)
                        except:
                            try:
                                robot.lambobot.post(comm_string_twitter)
                            except:
                                robot.logger.lprint(["Cannot tweet the status"])
                    else: 
                        try:
                            robot.lambobot.post(comm_string_twitter)
                        except:
                            robot.logger.lprint(["Cannot tweet the status"])
                    
                # Update the DB with trade logs
                if robot.timestamp_start_initiate is None:
                    active_start_timestamp = robot.timestamp_start_process
                else:
                    active_start_timestamp = robot.timestamp_start_initiate
                sql_string = "INSERT INTO trade_log(userid, start_timestamp," \
                " end_timestamp, trade_outcome, trade_commissions, " \
                "trade_funding, earned_ratio, percent_gained, core_strategy) VALUES " \
                "({}, {}, {}, {}, {}, {}, {}, {}, '{}')".format(robot.user_id, active_start_timestamp, robot.timestamp_finish,
                 trade_outcome, trade_commissions, trade_funding, robot.earned_ratio, percent_gained, robot.core_strategy)
                sql.query(sql_string)

### Just update db with the current price info
## NOPE! This messes up the prices
'''
def stop_reconfigure_update_db(robot, b_test):
    if not b_test.backtesting:
        sql_string = "SELECT id FROM market_info WHERE market = '{}'".format(robot.market)
        rows = sql.query(sql_string)
        if rows != []:
            # Existing - updating
            key_row_id = rows[0][0]
            sql_string = "UPDATE market_info SET price = {} WHERE id = {}".format(robot.price, key_row_id)
            sql.query(sql_string)
        else:
            # New - inserting
            sql_string = "INSERT INTO market_info(market, price) VALUES ('{}', {})".format(
                robot.market, robot.price
            )
            sql.query(sql_string)
'''

### Stop reconfigure status updates
def stop_reconfigure_status_update(robot, mode):
    # Status updates every 4H
    if (
            (mode == 'now') or
            ((mode == 'process') and (abs(int(robot.time_hour_update) - int(robot.time_hour_comms)) >= 4))
    ):
        robot.time_hour_comms = robot.time_hour_update

        # Percent of entry
        if mode != 'now':
            re_percent_of = robot.percent_of_entry
            if re_percent_of >= 100:
                re_percent_of -= 100
                price_descr_text = 'Price: (^) up {0:.2f}% from entry'.format(re_percent_of)
            else:
                re_percent_of = 100 - re_percent_of
                price_descr_text = 'Price: (v) down {0:.2f}% from entry'.format(re_percent_of)
        else:
            price_descr_text = ''

        status_update = "Status update ({} {}) {} \n\nPrediction: {}, confidence {:.0%}".format(
            robot.market, robot.exchange_abbr, price_descr_text, robot.predicted_name(robot.prediction),
            float(robot.prediction_probability))
        send_chat_message(robot.user_id, status_update)

        # Updating twitter
        if robot.lambobot is not None:
            comm_string_twitter = "You should have {} on {} (confidence {:.0%})".format(
                robot.predicted_name(robot.prediction), robot.market.upper(), float(robot.prediction_probability))

            try:  # just in case if this returns an error - this should not kill the whole script
                robot.lambobot.post(comm_string_twitter)
            except:
                pass


### Setting stop loss based on price data
# Returns whether price flipped to opposite TD action, and new stop targets based on larger td period
def stop_reconfigure(robot, mode = None, b_test = None):

    # Check if this is a time to exit in backtesting mode
    if b_test.finished:
        robot.logger.lprint(["Finished backtesting as per config"])
        robot.terminate()

    # Timers update
    robot.time_hour_update = b_test.strftime("%H")
    timer_minute = int(b_test.strftime("%M"))

    '''
    # NOPE! Prices are centralised now 
    # Rewritten: only update current price info and read predictions provided from the db
    stop_reconfigure_update_db(robot, b_test)
    '''

    # Get predictions from the DB if not backtesting
    if not b_test.backtesting:
        sql_string = "SELECT prediction, probability FROM market_info WHERE market = '{}'".format(robot.market)
        rows = sql.query(sql_string)
        if rows != []:
            robot.prediction = robot.predicted_num_from_name(rows[0][0])
            robot.prediction_probability = float(rows[0][1])

    # If backtesting
    else:
        # Updating control bars if due for ML
        if (timer_minute in robot.control_bars_minutes) or mode == 'now':
            timer_control_bars_check = '{}-{}'.format(robot.time_hour_update, timer_minute)
            if robot.timer_control_bars_update is None:
                robot.timer_control_bars_update = timer_control_bars_check
            if (robot.timer_control_bars_update != timer_control_bars_check) or mode == 'now':
                robot.timer_control_bars_update = timer_control_bars_check
                robot.logger.lprint(["(i) updating prediction"])

            # Predictions update (requires processed data in workflow db now
            try:
                if config.backtesting_use_db_labels:
                    label_to_predict = td_info.get_features(b_test.strftime("%Y-%m-%d %H:%M:00"),
                                                            robot)  # use this to get pre-computed DB results
                else:
                    label_to_predict = td_info.get_features_realtime(robot, b_test)  # realtime features calculation

                robot.prediction, robot.prediction_probability = td_info.predict_label(label_to_predict, robot)

            except TypeError:
                robot.logger.lprint(["error: cannot calculate features. check the prices file."])
                robot.prediction, robot.prediction_probability = 0, 1


    # Show the results
    robot.logger.lprint(["---- (i) prediction update: {}, confidence {:.0%}".format(
        robot.predicted_name(robot.prediction), robot.prediction_probability)])


    # Changing the result if we are out of market hours for traditional markets
    if not is_trading_hours(b_test, robot):
        robot.prediction, robot.prediction_probability = 0, 1
        robot.logger.lprint(["---- (i) out of market hours or close: changing the flag to 'no position'"])

    # Status updates every 4H
    if not robot.is_restart:
        stop_reconfigure_status_update(robot, mode=mode)
        robot.is_restart = False


                
### Main sell function to sell at current prices
# Will be performed until the balance available for sale is zero or slightly more
def sell_now(at_price, b_test = None):      # change for oanda: oanda closure is as simple as calling closeposition

    robot.price_exit = at_price

    # First run flag now to sleep on the first call
    proceed_w_sleep = False

    # Timer
    timer_sell_now_start = b_test.time()

    if robot.limit_sell_amount is not None:
        robot.limit_sell_amount = float(robot.limit_sell_amount)    # using str, we will not have more decimal numbers than needed
    if robot.sell_portion is not None:
        robot.sell_portion = float(robot.sell_portion)

    if robot.simulation:
        robot.balance_start = float(robot.simulation_balance)
        robot.balance_available = float(robot.simulation_balance)       # balance_available as of balance to close
        robot.remaining_sell_balance = float(robot.simulation_balance)

    # For bitmex / oanda, we will be trading contracts, no adjustments are available. Getting the balances and setting the original value
    if robot.exchange in ['bitmex', 'oanda']:
        if not robot.simulation and not b_test.backtesting:
            # There were issues with testnet returning blanks so changed this
            contracts_check = {}
            positions = e_api.getpositions(robot.exchange, robot.market)  # first not empty result
            for position in positions:
                if position != {}:
                    contracts_check = position
                    break # exit the for loop
            # print 'contracts_check', contracts_check #TEST
            # If nothing was found
            if contracts_check == {}:
                sell_run_flag = False
                contracts = 0
            else:
                if robot.market in config.primary_calc_markets: #robot.market == 'btc/usd':  #
                    contracts = contracts_check['contracts']
                else:
                    contracts = contracts_check['contracts_no']

                robot.contracts_start = contracts
                robot.balance_available = contracts
                balance_adjust = 0

        else: # if we are in the simulation mode
            if robot.market in config.primary_calc_markets:
                contracts =  robot.price_entry * robot.simulation_balance
            else:
                contracts = robot.simulation_balance / robot.price_entry
            robot.contracts_start = contracts

            #debug_str = "Backtesting - contracts check: {}, price entry {}, value original {}".format(robot.contracts_start, robot.price_entry, robot.value_original)
            #robot.logger.lprint([debug_str])      #DEBUG

    #  Working with sell_portion = contracts and with robot.contracts_start / robot.balance_available

    # Main sell loop
    sell_run_flag = True
    stopmessage = 'stop' # default stop message meaning successful sale

    #if (robot.exchange in ['bitmex']) or (config.backtesting_enabled and robot.exchange in ['oanda']):
    if (robot.exchange in ['bitmex', 'oanda']):
        while sell_run_flag:

            # Wait until existing orders are cancelled - that is why we need sleep here and not in the end
            # Checking Telegram requests and cancelling if needed
            if proceed_w_sleep:
                b_test.sleep(robot.sleep_sale)

            # Update the db
            process_db_updates(robot, sql, b_test, type='update')

            # 0. Check open orders, cancel if unfilled
            if not robot.simulation:
                orders_retry = True
                orders_retry_count = 0
                while orders_retry and orders_retry_count < 10:
                    my_orders = e_api.getopenorders(robot.exchange, robot.market)
                    if my_orders != '':
                        for val in my_orders:
                            # Checking if some are open not filling
                            if val['Quantity'] == 0:
                                unfilled_prop = 0
                            else:
                                unfilled_prop = float(val['QuantityRemaining'])/float(val['Quantity'])
                            if unfilled_prop >= 0.05:  # if more than 5% still left in the order
                                robot.logger.lprint(["-- cancelling unfilled order:", val['OrderUuid'], "quantity", val['Quantity'],
                                       "quantity remaining", val['QuantityRemaining'], "price", val['Price']
                                       ])
                                e_api.cancel(robot.exchange, robot.market, val['OrderUuid'])
                                b_test.sleep(5) # Wait for cancellations to be processed just in case
                    orders_retry = False


            # 1. Sell portion
            if robot.simulation:
                # If we are in the simulation mode - use the value from the previous run
                robot.balance_available = robot.remaining_sell_balance
                sell_portion = robot.balance_available

            # For bitmex, we will be trading contracts, no adjustments are available
            if robot.exchange in ['bitmex', 'oanda'] and not robot.simulation:
                # There were issues with testnet returning blanks so changed this
                contracts_check = {}
                positions = e_api.getpositions(robot.exchange, robot.market)  # first not empty result as there could be just 1 position open
                for position in positions:
                    if position != {}:
                        contracts_check = position
                        break # exit the for loop
                # If nothing was found
                if contracts_check == {}:
                    sell_run_flag = False
                else:
                    if robot.market in config.primary_calc_markets: #robot.market == 'btc/usd':  #
                        contracts = contracts_check['contracts']
                    else:
                        contracts = contracts_check['contracts_no']
                    robot.balance_available = contracts
                    balance_adjust = 0
                    sell_portion = robot.balance_available

            # Check if we have sold everything
            if robot.balance_available <= robot.contracts_start * 0.01:
                sell_run_flag = False

            #print(sell_run_flag, robot.balance_available, sell_portion, robot.contracts_start)

            # 2. If something is still required to be sold
            if sell_run_flag:
                robot.logger.lprint(["--- order amount", robot.balance_available, "at price threshold", at_price, "split on", sell_portion])
                remaining_sell_balance = robot.balance_available
                if robot.exchange == 'bitmex':
                    sale_steps_no = 1       # for the whole position (at least for now)
                else:
                    sale_steps_no = int(math.ceil(round(float((robot.balance_available))/float((sell_portion)), 3)))
                #print ">> Sell amount", balance_available, "remaining_sell_balance", remaining_sell_balance  #DEBUG#

                # Selling loop
                for i in range(1, sale_steps_no + 1):
                    # Check how much should we sell at this step
                    if sell_portion > remaining_sell_balance:
                        sell_q_step = remaining_sell_balance
                    else:
                        sell_q_step = sell_portion

                    # Price update
                    if robot.exchange != 'bitmex' or config.backtesting_enabled:
                        price_last_sell = get_price_feed(robot, b_test)
                    else:
                        # When we are long, on the exit we sell -> get the price from bids (the highest which is the first in the array)
                        # When we are short, on the exit we buy -> get the price from asks (the lowest, which is the first in the array)
                        if not robot.short_flag: #LONG
                            price_last_sell = float(e_api.getorderbook('bitmex', robot.market, 'bids')[0]['Rate'])
                        else: # SHORT
                            price_last_sell = float(e_api.getorderbook('bitmex', robot.market, 'asks')[0]['Rate'])

                    # Decreasing the price if necessary
                    price_to_sell = price_last_sell #*(1 - decrease_price_step)   # no need to do this with market making stuff

                    robot.logger.lprint(["----- placing order: Q:", sell_q_step, "@", price_to_sell, "last robot.market price:", price_last_sell,
                           "Remaining balance after sale:", round(remaining_sell_balance - sell_q_step, 6)])

                    # Account for attempts to try market making / using orderbook
                    current_postonly_flag = postonly_attempts_confirm(robot, timer_sell_now_start)

                    # Actually place sell orders if we are not in the simulation mode - re-check
                    if not robot.simulation:
                        # For bitmex, we will be placing contracts in the other direction (short)
                        if robot.exchange == 'bitmex':      # Bitmex
                            # Balance_available is the number of contracts here. Creating orders depending on the side (long or short)
                            if robot.market in config.primary_calc_markets: #robot.market == 'btc/usd':  #
                                price_to_sell = round(price_to_sell, 0)
                            else:
                                price_to_sell = round(price_to_sell, 20)
                            #robot.bitmex_sell_avg_arr.append(price_to_sell)

                            # Performing the order
                            if not robot.short_flag: #LONG
                                sell_result = e_api.selllimit(robot.exchange, robot.market, sell_q_step,
                                    price_to_sell, robot.balance_available, postonly = current_postonly_flag)
                            else: # SHORT
                                sell_result = e_api.buylimit(robot.exchange, robot.market, sell_q_step,
                                    price_to_sell, robot.balance_available, postonly = current_postonly_flag)

                            # print "e_api.selllimit({}, {}, {}, {}, {})".format(exchange, market, sell_q_step, price_to_sell, balance_available) #DEBUG

                        else:   # Any other exchange
                            if not robot.short_flag:  # LONG
                                sell_result = e_api.selllimit(robot.exchange, robot.market, sell_q_step, price_to_sell, postonly=current_postonly_flag)
                            else:
                                sell_result = e_api.buylimit(robot.exchange, robot.market, sell_q_step, price_to_sell, postonly=current_postonly_flag)

                        # Check sell results
                        robot.logger.lprint(["\n----- Sell result:", sell_result, "\n----"])
                        if sell_result is None:
                            robot.logger.lprint([ "None close position result. Retrying." ])
                            #send_chat_message(robot.user_id, 'None result when closing position. Script will be terminated, please close your residual positions manually')
                            return None
                        elif 'uuid' not in list(sell_result.keys()):
                            robot.logger.lprint([ "UUID not found in the results" ])
                            send_chat_message(robot.user_id, 'Order id not returned when closing position. Script will be terminated, please close your residual positions manually')
                            return None

                    else:
                        # If in simulation - calculate profit from the 'virtual' sale.
                        if robot.exchange != 'bitmex':
                            robot.main_curr_from_sell += float(sell_q_step) * price_to_sell
                            robot.commission_total += float(sell_q_step)*price_to_sell * robot.comission_rate
                        else:
                            robot.main_curr_from_sell += robot.contracts_start/price_to_sell
                            robot.commission_total = 0
                        sell_run_flag = False

                    # Update the db with price_last_sell
                    sql_string = "UPDATE jobs SET price_curr={}, selling={} WHERE job_id={} AND userid = {} AND core_strategy='{}' ".format(
                        round(price_last_sell, 8), 1, robot.job_id, robot.user_id, robot.core_strategy)
                    sql.query(sql_string)

                    # Decrease remaining balance to sell
                    remaining_sell_balance = remaining_sell_balance - sell_q_step

            # Checking Telegram requests and answering
            approved_flag = sql.check_cancel_flag(robot, robot.job_id, 'jobs')
            if not approved_flag:
                # Aborting if asked
                sell_run_flag = False
                stopmessage = 'abort_telegram'
            # Change the flag to sleep on the next cycle
            proceed_w_sleep = True

    #elif (not config.backtesting_enabled and robot.exchange in ['oanda']):
    #    stopmessage = e_api.closepositions(robot.exchange, market = robot.market, short_flag = robot.short_flag)

    # Finishing up
    #print "main_curr_from_sell {}, commission_total {}, robot.contracts_start {}".format (main_curr_from_sell,  commission_total, robot.contracts_start) # DEBUG

    # Timestamp for buyer start #added_precision
    robot.timestamp_finish = b_test.time()

    return stopmessage

### Short flag based on prediction
def short_flag_on_prediction(robot):
    if robot.prediction == 1:
        robot.short_flag = False
    elif robot.prediction == 2:
        robot.short_flag = True
    else:
        robot.short_flag = None
    robot.logger.lprint(['(i) prediction: {} ({}). short flag based on prediction: {}'.format(robot.predicted_name(robot.prediction), robot.prediction, robot.short_flag)])

### Checking direction based on the actual poritions
def process_direction_check(robot, e_api):

    flag_no_positions = True
    positions = e_api.getpositions(robot.exchange, robot.market)
    for position in positions:
        if position != {}:
            flag_no_positions = False
            if position['type'] == 'short':  # enabling short flag if the positions are in short
                robot.short_flag = True
                robot.logger.lprint(['(i) enabling robot.short_flag based on the actual position on the exchange'])
            break  # exit the for loop
    if flag_no_positions:
        send_chat_message(robot.user_id, 'Error: Zero positions on the exchange')
        robot.terminate()

### Process DB snippets
def process_db_updates(robot, sql, b_test, type = 'insert'):
    if type == 'insert':
        sql_string = "INSERT INTO jobs(market, simulation, mooning, selling, price_curr, " \
                            "percent_of, abort_flag, stop_loss, entry_price, mode, tp_p, sl_p, exchange, " \
                            "userid, core_strategy, short_flag) " \
                            "VALUES ('{}', {}, {},  {},  {},  {},  {}, {}, {}, '{}', {}, {}, '{}', {}, '{}', {})".format(
                            robot.market.upper(), int(robot.simulation),
                            int(False), int(False), robot.price_entry, 100, int(False), int(robot.stop_loss),
                            robot.price_entry, 0, 0, 0, robot.exchange,
                            robot.user_id, robot.core_strategy, int(robot.short_flag))
        robot.job_id, rows = sql.query_lastrow_id(sql_string)
        robot.logger.lprint(['Job id:', robot.job_id])
    elif type == 'update':
        if not b_test.backtesting:
            sql_string = "UPDATE jobs SET price_curr={}, percent_of={}, last_update={} WHERE job_id={} " \
            "AND userid = {} AND core_strategy = '{}'".format(
                round(robot.price, 8), robot.percent_of_entry, b_test.time(), robot.job_id,
                robot.user_id, robot.core_strategy)
            sql.query(sql_string)

### Collecting orders in the process pre-flow
def process_orders_init(robot, e_api, b_test):

    if not robot.simulation and not config.backtesting_enabled:
        orders_opening = None   #sometimes api fails and ends with an error - so retrying here
        while orders_opening is None:
            try:
                orders_opening = e_api.getorderhistory(robot.exchange, robot.market, lastid=robot.oanda_last_trans_id)
            except:
                b_test.sleep(3)

        robot.logger.lprint(["Last orders when starting the script"])
        if len(orders_opening) < 5:
            count_max = len(orders_opening)
        else:
            count_max = 5

        for i in range (0, count_max):
            robot.logger.lprint(['>', orders_opening[i]['OrderUuid']])

        for elem in orders_opening:
            robot.orders_start.add(elem['OrderUuid'])

### Time lag for backtests
def add_time_lag(robot, b_test):
    time_lag = random.randint(1, 10)
    robot.logger.lprint([ "-- artificial time lag to process the action: {} minutes".format(time_lag)])
    b_test.sleep(time_lag*60)

### Main workflow: process a position
def process(robot, b_test = None):

    ### Starting and default variables
    robot.sl_extreme = None
    sale_trigger = False
    status_update = ''
    robot.twitter_comment = ''
    robot.entry_time = b_test.strftime("%d-%m-%Y %H:%M")

    # Restoring the timers etc, including postonly attempts
    robot.assign_default_values()

    # Timestamp for initiation start
    robot.timestamp_start_process = b_test.time()

    # oanda specifics
    if robot.exchange == 'oanda':
        robot.oanda_last_trans_id = e_api.oanda_last_transaction_id(robot.market)
        
    #  If simulation and parameters are not specified
    if robot.simulation is True:
        if robot.limit_sell_amount == 0:
            robot.limit_sell_amount = 10
        robot.simulation_balance = robot.limit_sell_amount
        robot.sell_portion = robot.limit_sell_amount

    if robot.limit_sell_amount > 0:
        robot.logger.lprint(["Maximum quantity to sell", robot.limit_sell_amount])

    ### Set up the margin on bitmex
    if robot.exchange == 'bitmex' and not robot.simulation and not config.backtesting_enabled:
        set_margin = e_api.bitmex_leverage(robot.market, robot.margin_level)
        if set_margin == 'balance_insufficient':
            robot.logger.lprint(["Cannot set the margin due to insufficient balance, proceeding as is"])

    robot.cutoff_timer = b_test.time()  # For entry cutoff limitation, time in timestamp
    robot.time_hour = b_test.strftime("%H")     # For periodic updates of TD candles and stops
    robot.time_hour_comms = robot.time_hour     # For periodic status updates
    
    # 0. Original value refresh and value snapshot
    original_value(robot, robot.exchange, robot.market, e_api)
    robot.value_original_snapshot = robot.value_original/robot.margin_level

    if robot.value_original is None:
        print("No positions open")
        send_chat_message(robot.user_id,  '{}: no open positions to start the task'.format(robot.market))
        robot.terminate()

    robot.logger.lprint(["Original (entry) value:", robot.value_original]) 

    # 1. Checking robot.market correctness and URL validity, as well as protecting from fat fingers
    init_pre_check(robot, coinigy, b_test)

    ### 2. Checking available balance. If bitmex - checking whether we have a long or a short position
    if not robot.simulation:
        balance = e_api.getbalance(robot.exchange, robot.currency)

        # Updating the balance snapshot for history
        sql_string = "INSERT INTO user_balances(userid, balance, timestamp, core_strategy) VALUES ({}, {}, {}, '{}')".format(
            robot.user_id, balance['Total'], b_test.time(), robot.core_strategy)
        sql.query(sql_string)

        # Checking the direction based on the actual poritions
        process_direction_check(robot, e_api)

    #ML-based short flag when simulation 
    if robot.simulation: 
        short_flag_on_prediction(robot)
        if robot.short_flag is None:
            # Just pick any
            robot.short_flag = False

    ### 3. Start the main workflow
    run_flag, approved_flag = True, True
    robot.no_sell_orders = False      # default value to suit both simulation and the real run
    process_db_updates(robot, sql, b_test, type='insert')

    robot.start_time = b_test.time()

    # Update the prediction for process except for the case when it is called by reentry
    if robot.entry_direction is None:
        stop_reconfigure(robot, 'now', b_test = b_test)

    #### Creating new set to store previously executed orders. Will be used to calculate the gains
    process_orders_init(robot, e_api, b_test)

    # If limit losses is enabled
    if robot.limit_losses:
        if not robot.short_flag:
            limit_loss_price = robot.price_entry * (1 - robot.limit_losses_val)
        else:
            limit_loss_price = robot.price_entry * (1 + robot.limit_losses_val)

    ### 9. Start the main cycle of the robot
    while run_flag and approved_flag:

        # Get the last price
        robot.price = get_price_feed(robot, b_test)

        stop_reconfigure(robot, 'process', b_test = b_test)   # update predictions

        # Print info and update DB
        robot.percent_of_entry = round((float(robot.price)/float(robot.price_entry))*100, 2)

        curr_timing = b_test.strftime("%d-%m-%Y %H:%M")
        robot.logger.lprint([curr_timing, robot.user_name, '|', robot.exchange, robot.market, "@",
            robot.price, "|", robot.percent_of_entry, "% of entry"
            ])

        process_db_updates(robot, sql, b_test, type='update')

        # Should not do anything for at least 15 min
        time_passed = (b_test.time() - robot.timestamp_start_process)/60

        # Updates
        td_result, td_direction, over_threshold = robot.predicted_action_direction(type='exit')

        robot.logger.lprint(["-- short flag: {}. prediction: {} ({}), confidence {:.0%}, over_threshold {}, time passed: {} min".format(
            robot.short_flag, robot.predicted_name(robot.prediction), robot.prediction, float(robot.prediction_probability), over_threshold, int(time_passed))])

        time_passed_threshold = 10  # empirically 10 min is ok to exit

        if time_passed >= time_passed_threshold:
            if over_threshold:
                if (not robot.short_flag) and (td_direction in ['no position', 'red']):
                    sale_trigger = True
                    robot.stopped_mode = 'ml'
                    robot.logger.lprint(['--- prediction to exit long'])
                if (robot.short_flag) and (td_direction in ['no position', 'green']):
                    sale_trigger = True
                    robot.stopped_mode = 'ml'
                    robot.logger.lprint(['--- prediction to exit short'])

            # This is not useful
            ''' 
            # Also check if current prediction is different from the entry and we are still in the money  
            if not sale_trigger:
                if (((not robot.short_flag) and (td_direction in ['no position', 'red'])) or (robot.prediction == 1 and robot.prediction_probability < 0.5)) and (robot.price > robot.price_entry):
                    sale_trigger = True
                    robot.stopped_mode = 'ml'
                    robot.logger.lprint(['Exiting while still in the money while unsure on prediction'])
                elif (((robot.short_flag) and (td_direction in ['no position', 'green'])) or (robot.prediction == 2 and robot.prediction_probability < 0.5)) and (robot.price < robot.price_entry):
                    sale_trigger = True
                    robot.stopped_mode = 'ml'
                    robot.logger.lprint(['Exiting while still in the money while unsure on prediction'])
            ''' 
            
            # Also check limit loss failsafe
            if robot.limit_losses and not sale_trigger:
                if (not robot.short_flag and robot.price < limit_loss_price) or (robot.short_flag and robot.price > limit_loss_price):
                    # May fail
                    try:
                        ensure_sale_check = td_info.ensure_td_sale(robot, limit_loss_price, 'quick', b_test = b_test)
                        if ensure_sale_check:
                            sale_trigger = True
                            robot.stopped_mode = 'limiting_losses'
                            comm_string = "{}: limiting losses, exiting".format(robot.market)
                            robot.logger.lprint(['Key event:', comm_string])
                    except:
                        sale_trigger = True
                        robot.stopped_mode = 'limiting_losses'
                        comm_string = "{}: limiting losses, exiting (note - could not check on 10min candles)".format(robot.market)
                        robot.logger.lprint(['Key event:', comm_string])

        else:
            robot.logger.lprint(['-- prediction to exit, but {} min has not passed'.format(time_passed_threshold)])

        ########### Stop loss triggered
        if sale_trigger:

            # Introduced a time lag for backtests
            if config.backtesting_enabled:
                add_time_lag(robot, b_test)

            # Stop-loss triggered   predicted_name(robot.prediction), robot.prediction_probability  #<HERE>
            notification_text = '{}: Closing position @ {}. \nPrediction: {} (confidence {:.0%})'.format(
                robot.market, round(robot.price, robot.round_num), robot.predicted_name(robot.prediction), robot.prediction_probability)
            robot.logger.lprint([notification_text])
            send_chat_message(robot.user_id, notification_text)
            status = sell_now(robot.price, b_test = b_test)  # main selling function

            # Handling results
            if status is not None:
                run_flag, stat_msg = aux_functions.process_stat(status, robot, e_api, sql)
                robot.logger.lprint([stat_msg])
            else:
                sql_string = "DELETE FROM jobs WHERE job_id = {} " \
                "AND userid = {} AND core_strategy = '{}'".format(robot.job_id, robot.user_id, robot.core_strategy)    # deleting the task from the db
                sql.query(sql_string)
                robot.terminate()

            #robot.stopped_price = robot.sl_target

        ### Check if 'close now' request has been initiated
        if not b_test.backtesting:
            sell_init_flag = sql.check_sell_flag(robot)
            if sell_init_flag and approved_flag and run_flag:
                robot.logger.lprint(["Sale initiated via Telegram @", robot.price])
                robot.stopped_mode = 'telegram'
                status = sell_now(robot.price, b_test = b_test)

                # Handling results
                if status is not None:
                    run_flag, stat_msg = aux_functions.process_stat(status, robot, e_api, sql)
                    robot.logger.lprint([stat_msg])
                else:
                    sql_string = "DELETE FROM jobs WHERE job_id = {} " \
                    "AND userid = {} AND core_strategy = '{}'".format(robot.job_id, robot.user_id, robot.core_strategy)    # deleting the task from the db
                    sql.query(sql_string)
                    robot.terminate()

        # Stopped price
        robot.stopped_price = robot.price  # used in buyback

        # Checking cancellation request and sleeping
        if run_flag and approved_flag:
            if not b_test.backtesting:
                approved_flag = sql.check_cancel_flag(robot, robot.job_id, 'jobs')
                if not approved_flag:
                    robot.logger.lprint(["Shutdown was requested via Telegram"])
                    robot.stopped_mode = 'telegram'
                    robot.sleep_timer = 0
            b_test.sleep(robot.sleep_timer)

    ### 10. Exit point for the main cycle, sell cycle, mooning cycle
    sql_string = "DELETE FROM jobs WHERE job_id = {} " \
    "AND userid = {} AND core_strategy = '{}'".format(robot.job_id, robot.user_id, robot.core_strategy)    # deleting the task from the db
    sql.query(sql_string)

    # Just a simulation and cancelled by Telegram thing - no virtual sell orders
    if robot.simulation and not approved_flag:
        robot.no_sell_orders = True

    ### 11. Getting information on performed sell orders and displaying / recording the outcomes
    if (robot.stopped_mode != 'telegram') or config.run_testmode:    # testmode to <TEST>
        sell_orders_info(robot, b_test = b_test)
        sell_orders_outcome(robot, b_test = b_test)


    # If a Telegram stop was requested, we should just exit     # testmode to <TEST>
    if (robot.stopped_mode == 'telegram') and not config.run_testmode:
        robot.logger.lprint(["Stopping by the Telegram request"])
        send_chat_message(robot.user_id, '{}: stopped by the Telegram request'.format(robot.market))
        e_api.cancel_orders(robot.exchange, robot.market)
        robot.terminate()

    robot.run_program_mode = 'buyback'      # may not need to continue e.g. systemexit

    return None

### Aux: set margin on bitmex. Workaround because it is sometimes reset for no reason
def init_set_margin(robot, e_api):
    if robot.exchange == 'bitmex' and (robot.mode not in ['now-s', 'fullta-s']):
        if not config.backtesting_enabled:
            set_margin = e_api.bitmex_leverage(robot.market, robot.margin_level)
            if set_margin == 'balance_insufficient':
                robot.logger.lprint(["Cannot set the margin due to insufficient balance, proceeding as is"])

### Workflow record creation for initiating positions
def init_full_cycle(robot, sql):
    if robot.mode == 'full_cycle':  # if need to insert in workflow
        robot.mode = 'fullta'
        robot.simulation_param = 'r'

        # Insert a record in the db
        sql_string = "INSERT INTO workflow(market, trade, currency, run_mode, exchange, userid, core_strategy)"\
                "VALUES ('{}', '{}', '{}', '{}', '{}', {}, '{}')".format(
                    robot.market, robot.trade, robot.currency, 'r',
                    robot.exchange_abbr, robot.user_id, robot.core_strategy)
        robot.wf_id, _ = sql.query_lastrow_id(sql_string)   # _ is a throwaway variable
        robot.logger.lprint(["Workflow:", robot.wf_id, 'r'])

### Check if this is a part of workflow (meaning that a job should be then launched)
def init_get_workflow(robot, sql):
    sql_string = "SELECT wf_id, run_mode FROM workflow WHERE market = '{}' AND exchange = '{}' AND userid = {} AND core_strategy = '{}' ".format(
        robot.market, robot.exchange_abbr, robot.user_id, robot.core_strategy)
    rows = sql.query(sql_string)

    # Check workflow if it is not saved in robot
    if robot.wf_id is None:
        try:
            robot.wf_id = rows[0][0]   # first result if existing
            robot.wf_run_mode = rows[0][1]
            robot.logger.lprint(["Workflow:", robot.wf_id, robot.wf_run_mode])
        except:
            robot.logger.lprint(["Not a part of workflow"])
            robot.wf_id = None
            robot.wf_run_mode = None
    else:
        robot.wf_run_mode = robot.simulation_param

### Checking exchanges availability and balance
def init_pre_check(robot, coinigy, b_test):
    try:
        ticker_upd = coinigy.price(robot.exchange_abbr, robot.market, robot.logger, b_test)
        # Ticker could be failing if there is automatic maintenance - then sleep for a while
        if ticker_upd is None:
            send_chat_message(robot.user_id,
                              '{} seems to be on an automatic maintenance. Will try every 5 minutes.'.format(
                                  robot.market))
            while ticker_upd is None:
                b_test.sleep(300)  # sleeping for 5 minutes and checking again
                ticker_upd = coinigy.price(robot.exchange_abbr, robot.market, robot.logger, b_test)

        if ticker_upd == 'INVALID_MARKET':
            robot.logger.lprint(['Error: Invalid market'])
            send_chat_message(robot.user_id, 'Error: Invalid market to buy')
            robot.terminate()

    except urllib.error.URLError:
        robot.logger.lprint(['Exchange url unavailable to buy'])
        send_chat_message(robot.user_id, 'Error: Exchange url unavailable')
        robot.terminate()
    except:
        robot.logger.lprint(['Cannot get the price. Please check that you are using a correct market name.'])
        send_chat_message(robot.user_id,
                          'Error: Cannot get the price. Please check that you are using a correct market name.')
        robot.terminate()

### Checking modes
def init_mode_check(robot):
    if robot.mode == 'now-s':
        robot.wf_run_mode = 's' # simulating
        robot.mode = 'now' # setting up a regular mode
    if robot.mode == 'fullta-s':
        robot.wf_run_mode = 's' # simulating
        robot.mode = 'fullta' # setting up a regular mode
    if robot.wf_run_mode == 's':  # simulation switch
        robot.simulation = True
    else:
        robot.simulation = False

### Processing fulfilled orders
def init_orders_process(robot, buy_uuid, e_api, b_test, sum_paid, sum_quantity, source_filled, usd_x_rate):
    if buy_uuid is not None:
        ### 1. Get information on the existing orders and cancel them
        robot.logger.lprint(['>>> Cancelling:', buy_uuid, robot.exchange, robot.market])

        # Get order info for filled part
        e_api.cancel(robot.exchange, robot.market, buy_uuid)
        b_test.sleep(5)
        order_info = e_api.getorder(robot.exchange, robot.market, buy_uuid)

        ### 2. Filled / remaining
        buy_uuid = None
        # For safety # change
        if order_info is not None:
            quantity_filled = order_info['Quantity'] - order_info['QuantityRemaining']
        else:
            quantity_filled = 0

        # DEBUG
        print(">>>>> Quantity filled {}, order_info['Quantity'] {} , order_info['QuantityRemaining'] {}".format(
            quantity_filled, order_info['Quantity'], order_info['QuantityRemaining']))  # DEBUG
        print(">>>>> PricePerUnit {}, Price {}".format(order_info['PricePerUnit'], order_info['Price']))  # DEBUG

        price_unit = order_info['PricePerUnit']
        price_order = order_info['Price']

        if price_unit is None:
            price_unit = 0

        if robot.exchange == 'bitmex':
            if robot.market in config.primary_calc_markets:
                source_filled = Decimal(str(Decimal(quantity_filled) / Decimal(price_unit)))
                sum_paid += Decimal(str(source_filled))
                sum_quantity += quantity_filled
            else:
                source_filled = Decimal(str(Decimal(quantity_filled) * Decimal(price_unit)))
                sum_paid += Decimal(str(source_filled))  # for price averaging
                sum_quantity += quantity_filled
        elif robot.exchange == 'oanda':
            #print(usd_x_rate, quantity_filled, price_order)
            if robot.forex_pair:  # different approach to units for forex pairs
                source_filled = Decimal(str(abs(quantity_filled))) / Decimal(usd_x_rate)
            else:
                source_filled = Decimal(str(abs(price_order))) / Decimal(usd_x_rate)
            sum_paid += Decimal(str(price_order))
            sum_quantity += quantity_filled
        print('Filled: {}, sum_quantity {}'.format(source_filled, sum_quantity))

        # Returning results
    return sum_paid, sum_quantity, source_filled

### Updating price info in db
def init_db_upd(robot, sql, b_test, type = 'update'):
    if type == 'update':
        if not robot.fixed_price_flag and not b_test.backtesting:
            sql_string = "UPDATE buys SET price = {}, last_update={} WHERE job_id = {} " \
                         "AND userid = {} AND core_strategy = '{}' ".format(
                robot.price, b_test.time(), robot.job_id, robot.user_id, robot.core_strategy)
            #print(sql_string)
            sql.query(sql_string)
    elif type == 'delete':
        sql_string = "DELETE FROM buys WHERE job_id = {} " \
                     "AND userid = {} AND core_strategy = '{}' ".format(
            robot.job_id, robot.user_id, robot.core_strategy)
        sql.query(sql_string)
    elif type == 'wf_delete':
        if robot.wf_id is not None:
            sql_string = "DELETE FROM workflow WHERE wf_id = {} " \
                         "AND userid = {} AND core_strategy = '{}' ".format(
                robot.wf_id, robot.user_id, robot.core_strategy)
            sql.query(sql_string)
            robot.wf_id = None

### Checking if actually should start
def init_launch_position_opening(initiate_position_launch, robot):
    if not initiate_position_launch:
        # Mode: If requested to buy now
        if robot.mode == 'now':
            initiate_position_launch = True

        # Mode: ML-based
        td_result, td_direction, over_threshold = robot.predicted_action_direction()
        robot.logger.lprint(['--- validating (init): td_result {}, td_direction {}, over_threshold {}'.format(
           td_result, td_direction, over_threshold)])

        if (robot.mode in ['fullta', 'now']) and over_threshold and (td_direction in ['green', 'red']):
            initiate_position_launch = True
        else:
            robot.logger.lprint(
                [robot.user_name, '|', robot.exchange, robot.market, "| no prediction / prediction is below the threshold"])
            initiate_position_launch = False

    # If test run
    if config.run_testmode:
        initiate_position_launch = True
        if robot.short_flag is None:
            robot.short_flag = False
            robot.prediction = 1
        print("Testmode: launching immediately")

    return initiate_position_launch

### Updating prices to open position for
def init_price_update(robot, e_api, initiate_position_launch):
    if initiate_position_launch:
        if not config.backtesting_enabled:
            if not robot.fixed_price_flag: # otherwise price is in the input
                # When we are long, on the enter we buy -> get the price from asks (the lowest ask (sell price) which is the first in the array)
                # When we are short, on the enter we sell -> get the price from bids (the highest bid (buy price), which is the first in the array)
                if not robot.short_flag:  # LONG
                    robot.fixed_price = float(e_api.getorderbook(robot.exchange, robot.market, 'asks')[0]['Rate'])
                else:  # SHORT
                    robot.fixed_price = float(e_api.getorderbook(robot.exchange, robot.market, 'bids')[0]['Rate'])
        # for other cases (not fullta) like now or breakout - just get the averaged ticker price
        else:
            robot.fixed_price = get_price_feed(robot, b_test)

### pre 4.8 double checking if there are enough funds to buy. If not - waiting.
def init_pre_launch_check(initiate_position_launch, pre_order_open_state, flag_buyer_check_positions, approved_flag, balance_issue_notify, robot, sum_quantity, b_test, buy_rate, buy_flag):
    if initiate_position_launch and pre_order_open_state:
        pre_order_open_state = False
        robot.logger.lprint(['Confirming the balance...'])

        # If there is no minimum balance available, then cancel buying flag and wait for 5 minutes
        if not ensure_balance(robot, buy_rate):
            initiate_position_launch = False
            robot.logger.lprint(["The balance is not enough to buy. Cancelling buy flag and sleeping for 5 minutes."])
            if balance_issue_notify:
                send_chat_message(robot.user_id,
                                  'Please add to the balance or cancel the buy task. Bot will be sleeping in 5-min cycles.')
                balance_issue_notify = False
            b_test.sleep(300)

        # Also confirming that no positions are open
        if flag_buyer_check_positions:
            proceed_decision = buyer_check_positions(robot, e_api)
            flag_buyer_check_positions = False
            if not proceed_decision:
                buy_flag, approved_flag = False, False
                robot.sleep_buy_timer = 0
                sum_quantity = 0

    return flag_buyer_check_positions, initiate_position_launch, buy_flag, approved_flag, pre_order_open_state, sum_quantity, balance_issue_notify

### Init - quantity modifications
def init_quantity(robot, e_api, buy_rate, contracts):

    str_status = 'Used rate: {}'.format(buy_rate)
    robot.logger.lprint([str_status])

    # Source position to rate, including currency conversion if needed
    if robot.exchange != 'oanda':
        quantity = round(Decimal(str(robot.source_position)) / Decimal(str(buy_rate)), 6)
    else:
        # Need to account for the usd price; hardcoded AUD but could be changed to anything
        usd_x_rate = usd_rate_value(robot, e_api)
        source_in_usd = robot.source_position * Decimal(str(usd_x_rate))

        # For forex pairs like USD_JPY, unit = USD so no need to divide
        if robot.forex_pair:
            quantity = round(Decimal(str(source_in_usd)), 6)
        else:
            quantity = round(Decimal(str(source_in_usd)) / Decimal(str(buy_rate)), 6)
        robot.logger.lprint(["Changing {} AUD to {} USD".format(robot.source_position, source_in_usd)])  # DEBUG

    # Calculate quantity / contracts
    if robot.exchange == 'bitmex':  # need to do this in contracts because the api returns contracts and not xbt filled

        if robot.market in config.primary_calc_markets:  # robot.market == 'btc/usd':  #
            quantity = round(Decimal(str(robot.source_position)), 6)
            buy_rate = round(buy_rate, 0)
            contracts = round(quantity * Decimal(buy_rate))  # margin is already accounted for in the main code
        else:  # All alts are traded vs btc
            quantity = round(Decimal(str(robot.source_position)), 6)
            buy_rate = round(buy_rate, 20)
            contracts = round(quantity / buy_rate)  # margin is already accounted for in the main code

        robot.contracts_total += contracts
        robot.logger.lprint(["Quantity (xbt) {}, buy_rate {}, contracts {}, source_position {}".format(
            quantity, buy_rate, contracts, robot.source_position)])  # DEBUG

    # on OANDA, the number of units should be whole
    elif robot.exchange == 'oanda':
        if not b_test.backtesting:
            # Because we could have something like 0.99 units when there is enough margin left.
            # Subtracting 0.4 to e.g. not round 1.2 up to 2
            quantity = int(math.ceil(quantity - Decimal(0.4)))
            robot.logger.lprint(['Changing the quantity to whole:', quantity])

    str_status = 'Quantity to open position for: {}'.format(quantity)
    robot.logger.lprint([str_status])

    return quantity, buy_rate, contracts

### Postonly attempts handling
def postonly_attempts_confirm(robot, timer_start):
    # Account for attempts to try market making
    timer_now = b_test.time()
    robot.timer_diff = (timer_now - timer_start)/60 # in minutes

    if robot.timer_diff > config.postonly_minutes:
        current_postonly_flag = False
        robot.logger.lprint(['-- switching to market taking/market orders'])
    else:
        current_postonly_flag = True
        robot.logger.lprint(['-- trying market making/orderbook'])

    return current_postonly_flag

### Opening position when everything is ready
def init_position_open(robot, e_api, buy_flag, buy_rate, contracts, sum_quantity, quantity, avg_price):
    buy_uuid = None

    # Account for attempts to try market making or orderbook (for traditional)
    current_postonly_flag = postonly_attempts_confirm(robot, robot.timer_init_start)

    # Proceeding with the position
    if robot.simulation:
        buy_flag, robot.sleep_buy_timer = False, 0
        robot.logger.lprint(['Bought in simulation:', sum_quantity, quantity, buy_rate])
        sum_quantity = quantity
        avg_price = buy_rate

    # Real mode
    else:
        # Double-checking the quantity after we calculated the actual rate
        if quantity > 0.0:
            # Bitmex is a bit special (market making)
            if robot.exchange == 'bitmex':
                # Open a long or a short depending on the requested side if the number of contracts (calculated) > 0
                if contracts > 0:  # we can have a situation with non-zero quantity but zero contracts

                    # Process the order
                    if robot.short_flag:
                        robot.logger.lprint(['Contracts (short) {} buy_rate {}'.format(contracts, buy_rate)])  # DEBUG
                        buy_result = e_api.selllimit(robot.exchange, robot.market, None, buy_rate, contracts,
                                                     postonly=current_postonly_flag)
                    else:
                        robot.logger.lprint(['Contracts (long) {} buy_rate {}'.format(contracts, buy_rate)])  # DEBUG
                        buy_result = e_api.buylimit(robot.exchange, robot.market, None, buy_rate, contracts,
                                                    postonly=current_postonly_flag)

                else:  # if zero contracts to buy are left - finish buying
                    buy_flag = False
                    robot.sleep_buy_timer = 0
                    robot.logger.lprint(['Finished buying - zero contracts left'])

            else:  # other exchanges
                if robot.short_flag:
                    robot.logger.lprint(['Quantity (short) {} buy_rate {}'.format(quantity, buy_rate)])  # DEBUG
                    buy_result = e_api.selllimit(robot.exchange, robot.market, quantity, buy_rate, postonly=current_postonly_flag)
                else:
                    robot.logger.lprint(['Quantity (long) {} buy_rate {}'.format(quantity, buy_rate)])  # DEBUG
                    buy_result = e_api.buylimit(robot.exchange, robot.market, quantity, buy_rate, postonly=current_postonly_flag)

            # Process buy results
            # print "\n>>> Result", buy_result #DEBUG
            robot.logger.lprint(["------\nResult:", buy_result, "\n------"])  # DEBUG #

            if buy_result == 'MIN_TRADE_REQUIREMENT_NOT_MET':
                # If trade requirement were not met or an error occured
                buy_flag = False
                robot.sleep_buy_timer = 0
                send_chat_message(robot.user_id,
                                  'Cancelling buying on ' + robot.market + ' as minimum trade requirements were not met')
            elif buy_result == 'issue_unknown':
                robot.logger.lprint(['An issue occured while submitting the order. Trying again.'])
            elif buy_result == 'access_denied':
                robot.logger.lprint(["Your API keys do not have proper access"])
                send_chat_message(robot.user_id, 'Your API keys do not have proper access')
                buy_flag = False
                robot.sleep_buy_timer = 0
                robot.wf_id = None
            else:  # If the results are ok
                try:
                    if buy_result is not None:
                        buy_uuid = buy_result['uuid']
                        robot.logger.lprint(['>> Placed order', buy_uuid])
                    else:  # sometimes the last result is None but previous orders were actually fine
                        err_msg = "{} user had None is buy order - follow up".format(robot.user_id)
                        issue_notify(robot, err_msg, only_admin=True)
                        buy_flag = False
                        robot.sleep_buy_timer = 0
                        robot.wf_id = None
                except:
                    # If something else is wrong
                    buy_flag = False
                    robot.sleep_buy_timer = 0
                    err_msg = traceback.format_exc()
                    issue_notify(robot, err_msg)
                    # Also cancelling workflow until we figure out what's up
                    robot.wf_id = None

            print('sleeping...')
            b_test.sleep(robot.sleep_buy_timer)

        else:  # if quantity is zero
            buy_flag = False
            robot.sleep_buy_timer = 0

    return buy_uuid, buy_flag, sum_quantity, quantity, avg_price

### Init: post-orders work. Calculating averages and updating the information / logging the results
def init_post_results(robot, sum_quantity, sum_paid, source_filled, avg_price):

    if sum_quantity > 0:
        if not robot.simulation:
            if robot.exchange == 'bitmex':
                if robot.market in config.primary_calc_markets:  # robot.market == 'btc/usd':
                    avg_price = round(Decimal(sum_quantity) / Decimal(str(sum_paid)), 8)  # cause we are buying contracts there
                else:
                    avg_price = round(Decimal(sum_paid) / Decimal(str(sum_quantity)), 8)  # cause we are buying contracts there
            else:  # for oanda
                avg_price = round(Decimal(abs(sum_paid)) / Decimal(str(sum_quantity)), 8)
            robot.logger.lprint(['Average price paid:', avg_price])
        else:
            # If simulation
            sum_paid = robot.source_position

        # Fix for the backtesting - we will just use ticker as an average price paid
        if config.backtesting_enabled:
            avg_price = robot.price

        # Take absolute values if avg_price and spent as oanda returns negatives
        avg_price = abs(avg_price)
        source_filled = abs(source_filled)

        # Description
        if robot.short_flag:
            direction_desc = 'short'
            robot.entry_direction = 'red'
        else:
            direction_desc = 'long'
            robot.entry_direction = 'green'

        # Round the avg price for comms
        avg_price_comm = round(float(avg_price), 2)

        if robot.exchange == 'bitmex':
            comm_string = "{}: orders completed on {}, opened a position for {} contracts. \n" \
                          "Direction: {}. \nAverage price: {}".format(
                robot.market, robot.exchange, sum_quantity, direction_desc, avg_price_comm)
        else:
            comm_string = "{}: orders completed on {} at the average price {}.\n" \
                          "Position of {} unit(s).".format(robot.market, robot.exchange, avg_price_comm, sum_quantity)
        send_chat_message(robot.user_id, comm_string)
        robot.logger.lprint([comm_string])

        # Updating twitter
        if (robot.lambobot is not None) and not robot.simulation:
            comm_string_twitter = "{}: opened a {} position. #algotrading".format(
                robot.market.upper(), direction_desc, robot.core_strategy)
            try:  # just in case if this returns an error
                robot.lambobot.post(comm_string_twitter)
            except:
                pass

        # Updating workflow info if we have a workflow
        if robot.wf_id is not None:
            sql_string = "UPDATE workflow SET sum_q = '{}', avg_price = '{}' " \
                         "WHERE wf_id = {} AND userid = {} AND core_strategy = '{}' ".format(
                sum_quantity, avg_price, robot.wf_id, robot.user_id, robot.core_strategy)
            robot.job_id, rows = sql.query_lastrow_id(sql_string)

    else:  # if we have zero quantity as a result
        send_chat_message(robot.user_id,
                          '{} ({}): buy order was cancelled, no positions initiated'.format(robot.exchange, robot.market))
        robot.logger.lprint([robot.market, ': buy order was cancelled, no positions initiated'])

        if robot.wf_id is not None:
            sql_string = "DELETE FROM workflow WHERE wf_id = {} " \
                         "AND userid = {} AND core_strategy = '{}' ".format(
                robot.wf_id, robot.user_id, robot.core_strategy)
            sql.query(sql_string)
            robot.wf_id = None

        robot.terminate()

    return sum_quantity, sum_paid, source_filled, avg_price

### Init: check workflow runs
def init_check_wf(robot, sql):

    if robot.wf_id is not None:
        sql_string = "SELECT * FROM workflow WHERE wf_id = '{}' " \
            "AND userid = {} AND core_strategy = '{}' LIMIT 1".format(
                robot.wf_id, robot.user_id, robot.core_strategy)
        rows = sql.query(sql_string)

        # Checks to handle duplicated jobs situation
        try:
            wf_info = rows[0]
        except:
            sql_string = "SELECT * FROM workflow WHERE market = '{}' " \
                "AND userid = {} AND core_strategy = '{}' LIMIT 1".format(
                    robot.market.upper(), robot.user_id, robot.core_strategy)
            rows = sql.query(sql_string)
            try:
                wf_info = rows[0]
            except:
                wf_info = None
                chat_error_msg = 'Cannot launch the trading job for the market {}. ' \
                                             'Please launch it using new command.'.format(robot.market)
                send_chat_message(robot.user_id, chat_error_msg)

        # Launching a job if required by workflow
        if wf_info is not None:
            wf_info = rows[0]   # first result if existing
            wf_info_market = wf_info[1]
            wf_info_price = wf_info[8]
            wf_stop_mode = wf_info[9]
            wf_price_entry = wf_info[10]
            robot.exchange_abbr = wf_info[11]

            # Using actual average price as an entry: avg_price
            if (wf_info_price is None) and (wf_price_entry is not None):
                wf_info_price = wf_price_entry

            # Deleting wf_id from the db
            sql_string = "DELETE FROM workflow WHERE wf_id = {} " \
                "AND userid = {} AND core_strategy = '{}' ".format(
                    robot.wf_id, robot.user_id, robot.core_strategy)
            sql.query(sql_string)

            launch_str = "params: process, {}, {}, {}, {}".format(wf_stop_mode, robot.exchange_abbr, wf_info_market, str(wf_info_price))   #DEBUG
            robot.logger.lprint([launch_str])
            if not b_test.backtesting:
                robot.input('_', 'process', wf_stop_mode, robot.exchange_abbr, wf_info_market, str(wf_info_price))
            else: # limitation of sell amount needed
                robot.input('_', 'process', wf_stop_mode, robot.exchange_abbr, wf_info_market, str(wf_info_price), str(robot.source_position/robot.margin_level))

            robot.run_program_mode = 'process'

    else:  # if there is no workflow task - stop
        robot.run_continued = False

### USD - local curr rates update
def usd_rate_value(robot, e_api):
    if robot.exchange == 'oanda':
        if not robot.simulation:
            usd_x_rate = e_api.getticker('oanda', 'AUD_USD')
        else:
            usd_x_rate = 1  # does not matter

        # If market is closed
        if usd_x_rate is None:
            # a workaround to get the last known
            usd_x_rate = robot.usd_x_rate_last
        else:
            robot.usd_x_rate_last = usd_x_rate
        return usd_x_rate
    else:
        return None

### Main workflow: initiate a position
def buyer(robot, b_test):

    # Restoring the timers etc, incl. postonly attempts 
    robot.assign_default_values()

    # Update the prediction for buyer except for the case when it is called by reentry
    if robot.entry_direction is None:
        stop_reconfigure(robot, 'now', b_test = b_test)
    else:
        robot.logger.lprint(["Initiated from previous job. Direction {}, prediction {}, probability {}".format(
            robot.entry_direction, robot.prediction, robot.prediction_probability)])

    # Timestamp for initiation start #added_precision
    robot.timestamp_start_initiate = b_test.time()

    ### Set up the margin (needed on on bitmex)
    init_set_margin(robot, e_api)

    ### Price data analysis 
    robot.time_hour = b_test.strftime("%H")
    robot.time_hour_comms = robot.time_hour

    # Sleeping for a bit so that information on workflows is updated in the database just in case 
    b_test.sleep(int(30/robot.speedrun))

    init_full_cycle(robot, sql)   # full cycle mode handling
    init_get_workflow(robot, sql)   # check if this is a part of workflow (meaning that a job should be then launched)

    ### 1. Checking availability, balance 
    init_pre_check(robot, coinigy, b_test)

    ### 2. Start timer for price switching and handling simulation modes 
    robot.timer_init_start = b_test.time()

    # Modes check
    init_mode_check(robot)

    # Default values and starting balances / contracts
    robot.source_position = Decimal(str(robot.source_position))

    # Checking balance
    balance_check = ensure_balance(robot)  # added to modify the quantity on the start
    if balance_check is None:
        robot.logger.lprint(["Invalid API keys"])
        send_chat_message(robot.user_id, 'Invalid API keys - cannot check the balance')
        robot.terminate()

    robot.source_start = robot.source_position
    initiate_position_launch = False  # no launching just yet

    # Default variables
    robot.contracts_total = 0
    buy_uuid = None
    buy_flag = True
    sum_paid, sum_quantity, source_filled, contracts, avg_price, buy_rate = 0, 0, 0, 0, 0, 0
    approved_flag, balance_issue_notify, pre_order_open_state  = True, True, True

    usd_x_rate = usd_rate_value(robot, e_api)

    ### 3.9 Pre: if we are in the real mode and there are open positions on bitmex (e.g. we have set a stop manually) - done on the buying flag
    ### Inserting in the sqlite db if started fine
    sql_string = "INSERT INTO buys(market, abort_flag, price_fixed, price, source_position, mode, exchange, userid, core_strategy) " \
                 "VALUES ('{}', 0, {}, {}, {}, '{}', '{}', {}, '{}')".format(
        robot.market, int(robot.fixed_price_flag), robot.fixed_price,
        robot.source_position, robot.mode, robot.exchange, robot.user_id, robot.core_strategy)
    robot.job_id, rows = sql.query_lastrow_id(sql_string)

    # Buyer check positions should only be performed once
    flag_buyer_check_positions = True

    #Considering commissions
    robot.source_position = Decimal(str(robot.source_position)) * Decimal(str(1 - robot.comission_rate))
    robot.logger.lprint(["Updated source position considering commission:", robot.source_position])

    # Notify about the start of the job
    if not robot.is_restart:
        send_chat_message(robot.user_id, '{}: started the job to initiate a position.'.format(robot.market))


    ### 4. Main buying loop
    while buy_flag and approved_flag:

        # Update the prediction for buyer except for the case when it is called by reentry
        if (robot.entry_direction is None) and not initiate_position_launch:
            stop_reconfigure(robot, 'buyer', b_test = b_test)

        # ML-based short flag based on the current prediction
        short_flag_on_prediction(robot)

        try:
            # 4. Checking processed orders
            sum_paid, sum_quantity, source_filled = init_orders_process(robot, buy_uuid, e_api, b_test, sum_paid, sum_quantity, source_filled, usd_x_rate)

            ### 4.3. Timer update
            timer_now = b_test.time()
            robot.timer_diff = (timer_now - robot.timer_init_start)/60 # in minutes

            ### 4.4. Checking the cancellation flag
            approved_flag = sql.check_cancel_flag(robot, robot.job_id, 'buys')
            if not approved_flag:
                robot.logger.lprint(["Shutdown was requested via Telegram"])
                cancel_stat = e_api.cancel(robot.exchange, robot.market, buy_uuid)
                b_test.sleep(5) # wait for it to be cancelled
                robot.sleep_buy_timer = 0
            
            ### 4.5. Updating how much of source position (e.g. BTC) do we have left and placing a buy order if required
            robot.source_position = Decimal(str(robot.source_position)) - Decimal(str(source_filled))
            robot.logger.lprint(["Amount to open the position:", robot.source_position, "\n"])
            
            ### 4.6. Get the current price value and print it
            robot.price = get_price_feed(robot, b_test)

            init_db_upd(robot, sql, b_test)

            if approved_flag:
                curr_timing = b_test.strftime("%d-%m-%Y %H:%M")
                robot.logger.lprint([curr_timing, robot.user_name, '|', robot.exchange, robot.market, '| opening for', robot.source_position, '@', robot.price ])

            # Price conditions with fixed price for different scenarios
            initiate_position_launch = init_launch_position_opening(initiate_position_launch, robot)

            # Updating the fixed price in this loop iteration
            init_price_update(robot, e_api, initiate_position_launch)
            buy_rate = robot.fixed_price
                    
            ### 4.7. Checking how much is left to buy and setting the price
            ratio = Decimal(source_filled/robot.source_start)
            ratio = ratio.quantize(Decimal('1.01'))
            robot.logger.lprint(['Ratio (filled):', ratio])

            if (ratio < 0.96 or ratio == 0) and approved_flag:      # 96% is just empirical

                ### pre 4.8 double checking if there are enough funds to buy. If not - waiting.
                flag_buyer_check_positions, initiate_position_launch, buy_flag, approved_flag, pre_order_open_state, sum_quantity, balance_issue_notify = init_pre_launch_check(
                    initiate_position_launch, pre_order_open_state, flag_buyer_check_positions, approved_flag,
                    balance_issue_notify, robot, sum_quantity, b_test, buy_rate, buy_flag)

                ### Extra: time lag for backtests
                if config.backtesting_enabled:
                    add_time_lag(robot, b_test)

                ### 4.8. Placing an order when requirements are met
                if initiate_position_launch:
                    quantity, buy_rate, contracts = init_quantity(robot, e_api, buy_rate, contracts)

                    # Proceeding with the position
                    buy_uuid, buy_flag, sum_quantity, quantity, avg_price = init_position_open(robot, e_api, buy_flag, buy_rate,
                                                                                       contracts, sum_quantity,
                                                                                       quantity, avg_price)
            # If the position if filled
            else:
                buy_flag = False
                robot.sleep_buy_timer = 0

            # Sleeping depending on whether we have started buying or not 
            if ratio == 0: 
                b_test.sleep(30)
            else: 
                b_test.sleep(robot.sleep_buy_timer)

        except: # unknown issues with opening a position
            err_msg = traceback.format_exc()
            issue_notify(robot, err_msg)

            # Cancel the orders
            if buy_uuid is not None:
                # Get info and cancel 
                robot.logger.lprint(['Cancelling:' , buy_uuid])
                e_api.cancel(robot.exchange, robot.market, buy_uuid)

            # Deleting the task from the db
            init_db_upd(robot, sql, b_test, type='delete')

            # Delete workflow for this market
            if robot.wf_id is not None:
                init_db_upd(robot, sql, b_test, type='wf_delete')
            robot.terminate()

    ### 5. Deleting the task from the db on successful closure
    init_db_upd(robot, sql, b_test, type='delete')

    ### 6. Calculating averages and updating the information / logging the results 
    init_post_results(robot, sum_quantity, sum_paid, source_filled, avg_price)
            
    ### 7. If this is a workflow - launching a new process() flow. Otherwise stopping
    init_check_wf(robot, sql)


### Process input
def process_launch_parameters(argv):
    # Deleting argparse parameters (containing '--') from argv
    argv = [x for x in argv if "--" not in x]

    # Argparse floats
    for elem in [
        'limit_losses_val',
        'predicted_confidence_threshold',
        'exit_confidence_threshold'
        ]:
        parser.add_argument('--{}'.format(elem), type=float, help="Custom {} (float)".format(elem))

    # Argparse ints
    for elem in [
        'limit_losses'
        ]:
        parser.add_argument('--{}'.format(elem), type=int, help="Custom {} (int; 0/1 for False/True)".format(elem))

    parser.add_argument("--codename", type=str, help="Include custom codename in the log to navigate better")
    parser.add_argument("--start", type=str, help="Backtest start date and time, e.g. 01.03.2018:12.00")
    parser.add_argument("--end", type=str, help="Backtest end date and time, e.g. 01.03.2018:12.00")

    # Model name
    parser.add_argument("--modelname", type=str, help="Model name to rewrite")

    ## Separating argparse arguments from everything else
    args, unknown = parser.parse_known_args()

    # Core strategy (standard by default)   # think how to rename it (should be like exchange type)
    if args.core_strategy is not None:
        core_strategy = args.core_strategy.strip()
    else:
        core_strategy = 'standard'

    # Here in order to create properly named logs
    if args.codename is not None:
        codename = args.codename
    else:
        codename = 'normal'

    return argv, args, codename, core_strategy

### Check if full balance has to be used
def is_use_all_balance(user_id, sql):
    sql_string = "SELECT param_val FROM user_params WHERE userid = {} AND param_name = 'use_all_balance'".format(user_id)
    try:
        rows = sql.query(sql_string)
        use_all_balance = bool(int(rows[0][0]))
    except:
        use_all_balance = False

    return use_all_balance

### Selecting username from the DB
def username_by_id(user_id):
    sql_string = "SELECT name FROM user_info WHERE userid = {}".format(user_id)
    try:
        rows = sql.query(sql_string)
        user_name = rows[0][0]
    except:
        user_name = ''
    return user_name

### Assign a new model if requested
def scripting_assign_new_model(robot, args):
    if args.modelname is not None:
        robot.model_name = args.modelname

### Initiate backtesting for the bot
def scripting_initiate_backtesting(robot, config, args, b_test):

    # Initialising backtesting
    datetime_in = datetime(config.backtesting_start_y, config.backtesting_start_m, config.backtesting_start_d,
                                 config.backtesting_start_h, config.backtesting_start_min)
    datetime_until = datetime(config.backtesting_end_y, config.backtesting_end_m, config.backtesting_end_d,
                                 config.backtesting_end_h, config.backtesting_end_min)

    # Changing dates if requested
    if args.start is not None:
        try:
            datetime_in = datetime.strptime(args.start, '%d.%m.%Y:%H.%M')
        except:
            robot.logger.lprint(["Wrong start date value, using config instead"])
    if args.end is not None:
        try:
            datetime_until = datetime.strptime(args.end, '%d.%m.%Y:%H.%M')
        except:
            robot.logger.lprint(["Wrong end date value, using config instead"])

    b_test.init_testing(datetime_in, datetime_until, robot.exchange_abbr, robot.market)

### Check if current time is in trading hours for the traditional market 
def is_trading_hours(b_test, robot): 

    curr_date_time = datetime.strptime(b_test.strftime("%d-%m-%Y %H:%M"), "%d-%m-%Y %H:%M")
    curr_hour = (b_test.strftime("%H"))
    
    # Syd time: closing Sat 8am, opening Mon 8am, plus extra few hours just in case 
    if robot.exchange_abbr == 'oanda': 
        weekday = curr_date_time.weekday()
        if (int(weekday) == 5 and int(curr_hour) >= 7) or (int(weekday) == 6) or (int(weekday) == 0 and int(curr_hour) <= 9): 
            return False 
        else: 
            return True 
    else: 
        return True 

### Update robot params based on args
def params_update_from_args(robot, args):

    # Codename and user, update info
    if args.codename is not None:
        robot.logger.lprint(["Codename:", args.codename])
    robot.logger.lprint(["User:", robot.user_name, '| id', robot.user_id, '\n'])

    # Update threshold for predictions and limit loss
    if args.predicted_confidence_threshold is not None:
        robot.predicted_confidence_threshold = args.predicted_confidence_threshold
    if args.exit_confidence_threshold is not None:
        robot.exit_confidence_threshold = args.exit_confidence_threshold
    if args.limit_losses is not None:
        robot.limit_losses = bool(args.limit_losses)
    if args.limit_losses_val is not None:
        robot.limit_losses_val = args.limit_losses_val


###################################
#####            Main script  logic              #####
###################################    

if __name__ == "__main__":

    ### Process input
    argv, args, codename, core_strategy = process_launch_parameters(argv)

    # Initialising the class to store all the constants and parameters
    robot = robo_class.Scripting(user_id, strategy = core_strategy, codename = codename)

    # Check if all balance should be used
    robot.use_all_balance = is_use_all_balance(user_id, sql)
    
    robot.user_id = user_id  # storing user_id from the launch in a proper variable

    # Checking the program mode etc
    run_program_mode = robot.input(*argv)  # * to unpack the arguments

    # Check if market is supported and the strategy is supported
    if not sql.is_market_supported(robot.market):
        robot.logger.lprint(["Market is not supported"])
        send_chat_message(robot.user_id, 'Sorry, this market is not supported yet')
        robot.terminate()

    robot.logger.lprint(["Core strategy:", robot.core_strategy])

    # Initiating exchange api
    e_api = exch_api.api(user_id, strategy = core_strategy)

    # Initiating price feed api
    coinigy = coinigy(user_id, e_api = e_api)

    # Updating thresholds used in the price analysis depending on the strategy
    robot.update_thresholds()
    print("Loading...")

    # Check that exchange keys exist
    key_id, key_secret = e_api.keys_select(user_id, robot.core_strategy, robot.exchange)
    if key_id is None or key_secret is None:
        print("API keys are not specified for exchange")
        send_chat_message(robot.user_id, 'Please specify your keys via /keys_update before launching any tasks.')
        robot.terminate()

    # Selecting the user name (not just id)
    robot.user_name = username_by_id(user_id)

    robot.is_restart = is_restart   # changes messaging

    # Initiate backtesting
    scripting_initiate_backtesting(robot, config, args, b_test)

    # Update used model if neede
    scripting_assign_new_model(robot, args)

    # Update robot params based on args
    params_update_from_args(robot, args)

    robot.logger.lprint(["Predictions will be updated at the following minutes:", ', '.join(map(str, robot.control_bars_minutes))])

    # Logging parameters for further backtesting results analysis
    robot.store_launch_params(config)

    # Get the current price and check it
    robot.price = get_price_feed(robot, b_test)

    if robot.price is None:
        print("Price stream is unavailable")
        send_chat_message(robot.user_id, 'Price stream is unavailable. If you are launching the traditional markets job, note that the market may be untradeable now.')
        robot.terminate()

    # Initiate data source in backtesting for faster processing
    if b_test.backtesting:
        td_info.init_source(b_test)

    # Start date
    robot.start_date = b_test.strftime("%d-%m-%Y %H:%M")

    # Run the script depending on the input
    robot.run_program_mode = run_program_mode

    # Default continuation flag which is only disabled when stop of buyback is requested
    robot.run_continued = True
    
    while robot.run_continued:
        # Setting up margin
        robot.margin_level = e_api.return_margin()

        # Run the workflow
        try: # error handling
            if robot.run_program_mode == 'process':
                process(robot, b_test)
            elif robot.run_program_mode == 'initiate':
                buyer(robot, b_test)
            elif robot.run_program_mode == 'buyback':
                buy_back_wrapper(robot, b_test)
        except SystemExit as KeyboardInterrupt:
            print("Stopping by the system call")
            robot.run_continued = False
        except: # any other unknown exit
            err_msg = traceback.format_exc()
            issue_notify(robot, err_msg)