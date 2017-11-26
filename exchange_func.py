from exchanges.bittrex.client import bittrex # bittrex module with api and success flag check by default
from exchanges.binance.client import Client #binance module - unfinished 
from exchanges.bitfinex.client import Client_bitfinex, TradeClient # bitfinex external wrapper - https://github.com/scottjbarr/bitfinex, slightly modified to fix several issues - unfinished 
from sqltools import query_lastrow_id, query # proper requests to sqlite db

## Initialising clients with api keys - put your API keys in there 
api = bittrex('KEY1', 'KEY2')
api_binance = Client('KEY1', 'KEY2')  # balances only at this point
api_bitfinex = Client_bitfinex()    # does not require a key because there is a differentiation between public and private functions there
api_bitfinex_trade = TradeClient('KEY1', 'KEY2')

## Binance functions
def binance_ticker(market): 
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    tickers = api_binance.get_all_tickers()
    new_dict = {}
    for item in tickers:
       symbol = item['symbol']
       new_dict[symbol] = item['price']
    return float(new_dict[market])
    
def binance_balances(): 
    balances_return = []
    acc = api_binance.get_account()['balances']    
    for elem in acc: 
        balance_total = float(elem['locked']) + float(elem['free'])
        arr_row = {'Currency':elem['asset'], 'Balance':float(balance_total), 'Available':float(elem['free'])}
        balances_return.append(arr_row)
    return balances_return

## Bitfinex functions 
def bitfinex_ticker(market):
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    ticker = api_bitfinex.ticker(market)
    return ticker['last_price']

def bitfinex_balances():
    balances_return = []
    acc = api_bitfinex_trade.balances()
    for elem in acc: 
        arr_row = {'Currency':elem['currency'], 'Balance':elem['amount'], 'Available':elem['available']}
        balances_return.append(arr_row)
    return balances_return
    
def bitfinex_balance_curr(currency):
    acc = api_bitfinex_trade.balances()
    for elem in acc: 
        if elem['currency'].upper() == currency.upper(): 
            arr_row = {'Currency':elem['currency'], 'Balance':elem['amount'], 'Available':elem['available']}
    return arr_row 

def bitfinex_orderbook(market):
    orders_return = []
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    orderbook = api_bitfinex.order_book(market)['bids']
    for elem in orderbook: 
        arr_row = {'Rate':elem['price']}
        orders_return.append(arr_row)
    return orders_return
    
def bitfinex_getorderhistory(market): 
    arr_return = []
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    orderhist = api_bitfinex_trade.past_trades(market)
    # example of order id: 4903189438L
    for elem in orderhist: 
        arr_row = {'QuantityRemaining':0, 'Quantity':elem['amount'], 'CommissionPaid':(-float(elem['fee_amount'])), 'Price':elem['price'], 'OrderUuid':elem['order_id']}
        arr_return.append(arr_row)
    return arr_return
    
def bitfinex_getorder(item): 
    order = api_bitfinex_trade.status_order(int(item))
    return order
    
####################### Common functions #########################################  
def detect_exchange(market): 
    sql_string = "SELECT exchange FROM exchange WHERE market = '{}'".format(market)
    rows = query(sql_string)
    try: 
        exchange = rows[0][0] # first result 
    except: 
        exchange = 'bittrex'
    return exchange 
        
def getticker(exchange, market): 
    if exchange == 'bittrex': 
        return api.getticker(market)['Last']
    elif exchange == 'binance': 
        return binance_ticker(market)
    elif exchange == 'bitfinex': 
        return bitfinex_ticker(market)
    else: 
        return 0 

def getopenorders(exchange, market): 
    if exchange == 'bittrex': 
        return api.getopenorders(market)
    else: 
        return 0 
        
def cancel(exchange, orderid): 
    if exchange == 'bittrex': 
        return api.cancel(orderid)
    else: 
        return 0 
        
def getorderhistory(exchange, market): 
    if exchange == 'bittrex': 
        return api.getorderhistory(market, 100) 
    elif exchange == 'bitfinex': 
        return bitfinex_getorderhistory(market)
    else: 
        return 0 
        
def getorder(exchange, item): 
    if exchange == 'bittrex': 
        return api.getorder(item)
    elif exchange == 'bitfinex': 
        return bitfinex_getorder(item)
    else: 
        return 0     
        
def getbalance(exchange, currency): 
    retry = True 
    failed_attempts = 0
    if exchange == 'bittrex': 
        # if service is unavailable
        while retry: 
            try:
                curr_balance = api.getbalance(currency)
                retry = False
            except:
                failed_attempts += 1
        return curr_balance 
    elif exchange == 'bitfinex': 
        # if service is unavailable
        while retry: 
            try:
                curr_balance = bitfinex_balance_curr(currency)
                retry = False
            except:
                failed_attempts += 1
        return curr_balance 
    else: 
        return 0         

def getbalances(exchange): 
    if exchange == 'bittrex':     
        return api.getbalances() 
    elif exchange == 'binance': 
        return binance_balances()
    elif exchange == 'bitfinex': 
        return bitfinex_balances()
    else: 
        return 0      
        
def selllimit(exchange, market, sell_q_step, price_to_sell):  
    if exchange == 'bittrex': 
        return api.selllimit(market, sell_q_step, price_to_sell) 
    else: 
        return 0         

def buylimit(exchange, market, quantity, buy_rate): 
    if exchange == 'bittrex': 
        return api.buylimit(market, quantity, buy_rate)  
    else: 
        return 0         
        
def getorderbook(exchange, market): 
    if exchange == 'bittrex': 
        return api.getorderbook(market, 'buy')
    elif exchange == 'bitfinex': 
        return bitfinex_orderbook(market)
    else: 
        return 0         
        