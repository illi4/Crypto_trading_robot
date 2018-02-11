############################### Configuration file ############################################################

#### Price-related setup 
bitmex_margin = 2                                   # 1x to 3x is recommended

# If enabled, the robot will take minor profits as configured within the price indicator-based movements
# If the price continues to move higher, 15-min intervals will be checked to reconfigure the threshold 
take_profit = True 
take_profit_threshold = 0.045       # 4.5% from the entry 

# If this is enabled, the robot will be riding the opposite direction as soon as position is stopped (exited) based on TD indicator without looking at the larger time frame (td_period_extended) 
# If disabled, the robot will confirm on the larger time frame prior to entries 
ride_pullbacks = True 

# If bitmex_postpone_entries is True, buys are not executed on bitmex if there are contracts open already
# Handy to have this enabled when you have a stop set manually but you would like to reenter as soon as possible in fullta mode after the stop is hit 
bitmex_postpone_entries = True          

#### Timers 

# Set up the speedrun multiplier if need to test with higher speeds. 1 is normal, 2 is 2x faster 
speedrun = 1

# Robot
sleep_timer = 30                                    # Generic sleep timer (robot). Applicable for the main monitoring loop and for the mooning procedure.
sleep_timer_buyback = 60                  # Sleep timer for buybacks 
sleep_sale = 180                                     # Sleep timer for sell orders to be filled 
flash_crash_ind = 0.5                            # If something falls so much too fast - it is unusual and we should not sell (checking for 50% crashes)

# Buy
buy_sleep_timer = 180               # Sleep timer in seconds for buy task. changed to 3 minutes because orders were filling way too quickly at a higher price. 180 is 3 min 
orders_check = 5                       # Orders sequence for a market price calculation 

## Interval and number of checks to get current (last) prices 
steps_ticker = 3 
sleep_ticker = 10               # so that ticker in total takes 30 seconds 

## Steps and timer for buybacks 
candle_steps = 80               # 100 for 5 min, 80 for 4
candle_sleep = 2.8              # Tested, 3 sec lead to having ~5 min 30 sec in between 

#### Price analysis periods 
# Time analysis candles length 
td_period = '4h'    # possible options are in line with ohlc (e.g. 1h, 4h, 1d, 3d); customisable. This sets up smaller time interval for dynamic stop losses and buy backs     
td_period_extended = '9h'   # changed back to 1d with the current sentiment of uncertainty and mostly bearishness
# '9h'    # possible options are in line with ohlc (e.g. 1h, 4h, 1d, 3d); customisable. This sets up larger time interval for buy backs (should be in line with the smaller one)       
td_period_ext_opposite = '12h'  # changed back to 1d with the current sentiment of uncertainty and mostly bearishness
# '12h'  # for buybacks in the different direction (e.g. initiating short after going long first) 

#### Logins and passwords, comm method
comm_method = 'chat'        # 'mail' or 'chat'

# Gmail login and pass (if used) 
fromaddr = "fromaddress@gmail.com"    # replace to a proper address 
toaddr = "to@address.com"    # replace to a proper address 
email_passw = "your_gmail_pass"

#### Platform and system settings 
nix_folder = '/home/ubuntu/Robot/'                           # your unix machine folder (if you use nix) 
trade_hist_filename = 'Trade_history.xlsx'          # trade history file name   
timedelta = '11:00:00'                                         # convert price information to your local time. for Sydney, it is 11 hours (+11) 
local_curr = 'AUD'                                               # symbol to change the price to your local currency (for balance command)    
local_curr_fixed = 1.25                                       # exchange from USD to your local in case the url request does not work   

# Directories to copy (if needed - I am using this for backing up data on Dropbox) 
dir_from = '/home/ubuntu/Robot/price_log'
dir_to = '/home/ubuntu/Dropbox/Exchange'

# Commands to start a terminal in your *nix environment
cmd_init = 'gnome-terminal --tab --profile Active -e "python ' + nix_folder + 'robot.py '                       # do not remove this space in the end
cmd_init_buy = 'gnome-terminal --tab --profile Active -e "python ' + nix_folder + 'smart_buy.py '       # do not remove this space in the end

############### API KEYS ########################

# Initialising clients with api keys 
bittrex_apikey = 'key'
bittrex_secret = 'secret'

binance_apikey = 'key'
binance_secret = 'secret'

bitmex_apikey = 'key'
bitmex_secret = 'secret'
# Uncomment if you want to use bitmex testnet 
# bitmex.urls['api'] = bitmex.urls['test']

## Coinigy keys 
coinigy_key = 'key' 
coinigy_secret = 'secret'

############## Telegram settings ####################

# Telegram functions 
telegram_token = "YOUR_TOKEN"
telegram_url = "https://api.telegram.org/bot{}/".format(telegram_token)

telegram_key = "key" 
telegram_secret = "secret" 
telegram_chat_id = 1111111111111 # replace with yours 
telegram_check_sec = 1

######## Exchanges - commission rates ###############
comission_rate_bittrex = 0.003               # rate is 0.25% + 0.05% for contingency in roundings etc 
comission_rate_binance = 0.001            # rate is 0.1% + 0.05% for contingency in roundings etc 
comission_rate_bitmex = 0                     # no commissions as such when opening a position   

######## Price logger - which prices to collect ###########
markets_list = [
    ['XBT-USD' , 'BMEX'],           # abbreviations are consistent with coinigy
    ['BTC-USD' , 'BITF'],      
    ['BTC-OST', 'BINA'],  
    ['BTC-NANO', 'BINA'],  
    ['XRPH18', 'BMEX'], 
    ['ADAH18', 'BMEX'], 
    ['ETHH18', 'BMEX'], 
    ['BCHH18', 'BMEX'], 
    ['DASHH18', 'BMEX'], 
    ['ETC7D', 'BMEX'], 
    ['LTCH18', 'BMEX'], 
    ['XMRH18', 'BMEX'], 
    ['ZECH18', 'BMEX'],    
    ['XLMH18', 'BMEX']    
]

exch_supported = ['bmex', 'bina', 'btrx']

### Reference markets for BTC on bitmex (e.g. if we want to calculated the indicators based on values from a different exchange) 
btc_market_reference = False 
market_ref = 'BTC-USD'
exchange_abbr_ref = 'bitf'

### Contingency levels for time-based action 
var_contingency_btc = 0.00805   # Also tried: 0.86% lower/higher than the previous 4H candle for btc, as well as 0.75%. Found this one working better
var_contingency_alt = 0.01     # 1% lower/higher than the previous 4H candle for alts    
