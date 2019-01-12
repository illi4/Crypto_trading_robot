import pandas as pd
import numpy as np 
import warnings
warnings.filterwarnings("ignore")

from datetime import datetime, timedelta
import pytz
import math

import xgboost as xgb

# Garbage collector
import gc

# Threading for v3
import _thread

import libs.sqltools as sqltools
sql = sqltools.sql()

# Config file 
import config

# TD analysis
class tdlib(object):
    def __init__(self):
        #self.public = ['stats', 'stats_rsi_only', 'last_extreme_close', 'price_stats', 'price_rsi_stats', 'price_ma_stats', 'ensure_td_buy']
        self.rsi_df = None
        self.file_prefix = 'price_log/'
        self.using_data_source = False

    # To use in-memory instead of reading file all the time, useful for backtests
    def init_source(self, b_test):
        #file_full_path = 'price_log/{}_{}.csv'.format(b_test.market, b_test.exchange_abbr.lower())
        file_full_path = self.filename_define(b_test.market, b_test.exchange_abbr.lower())
        self.source_data_full = pd.read_csv(file_full_path, index_col='timestamp', names=['timestamp','price'])
        self.using_data_source = True
        print('(i) initiated data source')

    # To get just a snapshot of df
    def source_snapshot(self, timestamp):
        return_df = self.source_data_full[self.source_data_full.index <= timestamp]
        return return_df

    # Skip file rows
    def skip_rows_no(self, filename, nentries): 
        # Using this in order to not read everything and not to store everything in pandas dataframe 
        with open(filename) as f:
            for i, l in enumerate(f):
                pass
        rows_skip = i - nentries
        return rows_skip

    # Define which markets are standard to remove NaNs
    def is_traditional(self, market):
        if market == 'oanda':
            return True
        else:
            return False

    # Reading transactions
    def read_transactions(self, filename, nentries, b_test):
        if not config.backtesting_enabled:
            try:
                transactions = pd.read_csv(filename, skiprows=self.skip_rows_no(filename, nentries), names=['timestamp', 'price']).set_index('timestamp')
            except:
                return None
        else:
            # Checking if the nentries should be corrected (if there is no so much data and we use backtesting)
            if b_test._curr_pricelog_line_no - nentries + 1 < 0:
                nentries -= b_test._curr_pricelog_line_no - 1
            # Reading data
            try:
                transactions = pd.read_csv(filename, skiprows=b_test._curr_pricelog_line_no - nentries + 1,
                                           nrows = nentries, names=['timestamp', 'price']).set_index('timestamp')
            except:
                return None

        return transactions

    # Updated function for the new pandas lib; this calc is also more precise
    def RSI(self, period=14):
        delta =  self.rsi_df.diff()
        up, down = delta.copy(), delta.copy()
        up[up < 0] = 0
        down[down > 0] = 0
        rUp = up.ewm(com=period - 1,  adjust=False).mean()
        rDown = down.ewm(com=period - 1, adjust=False).mean().abs()
        rsi = 100 - 100 / (1 + rUp / rDown)
        return rsi

    # More precise nentries check
    def get_nentries(self, period):
        if period == '4h' or period == '2h':
            nentries = 60000
        elif period == '9h' or period == '12h':
            nentries = 95000
        elif period == '1d':
            nentries = 200000
        elif period == '1h':
            nentries = 15000
        elif period == '30min':
            nentries = 10000
        elif period == '15min':
            nentries = 4000
        elif period == '10min':
            nentries = 2000
        elif period == '5min':
            nentries = 1000
        elif period == '3min':
            nentries = 100
        else:
            nentries = 100000
        return nentries

    # Period
    def get_period(self, period, b_test):
        # Base for starting time
        if period == '15min':
            price_base = 15
        elif period == '10min':
            price_base = 10
        elif (period == '5min') or (period == '3min'):
            price_base = 0
        elif period == '12h':
            # Accounting for potential DST shift
            price_base = b_test.td_price_base_constant - 4 + self.isdaytime(b_test)
        elif (period == '30min'):
            price_base = self.isdaytime(b_test)  #- this works...or not?  #b_test.td_price_base_constant - 3 + self.isdaytime(b_test)
        else:
            # Accounting for potential DST shift
            price_base = b_test.td_price_base_constant + self.isdaytime(b_test) # e.g. for 4h. After april-something bars will start with 2, 4, 6
        return price_base

    # More convenient use of parameters
    def price_stats(self, robot, period, tail = 10, b_test = None):
        nentries = self.get_nentries(period)
        return self.stats(robot.market, robot.exchange_abbr, period, nentries, tail, robot.short_flag, b_test = b_test)

    # Defining filename
    def filename_define(self, market, exch_use):
        market = market.replace('/', '_')
        return '{}{}_{}.csv'.format(self.file_prefix, market, exch_use.lower())

    # Transactions resampling
    def transaction_resample(self, transactions, b_test, period, remove_nans = False):
        transactions.index = pd.to_datetime(transactions.index, unit='s')
        transactions.index = transactions.index + pd.Timedelta(b_test.timedelta_str)  # convert to local time
        transactions['price'] = transactions.price.astype('float32')

        bars = transactions.price.resample(period, base = self.price_base).ohlc()

        #Remove nans for traditional markets   # HERE reason for issue with oanda (why none @ 2017-02-07 07:00)
        if remove_nans:
            bars = bars.dropna(axis = 0, how = 'all')

        return bars

    # More convenient use of parameters in just rsi call
    def price_rsi_stats(self, robot, period, tail = 10, b_test = None, window_length = 14):
        nentries = self.get_nentries(period)
        return_result = self.stats_rsi_only(robot.market, robot.exchange_abbr,
            period, nentries, tail, robot.short_flag, b_test = b_test, window_length = window_length)
        if return_result is not None:
            try: # To prevent issues
                return return_result[-1]
            except:   
                return None
        else:
            return None

    # More convenient use of parameters in just MA call
    def price_ma_stats(self, robot, period, maperiod, tail = 10, b_test = None, ma_calc = 'simple'):
        nentries = self.get_nentries(period)
        return_result = self.stats_MA_only(robot.market, robot.exchange_abbr, period, maperiod, nentries, tail, robot.short_flag,
            b_test = b_test, ma_calc = ma_calc)
        if return_result is not None:
            try: # To prevent issues
                return return_result[-1]
            except:
                return None
        else:
            return None

    # For daytime savings check. Need to check every hour
    def isdaytime(self, b_test):
        naive = datetime.fromtimestamp(b_test._curr_time)
        loctime = pytz.timezone(b_test.pytz_timezone)
        try: #handling ambiguous time error
            aware = loctime.localize(naive, is_dst=None)
        except:
            aware = loctime.localize(naive + timedelta(hours=1), is_dst=None)
        aware_dt = bool(aware.dst())
        # Handling delta
        b_test.timedelta_current = b_test.timedelta + aware_dt
        b_test.timedelta_str = ":".join([str(b_test.timedelta_current), '00', '00'])
        # Returning the shift
        return int(aware_dt)


    # Main statistics on candles
    def stats(self, market, exch_use, period = '1h', nentries = 100000, tail = 10, short_flag = False, b_test = None):
        transactions, bars_prices_original, bars = None, None, None

        nentries = self.get_nentries(period)

        # If using available data source
        if not self.using_data_source:
            filename = self.filename_define(market, exch_use)
            #print(filename)
            #filename = self.file_prefix + market + '_' + exch_use.lower() + '.csv'
            transactions = self.read_transactions(filename, nentries, b_test)
            if transactions is None:
                return None
            self.price_base = self.get_period(period, b_test)
            bars = self.transaction_resample(transactions, b_test, period, remove_nans = self.is_traditional(exch_use))

            # Checking preservation - not needed
            '''
            datelike = transactions.loc[:,transactions.dtypes.isin([np.dtype('datetime64[ns]')])]
            datelike = datelike.resample(period, how=lambda x: Timestamp(x.view('i8').mean()))
            concat([numeric,datelike],axis=1)
            '''

            # Checking the length
            if len(bars.index) < 7:
                return None

        # If recalculating on the fly
        else:
            transactions = self.source_snapshot(b_test.time()).tail(nentries).copy()
            # Base for starting time
            self.price_base = self.get_period(period, b_test)
            bars = self.transaction_resample(transactions, b_test, period, remove_nans=self.is_traditional(exch_use))
        
        # Initial conditions, working through TD
        bearish_flip = False
        bullish_flip = False
        setup_up = 0
        setup_down = 0

        size = bars['close'].size
        # print "TDLib: Bars df size:", size

        # Calculate the RSI values
        self.rsi_df = bars['close']
        bars['rsi'] = self.RSI(14)  # window length of 14

        # Calculated fields
        bars.loc[:, 'td_setup'] = 0    # additional column: td setup number
        bars.loc[:, 'td_direction'] = ''  # td setup direction
        bars.loc[:, 'move_extreme'] = None # for stopping when the setup extreme is broken

        # Changing the types to preserve memory space
        bars['td_setup'] = pd.to_numeric(bars['td_setup'], errors='coerce')
        bars['move_extreme'] = pd.to_numeric(bars['move_extreme'], errors='coerce')

        # Initial direction and values
        direction_up = False
        direction_down = False
        move_extreme = None
        countdown_up_flag = False
        countdown_down_flag = False
        countdown_up_list = []
        countdown_down_list = []

        if (bars['close'].iloc[5] > bars['close'].iloc[4]):
            direction_up = True
        elif (bars['close'].iloc[5] < bars['close'].iloc[4]):
            direction_down = True

        # Shifting for further calculations
        bars['shifted_1'] = bars['close'].shift(1)
        bars['shifted_2'] = bars['close'].shift(2)
        bars['shifted_4'] = bars['close'].shift(4)
        bars['shifted_5'] = bars['close'].shift(5)
        
        # Comparison operations, resulting in A (above) or B (below)
        bars['bear_flip'] = bars.apply(lambda x : True if x['shifted_1'] > x['shifted_5'] and x['close'] < x['shifted_4'] else False, axis=1)
        bars['bull_flip'] = bars.apply(lambda x : True if x['shifted_1'] < x['shifted_5'] and x['close'] > x['shifted_4'] else False, axis=1)
        bars['bear_reset'] = bars.apply(lambda x : True if x['close'] > x['shifted_4'] else False, axis=1)
        bars['bull_reset'] = bars.apply(lambda x : True if x['close'] < x['shifted_4'] else False, axis=1)
        # For move_extremes
        bars['shifted_1_low'] = bars['low'].shift(1)
        bars['shifted_2_low'] = bars['low'].shift(2)
        bars['shifted_1_high'] = bars['high'].shift(1)
        bars['shifted_2_high'] = bars['high'].shift(2)
        # Resulting move_extreme
        bars['max_1_2'] = bars[['shifted_1_high', 'shifted_2_high']].max(axis = 1)
        bars['min_1_2'] = bars[['shifted_1_low', 'shifted_2_low']].min(axis = 1)
        # For countdowns
        bars['if_countdown_down'] = bars.apply(lambda x: True if x['close'] <= x['shifted_2_low'] else False, axis=1)
        bars['if_countdown_up'] = bars.apply(lambda x: True if x['close'] >= x['shifted_2_high'] else False, axis=1)

        np_setup = np.zeros(shape = (size, 1), dtype = int)
        np_direction = np.empty(shape = (size, 1), dtype=object)
        np_move_extremes = np.empty(shape = (size, 1))
        np_move_extremes.fill(np.nan)
        # Countdown
        np_countdown_up = np.zeros(shape = (size, 1), dtype = int)
        np_countdown_down = np.zeros(shape = (size, 1), dtype = int)

        ## Looping through, numpy to speed up
        # 0 O
        # 1 H
        # 2 L
        # 3 C
        # 4 rsi
        # 5 td_setup
        # 6 td_direction
        # 7 move_extr
        # 8 shifted_1
        # 9 shifted_2
        # 10 shifted_4
        # 11 shifted_5
        # 12 bear_flip
        # 13 bull_flip
        # 14 bear_reset
        # 15 bull_reset
        # ...
        # 20 max_1_2
        # 21 min_1_2
        # 22 if_countdown_down
        # 23 if_countdown_up

        # print "Directions", direction_down, direction_up # this is ok

        for i, bar_row in enumerate(bars.values):
            if i > 5:    # need 6 candles to start
                ## Price flip
                bearish_flip = False
                bullish_flip = False

                if setup_up == 9:
                    setup_up = 0 # restart count
                if setup_down == 9:
                    setup_down = 0 # restart count

                # Flips - bearish
                # TEST
                '''
                if i < 20: 
                    print "Close price", bar_row[3]   # this is ok  
                    print "Bear_flip", bar_row[12]      # this is not 
                    print "i-1 {} i-5 {}   i-3 {} i-10 {}".format(bar_row[8], bar_row[11], bar_row[3], bar_row[10]) 
                '''

                if bar_row[12]:
                    bearish_flip = True
                    direction_down = True
                    bullish_flip = False
                    move_extreme = None

                # Flips - bullish
                if bar_row[13]:
                    bullish_flip = True
                    direction_up = True
                    bearish_flip = False
                    move_extreme = None

                if bearish_flip and direction_up:
                    direction_up = False
                    setup_down = 1
                if bullish_flip and direction_down:
                    direction_down = False
                    setup_up = 1

                ## TD Setup (sequential)        # bear reset
                if direction_down and not bearish_flip:
                    if bar_row[14]:    # restarting if a condition is not met
                        setup_down = 1
                    else:
                        setup_down += 1

                if direction_up and not bullish_flip:       # bull reset
                    if bar_row[15]:  # restarting if a condition is not met
                        setup_up = 1
                    else:
                        setup_up += 1

                ## Move_extreme update; based on 2 completed td intervals so we have at least 1 -> 2
                # That is why referring to 3 here (the script returns all including the current one )
                # Otherwise it would be exiting on every flip potentially
                if (direction_down and (setup_down > 2) and short_flag):
                    if setup_down == 3:
                        move_extreme = bar_row[20]
                    else:
                        if (bar_row[1] > move_extreme):
                            move_extreme = bar_row[1]

                if (direction_up and (setup_up > 2) and not short_flag):
                    if setup_up == 3:
                        move_extreme = bar_row[21]
                    else:
                        if (bar_row[2] < move_extreme):
                            move_extreme = bar_row[2]

                # Filling the np arrays
                if direction_down:
                    np_setup[i] = setup_down
                    np_direction[i] = 'red'           # down
                if direction_up:
                    np_setup[i] = setup_up
                    np_direction[i] = 'green'           # up
                # Common for any direction
                np_move_extremes[i] = move_extreme

                # Countdowns check
                # Will need to store a list with counters
                # If there is active countdown but we get a 9 in the same direction again - one more countdown is added
                # If a 9 in different direction - the previous direction countdown should stop
                if direction_up and setup_up == 9:
                    countdown_up_flag = True
                    countdown_down_flag = False  # also in this case delete countdowns
                    countdown_down_list = []
                    countdown_up_list.append(0) # reserving place for counter increase
                if direction_down and setup_down == 9:
                    countdown_down_flag = True
                    countdown_up_flag = False
                    countdown_up_list = []
                    countdown_down_list.append(0) # reserving place for counter increase
                # TD seq buy: if bar 9 has a close less than or equal to the low of two bars earlier
                # then bar 9 becomes 1 countdown
                # if not met - then countdown 1 postponed until condition is met and continues until total of 13 closes
                # each should be less or equal to the low 2 bars earlier
                # If one of elements in on 13, delete it.
                # This is a simplified approach as completion of 13 also requires comparison with 8th setup bar
                if direction_up and countdown_up_flag and bar_row[23]:
                    countdown_up_list = [x + 1 for x in countdown_up_list]
                    countdown_up_list = [x for x in countdown_up_list if x != 13]
                if countdown_up_list != []:
                    np_countdown_up[i] = max(countdown_up_list) # this is enough for our purposes
                if direction_down and countdown_down_flag and bar_row[22]:
                    countdown_down_list = [x + 1 for x in countdown_down_list]
                    countdown_down_list = [x for x in countdown_down_list if x != 13]
                if countdown_down_list != []:
                    np_countdown_down[i] = max(countdown_down_list) # this is enough for our purposes

        # Join np arrays with the dataframe
        setup_df = pd.DataFrame(data = np_setup)
        setup_df.index = bars.index.copy()
        bars['td_setup'] = setup_df

        setup_dir = pd.DataFrame(data = np_direction)
        setup_dir.index = bars.index.copy()
        bars['td_direction'] = setup_dir

        move_extreme_df = pd.DataFrame(data = np_move_extremes)
        move_extreme_df.index = bars.index.copy()
        bars['move_extreme'] = move_extreme_df

        np_countdown_up_df = pd.DataFrame(data = np_countdown_up)
        np_countdown_up_df.index = bars.index.copy()
        bars['countdown_up'] = np_countdown_up_df

        np_countdown_down_df = pd.DataFrame(data = np_countdown_down)
        np_countdown_down_df.index = bars.index.copy()
        bars['countdown_down'] = np_countdown_down_df

        # Change types to save memory
        bars['countdown_up'] = bars.countdown_up.astype('int8')
        bars['countdown_down'] = bars.countdown_down.astype('int8')
        bars['td_setup'] = bars.td_setup.astype('int8')
        bars['open'] = bars.open.astype('float32')
        bars['high'] = bars.high.astype('float32')
        bars['low'] = bars.low.astype('float32')
        bars['close'] = bars.close.astype('float32')

        # Deleting unnecessary rows
        for elem in ['shifted_1', 'shifted_2', 'shifted_4', 'shifted_5',
                'bear_flip', 'bull_flip', 'bear_reset', 'bull_reset', 'shifted_1_low',
                'shifted_2_low', 'shifted_1_high', 'shifted_2_high',
                'max_1_2', 'min_1_2'
                ]:
            del bars[elem]


        bars_return =  bars.tail(tail).copy()

        # Memory cleansing
        del transactions
        del bars
        if bars_prices_original is not None:
            del bars_prices_original
        del np_setup, move_extreme, setup_down, setup_up
        del np_direction, np_move_extremes, np_countdown_down, np_countdown_up
        gc.collect()
        ### ended cleanup

        return bars_return


    ### Only returning rsi
    def stats_rsi_only(self, market, exch_use, period = '1h', nentries = 100000, tail = 10, short_flag = False,
        b_test = None, window_length = 14, bars_to_use = None):

        nentries = self.get_nentries(period)

        if not self.using_data_source:
            # Added for cases when we have a different reference exchange / market for calculating the TD
            filename = self.filename_define(market, exch_use)
            transactions = self.read_transactions(filename, nentries, b_test)
            if transactions is None:
                return None
        # if bars are provided, e.g. for traditional markets
        else:
            transactions = self.source_snapshot(b_test.time()).tail(nentries).copy()

        # Base for starting time
        self.price_base = self.get_period(period, b_test)
        bars = self.transaction_resample(transactions, b_test, period, remove_nans=self.is_traditional(exch_use))
        del transactions

        # Calculate the RSI values
        self.rsi_df = bars['close']
        rsi_return = self.RSI(window_length)  # window length of 14 is standard

        # Memory cleaning
        del bars
        gc.collect()
        ### ended cleanup

        return rsi_return


    ### Only returning MA
    def stats_MA_only(self, market, exch_use, period = '1h', maperiod = 10, nentries = 100000, tail = 10, short_flag = False,
        b_test = None, ma_calc = 'simple'):

        nentries = self.get_nentries(period)

        if not self.using_data_source:
            # Added for cases when we have a different reference exchange / market for calculating the TD
            filename = self.filename_define(market, exch_use)
            transactions = self.read_transactions(filename, nentries, b_test)
            if transactions is None:
                return None
        # if bars are provided, e.g. for traditional markets
        else:
            transactions = self.source_snapshot(b_test.time()).tail(nentries).copy()

        # Base for starting time
        self.price_base = self.get_period(period, b_test)
        bars = self.transaction_resample(transactions, b_test, period, remove_nans = self.is_traditional(exch_use))
        del transactions

        # Calculate the MA values
        ma_df = bars['close']   # why not working for simple ma for oanda?

        if ma_calc == 'simple':
            ma_rolling = ma_df.rolling(window=maperiod, min_periods=maperiod).mean()
        else:
            ma_rolling = pd.ewma(ma_df, span=maperiod)

        # Memory cleaning
        del bars
        gc.collect()
        ### ended cleanup

        return ma_rolling
        
    ### Returning the max or min of last N candles for specific period 
    def last_extreme_close(self, market, exch_use, period = '1h', nentries = 100000, tail = 10, short_flag = False, number_compare = 4):
        bars = self.stats(market, exch_use, period, nentries, tail, short_flag)
        # Returning max or min 
        rng = -number_compare - 1   # e.g. last 4 excluding current: from -5 to -1  
        ret_val = bars['close'][rng]
        for i in range(rng, rng + number_compare + 1):
            if not short_flag: #long   
                if bars['close'][i] > ret_val: 
                    ret_val = bars['close'][i] 
            else: #short 
                if bars['close'][i] < ret_val: 
                    ret_val = bars['close'][i] 
        return ret_val

    ### Ensuring that we should buy based on TD
    def ensure_td_buy(self, robot, check_price, mode='standard', b_test=None):
        control_bars_allowed_deviation = 0  # allow slight deviation when checking control bar values

        control_bars_confirmation = False  # defaults
        proceed_buy = False
        robot.logger.lprint(
            ["--- launching ensure_td_buy @", check_price, "| robo_delta", robot.buy_delta, "consider_ma:", robot.consider_ma])

        # Standard mode: Nx30min candles closing beyond the check price (excluding the current one)
        if mode == 'standard':
            # Modified check_price allowing for slight deviations
            if not robot.short_flag:
                check_price_control_bars = check_price * (1 - control_bars_allowed_deviation)
            else:
                check_price_control_bars = check_price * (1 + control_bars_allowed_deviation)

            # Control bars should not be off
            if robot.control_bars is not None:
                # Update: number of candles depending on the input parameter
                robot.logger.lprint(["--- analyzing control candles close values"])
                if robot.ensure_buy_confirmations_no == 0:
                    if not robot.short_flag and (robot.control_bars['close'].iloc[-2] > check_price_control_bars):
                        control_bars_confirmation = True
                    if robot.short_flag and (robot.control_bars['close'].iloc[-2] < check_price_control_bars):
                        control_bars_confirmation = True
                    robot.logger.lprint(["--- last bar close value:", robot.control_bars['close'].iloc[-2],
                                         "| compared price (w deviation):", check_price_control_bars])
                else:  # if more should be checked
                    check_i = - (robot.ensure_buy_confirmations_no + 1)
                    # String of closes and arr
                    str_closes = ''
                    arr_closes = []
                    for j in range(robot.ensure_buy_confirmations_no, 0, -1):
                        str_closes = ' '.join([str_closes, str(robot.control_bars['close'].iloc[-j])])
                        arr_closes.append(robot.control_bars['close'].iloc[-j])
                    # Check for longs
                    if not robot.short_flag:
                        robot.logger.lprint(["--- last bars close values (check for long):",
                                             str_closes, "| compared price (w deviation):", check_price_control_bars])
                        if (min(arr_closes) > check_price_control_bars):
                            control_bars_confirmation = True
                            robot.logger.lprint(["--- confirmed on control bars value"])
                        else:
                            robot.logger.lprint(["--- not confirmed on control bars value"])
                    # Check for shorts
                    if robot.short_flag:
                        robot.logger.lprint(["--- last bars close values (check for short):",
                                             str_closes, "| compared price (w deviation):", check_price_control_bars])
                        if (max(arr_closes) < check_price_control_bars):
                            control_bars_confirmation = True
                            robot.logger.lprint(["--- confirmed on control bars value"])
                        else:
                            robot.logger.lprint(["--- not confirmed on control bars value"])

                if control_bars_confirmation:
                    proceed_buy = True

                # Only opening candle if the last 30-min candle is not TD 7,8,9, and is not in the different direction (if enabled)
                if robot.consider_control_count:
                    if (robot.control_bars['td_setup'].iloc[-1] in [8, 9]):
                        proceed_buy = False
                        robot.logger.lprint(
                            ["--- not confirmed: control candle is on TD", robot.control_bars['td_setup'].iloc[-1]])
                    else:
                        robot.logger.lprint(["--- confirmed: control candle is on TD", robot.control_bars['td_setup'].iloc[-1]])

            else:
                # If we do not have control bars - proceed with buy
                control_bars_confirmation = True

            # Now, check for countdown if this option is enabled
            if proceed_buy and robot.consider_countdown and not robot.enter_on_unaligned_td:
                if ((robot.short_flag and robot.main_bars['countdown_up'].iloc[-1] != 0)
                        or (not robot.short_flag and robot.main_bars['countdown_down'].iloc[-1] != 0)):
                    proceed_buy = False
                    robot.logger.lprint(["--- not confirmed on the countdown. Short flag:", robot.short_flag,
                                         ", countdown up:", robot.main_bars['countdown_up'].iloc[-1], ", countdown down:",
                                         robot.main_bars['countdown_down'].iloc[-1]])
                else:
                    robot.logger.lprint(["--- confirmed on the countdown. Short flag:", robot.short_flag,
                                         ", countdown up:", robot.main_bars['countdown_up'].iloc[-1], ", countdown down:",
                                         robot.main_bars['countdown_down'].iloc[-1]])

            # Also check for MA if MA option is enabled
            if proceed_buy and robot.consider_ma:
                if robot.ma is not None:
                    if robot.short_flag and check_price > robot.ma:
                        proceed_buy = False
                        robot.logger.lprint(
                            ["--- not confirmed: price is higher than moving average when initiating short - ma:",
                             robot.ma])
                    if not robot.short_flag and check_price < robot.ma:
                        proceed_buy = False
                        robot.logger.lprint(
                            ["--- not confirmed: price is lower than moving average when initiating long - ma:", robot.ma])
                    if proceed_buy:
                        robot.logger.lprint(["--- moving average is fine:", robot.ma])
                else:
                    robot.logger.lprint(["--- warning - moving average is None"])

            # If a higher TF needs to be validated
            if proceed_buy and robot.align_timeframes:
                try:
                    if robot.short_flag and (robot.bars_higher_tf['td_direction'].iloc[-1] == 'green'):
                        robot.logger.lprint(["Not confirmed: higher TF is not aligned"])
                        proceed_buy = False
                    if not robot.short_flag and (robot.bars_higher_tf['td_direction'].iloc[-1] == 'red'):
                        robot.logger.lprint(["Not confirmed: higher TF is not aligned"])
                        proceed_buy = False
                    if proceed_buy:
                        robot.logger.lprint(["Higher TF is aligned"])
                except IndexError:
                    robot.logger.lprint(["Not enough data to check, skipping"])
                    proceed_buy = False

            # Checking RSI
            if proceed_buy:
                if robot.short_flag:  # in shorts
                    rsi_info_higher = robot.rsi_higher_down_extreme
                    rsi_info_lower = robot.rsi_lower_down_extreme
                    if robot.rsi_mode == 'or':
                        if (robot.rsi_higher <= robot.rsi_higher_down_extreme) or (
                                robot.rsi_lower <= robot.rsi_lower_down_extreme):
                            robot.logger.lprint(["--- not confirmed: extreme RSI values (higher {} OR lower tf {}):".format(
                                robot.rsi_higher, robot.rsi_lower)])
                            proceed_buy = False
                    else:
                        if (robot.rsi_higher <= robot.rsi_higher_down_extreme) and (
                                robot.rsi_lower <= robot.rsi_lower_down_extreme):
                            robot.logger.lprint([
                                                    "--- not confirmed: extreme RSI values (higher {} AND lower tf {}):".format(
                                                        robot.rsi_higher, robot.rsi_lower)])
                            proceed_buy = False
                else:  # in longs
                    rsi_info_higher = robot.rsi_higher_up_extreme
                    rsi_info_lower = robot.rsi_lower_up_extreme
                    if robot.rsi_mode == 'or':
                        if (robot.rsi_higher >= robot.rsi_higher_up_extreme) or (
                                robot.rsi_lower >= robot.rsi_lower_up_extreme):
                            robot.logger.lprint(["--- not confirmed: extreme RSI values (higher {} OR lower tf {}):".format(
                                robot.rsi_higher, robot.rsi_lower)])
                            proceed_buy = False
                    else:
                        if (robot.rsi_higher >= robot.rsi_higher_up_extreme) and (
                                robot.rsi_lower >= robot.rsi_lower_up_extreme):
                            robot.logger.lprint([
                                                    "--- not confirmed: extreme RSI values (higher {} AND lower tf {}):".format(
                                                        robot.rsi_higher, robot.rsi_lower)])
                            proceed_buy = False
                # If still ok
                if proceed_buy:
                    robot.logger.lprint(["--- confirmed on RSI:", robot.rsi_higher, robot.rsi_lower])

        elif mode == 'quick':  # if we are checking this for the previous 3-min candle
            # This may fail
            try:
                # Updating candles
                if ((robot.bars_5m_timer is not None) and (abs(robot.bars_5m_timer - int(b_test.strftime("%M"))) >= 5)):
                    robot.bars_5m = self.td_price_threading(robot, '5min', b_test)
                    robot.bars_5m_timer = int(b_test.strftime("%M"))
                    robot.logger.lprint(["(i) updating 5min bars"])
                robot.logger.lprint(["Last 5-min candle close value:", robot.bars_5m['close'].iloc[-2]])
                if ((not robot.short_flag and (robot.bars_5m['close'].iloc[-2] > check_price))
                        or (robot.short_flag and (robot.bars_5m['close'].iloc[-2] < check_price))):
                    proceed_buy = True
            except:
                robot.logger.lprint(["Cannot use 5m for confirmation - buying now"])
                proceed_buy = True
            if not proceed_buy:
                robot.logger.lprint(["Entry not confirmed because of the 5min candle"])

        robot.logger.lprint(["Proceed buy result:", proceed_buy])

        return proceed_buy

    ### Ensure that we should sell based on td
    def ensure_td_sale(self, robot, check_price, mode = 'standard', b_test = None):

        proceed_sale = False
        robot.logger.lprint([
            "Running ensure_sale check for TD price. Mode {}, robot.short flag {}, check_price {}".format(
                mode, robot.short_flag, check_price)
            ])

        # Standard mode: checking the last 2 closes of 10-min candles (excluding the current one)
        if mode == 'standard':
            ###robot.logger.lprint(["Timer delta:", robot.ensure_td_sale_minute, '|', int(b_test.strftime("%M")) ])

            if (b_test.backtesting and abs(robot.ensure_td_sale_minute - int(b_test.strftime("%M"))) >= 10) or (not b_test.backtesting):
                robot.ensure_td_sale_minute = int(b_test.strftime("%M"))

                bars_x_min = self.td_price_threading(robot, robot.ensure_sale_standard_length, b_test)
                if bars_x_min is not None:
                    if math.isnan(bars_x_min['close'].iloc[-3]) or math.isnan(bars_x_min['close'].iloc[-2]):
                        robot.logger.lprint(["(i) selling because there is no data"])
                        proceed_sale = True
                    else:
                        robot.logger.lprint(["Last two exit control candles close values: {}, {}".format(
                            bars_x_min['close'].iloc[-3], bars_x_min['close'].iloc[-2])])
                        # Selling only if the last 2 closes went beyond our threshold
                        if not robot.short_flag and (bars_x_min['close'].iloc[-2] < check_price) and (bars_x_min['close'].iloc[-3] < check_price):
                            proceed_sale = True
                        if  robot.short_flag and (bars_x_min['close'].iloc[-2] > check_price) and (bars_x_min['close'].iloc[-3] > check_price):
                            proceed_sale = True
                else:
                    robot.logger.lprint(["(i) selling because there is no data"])
                    proceed_sale = True
                # Free up memory
                del bars_x_min

        elif mode == 'quick':   # if we are checking this for the previous 5-min candle
            try:
                # Updating candles
                if ((robot.bars_5m_timer is not None) and (abs(robot.bars_5m_timer - int(b_test.strftime("%M"))) >= 5)):
                    robot.bars_5m = self.td_price_threading(robot, '5min', b_test)
                    robot.bars_5m_timer = int(b_test.strftime("%M"))
                    robot.logger.lprint(["(i) updating 5min bars"])

                # Selling only if the last 2 closes went beyond our threshold
                robot.logger.lprint(["Last 5-min candles close value:", robot.bars_5m['close'].iloc[-2]])
                if ( (not robot.short_flag and (robot.bars_5m['close'].iloc[-2] < check_price))
                or (robot.short_flag and (robot.bars_5m['close'].iloc[-2] > check_price)) ):
                    proceed_sale = True
            # 5 min can fail for backtesting due to data completeness
            except:
                robot.logger.lprint(["Cannot use 5m for confirmation - selling now"])
                proceed_sale = True

        return proceed_sale

    ### Prices info
    def td_price_threading(self, robot, control_bars_period, b_test, for_ml = False):
        if (control_bars_period not in ['5min', '10min', '15min']) and b_test.backtesting:
            return self.analysis_combined(robot, control_bars_period, b_test, type = 'price', for_ml = for_ml)
        else:
            bars_update = self.price_stats(robot, control_bars_period, b_test=b_test)
            if bars_update is not None:
                bars_return = bars_update.copy()
            else:
                bars_return = None
            '''
            thread_result = queue.Queue()
            t1 = FuncThread(self.td_price_stats, robot, control_bars_period, b_test, thread_result)
            t1.start()
            t1.join()
            bars_update = thread_result.get()
            if bars_update is not None:
                bars_return = bars_update.copy()
            else:
                bars_return = None
            thread_result.queue.clear()
            '''
            del bars_update
            #del  t1, thread_result
            gc.collect()

            return bars_return

    '''
    def td_price_stats(self, robot, control_bars_period, b_test, thread_result):
        td_calc = self.price_stats(robot, control_bars_period, b_test=b_test)
        thread_result.put(td_calc)
    '''

    # MA
    def td_ma_threading(self, robot, bars_period, ma_period, b_test, ma_calc):
        if (bars_period not in ['5min', '10min', '15min']) and b_test.backtesting:
            return self.analysis_combined(robot, bars_period, b_test, type='ma', ma_period=ma_period, ma_calc=ma_calc)
        else:
            bars_update = self.price_ma_stats(robot, bars_period, ma_period, b_test=b_test, ma_calc=ma_calc)
            '''
            thread_result = queue.Queue()
            t1 = FuncThread(self.td_ma_stats, robot, bars_period, ma_period, thread_result, ma_calc, b_test)
            t1.start()
            t1.join()
            bars_update = thread_result.get()
            thread_result.queue.clear()
            del t1, thread_result
            '''
            gc.collect()
            return bars_update

    '''
    def td_ma_stats(self, robot, bars_period, ma_period, thread_result, ma_calc, b_test):
        td_calc = self.price_ma_stats(robot, bars_period, ma_period, b_test=b_test, ma_calc=ma_calc)
        thread_result.put(td_calc)
    '''

    # RSI
    def td_rsi_threading(self, robot, bars_period, b_test):
        if (bars_period not in ['5min', '10min', '15min']) and b_test.backtesting:
            return self.analysis_combined(robot, bars_period, b_test, type='rsi')
        else:
            bars_update = self.price_rsi_stats(robot, bars_period, b_test=b_test)
            '''
            thread_result = queue.Queue()
            t1 = FuncThread(self.td_rsi_stats, robot, bars_period, b_test, thread_result)
            t1.start()
            t1.join()
            bars_update = thread_result.get()
            thread_result.queue.clear()
            del t1, thread_result
            '''
            gc.collect()
            return bars_update

    '''
    def td_rsi_stats(self, robot, bars_period, b_test, thread_result):
        td_calc = self.price_rsi_stats(robot, bars_period, b_test=b_test)
        thread_result.put(td_calc)
    '''

    ### Function to get pre-calculated TD values from the DB
    # Note: is not appropriate for ML because it would include future values thus should be deprecated
    def analysis_combined(self, robot, control_bars_period, b_test, type = 'price', ma_period = None, ma_calc = None, for_ml = False):
        if (control_bars_period != '30min') and not for_ml: # for ML need to add at least 1 min otherwise the result is incorrect
            check_time = b_test.strftime("%Y-%m-%d %H:%M")
        else: # workaround - in the original script 30min included the last bar
            datetime_object = datetime.strptime(b_test.strftime("%Y-%m-%d %H:%M"), '%Y-%m-%d %H:%M')
            check_time = datetime_object + timedelta(minutes = 3)

        request = "SELECT * FROM td_stats where market = '{}' AND period = '{}' " \
            "AND timestamp <= '{}' order by timestamp desc limit 10".format(robot.market, control_bars_period, check_time)
        results = sql.query(request)

        #robot.logger.lprint(["SQL request", request])
        colnames = [
            'timestamp',
            'open',
            'high',
            'low',
            'close',
            'rsi',
            'td_setup',
            'td_direction',
            'move_extreme',
            'if_countdown_down',
            'if_countdown_up',
            'countdown_up',
            'countdown_down',
            'ma_30',
            'ma_20',
            'ma_10',
            'ma_30_exp',
            'ma_20_exp',
            'ma_10_exp',
            'time_st',
            'market',
            'period'
        ]

        df_results = pd.DataFrame(results, columns = colnames)
        df_results['if_countdown_down'] = df_results['if_countdown_down'].astype(bool)
        df_results['if_countdown_up'] = df_results['if_countdown_up'].astype(bool)
        df_results = df_results.sort_values(by=['timestamp'])

        if type == 'price':
            return df_results
        elif type == 'rsi':
            return df_results['rsi'].iloc[-1]
        elif type == 'ma':
            if ma_calc == 'exponential':
                ma_prefix = '_exp'
            else:
                ma_prefix = ''
            ma_col = ''.join(['ma_', str(ma_period), ma_prefix])

            return df_results[ma_col].iloc[-1]


    ### Machine Learning
    # Get pre-calculated features from the database
    def get_features(self, check_time, robot): # to generalise and rewrite to make this unified
        request = "SELECT * FROM labels_generated where timestamp <= '{}' and market = '{}' and exchange = '{}' " \
            "order by timestamp desc limit 1".format(check_time, robot.market, robot.exchange_abbr)
        results = sql.query(request)

        #robot.logger.lprint(["SQL request", request])    # DEBUG

        colnames = [
            'timestamp',
            'rsi_1h',
            'td_setup_1h',
            'td_direction_1h',
            'if_countdown_down_1h',
            'if_countdown_up_1h',
            'countdown_up_1h',
            'countdown_down_1h',
            'ma_30_1h',
            'ma_20_1h',
            'ma_10_1h',
            'close_percent_change_1h',
            'rsi_percent_change_1h',
            'high_to_close_1h',
            'low_to_close_1h',
            'close_to_ma10_1h',
            'close_to_ma20_1h',
            'close_to_ma30_1h',
            'rsi_4h',
            'td_setup_4h',
            'td_direction_4h',
            'if_countdown_down_4h',
            'if_countdown_up_4h',
            'countdown_up_4h',
            'countdown_down_4h',
            'ma_30_4h',
            'ma_20_4h',
            'ma_10_4h',
            'close_percent_change_4h',
            'rsi_percent_change_4h',
            'high_to_close_4h',
            'low_to_close_4h',
            'close_to_ma10_4h',
            'close_to_ma20_4h',
            'close_to_ma30_4h',
            'rsi_1d',
            'td_setup_1d',
            'td_direction_1d',
            'if_countdown_down_1d',
            'if_countdown_up_1d',
            'countdown_up_1d',
            'countdown_down_1d',
            'ma_30_1d',
            'ma_20_1d',
            'ma_10_1d',
            'close_percent_change_1d',
            'rsi_percent_change_1d',
            'high_to_close_1d',
            'low_to_close_1d',
            'close_to_ma10_1d',
            'close_to_ma20_1d',
            'close_to_ma30_1d',
            'market', 'exchange'
        ]

        df_results = pd.DataFrame(results, columns = colnames)
        columns_omit = [
            'timestamp',
            'ma_30_1h', 'ma_20_1h', 'ma_10_1h',
            'ma_30_4h', 'ma_20_4h', 'ma_10_4h',
            'ma_30_1d', 'ma_20_1d', 'ma_10_1d',
            'market', 'exchange'
        ]
        #Choose all predictors
        X_col = [x for x in df_results.columns if x not in columns_omit]
        X = df_results[X_col]
        
        return X

    # Predict, current approach 
    def predict_label(self, X, robot):

        bst = xgb.Booster({'nthread': 4})  # init model
        bst.load_model('models/{}'.format(robot.model_name))  # load the model

        try: # may not work if there are Nones
            dtest = xgb.DMatrix(X)
            pred = bst.predict(dtest)
            label = np.argmax(pred, axis=1)[0]   # giving a prediction:
            # 0 : nothing
            # 1 : long
            # 2: short
            label_probability = pred[0][int(label)]
        except ValueError:   # in case it fails
            label, label_probability = 0, 1
            print('Note: Issue when predicting the value')

        return label, label_probability


    ### Data preparation
    def df_perc_calc(self, df):
        df['close_shifted'] = df['close'].shift(1)
        df['close_percent_change'] = 100*(df['close'] - df['close_shifted'])/df['close']
        # rsi percent change
        df['rsi_shifted'] = df['rsi'].shift(1)
        df['rsi_percent_change'] = 100*(df['rsi'] - df['rsi_shifted'])/df['rsi']   # New
        # High to close and low to close should be a feature (could be useful)
        df['high_to_close'] = df['high']/df['close']
        df['low_to_close'] = df['low']/df['close']
        # Close below/above MAs or % to MA should be a feature (%)
        df['close_to_ma10'] = df['close']/df['ma_10']
        df['close_to_ma20'] = df['close']/df['ma_20']
        df['close_to_ma30'] = df['close']/df['ma_30']
        # Change to numeric
        df['td_direction'] = (df['td_direction'] == 'green').astype(int)        # 1 for green, 0 for red

        # Drop unnecessary columns
        for colname in ['open', 'high', 'low', 'close', 'move_extreme','close_shifted', 'rsi_shifted']:  #, 'if_countdown_up', 'if_countdown_down']:
            df.drop(colname, axis=1, inplace=True)

        return df.tail(1)

    ### Needed for ML testing point in time
    def get_features_realtime(self, robot, b_test):

        period_arr =  robot.feature_periods

        bars_temp = None

        for period in period_arr:
            if robot.logger is not None:
                robot.logger.lprint(["(i) updating features for {}".format(period)])
            else:
                print("(i) updating features for {}".format(period))

            # Bars   #bools should be converted to numeric
            barsb = self.stats(robot.market, robot.exchange_abbr, period, 0, 2, True, b_test=b_test)
            barsb['if_countdown_up'] = pd.to_numeric(barsb['if_countdown_up'], errors='coerce')
            barsb['if_countdown_down'] = pd.to_numeric(barsb['if_countdown_down'], errors='coerce')

            bars_ma_30 = self.stats_MA_only(robot.market, robot.exchange_abbr, period, 30, 0, 2, False, b_test = b_test)
            bars_ma_20 = self.stats_MA_only(robot.market, robot.exchange_abbr, period, 20, 0, 2, False, b_test = b_test)
            bars_ma_10 = self.stats_MA_only(robot.market, robot.exchange_abbr, period, 10, 0, 2, False, b_test = b_test)
            barsb['ma_30'] = bars_ma_30
            barsb['ma_20'] = bars_ma_20
            barsb['ma_10'] = bars_ma_10
            barsb = self.df_perc_calc(barsb)   # get values

            # Reset index
            barsb.reset_index(drop=True, inplace=True)

            barsb.columns = [str(col) + '_' + period for col in barsb.columns]

            if bars_temp is None:
                bars_temp = barsb.copy()
            else:
                bars_temp = pd.concat([bars_temp, barsb], axis=1)

        columns_omit = robot.features_omit

        #Choose all predictors
        X_col = [x for x in bars_temp.columns if x not in columns_omit]
        X = bars_temp[X_col]

        return X
