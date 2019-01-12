## Standard libraries 
import json
import urllib.request, urllib.error, urllib.parse
from time import sleep, time

# Import exchanges library ticker in case coinigy api fails to get a price 
#from exchange_func import getticker, market_std
import exch_api

# Config 
import config

import libs.sqltools as sqltools
sql = sqltools.sql()

from libs.aux_functions import send_chat_message

 
### Interval and number of checks to get current (last) prices 
steps_ticker = config.steps_ticker 
sleep_ticker = config.sleep_ticker       

## Steps and timer for buybacks 
candle_steps = config.candle_steps         
candle_sleep = config.candle_sleep       
speedrun = config.speedrun

sleep_ticker = int(sleep_ticker/speedrun)
candle_steps = int(candle_steps/speedrun)

# Coinigy functions 
class coinigy(object):
    def __init__(self, user, e_api = None):
        self.public = ['price', 'price_history', 'balances', 'market_name']
        self.key = config.coinigy_key
        self.secret = config.coinigy_secret
        self.user = user
        self.content = "application/json"
        if e_api is not None:
            self.e_api = e_api
        else:
            self.e_api = exch_api.api(user)

    ### Handle naming
    def naming_handle(self, ticker, exchange, direct = False):
        # Deprecated
        '''
        # For bitmex, USD-BTC ticker is available through the XBT/USD product
        if (ticker == 'BTC-USD' or ticker == 'USD-BTC' or ticker == 'XBT-USD') and exchange == 'BMEX':
            ticker = 'XBT/USD'
        # ETH naming
        if (ticker == 'ETH-USD' or ticker == 'USD-ETH') and exchange == 'BMEX':
            ticker = 'ETH/USD'
        # Coinigy also changed other derivatives notation. Remember to check each quarter
        for elem in ['U18', 'Z18']:
            ticker = ticker.replace(elem, '/'.join(['', elem]))

        # For direct requests
        if direct and exchange == 'BMEX':
            ticker = ticker.replace('/', '-')
            if ticker == 'XBT-USD':
                ticker = 'USD-BTC'
        '''

        return ticker, exchange


    ### Mapping of names when reading from DB
    '''
    def market_name_mapping(self, ticker):
        if ticker == 'XBT-USD':
            ticker = 'XBTUSD'
    '''

    ### Price data from DB
    def price_db_read(self, ticker):
        db_ticker = None
        sql_string = "SELECT last_update, price FROM market_info WHERE market = '{}'".format(ticker.upper())
        #print(">>>", sql_string)

        rows = sql.query(sql_string)
        if rows != []:
            last_updated = rows[0][0]
            db_ticker = float(rows[0][1])
            diff = (time()-last_updated)/60

            # Check time
            if last_updated is not None:
                if diff > 1:
                    db_ticker = None
                    print('---- last price update more than a minute ago, returning None')
                else:
                    print('---- returning DB ticker for {}: {}'.format(ticker, db_ticker))

        return db_ticker


    ### Price data
    def price(self, exchange, ticker, logger = None, b_test = None, strategy = None):
        # If backtesting
        if config.backtesting_enabled:
            return b_test.get_market_price(exchange, ticker, logger)

        # Try to read from central updater if the market is open
        db_ticker = self.price_db_read(ticker)

        # If db ticker is None, retry for a while
        if db_ticker is None:
            print('--- DB ticker timestamp is outdated. Returning None.')
            return None
        else:
            return float(db_ticker)


    # Return the price history from coinigy (a better way to calculate ohlc) # Deprecated
    '''
    def price_history(self, exchange, ticker): 
        count = 0 
        json_resp = None 
        exchange = exchange.upper()
        
        # For bitmex, USD-BTC ticker is available through the XBTUSD product 
        if (ticker == 'BTC-USD' or ticker == 'USD-BTC' or ticker == 'XBT-USD') and exchange == 'BMEX':
            ticker = 'XBTUSD'  
        
        # Changing the ticker for coinigy if we are working with exchanges other than bitmex 
        if exchange != 'BMEX':
            ticker = self.e_api.market_std(ticker)
        
        # Checking the price 
        while count < 3:    # several attempts to handle availability / overload issues 
            try:
                values =  {
                    "exchange_code": exchange, 
                    "exchange_market": ticker, 
                    "type": "history"
                  }
                
                req = urllib.request.Request('https://api.coinigy.com/api/v1/data')
                req.add_header('x-api-key', self.key)
                req.add_header('x-api-secret', self.secret)
                req.add_header('content-type', self.content)

                response = urllib.request.urlopen(req, json.dumps(values).encode('utf-8')).read()
                
                json_resp = json.loads(response.decode('utf-8'))
                count = 3
            except:
                count += 1
                sleep(0.5)

        if json_resp is not None: 
            try: 
                return json_resp['data']['history']
            except: 
                return None 
    '''
        

    # Deprecated
    '''
    def balances(self, filter_name = None): 
        exchanges = {}
        return_result = []
        str_balance = ''     
        balance_total_btc_val = 0 
        usdte = 0 

        # Getting account names 
        req = urllib.request.Request('https://api.coinigy.com/api/v1/accounts')
        req.add_header('x-api-key', self.key)
        req.add_header('x-api-secret', self.secret)
        req.add_header('content-type', self.content)
        response = urllib.request.urlopen(req, json.dumps('')).read()
        json_resp = json.loads(response)
        for elem in json_resp['data']: 
            if (filter_name is not None): 
                if (elem['exch_name'] == filter_name): 
                    exchanges[elem['auth_id']] = elem['exch_name']
            else: 
                exchanges[elem['auth_id']] = elem['exch_name']
            
        for key, exch_name in exchanges.items(): 
            str_balance += exch_name + '\n'  
            req = urllib.request.Request('https://api.coinigy.com/api/v1/refreshBalance')      # balance refresh is needed for coinigy 
            req.add_header('x-api-key', self.key)
            req.add_header('x-api-secret', self.secret)
            req.add_header('content-type', self.content)
            values =  {
                "auth_id": key
              }
            refresh = urllib.request.urlopen(req, json.dumps(values)).read()
            refresh_resp = json.loads(refresh)
            
            # Getting balances     
            req = urllib.request.Request('https://api.coinigy.com/api/v1/balances')
            req.add_header('x-api-key', self.key)
            req.add_header('x-api-secret', self.secret)
            req.add_header('content-type', self.content)
            
            values =  {
                "show_nils": 0,
                "auth_ids": key
              }

            response_exchanges = urllib.request.urlopen(req, json.dumps(values)).read()
            json_resp = json.loads(response_exchanges)
            
            ### Formatting the response 
            for elem in json_resp['data']: 
                currency = elem['balance_curr_code']
                balance_total = float(elem['balance_amount_total'])
                balance = float(elem['balance_amount_avail'])
                pending = balance_total - balance
                btc_balance = float(elem['btc_balance'])
                
                if pending == 0: 
                    pending_str = '\n'
                else:
                    pending_str = '[P: {}]\n'.format(round(pending, 3))        
                    
                if (round(balance_total, 3) > 0): 
                    if currency == 'USDT': 
                        usdte = balance / btc_balance
                        market_symbol = currency + '-BTC' 
                        balance_total_btc_val += btc_balance
                        str_balance += '{}: {} (~{} BTC) {}'.format(currency, round(balance, 3), round(btc_balance, 3), pending_str)  
                    elif (currency == 'BTC') or (currency == 'XBT'): 
                        balance_total_btc_val += balance_total
                        str_balance += '{}: {} {}'.format(currency, round(balance, 3), pending_str)   
                    else: 
                        market_symbol = 'BTC-' + currency 
                        balance_total_btc_val += btc_balance
                        str_balance += '{}: {} (~{} BTC) {}'.format(currency, round(balance, 3), round(btc_balance, 3), pending_str)
            str_balance += '\n'  
        
        # Local currency conversion 
        try:
            request_exchange_rate = 'http://api.fixer.io/latest?base=USD&symbols=' + config.local_curr
            response = urllib.request.urlopen(request_exchange_rate) 
            usd_local = json.load(response)['rates'][config.local_curr]   
        except: 
            usd_local = config.local_curr_fixed  
        
        if usdte == 0: 
            usdte = self.price('BTRX', 'USDT/BTC')
            
        balance_usdt_val = balance_total_btc_val * float(usdte)
        balance_aud_val = round(usd_local*balance_usdt_val, 1) 
        str_balance += 'Value in BTC: {}\nValue in {}: ~{}'.format(round(balance_total_btc_val, 3), config.local_curr, balance_aud_val)            
        return str_balance         
            
    ##################### Candle analysis; returns high, low, and whether the price crossed a value - among N-min intervals (candles) 
    '''

    def candle_analysis(self, exchange, exchange_abbr, market, logger, cross_target):
        
        ticker_upd = {}
        price_upd = 0
        price_h = 0
        price_l = 0 
        crossed_flag = False
        failed_attempts = 0
        
        for i in range(1, candle_steps + 1): # 5 min: 100 checks x 3 sec (better indication than 30 checks x 10 sec)
            try:
                ticker_upd = coinigy.price(exchange_abbr, market) 
                price_upd = ticker_upd
                if (price_l == 0) or (price_upd < price_l): 
                    price_l = price_upd
                if (price_h == 0) or (price_upd > price_h): 
                    price_h = price_upd
                if price_upd >= cross_target: 
                    crossed_flag = True 
            except:
                failed_attempts += 1
            sleep(candle_sleep) 
            
        # Logging failed attempts number
        if failed_attempts > 0: 
            logger.lprint(["Failed attempts to receive price:", failed_attempts])    
        
        # If retreiving prices fails completely
        if failed_attempts == steps_ticker:     
            ticker_upd = None  
            # Could be related to maintenance
            try:
                send_chat_message(self.user, market + ' seems to be on an automatic maintenance. Will try every 5 minutes.')
            except: 
                logger.lprint(["Failed to send notification"])    
            while ticker_upd is None: 
                sleep(300)  
                logger.lprint(["Market could be on maintenance. Sleeping for 5 minutes."])    
                try:
                    ticker_upd = self.price(exchange_abbr, market) 
                except: 
                    ticker_upd = None
                price_upd = ticker_upd
                
                # If unsuccessful
                price_l = 0
                price_h = 0
        return price_l, price_h, crossed_flag
        
    ##################### Extreme in time series; returns value with the lowest or the highest ticker price among N-min intervals (candles) 
    # type should be 'H' or 'L' (highest ore lowest in the series) 
    def candle_extreme(self, exchange, exchange_abbr, market, logger, type): 

        ticker_upd = {}
        price_upd = 0
        price_extreme = 0
        failed_attempts = 0
        
        for i in range(1, candle_steps + 1): # 5 min: 100 checks x 3 sec (better indication than 30 checks x 10 sec); 80 x 3 for 4 minutes
            try:
                ticker_upd = self.price(exchange_abbr, market)
                price_upd = ticker_upd
                if type == 'L': 
                    if (price_extreme == 0) or (price_upd < price_extreme): 
                        price_extreme = price_upd
                if type == 'H': 
                    if (price_extreme == 0) or (price_upd > price_extreme): 
                        price_extreme = price_upd
            except:
                failed_attempts += 1
            sleep(candle_sleep) 
            
        # Logging failed attempts number
        if failed_attempts > 0: 
            logger.lprint(["Failed attempts to receive price:", failed_attempts])    
            
        # If retreiving prices fails completely
        if failed_attempts == steps_ticker:     
            ticker_upd = None 
            # Could be related to maintenance
            try:
                send_chat_message(self.user, market + ' seems to be on an automatic maintenance. Will try every 5 minutes.')
            except: 
                logger.lprint(["Failed to send notification"])    
            while ticker_upd is None: 
                sleep(300)  
                logger.lprint(["Market could be on maintenance. Sleeping for 5 minutes."])    
                try:
                    ticker_upd = self.price(exchange_abbr, market)
                except: 
                    ticker_upd = None
                price_upd = ticker_upd
                price_extreme = price_upd
        return price_extreme
