## Standard libraries 
import json
import urllib2
import time

# Import exchanges libraries in case coinigy api fails to get a price 
from exchange_func import getticker

# Config 
import config 

# Coinigy functions 
class coinigy(object):
    def __init__(self):
        self.public = ['price', 'balances', 'market_name']
        self.key = config.coinigy_key
        self.secret = config.coinigy_secret
        self.content = "application/json"     
        
    def price(self, exchange, ticker): 
        count = 0 
        json_resp = None 
        exchange = exchange.upper()
        
        # For bitmex, USD-BTC ticker is available through XBTUSD product 
        if (ticker == 'BTC-USD' or ticker == 'USD-BTC') and exchange == 'BMEX':
            ticker = 'XBTUSD'  
        
        # Checking the price 
        while count < 3: 
            try:
                values =  {
                    "exchange_code": exchange, 
                    "exchange_market": ticker
                  }
                req = urllib2.Request('https://api.coinigy.com/api/v1/ticker')
                req.add_header('x-api-key', self.key)
                req.add_header('x-api-secret', self.secret)
                req.add_header('content-type', self.content)

                response = urllib2.urlopen(req, json.dumps(values)).read()
                json_resp = json.loads(response)
                #print json_resp
                count = 3
            except:
                count+= 1
                #print json_resp
                #print count 
                time.sleep(0.5)
                
        if json_resp is not None: 
            try: 
                return float(json_resp['data'][0]['last_trade'])
            except: 
                json_resp = None 
        
        if json_resp is None: 
            # Trying directly via an exchange if coinigy is not responding 
            if exchange == 'BTRX': 
                exchange = 'bittrex'
            elif exchange == 'BINA':      
                exchange = 'binance'
            elif exchange == 'BMEX':   
                exchange = 'bitmex'
            # conversions 
            ticker = ticker.replace('/', '-')
            if ticker == 'XBT-USD': 
                ticker = 'USD-BTC'
            print '>> Trying exchange directly for', ticker, exchange
            count = 0
            price_ticker = None 
            while count < 3: 
                try:
                    price_ticker = getticker(exchange, ticker) 
                    count = 3
                except:
                    count += 1
                    time.sleep(0.5)
            return float(price_ticker)
            
    def balances(self, filter_name = None): 
        exchanges = {}
        return_result = []
        str_balance = ''     
        balance_total_btc_val = 0 
        usdte = 0 

        # Getting account names 
        req = urllib2.Request('https://api.coinigy.com/api/v1/accounts')
        req.add_header('x-api-key', self.key)
        req.add_header('x-api-secret', self.secret)
        req.add_header('content-type', self.content)
        response = urllib2.urlopen(req, json.dumps('')).read()
        json_resp = json.loads(response)
        for elem in json_resp['data']: 
            if (filter_name is not None): 
                if (elem['exch_name'] == filter_name): 
                    exchanges[elem['auth_id']] = elem['exch_name']
            else: 
                exchanges[elem['auth_id']] = elem['exch_name']
            
        for key, exch_name in exchanges.iteritems(): 
            str_balance += exch_name + '\n'  
            # Refreshing balance 
            req = urllib2.Request('https://api.coinigy.com/api/v1/refreshBalance')
            req.add_header('x-api-key', self.key)
            req.add_header('x-api-secret', self.secret)
            req.add_header('content-type', self.content)
            values =  {
                "auth_id": key
              }
            refresh = urllib2.urlopen(req, json.dumps(values)).read()
            refresh_resp = json.loads(refresh)
            
            # Getting balances     
            req = urllib2.Request('https://api.coinigy.com/api/v1/balances')
            req.add_header('x-api-key', self.key)
            req.add_header('x-api-secret', self.secret)
            req.add_header('content-type', self.content)
            
            values =  {
                "show_nils": 0,
                "auth_ids": key
              }

            response_exchanges = urllib2.urlopen(req, json.dumps(values)).read()
            json_resp = json.loads(response_exchanges)
            
            for elem in json_resp['data']: 
                # print elem # DEBUG 
                currency = elem['balance_curr_code']
                balance_total = float(elem['balance_amount_total'])
                balance = float(elem['balance_amount_avail'])
                pending = balance_total - balance
                btc_balance = float(elem['btc_balance'])
                
                # print key, exch_name, currency, balance_total, btc_balance   # DEBUG 
                
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
        
        try:
            request_exchange_rate = 'http://api.fixer.io/latest?base=USD&symbols=' + config.local_curr
            response = urllib2.urlopen(request_exchange_rate) 
            usd_local = json.load(response)['rates'][config.local_curr]   
        except: 
            usd_local = config.local_curr_fixed  
        
        if usdte == 0: 
            usdte = self.price('BTRX', 'USDT/BTC')
            
        balance_usdt_val = balance_total_btc_val * float(usdte)
        balance_aud_val = round(usd_local*balance_usdt_val, 1) 
        str_balance += 'Value in BTC: {}\nValue in {}: ~{}'.format(round(balance_total_btc_val, 3), config.local_curr, balance_aud_val)            
        return str_balance         
            

     