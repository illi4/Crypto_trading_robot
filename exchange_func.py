################################ Libraries ############################################

from sqltools import query_lastrow_id, query  # proper requests to sqlite db, custom library

## Standard libraries 
import time
import json
from time import localtime, strftime
import math

import decimal
from decimal import Decimal, getcontext

# CCTX and other exchange client libraries
import ccxt   
from exchanges.bittrex.client import bittrex # bittrex module with api and success flag check by default

################################ Config ############################################

# Decimal precision
decimal.getcontext().prec = 20

# Initialising clients with api keys 

api_bittrex = bittrex('KEY', 'SECRET')

binance = ccxt.binance ({
    'apiKey': 'KEY',
    'secret': 'SECRET',
})

bitstamp = ccxt.bitstamp ({     # Not ready to use 
    'apiKey': 'KEY',
    'secret': 'SECRET',
    'uid': 'UID', 
})

bitmex = ccxt.bitmex ({
    'apiKey': 'KEY',
    'secret': 'SECRET',
})
 
# Configure wanted margin on bitmex
bitmex_margin = 4.5

################################ Functions ############################################

### CCTX functions common 
def market_std(market): 
    market_str = market.split('-')
    market = market_str[1] + '/' + market_str[0]
    return market 

#### Bitstamp functions - using cctx 
def bitstamp_ticker(market): 
    market = market_std(market)    
    ticker = bitstamp.fetch_ticker(market)['last']
    return Decimal(ticker) 
    
def bitstamp_balances(): 
    balances_return = []
    balances = bitstamp.fetch_balance()
    
    # Do not need these values 
    del balances['info']
    del balances['free']
    del balances['used']
    del balances['total']
    for key, value in balances.iteritems():
        balance_total = float(value['total'])
        arr_row = {'Currency':key, 'Balance':float(balance_total), 'Available':float(value['free'])}
        balances_return.append(arr_row)
    return balances_return

def bitstamp_get_balance(currency):
    output = {} # to make consistent with the overall script
    output['Available'] = 0 
    balances = binance.fetch_balance ()
    # Do not need these values 
    del balances['info']
    del balances['free']
    del balances['used']
    del balances['total']
    
    for key, value in balances.iteritems():
        if key == currency:
            output['Available'] = float(value['free'])       
    return output

def bitstamp_orderbook(market):
    market = market_std(market)    
    bids = bitstamp.fetch_order_book(market)['bids']
    output_buy_list = []
    output_sell_list = []
    for bid in bids:
        temp_dict = {}
        temp_dict["Rate"] = float(bid[0])  # For consistency with the main code        
        temp_dict["Quantity"] = float(bid[1])
        output_buy_list.append(temp_dict)
    return output_buy_list
    
def bitstamp_openorders(market): # returns my open orders.
    market = market_std(market)    
    
    retry = True 
    while retry:  #  added a condition to handle nonce issues     
        try: 
            trades = bitstamp.fetch_open_orders(symbol = market, since = None, limit = None, params = {})
            retry = False 
        except: 
            retry = True 
            
    #print trades
    result = []
    for trade in trades: 
        temp_dict = {}
        temp_dict["OrderUuid"]  = trade["id"]
        temp_dict["PricePerUnit"] = trade["price"]
        temp_dict['Quantity'] = Decimal(str(trade["amount"]))
        temp_dict["Price"] = Decimal(str(trade["amount"]))*Decimal(str(trade["price"]))
        temp_dict["QuantityRemaining"] = None 
        temp_dict["Limit"] = ''   #not really used but is showed for bittrex 
        result.append(temp_dict)
    return result    

    
def bitstamp_get_order(market, item):     # This bitstamp function is unfinished 
    # We will need ['Price'] , ['CommissionPaid'], ['Quantity'] , ['QuantityRemaining'] , ['PricePerUnit']
    # Bistamp orders can be Open, In Queue, Finished. Open do not have any data compared to the other types 
    
    output = {}
    market = market_std(market)    
    
    retry = True 
    while retry:  #  added a condition to handle nonce issues     
        try: 
            order = bitstamp.fetch_order(item, symbol = market, params = {})
            retry = False 
            print order 
        except: 
            retry = True  
            
    if order['transactions'] == []: # if the order was not even started to be filled - we will need to grab info from another method ( ? orderhistory) 
        print 'unfullfilled'
    else: 
        print 'finished' 
    
    ''' 
    if order['status'] == 'Open': 
        trades = bitstamp.fetch_open_orders(symbol = market, since = None, limit = None, params = {})
        for trade in trades: 
            if trade['id'] == item: 
                output['Price'] = Decimal(str(trade["amount"]))*Decimal(str(trade["price"]))
                output['Quantity'] = Decimal(str(trade["amount"]))
                output['QuantityRemaining'] = output['Quantity'] #open
                output['PricePerUnit'] =  Decimal(str(order['info']["price"]))
                output['CommissionPaid'] = Decimal(0) 
    
    output = {}
    output['Price'] = Decimal(str(order['info']["price"])) * Decimal(str(order['info']['origQty']))
    output['Quantity'] = Decimal(str(order['info']['origQty']))
    output['PricePerUnit'] =  Decimal(str(order['info']["price"]))
    output['QuantityRemaining'] = Decimal(str(order['info']['origQty'])) - Decimal(str(order['info']['executedQty']))
    if binance_order['fee'] is not None:    # it is always none, look at the original github code and contribute a fix 
        try:    
            output['CommissionPaid'] = Decimal(order['fee'])
        except: 
            output['CommissionPaid'] = Decimal(str(order['info']['price'])) * Decimal(str(0.0025)) 
    else:
        output['CommissionPaid'] = Decimal(str(order['info']['price'])) * Decimal(str(0.0025)) 
    ''' 
    return output   
    
def bitstamp_cancel(market, orderid): 
    market = market_std(market)    
    try:
        cancel_result = bitstamp.cancel_order(id = orderid, params = {}) 
    except: # error handling 
        cancel_result = 'unknown order' 
    return cancel_result    
    
    
#### Bitmex functions - using cctx  
def bitmex_ticker(market): 
    market = market_std(market)    
    ticker = bitmex.fetch_ticker(market)['close']
    return Decimal(ticker) 

def bitmex_get_balance(currency):
    output = {} # to make consistent with the overall script   
    balances = bitmex.fetch_balance()['free']['BTC']
    output['Available'] = float(balances)       
    return output
    
def bitmex_openorders(market): # returns my open orders, not initially available in ccxt 
    market = market_std(market)    
    orders = bitmex.fetchOrders(symbol = market, since = None, limit = 300, params = {'filter' : json.dumps({"open":True})} )
    result = []
    for bitmex_order in orders: 
        temp_dict = {}
        temp_dict["OrderUuid"]  = bitmex_order["orderID"]
        temp_dict["Quantity"] = bitmex_order["orderQty"]
        temp_dict["QuantityRemaining"] = Decimal(bitmex_order["leavesQty"])
        temp_dict["Price"] = bitmex_order["price"]
        temp_dict["Limit"] = '' #not really used but is showed for bittrex 
        if bitmex_order["side"] == 'Sell': 
             temp_dict["type"] = 'short' 
        else: 
             temp_dict["type"] = 'long'   
        result.append(temp_dict)
    return result
    
def bitmex_cancel(market, orderid): 
    market = market_std(market)    
    try:
        cancel_result = bitmex.cancel_order(id = orderid, symbol = market, params = {}) 
    except: # error handling 
        cancel_result = 'unknown order' 
    return cancel_result    
    
def bitmex_get_order(market, item): 
    market = market_std(market)    
    try: 
        bitmex_order = bitmex.fetchOrders(symbol = market, since = None, limit = 300, params = {'filter' : json.dumps({"orderID":item})})[0]
        output = {} 
        output["OrderUuid"]  = bitmex_order["orderID"]
        output["Quantity"] = bitmex_order["orderQty"]
        output["QuantityRemaining"] = Decimal(bitmex_order["leavesQty"])
        output["PricePerUnit"] = bitmex_order["price"]   # handle this later, not critical 
        output["Price"] = bitmex_order["price"]  # handle this later, not critical  
        output['CommissionPaid'] = 0
        output['Status'] = bitmex_order["ordStatus"]  # handy for the calculation of results 
        output['simpleCumQty'] = bitmex_order["simpleCumQty"] # handy for the calculation of results 
    except: 
        output = None 
    return output

def bitmex_orderbook(market):    
    market = market_std(market)    
    bids = bitmex.fetch_order_book(market)['bids']
    output_buy_list = []
    for bid in bids:
        temp_dict = {}
        temp_dict["Rate"] = float(bid[0])  # For consistency with the main code        
        temp_dict["Quantity"] = float(bid[1])
        output_buy_list.append(temp_dict)
    return output_buy_list

def bitmex_buylimit(market, quantity_buy, buy_rate, contracts = None):    # Open a long 
    market = market_std(market)    
    msg = ''  
    # Calculate contracts; maximum recommended x3-5 margin 
    if contracts is None: 
        contracts = round(quantity_buy * buy_rate)     #* bitmex_margin)     # accounting for margin in the main code anyways 
    try: 
        result = bitmex.createOrder(market, 'limit', 'Buy', contracts, float(buy_rate), params = {})
        result['uuid'] = result['id']  # for consistency in the main code 
    except: 
        msg = 'MIN_TRADE_REQUIREMENT_NOT_MET'
    if msg <> '': 
        return msg 
    else: 
       return result       
       
def bitmex_selllimit(market, quantity_sell, sell_rate, contracts = None):    # Open a short
    market = market_std(market)    
    msg = ''  
    # Calculate contracts; maximum recommended x3-5 margin 
    if contracts is None: 
        contracts = round(quantity_sell * sell_rate) #* bitmex_margin)     # accounting for margin in the main code anyways 
    try: 
        result = bitmex.createOrder (market, 'limit', 'Sell', contracts, float(sell_rate), params = {})
        result['uuid'] = result['id']  # for consistency in the main code 
    except: 
        msg = 'MIN_TRADE_REQUIREMENT_NOT_MET'
    if msg <> '': 
        return msg 
    else: 
       return result     

# A few additional functions relevant to bitmex only (positions and not orders)        
def bitmex_openpositions(market):  
    market = market_std(market)    
    positions = bitmex.fetchPositions(symbol = market, since = None, limit = 300, params = {})   
    result = []
    for position in positions: 
        # print position 
        temp_dict = {}
        if position["isOpen"] is True: 
            if position["simpleCost"] > 0: 
                temp_dict["type"]  = 'long'
            else: 
                temp_dict["type"]  = 'short'
            temp_dict['xbt'] = abs(position['homeNotional']) # using abs here because we will be working on both longs and shorts 
            temp_dict['contracts'] = abs(position['simpleCost'])
            temp_dict['entryprice'] = position['avgEntryPrice']
        result.append(temp_dict)
    return result    
    
def bitmex_closepositions(positions, market, price): 
    contracts_total = 0 
    # Total contracts to close the position  
    for position in positions: 
        if position['type'] == 'short': 
            contracts_total -= position['contracts'] 
        else: 
            contracts_total += position['contracts'] 
    if contracts_total < 0: 
        # If the original was short 
        result = bitmex_buylimit(market, None, price, contracts_total)
    else: 
        result = bitmex_selllimit(market, None, price, contracts_total)
    return result    

def bitmex_get_sell_ordhist(market):  # only need sell (short) orders (IDs) 
    market = market_std(market)    
    listoforders = [] 
    bitmex_orders = bitmex.fetchOrders(symbol = market, since = None, limit = 300, params = {})
    for order in bitmex_orders:  
        temp_dict = {}
        temp_dict['OrderUuid'] = order["orderID"]
        listoforders.append(temp_dict)
    return listoforders
     
    
#### Binance functions - using cctx 
def binance_ticker(market): 
    market = market_std(market)    
    ticker = binance.fetch_ticker(market)['info']['lastPrice']
    return Decimal(ticker) 

def binance_price_precise(market, price): 
    market = market_std(market)    
    binance.load_markets()
    market_info = binance.markets[market] 
    
    # Getting precision
    tickSize = market_info['info']['filters'][0]['tickSize']
    
    # Converting the price 
    getcontext().rounding = 'ROUND_DOWN'
    tickSize = tickSize.rstrip('0')
    price = Decimal(str(price))
    price = price.quantize(Decimal(tickSize))
    return price
     
def binance_quantity_precise(market, quantity): 
    market = market_std(market)    
    binance.load_markets()
    market_info = binance.markets[market] 
    
    # Getting precision
    stepsize = market_info['info']['filters'][1]['stepSize']
    
    # Converting the quantity. Stepsize is something like '0.0010000'
    getcontext().rounding = 'ROUND_DOWN'
    stepsize = Decimal(stepsize) # * 10 
    stepsize = Decimal(str(stepsize))  
    quantity_orig = Decimal(str(quantity))    
    quantity = Decimal(str(quantity))
    n_num = (quantity/stepsize).quantize(Decimal('1'))
    quantity = stepsize * int(n_num) - stepsize  # weirdly enough, this solves the issue
    # print 'Stepsize', stepsize, ' qty ', quantity, ' n_num ', n_num   # DEBUG
    return quantity, stepsize 

def binance_balances(): 
    balances_return = []
    balances = binance.fetch_balance ()
    
    # Do not need these values 
    del balances['info']
    del balances['free']
    del balances['used']
    del balances['total']
    
    for key, value in balances.iteritems():
        balance_total = float(value['total'])
        arr_row = {'Currency':key, 'Balance':float(balance_total), 'Available':float(value['free'])}
        balances_return.append(arr_row)
    return balances_return

def binance_get_balance(currency):
    output = {} # to make consistent with the overall script
    output['Available'] = 0 
   
    balances = binance.fetch_balance ()
    
    # Do not need these values 
    del balances['info']
    del balances['free']
    del balances['used']
    del balances['total']
    
    for key, value in balances.iteritems():
        if key == currency:
            output['Available'] = float(value['free'])       
    return output

def binance_get_sell_ordhist(market):     # only need sell orders (IDs) 
    market = market_std(market)    
    trades = binance.fetchMyTrades(symbol = market, since = None, limit = None, params = {})
    listoftrades = []
    for trade in trades: 
        temp_dict = {}
        if trade['side'] == 'sell': 
            temp_dict['OrderUuid'] = trade['info']['orderId']
            listoftrades.append(temp_dict)
    return listoftrades    
    
def binance_openorders(market): # returns my open orders 
    market = market_std(market)    
    orders = binance.fetchOpenOrders(symbol = market, since = None, limit = None, params = {})
    result = []
    for binance_order in orders: 
        temp_dict = {}
        temp_dict["OrderUuid"]  = binance_order['info']["orderId"]
        temp_dict["Quantity"] = binance_order['info']["origQty"]
        temp_dict["QuantityRemaining"] = Decimal(binance_order['info']["origQty"]) - Decimal(binance_order['info']["executedQty"])
        temp_dict["Price"] = binance_order['info']["price"]
        temp_dict["Limit"] = '' #not really used but is showed for bittrex 
        result.append(temp_dict)
    return result
    
def binance_get_order(market, item):     
    # We will need ['Price'] , ['CommissionPaid'], ['Quantity'] , ['QuantityRemaining'] , ['PricePerUnit']
    
    market = market_std(market)    
    binance_order = binance.fetch_order(item, symbol = market, params = {})
    
    output = {}
    output['Price'] = Decimal(str(binance_order['info']["price"])) * Decimal(str(binance_order['info']['origQty']))
    output['Quantity'] = Decimal(str(binance_order['info']['origQty']))
    output['PricePerUnit'] =  Decimal(str(binance_order['info']["price"]))
    output['QuantityRemaining'] = Decimal(str(binance_order['info']['origQty'])) - Decimal(str(binance_order['info']['executedQty']))
    if binance_order['fee'] is not None:    # it is always none, look at the original github code and contribute a fix 
        try:    
            output['CommissionPaid'] = Decimal(binance_order['fee'])
        except: 
            output['CommissionPaid'] = Decimal(str(binance_order['info']['price'])) * Decimal(str(0.001)) 
    else:
        output['CommissionPaid'] = Decimal(str(binance_order['info']['price'])) * Decimal(str(0.001)) 
 
    return output
    
def binance_cancel(market, orderid): 
    market = market_std(market)    
    try:
        cancel_result = binance.cancel_order(id = orderid, symbol = market, params = {}) 
    except: # error handling 
        cancel_result = 'unknown order' 
    return cancel_result 
   
def binance_orderbook(market):
    market = market_std(market)    
    bids = binance.fetch_order_book(market)['bids']
    output_buy_list = []
    output_sell_list = []
    for bid in bids:
        temp_dict = {}
        temp_dict["Rate"] = float(bid[0])  # For consistency with the main code        
        temp_dict["Quantity"] = float(bid[1])
        output_buy_list.append(temp_dict)
    return output_buy_list

def binance_buylimit(market, quantity_buy, buy_rate):    
    # Defining precision 
    buy_rate = binance_price_precise(market, buy_rate)
    quantity_buy, mult = binance_quantity_precise(market, quantity_buy)
    msg = '' 

    # Placing an order 
    market = market_std(market)    
    
    try: 
        quantity_request = quantity_buy
        result = binance.createLimitBuyOrder (market, float(quantity_request), float(buy_rate))
        return_result = result['info']
        return_result['uuid'] = return_result['orderId']  # for consistency in the main code 
    except: 
        msg = 'MIN_TRADE_REQUIREMENT_NOT_MET'

    if msg <> '': 
        return msg 
    else: 
       return return_result    

def binance_selllimit(market, sell_q_step, price_to_sell):   
    # Defining precision 
    price_to_sell = binance_price_precise(market, price_to_sell)
    sell_q_step, mult = binance_quantity_precise(market, sell_q_step)
    msg = '' 
    
    # Placing an order 
    # cctx seems to have fixed a weird issue the solution for which is commented here 
    market = market_std(market)    
    
    try: 
        result = binance.createLimitSellOrder (market, float(sell_q_step), float(price_to_sell))
        return_result = result['info']
        return_result['uuid'] = return_result['orderId']  # for consistency in the main code 
    except: 
        msg = 'MIN_TRADE_REQUIREMENT_NOT_MET'   

    if msg <> '': 
        return msg 
    else: 
       return return_result

### Bittrex some modifications 
def bittrex_get_sell_ordhist(market):   
    orders_return = []
    orders_all = api_bittrex.getorderhistory(market, 100)
    for order in orders_all: 
        if order['OrderType'] == 'LIMIT_SELL': 
            orders_return.append(order)
    return orders_return 
       
       
############################################################################ 
############# Common functions for all exchanges ##################################    
############# For robot to work, all the data should be in the same format ################
############################################################################
        
def getticker(exchange, market): 
    if exchange == 'bittrex': 
        return api_bittrex.getticker(market)['Last']
    elif exchange == 'binance': 
        return binance_ticker(market)
    elif exchange == 'bitmex': 
        return bitmex_ticker(market)
    elif exchange == 'bitstamp': 
        return bitstamp_ticker(market) 
    else: 
        return 0  
         
def getopenorders(exchange, market):
    if exchange == 'bittrex':
        return api_bittrex.getopenorders(market)
    elif exchange == 'binance':
        return binance_openorders(market)
    elif exchange == 'bitmex':
        return bitmex_openorders(market) 
    elif exchange == 'bitstamp':
        return bitstamp_openorders(market)
    else:
        return 0

def cancel(exchange, market, orderid):
    if exchange == 'bittrex':
        return api_bittrex.cancel(orderid)
    elif exchange == 'binance':
        return binance_cancel(market, orderid) 
    elif exchange == 'bitmex':
        return bitmex_cancel(market, orderid) 
    elif exchange == 'bitstamp':
        return bitstamp_cancel(market, orderid) 
    else:
        return 0

def getorderhistory(exchange, market):  # getting orders history; this is only used to get sell orders (in robot.py) 
    if exchange == 'bittrex':
        return bittrex_get_sell_ordhist(market)
    elif exchange == 'binance':
        return binance_get_sell_ordhist(market) 
    elif exchange == 'bitmex':
        return bitmex_get_sell_ordhist(market) 
    else:
        return 0

def getorder(exchange, market, item):
    if exchange == 'bittrex':
        return api_bittrex.getorder(item)
    elif exchange == 'binance':
        return binance_get_order(market, item)
    elif exchange == 'bitmex':
        return bitmex_get_order(market, item) 
    elif exchange == 'bitstamp':
        return bitstamp_get_order(market, item) 
    else:
        return 0

def getbalance(exchange, currency):
    retry = True
    failed_attempts = 0
    if exchange == 'bittrex':
        # if service is unavailable
        while retry:
            try:
                curr_balance = api_bittrex.getbalance(currency)
                retry = False
            except:
                failed_attempts += 1
        return curr_balance
    elif exchange == 'binance':
        while retry:
            try:
                curr_balance = binance_get_balance(currency)
                retry = False
            except:
                failed_attempts += 1
        return curr_balance
    elif exchange == 'bitmex':
        while retry:
            try:
                curr_balance = bitmex_get_balance(currency)
                retry = False
            except:
                failed_attempts += 1
        return curr_balance
    elif exchange == 'bitstamp':
        while retry:
            try:
                curr_balance = bitstamp_get_balance(currency)
                retry = False
            except:
                failed_attempts += 1
        return curr_balance
    else:
        return 0

def getbalances(exchange): 
    if exchange == 'bittrex':     
        return api_bittrex.getbalances() 
    elif exchange == 'binance': 
        return binance_balances()
    elif exchange == 'bitstamp': 
        return bitstamp_balances()
    else: 
        return 0 

def selllimit(exchange, market, sell_q_step, price_to_sell, contracts = None):
    if exchange == 'bittrex':
        return api_bittrex.selllimit(market, sell_q_step, price_to_sell)
    elif exchange == 'binance':
        return binance_selllimit(market, sell_q_step, price_to_sell) 
    elif exchange == 'bitmex':
        return bitmex_selllimit(market, sell_q_step, price_to_sell, contracts) 
    else:
        return 0

def buylimit(exchange, market, quantity, buy_rate, contracts = None):
    if exchange == 'bittrex':
        return api_bittrex.buylimit(market, quantity, buy_rate)
    elif exchange == 'binance':
        return binance_buylimit(market, quantity, buy_rate) 
    elif exchange == 'bitmex':
        return bitmex_buylimit(market, quantity, buy_rate, contracts) 
    else:
        return 0

def getorderbook(exchange, market):
    if exchange == 'bittrex':
        return api_bittrex.getorderbook(market, 'buy')
    elif exchange == 'binance':
        return binance_orderbook(market)
    elif exchange == 'bitmex':
        return bitmex_orderbook(market)
    elif exchange == 'bitstamp':
        return bitstamp_orderbook(market)
    else:
        return 0  

# Bitmex only 
def getpositions(exchange, market):
    if exchange == 'bitmex':
        return bitmex_openpositions(market) 
    else:
        return 0
 
def closepositions(exchange, positions, market, price):
    if exchange == 'bitmex':
        return bitmex_closepositions(positions, market, price) 
    else:
        return 0