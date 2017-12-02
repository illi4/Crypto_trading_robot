from exchanges.bittrex.client import bittrex # bittrex module with api and success flag check by default
from exchanges.binance.client import Client #binance module  
from exchanges.bitfinex.client import Client_bitfinex, TradeClient # bitfinex external wrapper - https://github.com/scottjbarr/bitfinex, slightly modified to fix several issues - unfinished 
import exchanges.binance.exceptions as binance_exceptions

from sqltools import query_lastrow_id, query # proper requests to sqlite db

## Standard libraries 
import time
from time import localtime, strftime
import math

import decimal
from decimal import Decimal
# Decimal precision
decimal.getcontext().prec = 20

# Initialising clients with api keys 
api = bittrex('key1', 'key2')
api_binance = Client('key1', 'key2')    
api_bitfinex = Client_bitfinex()
api_bitfinex_trade = TradeClient('key1', 'key2')


# Binance functions
def binance_ticker(market): 
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    tickers = api_binance.get_all_tickers()
    new_dict = {}
    for item in tickers:
       symbol = item['symbol']
       new_dict[symbol] = item['price']
    return float(new_dict[market])


def binance_openorder(market):
    """
    Exchange + Market -> ListOfDictsInBittrexFormat
    key values from open orders used by robot.py:
    'OrderUuid', 'Quantity', 'quantity Remaining', 'limit'
    :param exchange:
    :param market:
    :return:
    """
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    binance_oo = api_binance.get_open_orders(symbol=market) # data is in Binance format
    result = []
    for binance_order in binance_oo:
        temp_dict = {}
        temp_dict["OrderUuid"]  = binance_order["orderId"]
        temp_dict["Quantity"] = binance_order["origQty"]
        temp_dict["QuantityRemaining"] = Decimal(binance_order["origQty"]) - Decimal(binance_order["executedQty"])
        temp_dict["Price"] = binance_order["price"]
        temp_dict["Limit"] = '' #not really used but is showed for bittrex 
        result.append(temp_dict)
    return result

def binance_get_trades(market):
    """
    market -> ListOfDicts(Bittrex format)
    Returns list of executed trades, each trade is a dict with the key being the order ID
    :return:
    """
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    trades = api_binance.get_my_trades(symbol=market)
    listoftrades = []
    # print(trades)
    for trade in trades:
        temp_dict = {}
        temp_dict['OrderUuid'] = trade['orderId']
        listoftrades.append(temp_dict)
    return listoftrades

def binance_get_order(market, item):
    """
    market + item -> Dict
    Key data items: Price, CommissionPaid, Quantity, Quantity remaining,
    get_my_trades can access commission, get_order cannot, but does have qtys
    use both
    """
    # We will need ['Price'] , ['CommissionPaid'], ['Quantity'] , ['QuantityRemaining'] , ['PricePerUnit']
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    trades = api_binance.get_my_trades(symbol=market)
    binance_order = api_binance.get_order(symbol=market, orderId=item)
    output = {}
    for trade in binance_order:
        output['Price'] = Decimal(str(binance_order["price"])) * Decimal(str(binance_order['origQty']))
        output['Quantity'] = Decimal(str(binance_order['origQty']))
        output['PricePerUnit'] =  Decimal(str(binance_order["price"]))
        output['QuantityRemaining'] = Decimal(str(binance_order['origQty'])) - Decimal(str(binance_order['executedQty']))
    for trade in trades:
        if trade['orderId'] == item:
            output['CommissionPaid'] = Decimal(str(trade['commission']))
    return output

def binance_get_balance(currency):
    """Currency -> Float
    Returns balance in binance account for particular currency"""
    output = {} # to make consistent with the overall script
    output['Available'] = 0 
    account_info = api_binance.get_account()
    for balance in account_info['balances']:
        if balance['asset'] == currency:
            output['Available'] = float(balance['free'])
    return output

def binance_orderbook(market):
    # Just collecting bids in this function
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    """Market->Dict[Result[Bid&Ask]]
    Returns order book in bittrex format"""
    order_book = api_binance.get_order_book(symbol=market)
    output_dict = {}
    result_dict = {}
    bid_list = order_book["bids"]
    ask_list = order_book["asks"]
    output_buy_list = []
    output_sell_list = []
    for bid in bid_list:
        temp_dict = {}
        temp_dict["Rate"] = float(bid[0])  # For consistency with the main code       #temp_dict["Price"] = float(bid[0])
        temp_dict["Quantity"] = float(bid[1])
        output_buy_list.append(temp_dict)
    ''' # Do not need both here 
    for ask in ask_list:
        temp_dict = {}
        temp_dict["Price"] = float(ask[0])
        temp_dict["Quantity"] = float(ask[1])
        output_sell_list.append(temp_dict)
    result_dict['buy'] = output_buy_list
    result_dict['sell'] = output_sell_list
    output_dict['result'] = result_dict
    ''' 

    return output_buy_list

def binance_balances(): 
    balances_return = []
    acc = api_binance.get_account()['balances']    
    for elem in acc: 
        balance_total = float(elem['locked']) + float(elem['free'])
        arr_row = {'Currency':elem['asset'], 'Balance':float(balance_total), 'Available':float(elem['free'])}
        balances_return.append(arr_row)
    return balances_return

def binance_cancel(market, orderid): 
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    try:
        cancel_result = api_binance.cancel_order(symbol = market, orderId = orderid) 
    except: # error handling 
        cancel_result = 'unknown order' 
    return cancel_result 
 
def binance_selllimit(market, sell_q_step, price_to_sell):  # CHANGE (!) 
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    try: 
        price_to_sell = Decimal(str(price_to_sell))     # str to preserve the same number of decimals 
        result = api_binance.create_order(symbol = market, quantity = sell_q_step, price = price_to_sell, side = 'SELL', type = 'LIMIT', timestamp = time.time(), timeInForce = 'GTC')
        result['uuid'] = result['orderId']  # for consistency in the main code 
    except binance_exceptions.BinanceAPIException as BalanceTooSmall:
        print BalanceTooSmall
        return BalanceTooSmall
    except binance_exceptions.BinanceOrderMinTotalException as TradeSizeTooSmall:
        print TradeSizeTooSmall
        return TradeSizeTooSmall
    except binance_exceptions.BinanceOrderMinAmountException as e:
        print e
        err_str = str(e)
        position = err_str.find('a multiple of') + len('a multiple of') + 1
        multiple_value = Decimal(err_str[position:])
        sell_qty = Decimal(sell_q_step)
        multiplier = 0
        if sell_qty > multiple_value:
            multiplier = int(sell_qty/multiple_value)
        elif sell_qty < multiple_value:
            multiplier = 1
        new_sell_qty = multiplier * multiple_value
        print "Creating New Order with quantity:", new_sell_qty
        try: 
            result = api_binance.create_order(symbol = market, quantity = new_sell_qty, price = price_to_sell, side = 'SELL', type = 'LIMIT', timestamp = time.time(), timeInForce = 'GTC')
            result['uuid'] = result['orderId']  # for consistency in the main code 
        except:
            return 'MIN_TRADE_REQUIREMENT_NOT_MET'

    return result  
 
def binance_buylimit(market, quantity_buy, buy_rate):    
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    buy_rate = Decimal(str(buy_rate))     # str to preserve the same number of decimals 
    try: 
        result = api_binance.create_order(symbol = market, quantity = quantity_buy, price = buy_rate, side = 'BUY', type = 'LIMIT', timestamp = time.time(), timeInForce = 'GTC')
        result['uuid'] = result['orderId']  # for consistency in the main code 
    except binance_exceptions.BinanceAPIException as BalanceTooSmall:
        print BalanceTooSmall
        return BalanceTooSmall
    except binance_exceptions.BinanceOrderMinTotalException as TradeSizeTooSmall:
        print TradeSizeTooSmall
        return TradeSizeTooSmall
    except binance_exceptions.BinanceOrderMinAmountException as e:
        print e
        err_str = str(e)
        position = err_str.find('a multiple of') + len('a multiple of') + 1
        multiple_value = Decimal(err_str[position:])
        buy_qty = Decimal(quantity_buy)
        multiplier = 0
        if buy_qty > multiple_value:
            multiplier = int(buy_qty/multiple_value)
        elif buy_qty < multiple_value:
            multiplier = 1
        new_buy_qty = multiplier * multiple_value
        print "Creating New Order with quantity:", new_buy_qty
        try: 
            result = api_binance.create_order(symbol = market, quantity = new_buy_qty, price = buy_rate, side = 'BUY', type = 'LIMIT', timestamp = time.time(), timeInForce = 'GTC')
            result['uuid'] = result['orderId']  # for consistency in the main code 
        except:
            return 'MIN_TRADE_REQUIREMENT_NOT_MET'

    return result  
 
## Bitfinex functions - decided not to finalise 
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
    
############# Common functions ##################################    
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
    elif exchange == 'binance':
        return binance_openorder(market)
    else:
        return 0


def cancel(exchange, market, orderid):
    """
    Had to add additional parameter "market" for binance
    """
    if exchange == 'bittrex':
        return api.cancel(orderid)
    elif exchange == 'binance':
        return binance_cancel(market, orderid) 
    else:
        return 0


def getorderhistory(exchange, market):
    """Returns list of executed trades for a given symbol
    """
    if exchange == 'bittrex':
        return api.getorderhistory(market, 100)
        # elif exchange == 'bitfinex':
    #     return bitfinex_getorderhistory(market)
    elif exchange == 'binance':
        return binance_get_trades(market) 
    else:
        return 0


def getorder(exchange, market, item):
    """:
    binance doesnt give commission info
    item is Order ID
    Key values
    Price, CommissionPaid, Quantity, Quantity remaining,
    Params edited to include market
    """
    if exchange == 'bittrex':
        return api.getorder(item)
    # elif exchange == 'bitfinex':
    #     return bitfinex_getorder(item)
    elif exchange == 'binance':
        return binance_get_order(market, item)
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
    elif exchange == 'binance':
        while retry:
            try:
                curr_balance = binance_get_balance(currency)
                retry = False
            except:
                failed_attempts += 1
        return curr_balance
    # elif exchange == 'bitfinex':
    #     # if service is unavailable
    #     while retry:
    #         try:
    #             curr_balance = bitfinex_balance_curr(currency)
    #             retry = False
    #         except:
    #             failed_attempts += 1
    #     return curr_balance
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
    elif exchange == 'binance':
        return binance_selllimit(market, sell_q_step, price_to_sell) 
    else:
        return 0


def buylimit(exchange, market, quantity, buy_rate):
    if exchange == 'bittrex':
        return api.buylimit(market, quantity, buy_rate)
    elif exchange == 'binance':
        return binance_buylimit(market, quantity, buy_rate) 
    else:
        return 0


def getorderbook(exchange, market):
    if exchange == 'bittrex':
        return api.getorderbook(market, 'buy')
    elif exchange == 'binance':
        return binance_orderbook(market)
    # elif exchange == 'bitfinex':
    #     return bitfinex_orderbook(market)
    else:
        return 0  
        
