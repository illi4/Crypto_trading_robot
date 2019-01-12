# Robot class

import config
from libs.loglib import logfile  # logging
import libs.aux_functions as aux_functions  # various auxiliary functions
import exch_api # to get balance when there is no input
import libs.lambobot as lambobot
from sys import exit

from libs.aux_functions import send_chat_message

class Scripting:
    def __init__(self, user, strategy = 'standard', codename = 'reg'):
        self.public = ['update_thresholds', 'robot_input']

        # If there is no user
        if user is None:
            user = config.telegram_chat_id

        # Default mode is 'now'
        self.mode = 'now'
            
        self.aux_functions = aux_functions.aux_functions()
        self.e_api = exch_api.api(user, strategy = strategy)
        self.user_id = user

        self.logger = None
        self.codename = codename
        self.core_strategy = strategy
        self.use_all_balance = False
        self.logger = None 
        
        # Initial 'do nothing' label 
        self.prediction = 0   # default prediction is 0 (do nothing)
        self.prediction_probability = 1

        # For compatibility with the old code
        self.stop_loss = True

        # Default buy_back and buyer (entry) direction is none (when just starting the scripts)
        self.entry_direction = None
        
        self.assign_default_values()  # static values which should be reset each input

        # Lambobot to share tweets
        if (config.lambobot_available) and (user == config.telegram_chat_id):
            self.lambobot = lambobot.tweep()
        else:
            self.lambobot = None

        self.price = 0
        self.percent_of_entry = 100
        
        # Default flag for shorting. The bot can be used to short on bitmex, not only go long
        self.short_flag = False

        # To cancel buyback if there is an error and there were no sales made
        self.cancel_buyback = False

        # Workflow id and job id
        self.job_id = None
        self.wf_id = None

        ## Bitmex margin
        self.margin_level = self.e_api.return_margin() #config.margin_level  # size of margin on bitmex margin

        self.simulation_balance = 0

        # Results list for backtesting
        self.backtest_results = []

        # Minutes update
        self.control_bars_minutes = []

        # Time stamps: buyer start, sell_now finished to calculate the outcomes
        self.timestamp_start_initiate = None
        self.timestamp_start_process = None
        self.timestamp_finish = None
        self.timer_control_bars_update = None

        # Other
        self.attr_string = '' # attributes string used in backtesting

        # oanda last id
        self.oanda_last_trans_id = 0

    # For control bars milestones update
    def control_bars_milestones(self):
        # If the connotation is a list like ['25min', '55min']:
        if isinstance(self.control_bars_period, (list)):
            for elem in self.control_bars_period:
                minute = int(str(elem).replace('min', ''))
                self.control_bars_minutes.append(minute)
        else: # If the connotation is just one period like '30min'
            if self.control_bars_period.find('min') >= 0:
                period = int(self.control_bars_period.replace('min', ''))
                mark = 0
                while mark < 60:  # within 1 hour
                    self.control_bars_minutes.append(mark)
                    mark += period
            else: # if more than 1 hour - hourly update is fine
                self.control_bars_minutes.append(0)

    # Store call attributes (console params) string for logging
    def store_launch_params(self, config):
        if config.backtesting_enabled:
            attr_string = ''
            for elem in self.key_names:
                attr_string += '{}: {}\n'.format(elem, getattr(self, elem))
            self.logger.lprint([attr_string])
            self.attr_string = attr_string

    # Function to return action and direction
    def predicted_action_direction(self, type='entry'):
        if (self.prediction == 1):
            action, direction = True, 'green'
        elif (self.prediction == 2):
            action, direction = True, 'red'
        else:
            action, direction = False, 'no position'

        # Different thresholds depending on the type
        if type == 'entry':
            checked_threshold = self.predicted_confidence_threshold
        elif type == 'exit':
            checked_threshold = self.exit_confidence_threshold

        if self.prediction_probability >= checked_threshold:
            over_threshold = True
        else:
            over_threshold = False

        return action, direction, over_threshold

    ### Predicted class name for ML
    def predicted_name(self, num):
        if num == 0:
            num_name = 'no positions'
        elif num == 1:
            num_name = 'long position'
        elif num == 2:
            num_name = 'short position'
        return num_name

    ### Predicted class name for ML, inverse (when reading from DB)
    def predicted_num_from_name(self, num_name):
        if num_name == 'no positions':
            num = 0
        elif num_name == 'long position':
            num = 1
        elif num_name == 'short position':
            num = 2
        return num

    # Updating thresholds depending on the strategy, this also speeds up execution
    def update_thresholds(self):

        market_id = self.market.lower()
        self.key_names = [
            'model_name',
            'feature_periods',
            'features_omit',
            'limit_losses', 'limit_losses_val',
            'predicted_confidence_threshold',
            'exit_confidence_threshold',
            'control_bars_period', # needed for prediction updates
            'forex_pair' # units calculation is different for forex pairs
        ]


        if self.market.lower() in list(config.param_dict.keys()):
            for key_name in self.key_names:
                setattr(self, key_name, config.param_dict[market_id][key_name])
        else:
            for key_name in self.key_names:
                setattr(self, key_name, config.param_dict['other'][key_name])

        # Control bars update marks: define
        self.control_bars_milestones()


    # Close the logger
    def close_log(self):
        if self.logger is not None:
            self.logger.close_handler()

    # Stop everything and exit
    def terminate(self):
        self.close_log()
        exit(0)

    # Assign defaults 
    def assign_default_values(self):    # reconsider for deprecation
        # Intervals and timers in seconds
        self.speedrun = config.speedrun
        self.sleep_timer = config.sleep_timer  # Generic sleep timer. Applicable for the main monitoring loop and for the mooning procedure.
        self.sleep_timer_buyback = config.sleep_timer_buyback  # Sleep timer for buybacks
        self.sleep_sale = config.sleep_sale  # Sleep timer for sell orders to be filled

        # Precision; precision higher than 2 should be some edge cases (to be considered later)
        self.round_num = 2

        # Resetting entry cutoff price  # deprecate
        self.entry_cutoff_price = None

        # Postonly (market making)
        self.postonly_minutes = config.postonly_minutes

        # Deprecated
        # Number of attempts to try market making
        #self.postonly_attempts = config.postonly_attempts

        ## Interval and number of checks to get current (last) prices
        self.steps_ticker = config.steps_ticker
        self.sleep_ticker = config.sleep_ticker

        ## Steps and timer for buybacks
        self.candle_steps = config.candle_steps
        self.candle_sleep = config.candle_sleep

        ## Opening a position
        self.sleep_buy_timer = config.buy_sleep_timer

        # For traditional   # Deprecate
        if self.core_strategy == 'traditional':
            extra_multiplier = config.traditional_wait_multiplier
        else:
            extra_multiplier = 1

        if not config.backtesting_enabled: 
            self.sleep_timer = int(self.sleep_timer / self.speedrun) * extra_multiplier
            self.sleep_sale = int(self.sleep_sale / self.speedrun) * extra_multiplier
            self.sleep_buy_timer = int(self.sleep_buy_timer / self.speedrun) * extra_multiplier
            self.sleep_ticker = int(self.sleep_ticker / self.speedrun) * extra_multiplier
            self.candle_steps = int(self.candle_steps / self.speedrun) * extra_multiplier

        # Other variables used
        self.main_curr_from_sell = 0
        self.commission_total = 0
        self.alt_sold_total = 0
        self.value_original = 0
        self.contracts_start = 0
        self.bitmex_sell_avg = 0  # for bitmex price averaging
        self.sl_extreme = None
        self.strategy = None
        self.direction_previous = None
        self.price_flip = False
        self.bitmex_sell_avg = None
        self.twitter_comment = ''

        self.orders_start = set()
        self.orders_new = set()

        self.fixed_price_starter = False

    # If platform is supported
    def is_supported(self, ex_name):
        if ex_name not in config.exch_supported:
            print('Incorrect exchange specified (should be in {})\n\n'.format(config.exch_supported))
            exit(0)

    # Shorts support check
    def is_short_supported(self, ex_name):
        if (ex_name not in config.exch_short) and self.short_flag:
            self.logger.lprint(["Shorts are not supported on the exchange", self.exchange])
            exit(0)

    def ex_params(self):
        self.exchange = config.exch_types[self.exchange_abbr]['fullname']
        self.comission_rate_percent = config.exch_types[self.exchange_abbr]['commission']
        self.exchange_type = config.exch_types[self.exchange_abbr]['type']
        self.comission_rate = self.comission_rate_percent * self.margin_level

    def ex_trade_curr(self, input_name):
        self.market = input_name.upper()
        if self.exchange_type == 'crypto':

            #Might be needed later
            #try:
            #    self.trade, self.currency = self.market.split('-')
            #except:

            self.trade = self.market  # e.g. if only one market vs BTC is provided - such as XRPH18 on bitmex
            self.currency = 'BTC'
        else:
            self.trade = self.market
            self.currency = ''

    ### Input - process mode
    def input_process(self, input_params):
        try:
            self.simulation_param = input_params[2]
            if  self.simulation_param == 's':
                self.simulation = True
            elif self.simulation_param == 'r':
                self.simulation = False
            else:
                self.no_input = True

            self.exchange_abbr = input_params[3].lower()
            self.is_supported(self.exchange_abbr)
            # Commissions and full exchange names
            self.ex_params()

            # Market to trade
            self.ex_trade_curr(input_params[4])

            # Logger initialisation
            if self.logger is None:
                self.logger = logfile(self.market.replace('/','_'), 'trade', self.codename, username = str(self.user_id))
            self.logger.lprint(["###################### CYCLE: ROBOT ###########################"])

            self.price_entry = float(input_params[5])  # entry price

            # Deprecated
            #self.price_target = float(input_params[6])  # target price
            #self.sl_target = float(input_params[7])  # stop loss price

            try:
                self.limit_sell_amount = float(input_params[6]) #float(input_params[8])
            except:
                self.limit_sell_amount = 0
            try:
                self.sell_portion = float(input_params[7]) # float(input_params[9])
            except:
                self.sell_portion = None

        except:
            err_msg = '''
Run parameters not specified or are incorrect. Restart the script using:
robot.py simulation (s/r) exchange basic_curr-altcoin entry_price [limit_of_amount_to_sell] [sell_portion]
Example: > python robot.py s btrx BTC-LTC 0.0017 100      
            '''
            print(err_msg)
            exit(0)

    # Input position sizing
    def initiate_position_size(self, input_size):

        try:
            self.source_position = float(input_size)
            # For shorts
            if self.source_position < 0:
                self.short_flag = True
                self.source_position = abs(self.source_position)
        except:
            if not config.backtesting_enabled:
                self.source_position = float(self.balance['Available'])
                # For oanda, should be multiplied by margin
                self.logger.lprint(["Buying for the whole balance of", self.source_position])

        # Full balance also in the case the parameter was enabled on the start
        if not config.backtesting_enabled:
            if self.use_all_balance and self.mode not in ['now-s', 'fullta-s']:
                if self.source_position > 0:
                    self.source_position = abs(float(self.balance['Available']))
                else:
                    self.source_position = -abs(float(self.balance['Available']))
                self.logger.lprint(["Buying for the whole balance of", self.source_position])

        # Also change to properly reflect the margin
        self.source_position = self.source_position * self.margin_level
        # Commission should also be changed based on the margin value
        self.comission_rate = self.comission_rate * self.margin_level


    ### Input - initiate
    def input_initiate(self, input_params):

        # Modes
        self.mode = input_params[2].lower()

        if self.mode not in ['now', 'now-s', 'fullta', 'fullta-s', 'full_cycle']:
            print("Incorrect mode specified (should be 'now', 'now-s', 'fullta', 'fullta-s', 'full_cycle')\n\n")
            send_chat_message(self.user_id, 'Incorrect mode specified')
            exit(0)

        # Exchange
        self.exchange_abbr = input_params[3].lower()
        self.is_supported(self.exchange_abbr)
        # Commissions and full exchange names
        self.ex_params()

        # Market to trade
        self.ex_trade_curr(input_params[4])


        # Logger initialisation
        if self.logger is None:
            self.logger = logfile(self.market.replace('/','_'), 'trade', self.codename, username=str(self.user_id))
        self.logger.lprint(["###################### CYCLE: OPENING A POSITION  ###########################"])

        # Getting stuff for the whole if there is no input
        if not config.backtesting_enabled:
            self.balance = self.e_api.getbalance(self.exchange, self.trade)

        # Position size
        self.initiate_position_size(input_params[5])

        # If the price is set up
        try:
            self.fixed_price = float(input_params[6])
            self.fixed_price_flag = True
        except:
            self.fixed_price = 0
            self.fixed_price_flag = False

        # Shorts support check
        self.is_short_supported(self.exchange_abbr)

        '''
        except:
            print 'Specify the parameters: mode exchange basic_curr-altcoin total_in_basic_curr [price] [time limit for the price in minutes] \n>
            Example: reg/brk/now/reg-s/brk-s/4h btrx BTC-QTUM 0.005 0.0038 15 \nThis tries to buy QTUM for 0.005 BTC at 
            Bittrex for the price of 0.0038 for 15 minutes, then switches to market prices \n\nModes: \n
            4h - buy based on 4h candles price action \nreg - buy at fixed price \nbrk - 
            buy on breakout (above the specified price) \noptions with -s mean the same but 
            they run in the simulation mode \nnow is immediately \n\nExchanges: bmex or oanda'
            exit(0)
        '''

    ### Input - general
    def input(self, arg1=None,
                    arg2=None,
                    arg3=None,
                    arg4=None,
                    arg5=None,
                    arg6=None,
                    arg7=None,
                    arg8=None,
                    arg9=None
                    ):

        # Input_params
        input_params = [arg1, arg2, arg3, arg4, arg5, arg6, arg7, arg8, arg9]  # for compatibility with the code further

        try:
            self.robot_mode = input_params[1]

        # If no mode is specified at all (process or initiate)
        except:
            print('Please specify the robot mode: process or initiate')
            exit(0)

            # Process is when we have a position open
        # Initiate when the position should be opened (e.g. bought)
        if self.robot_mode not in ['process', 'initiate']:
            print('Incorrect mode specified \n\n')
            exit(0)

        # Reset the timers and the references
        self.assign_default_values()

        # Processing an open position
        if self.robot_mode == 'process':
            self.input_process(input_params)
        # Opening a position
        elif self.robot_mode == 'initiate':
            self.input_initiate(input_params)

        return self.robot_mode