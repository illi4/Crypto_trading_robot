############################### Configuration file ############################################################
### For production, disable backtesting and enable lambobot_available, set speedrun to 1

## Backtesting mode
backtesting_enabled = False      # remember to switch commission to 0 when testing
backtesting_use_db_labels = False   # to use pre-calculated labels from DB or to calculate on the fly
use_testnet = False # change to true for testing
run_testmode = False     ### Testmode control if needed

# Backtesting start and end dates (are overwritten if launched from terminal with --start --end)
backtesting_start_d, backtesting_start_m, backtesting_start_y  = 5, 2, 2014
backtesting_start_h, backtesting_start_min = 3, 0
backtesting_end_d, backtesting_end_m, backtesting_end_y  = 25, 3, 2017
backtesting_end_h, backtesting_end_min = 22, 0

# Set up the speedrun multiplier if need to test with higher speeds. 1 is normal, 2 is 2x faster 
# Work only _not_ in backtesting
speedrun = 1
traditional_wait_multiplier = 3  # things happen slower in the traditional space

# Bitmex: How many minutes should the bot wait after the start of orders making to switch to market taking
# Traditional (oanda): How many minutes to wait until switching to market orders
postonly_minutes = 15

### Lambobot (if posting to twitter is needed)
lambobot_available = True

if run_testmode:
    speedrun = 10
    postonly_minutes = 1
    lambobot_available = False
    backtesting_enabled = False
    traditional_wait_multiplier = 1

if backtesting_enabled:
    lambobot_available = False
    comission_rate_bitmex = 0

# If enabled, the robot will take minor profits as configured within the price indicator-based movements
# If the price continues to move higher, 15-min intervals will be checked to reconfigure the threshold 

take_profit = True 
take_profit_error_margin = 0.0015   # 0.15% for the noise on taking profit 

postpone_entries = True
# If bitmex_postpone_entries is True, buys are not executed on bitmex if there are contracts open already
# Handy to have this enabled when you have a stop set manually and start robot but want to reenter as soon as possible in the robot

## Timers
# Robot
sleep_timer = 30                                    # Generic sleep timer (robot). Applicable for the main monitoring loop and for the mooning procedure.
sleep_timer_buyback = 60                    # Sleep timer for buybacks 
sleep_sale = 60                                     # Sleep timer for sell orders to be filled 

# Buy
buy_sleep_timer = 60               # Sleep timer in seconds for buy task. changed to 3 minutes because orders were filling way too quickly at a higher price. 180 is 3 min

## Interval and number of checks to get current (last) prices
steps_ticker = 3 
sleep_ticker = 10               # so that ticker in total takes 30 seconds 

## Steps and timer for buybacks 
candle_steps = 80               # 100 for 5 min, 80 for 4
candle_sleep = 2.8              # Tested, 3 sec lead to having ~5 min 30 sec in between 


#### Logins and passwords, comm method
comm_method = 'chat'        # 'mail' or 'chat'

# Gmail login and pass (if used) 
fromaddr = "fromaddress@gmail.com"    # replace to a proper address 
toaddr = "to@address.com"    # replace to a proper address 
email_passw = "your_gmail_pass"

#### Platform and system settings, time settings
nix_folder = '/home/ubuntu/Robot/'                       # your unix machine folder (if you use nix)
timedelta = 10                                                      # convert price information to your local time. For Sydney, it is 10 during DST (Oct-Apr). Shift from DST is handled automatically.
td_price_base_constant = 2                              # price base for TDlib. For 4H, it should be 2 during DST (Oct-Apr). Shift from DST is handled automatically.     
pytz_timezone = 'Australia/Sydney'                  # for proper daylight saving time detection
local_curr = 'AUD'                                               # symbol to change the price to your local currency (for balance command)    
local_curr_fixed = 1.25                                       # exchange from USD to your local in case the url request does not work   

# Directories to copy (if needed - I am using this for backing up data on Dropbox) 
dir_from = '/home/ubuntu/Robot/price_log'
dir_to = '/home/ubuntu/Dropbox/Exchange/'

# Commands to start a terminal in your *nix environment
cmd_init = 'gnome-terminal --tab --profile Active -e "python3 ' + nix_folder + 'robot.py '                       # do not remove this space in the end


############## Telegram settings ####################

# Telegram functions 
telegram_token = "XXXXXXXXXX:AAG-XXXXXXXXX-XXXXXXXXXX-XXXXXXXXXX"
telegram_url = "https://api.telegram.org/bot{}/".format(telegram_token)

telegram_key = "XXXXXXXXXXXXXXXXX" 
telegram_secret = "XXXXXXXXXXXXXXXXXXX" 
telegram_chat_id = 9999999999 # (admin) id 
telegram_check_sec = 1

########## Twitter ###############################
twitter_keys = { 
                        "consumer_key": "4qfIL4Gc0GgWIjmBxhM1dAxGt",
                        "consumer_secret": "bUEngPnxClngFvPutSlAphGuR9wlSw1Qiyoy5ut59oq3rnX6Uu",
                        "access_token": "867620525236830208-mwn7w7YN4HELwniEGxah3nj3OiugxM6",
                        "access_token_secret": "ONtECLNWKDTfGEgASvzerQYrmaL91ZQXsxVP2CzvHK9YU"
                        }

##### Testnet keys which are used when testmode = True
testnet_keys = {
    'key_bitmex': 'XXXXXXXXXXXXXX',
    'secret_bitmex': 'awRj-XXXXXXXXXXXXXXXXX',
    'key_oanda': '101-011-XXXXXXXXX-XXXXXXXXXXX',
    'secret_oanda': 'XXXXXXXXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXX'
}

########## Twitter ###############################
twitter_keys = { 
                        "consumer_key": "XXXXXXXXXXXX",
                        "consumer_secret": "XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                        "access_token": "XXXXXXXXXXXXXXX-XXXXXXXXXXXXXXXXXXXXXX",
                        "access_token_secret": "XXXXXXXXXXXXXXXXXXXXXX"
                        }

######## Price logger - which prices to collect ###########
markets_list = [
    ['BTC/USD' , 'BMEX', 'standard'],  # deprecate strategy names
    ['ETH/USD' , 'BMEX', 'standard'],
    ['SPX500_USD', 'OANDA', 'traditional'],
    ['NAS100_USD', 'OANDA', 'traditional'],
    ['XAU_USD', 'OANDA', 'traditional'],
    ['BCO_USD', 'OANDA', 'traditional' ],
    ['USD_JPY', 'OANDA', 'traditional' ]
    #['ETHZ18', 'BMEX', 'standard'],
    #['XBTZ18', 'BMEX', 'standard'],
]

exch_supported =  ['bmex', 'oanda']    # supported exchanges
exch_short =  ['bmex', 'oanda']  # exchanges where shorts are supported

# Strategies used when communicating with daemon, to deprecate
strategies = {
    'bitmex': ['standard'],
    'oanda': ['traditional']
}
exch_types = {
    'bmex': {'fullname': 'bitmex', 'type': 'crypto', 'commission': 0.00075},
    'oanda': {'fullname': 'oanda', 'type': 'traditional', 'commission': 0}
}


# Dictionary with market parameters
param_dict  = {
    'btc/usd': {
        'model_name': 'btc_100_lr001_18-11-04.model',
        'feature_periods': ['1h', '4h', '1d'],
        'features_omit': [  # calculated features are standard for all
            'timestamp',
            'ma_30_1h', 'ma_20_1h', 'ma_10_1h',
            'ma_30_4h', 'ma_20_4h', 'ma_10_4h',
            'ma_30_1d', 'ma_20_1d', 'ma_10_1d'
        ],  # another possible check - order of columns should be strictly followed
        'predicted_confidence_threshold': 0.5, # % threshold of entering the position
        'exit_confidence_threshold': 0.4,  # threshold on exiting
        'limit_losses': False,
        'limit_losses_val': 0.03,
        'control_bars_period': ['25min', '55min'],
        'forex_pair': False
    },
    'usd_jpy': {
        'model_name': 'jpy_18-10-22.model',
        'feature_periods': ['1h', '4h', '1d'],
        'features_omit': [  # calculated features are standard for all
            'timestamp',
            'ma_30_1h', 'ma_20_1h', 'ma_10_1h',
            'ma_30_4h', 'ma_20_4h', 'ma_10_4h',
            'ma_30_1d', 'ma_20_1d', 'ma_10_1d'
        ],  # another possible check - order of columns should be strictly followed
        'predicted_confidence_threshold': 0.4, # % threshold of entering the position
        'exit_confidence_threshold': 0.4, # threshold on exiting
        'limit_losses': False,
        'limit_losses_val': 0.03,
        'control_bars_period': ['25min', '55min'],
        'forex_pair': True
    },
    'nas100_usd': {
        'model_name': 'nas_100_lr001_18-11-04.model',
        'feature_periods': ['1h', '4h', '1d'],
        'features_omit': [  # calculated features are standard for all
            'timestamp',
            'ma_30_1h', 'ma_20_1h', 'ma_10_1h',
            'ma_30_4h', 'ma_20_4h', 'ma_10_4h',
            'ma_30_1d', 'ma_20_1d', 'ma_10_1d'
        ],  # another possible check - order of columns should be strictly followed
        'predicted_confidence_threshold': 0.5, # % threshold of entering the position
        'exit_confidence_threshold': 0.4, # threshold on exiting
        'limit_losses': False,
        'limit_losses_val': 0.03,
        'control_bars_period': ['25min', '55min'],
        'forex_pair': False
    },
}

# Update traditional

## All BTC markets including futures
primary_calc_markets = ['BTC/USD', 'XBTU18', 'XBTZ18', 'ETH/USD']  # contracts primary in calc vs secondary

#param_dict['xbtu18'] = param_dict['btc/usd']
#param_dict['xbtz18'] = param_dict['btc/usd']
#param_dict['eth-usd'] = param_dict['ethz18']
