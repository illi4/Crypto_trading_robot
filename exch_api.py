import libs.sqltools as sqltools
sql = sqltools.sql()

## Standard libraries
import time
import json
import traceback
import decimal
from decimal import Decimal, getcontext

from datetime import datetime

# Config
import config

## Exchange libraries
# Bitmex: https://github.com/BitMEX/api-connectors/tree/master/official-http/python-swaggerpy
import bitmex
import bravado

# OANDA: https://github.com/hootnot/oanda-api-v20 works ok
from oandapyV20 import API    # the client
from oandapyV20.exceptions import V20Error
import oandapyV20.endpoints.pricing as pricing
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.instruments as instruments
import oandapyV20.endpoints.transactions as transactions
import oandapyV20.endpoints.orders as orders



class api(object):
    def __init__(self, user, strategy = None):

        # Not needed
        '''
        self.public = [
            'getticker',
            'getopenorders',
            'cancel',
            'getorderhistory',
            'getorder',
            'getbalance',
            'selllimit',
            'buylimit',
            'getorderbook',
            'getpositions',
            'closepositions',
            'cancel_orders',
            'return_margin',
            'results_over_time', # oanda is easier than bitmex because the results are in the closing trade; robot.py changed accordingly
            'bitmex_load_markets',
            'bitmex_leverage',
            'bitmex_get_balance_total',
            'keys_select'
        ]
        '''

        # Selecting the margin
        sql_string = "SELECT param_val FROM user_params WHERE userid = {} " \
            "AND param_name = 'margin' and core_strategy = '{}'".format(user, strategy)
        try:
            rows = sql.query(sql_string)
            self.margin_level = int(rows[0][0])
        except:
            self.margin_level = 1

        # Selecting the keys: bitmex
        self.bitmex_apikey, self.bitmex_secret =self.keys_select(user, 'standard', 'bitmex')
        
        # Selecting the keys: oanda 
        self.key_id_oanda, self.secret_id_oanda =self.keys_select(user, 'traditional', 'oanda')  # always 'traditional' for oanda
            
        # Decimal precision
        decimal.getcontext().prec = 20

        # Initialising clients with api keys: bitmex
        if not config.use_testnet:
            self.bitmex = bitmex.bitmex(
                api_key=self.bitmex_apikey,
                api_secret=self.bitmex_secret,
                test=False)
        else:
            # Use this for testnet  #islobodch acc
            print('(i) Note: using testnet - bitmex')
            self.bitmex = bitmex.bitmex(
                api_key = config.testnet_keys['key_bitmex'],
                api_secret = config.testnet_keys['secret_bitmex'],
                test=True)
        
        # Initialising clients with api keys: oanda
        if not config.use_testnet:
            self.oanda = API(access_token = self.secret_id_oanda, environment='live')
            self.oanda_account_id = self.key_id_oanda
        else:
            print('(i) Note: using testnet - oanda')
            self.oanda = API(access_token = config.testnet_keys['secret_oanda'])
            self.oanda_account_id = config.testnet_keys['key_oanda']

        # Contracts to use
        self.contracts_to_use = None


    # Returns the keys (or none) 
    def keys_select(self, user, strategy, exchange):
        sql_string = """
        SELECT key_id, key_secret FROM keys 
        WHERE user = {} and strategy = '{}' and exchange = '{}'
        """.format(user, strategy, exchange)

        rows = sql.query(sql_string)
        if rows != []: 
            key_id = rows[0][0]
            key_secret = rows[0][1]
        else:
            key_id = None
            key_secret = None
        return key_id,  key_secret
        
    # Returns the margin
    def return_margin(self):
        return self.margin_level

    ### Rename the market to use with the bitmex lib
    def market_std(self, market):
        if market == 'BTC/USD':
            return 'XBTUSD'
        elif market == 'ETH/USD':
            return 'ETHUSD'
        else:
            return market

    ### OANDA functions using v20

    # Check if market hours
    def oanda_market_hours(self, market):
        params={"instruments": market}
        request = pricing.PricingInfo(self.oanda_account_id, params=params)
        rv = self.oanda.request(request)['prices'][0]
        if rv['status'] == 'tradeable':
            return True
        else:
            return False

    # Ticker
    def oanda_ticker(self, market):
        params={"instruments": market}
        request = pricing.PricingInfo(self.oanda_account_id, params=params)
        rv = self.oanda.request(request)['prices'][0]
        if rv['status'] == 'tradeable': 
            ticker = rv['closeoutBid']
            return Decimal(ticker)
        else: 
            return None 

    # Get instrument precision
    def oanda_precision(self, market):
        result = self.oanda_getinstruments()
        precision = 0 # default

        for elem in result['instruments']:
            if elem['name'] == market:
                #print elem
                precision = int(elem['displayPrecision'])
        return precision

    # Balance
    def oanda_balance(self):
        request = accounts.AccountSummary (self.oanda_account_id) #, params=params)
        rv = self.oanda.request(request)
        rv = rv['account']['marginAvailable']   # this accounts for open positions whereas 'balance' is total (nav)
        result = {}
        result['Available'] = float(rv)
        result['Total'] = float(rv)
        return result

    # Positions
    def oanda_position_elem_process(self, elem, temp_dict):
        if float(elem['short']['units']) != 0:
            temp_dict["type"] = 'short'
            temp_dict['contracts_no'] = abs(float(elem['short']['units']))
            temp_dict['entryprice'] = float(elem['short']['averagePrice'])
            temp_dict['tradeid'] = int(elem['short']['tradeIDs'][0])
        if float(elem['long']['units']) != 0:
            temp_dict["type"] = 'long'
            temp_dict['contracts_no'] = abs(float(elem['long']['units']))
            temp_dict['entryprice'] = float(elem['long']['averagePrice'])
            temp_dict['tradeid'] = int(elem['long']['tradeIDs'][0])
        temp_dict['contracts'] = temp_dict['contracts_no']
        return temp_dict

    # Get positions
    def oanda_getpositions(self, market = None):
        request = positions.OpenPositions(self.oanda_account_id)
        rv = self.oanda.request(request)
        result = []
        if market is not None:  # for specific market
            temp_dict = {}
            for elem in rv['positions']:
                if elem['instrument'] == market:
                    temp_dict = self.oanda_position_elem_process(elem, temp_dict)
            result.append(temp_dict)
        else: # for all markets
            for elem in rv['positions']:
                temp_dict = {}
                temp_dict = self.oanda_position_elem_process(elem, temp_dict)
                temp_dict['market'] = elem['instrument']
                if temp_dict != {}:
                    result.append(temp_dict)
        return result


    # Results over time
    def oanda_results_over_time(self, market, timestamp_from, timestamp_to, lastid=0):
        pre_list = []
        results_dict = {}

        params={"id": lastid}    # market param does not work for some reason
        request = transactions.TransactionsSinceID(self.oanda_account_id, params=params)
        result = self.oanda.request(request)['transactions']
        for elem in result:
            if 'instrument' in list(elem.keys()):
                if elem['instrument'] == market:
                    utc_datetime = elem['time']
                    try:
                        utc_datetime = datetime.strptime(utc_datetime, "%Y-%m-%dT%H:%M:%S.%fZ")
                    except ValueError:  # can be insonsistent
                        utc_datetime = datetime.strptime(utc_datetime[:-4], "%Y-%m-%dT%H:%M:%S.%f")
                    timestamp = (utc_datetime - datetime(1970, 1, 1)).total_seconds()
                    if (timestamp > timestamp_from) and (timestamp < timestamp_to):
                        pre_list.append(elem)

        # Only the last element is needed for calculations for OANDA
        last_result = pre_list[-1]

        total_commission = abs(float(last_result['commission']))
        total_funding = abs(float(last_result['financing']))
        gain = float(last_result['pl'])
        total_value = gain + total_commission + total_funding   # for consistency

        print("> Total value in fiat", -total_value, "funding", total_funding)
        print("> Total gain / loss (outcome):", gain)

        results_dict['position_diff'] = total_value
        results_dict['commission'] = total_commission
        results_dict['funding'] = total_funding
        results_dict['total_outcome'] = gain

        result = results_dict
        return result

    # Get transactions list
    def oanda_last_transaction_id(self, market):
        pre_list = []
        results_dict = {}

        params={"pageSize": 1000}    # gives the last orders
        request = transactions.TransactionList(self.oanda_account_id, params=params)
        result = self.oanda.request(request)['lastTransactionID']

        # Subtract 20 so that we get info on orders before last (for code consistency)
        if int(result) < 20:
            result = 1
        else:
            result = str(int(result) - 20)

        return result

    # Get last orders IDs
    def oanda_get_sell_ordhist(self, market, lastid):
        pre_list = []
        results_dict = {}

        params={"id": lastid}    # market param does not work for some reason
        request = transactions.TransactionsSinceID(self.oanda_account_id, params=params)
        result = self.oanda.request(request)['transactions']
        for elem in result:
            if 'instrument' in list(elem.keys()):
                if elem['instrument'] == market:
                    pre_list.append(elem)

        # Reverse list (need from new to old)
        listoforders = []
        for elem in pre_list:
            temp_dict = {}
            temp_dict['OrderUuid'] = elem["id"]
            listoforders.append(temp_dict)

        return listoforders

    # Returns my open orders
    def oanda_openorders(self, market):
        result = []
        request = orders.OrdersPending(self.oanda_account_id)
        oanda_orders = self.oanda.request(request)

        for order in oanda_orders['orders']:
            if order['instrument'] == market:
                temp_dict = {}
                temp_dict["OrderUuid"] = order["id"]
                temp_dict["Quantity"] = abs(Decimal(order["units"]))
                temp_dict["QuantityRemaining"] = abs(Decimal(order["units"]))  # same for OANDA
                temp_dict["Price"] = float(order["price"])
                if float(order["units"]) < 0:
                    temp_dict["type"] = 'short'
                else:
                    temp_dict["type"] = 'long'
                result.append(temp_dict)
        return result

    # Cancel orders
    def oanda_cancel(self, market, orderid):
        request = orders.OrderCancel(accountID=self.oanda_account_id, orderID=orderid)
        try:
            cancel_result = self.oanda.request(request)
        except V20Error as e:
            cancel_result = 'unknown order'
        return cancel_result

    # Get order info
    def oanda_get_order(self, market, item):
        try:
            request = orders.OrderDetails(accountID=self.oanda_account_id, orderID=item)
            order_info = self.oanda.request(request)['order']
            # Cancelled filled orders are differentiated by replacedByOrderID
            output = {}
            output["OrderUuid"] = order_info["id"]

            # Price may not be in the order (if trying out market orders for example)
            if 'price' not in list(order_info.keys()):
                order_info['price'] = self.oanda_ticker(market)

            # On the platform filledTime in keys mean that the order was actually filled
            if 'filledTime' in list(order_info.keys()):
                output["Quantity"] = abs(float(order_info["units"]))
                output["QuantityRemaining"] = 0
                output["PricePerUnit"] = float(order_info['price'])
                output["Price"] = float(order_info['price'])*float(order_info["units"])
            else:
                output["Quantity"] = abs(float(order_info["units"]))
                output["QuantityRemaining"] = abs(float(order_info["units"]))
                output["PricePerUnit"] = 0
                output["Price"] = 0

            output['CommissionPaid'] = 0
            output['Status'] = order_info['state']
            output['simpleCumQty'] = abs(float(order_info["units"]))

        except V20Error as e:
            print(e)  # 404 is order not found
            output = None
        return output

    # Get instruments
    def oanda_getinstruments(self):
        r = accounts.AccountInstruments(accountID=self.oanda_account_id)
        rv = self.oanda.request(r)
        return rv

    # Orderbook
    def oanda_orderbook(self, market, type):
        if type not in ['bids', 'asks']:
            type = 'bids'

        '''# This endpoint does not work for some instruments (officia oanda response) 
        request = instruments.InstrumentsOrderBook(instrument = "NAS100_USD") #(instrument='UK10YB_GBP')
        orderbook = self.oanda.request(request)
        '''
        # Using pricing as a workaround until the issue is fixed
        params={"instruments": market}
        request = pricing.PricingInfo(self.oanda_account_id, params=params)

        if type == 'bids':
            rv = self.oanda.request(request)['prices'][0]['bids']
        else:
            rv = self.oanda.request(request)['prices'][0]['asks'] 

        output_buy_list = []
        temp_dict = {}
        temp_dict["Rate"] = float(rv[0]['price'])
        temp_dict["Quantity"] = float(rv[0]['liquidity'])
        output_buy_list.append(temp_dict)
        return output_buy_list        

    # Orders wrapper
    def oanda_execorder(self, side, rate, market, units, postonly_flag=False):
        if side == 'buy':
            units = abs(units)
        elif side == 'sell':
            units = -abs(units)
        else:
            return None

        # Limit if not too much time passed
        if postonly_flag:
            ord_type = 'LIMIT'
        else:
            ord_type = 'MARKET'

        # For testing purposes bump up/down values so the order executes right away
        if config.use_testnet:
            if units < 0:
                rate = rate*0.98
            else:
                rate = rate*1.02

        # Get the instrument precision
        precision = self.oanda_precision(market)
        rate = round(float(rate), precision)
        data = {
            'order': {
                'price': str(rate), # otherwise weird conversions happen and decimals can be changed unpredictably
                'instrument': market,
                'units': units,
                'type': ord_type,
                "positionFill": "DEFAULT"
            }
        }
        try:
            #print "Data to submit:", rate, data, '\n\n'
            request = orders.OrderCreate(accountID=self.oanda_account_id, data=data)
            result = self.oanda.request(request)
            result['uuid'] = result['orderCreateTransaction']['id']
        except V20Error as e:
            print("Oanda error {}, {}, {}".format(e.code, e.message, e.msg))  # 400 is insufficient balance
            if e.code == 400:
                result = 'MIN_TRADE_REQUIREMENT_NOT_MET'        # rework this
            else:
                result = None
        return result

    # Limit buy order
    def oanda_buylimit(self, market, quantity_buy, buy_rate, postonly_flag=False):  # >> Open a long
        result = self.oanda_execorder('buy', buy_rate, market, quantity_buy, postonly_flag=postonly_flag)
        return result

    # Limit sell order
    def oanda_selllimit(self, market, sell_q_step, price_to_sell, postonly_flag=False): # >> Open a short
        result = self.oanda_execorder('sell', price_to_sell, market, sell_q_step, postonly_flag=postonly_flag)
        return result

    # Close a position
    def oanda_closepositions(self, market_positions, market, price, short_flag):    # closing all for now but could change the number
        if short_flag:
            data = {'shortUnits':'ALL'}
        else:
            data = {'longUnits':'ALL'}
        request = positions.PositionClose(accountID=self.oanda_account_id, data=data, instrument=market) # ...
        rv = self.oanda.request(request)
        return rv

    #### Bitmex functions: using ccxt
    # OHLC
    def bitmex_bucketed(self, market, limit = 750, since=None):
        market = self.market_std(market)
        if since is None:
            ohlcv = self.bitmex.fetch_ohlcv(market, limit=limit)
        else:
            ohlcv = self.bitmex.fetch_ohlcv(market, limit=limit, since=since)
        return ohlcv

    # Ticker
    def bitmex_ticker(self, market):
        market = self.market_std(market)
        ticker = self.bitmex.Trade.Trade_get(symbol=market, count=1, reverse=True).result()[0][0]['price']
        return Decimal(ticker)

    # Balance info
    def bitmex_get_balance(self, currency):
        output = {}  # to make consistent with the overall script

        pre_result = self.bitmex.User.User_getMargin().result()
        balances = pre_result[0]['walletBalance']/100000000
        output['Total'] = output['Available'] = float(balances)

        return output

    # Returns my open orders
    def bitmex_openorders(self, market):
        market = self.market_std(market)

        response = self.bitmex.Order.Order_getOrders(symbol=market, count=300,  filter=json.dumps({'open': True}) ).result()   #, limit=300
        orders = list(response)[0]

        result = []
        for bitmex_order in orders:
            temp_dict = {}
            temp_dict["OrderUuid"] = bitmex_order["orderID"]
            temp_dict["Quantity"] = bitmex_order["orderQty"]
            temp_dict["QuantityRemaining"] = Decimal(bitmex_order["leavesQty"])
            temp_dict["Price"] = bitmex_order["price"]
            temp_dict["Limit"] = ''  # not really used but is showed for bittrex
            if bitmex_order["side"] == 'Sell':
                temp_dict["type"] = 'short'
            else:
                temp_dict["type"] = 'long'
            result.append(temp_dict)
        return result

    # Cancel orders
    def bitmex_cancel(self, market, orderid):
        market = self.market_std(market)
        try:
            cancel_result = self.bitmex.Order.Order_cancel(orderID=orderid).result()
            cancel_result = list(response)[0]
        except:  # error handling
            cancel_result = 'unknown order'
        return cancel_result

    # Get order info
    def bitmex_get_order(self, market, item):
        market = self.market_std(market)

        # response = self.bitmex.Position.Position_get(filter=json.dumps({'symbol': market}), count=300).result()

        response = self.bitmex.Order.Order_getOrders(filter=json.dumps({'symbol': market, 'orderID':item}),
            count=300).result()   #, limit=300
        bitmex_order = order_info = list(response)[0][0]

        print("(i) Order info when getting the order: {}\n".format(order_info))

        output = {}
        output["OrderUuid"] = bitmex_order["orderID"]
        output["Quantity"] = bitmex_order["orderQty"]
        output["QuantityRemaining"] = Decimal(bitmex_order["orderQty"] - bitmex_order["cumQty"]) #Decimal(bitmex_order["leavesQty"])
        output["PricePerUnit"] = bitmex_order["price"]  # handle this later, not critical
        output["Price"] = bitmex_order["price"]  # handle this later, not critical
        output['CommissionPaid'] = 0
        output['Status'] = bitmex_order["ordStatus"]  # handy for the calculation of results
        output['simpleCumQty'] = bitmex_order["simpleCumQty"]  # handy for the calculation of results
        return output


    # Orderbook
    def bitmex_orderbook(self, market, type):
        market = self.market_std(market)

        if type not in ['bids', 'asks']:
            type = 'bids'

        if type == 'bids':
            type = 'Buy'
        else:
            type = 'Sell'

        response = self.bitmex.OrderBook.OrderBook_getL2(symbol=market, depth=50).result()[0]
        result = []
        for elem in response:
            if elem['side'] == type:
                tmp_dict = {}
                tmp_dict['Rate'] = elem['price']
                tmp_dict['Quantity'] = elem['size']
                result.append(tmp_dict)

        if type == 'Sell':
            result = list(reversed(result))

        return result


    # Limit buy order
    def bitmex_buylimit(self, market, quantity_buy, buy_rate, contracts=None, postonly=False):  # >> Open a long
        market = self.market_std(market)
        msg = ''
        buy_rate = self.bitmex_convert_price(market, buy_rate)
        # Calculating how many contracts do we need to open
        if contracts is None:
            contracts = round(quantity_buy * buy_rate)
            #print(("Contracts:", contracts)) # DEBUG
        if postonly:
            #print(("Contracts:", contracts)) # DEBUG
            result = self.bitmex.Order.Order_new(symbol=market, orderQty=contracts,
                price=float(buy_rate), execInst='ParticipateDoNotInitiate').result()[0]
        else:
            #print(("Contracts:", contracts)) # DEBUG
            result = self.bitmex.Order.Order_new(symbol=market, orderQty=contracts,
                price=float(buy_rate)).result()[0]
        result['uuid'] = result['orderID']  # for consistency in the main code (robot)
        # Handling the outcomes
        if msg != '':
            return msg
        else:
            return result

    # Limit sell order
    def bitmex_selllimit(self, market, quantity_sell, sell_rate, contracts=None, postonly=False):  # >> Open a short
        market = self.market_std(market)
        sell_rate = self.bitmex_convert_price(market, sell_rate)
        if contracts is None:
            contracts = round(quantity_sell * sell_rate)
        if postonly:
            result = self.bitmex.Order.Order_new(symbol=market, orderQty=-contracts,
                price=float(sell_rate), execInst='ParticipateDoNotInitiate').result()[0]
        else:
            result = self.bitmex.Order.Order_new(symbol=market, orderQty=-contracts,
                price=float(sell_rate)).result()[0]
        result['uuid'] = result['orderID']  # for consistency in the main code

        return result

    # Bitmex specifics: return open positions (not orders)
    def bitmex_openpositions(self, market):
        result = []
        if market is not None:
            # Position for the specific market
            market = self.market_std(market)
            response = self.bitmex.Position.Position_get(filter=json.dumps({'symbol': market}), count=300).result()
            positions = list(response)[0]
            for position in positions:
                temp_dict = {}
                if position["isOpen"] is True:
                    if position["homeNotional"] > 0:
                        temp_dict["type"] = 'long'
                    else:
                        temp_dict["type"] = 'short'
                    temp_dict['contracts_no'] = abs(
                        position['homeNotional'])  # using abs here because we will be working on both longs and shorts  #CHANGE
                    temp_dict['contracts'] = abs(position['currentQty'])
                    temp_dict['entryprice'] = position['avgEntryPrice']
                result.append(temp_dict)
        else:
            # All
            response = self.bitmex.Position.Position_get(count=300).result()
            positions = list(response)[0]
            for position in positions:
                temp_dict = {}
                if position["isOpen"] is True:
                    temp_dict['market'] = position['symbol']
                    if position["homeNotional"] > 0:
                        temp_dict["type"] = 'long'
                    else:
                        temp_dict["type"] = 'short'
                    temp_dict['contracts_no'] = abs(
                        position['homeNotional'])  # using abs here because we will be working on both longs and shorts  #CHANGE
                    temp_dict['contracts'] = abs(position['currentQty'])
                    temp_dict['entryprice'] = position['avgEntryPrice']
                if temp_dict != {}:
                    result.append(temp_dict)
        return result


    # Bitmex specifics: close a position
    def bitmex_closepositions(self, positions, market, price):
        contracts_total = 0
        # Total contracts to close the position
        for position in positions:
            if position['type'] == 'short':
                contracts_total -= position['contracts']
            else:
                contracts_total += position['contracts']
        if contracts_total < 0:  # short
            result = self.bitmex_buylimit(market, None, price, contracts_total)
            retry = False
        else:  # long
            result = self.bitmex_selllimit(market, None, price, contracts_total)
            retry = False
        return result


    # Get last orders IDs
    def bitmex_get_sell_ordhist(self, market):
        market = self.market_std(market)

        response = self.bitmex.Order.Order_getOrders(symbol=market, count=300, reverse=True).result()   #, limit=300
        bitmex_orders = list(response)[0]

        listoforders = []
        for order in bitmex_orders:
            temp_dict = {}
            temp_dict['OrderUuid'] = order["orderID"]
            listoforders.append(temp_dict)
        return listoforders

    # Fixes the price value considering relevant TickSize
    def bitmex_convert_price(self, market, price):

        tickSize = self.bitmex_ticksize(market)
        getcontext().rounding = 'ROUND_DOWN'
        price = Decimal(str(price))
        price = price.quantize(Decimal(str(tickSize)))

        return price

    # Return the ticksize for a specific market 
    def bitmex_ticksize(self, market):

        market = self.market_std(market)

        response = self.bitmex.Instrument.Instrument_get(symbol=market).result()
        market_info = list(response)[0][0]
        tickSize = market_info['tickSize']

        return tickSize
        
    # Change the leverage on a contract
    def bitmex_leverage(self, market, leverage=1):
        market = self.market_std(market)

        try:
            result = self.bitmex.Position.Position_updateLeverage(symbol=market, leverage=leverage).result()
        except:
            err_msg = traceback.format_exc()
            if err_msg.find('insufficient Available Balance') >= 0:  # surely error handling could be coded better
                result = 'balance_insufficient'
            else:
                result = 'other'

        return result

    # Get results over time
    def bitmex_results_over_time(self, market, timestamp_from, timestamp_to):
        orders_recent = self.detailed_trade_history('bitmex', market)
        executed_orders = []
        results_dict = {}

        for order in orders_recent:
            utc_datetime = order['timestamp']
            utc_datetime = utc_datetime.replace(tzinfo=None)

            timestamp = (utc_datetime - datetime(1970, 1, 1)).total_seconds()
            if (timestamp > timestamp_from) and (timestamp < timestamp_to):
                executed_orders.append(order)

        # Calculating value
        total_commission = 0
        total_value = 0
        total_funding = 0
        for order in executed_orders:
            order_type = order['execType']
            if order_type == 'Funding':
                order_funding = abs(order['homeNotional'])*order['commission']
                print('>> Funding', order_funding)
                total_funding += order_funding
            if order_type == 'Trade':
                order_side = order['side']
                order_value = -order['homeNotional']  # for comparison with bitmex report
                order_commission = abs(order['homeNotional'])*order['commission']
                print('>> Trade', order_side, order_value, 'commission', order_commission)
                total_commission += order_commission
                total_value += order_value

        gain = -(total_value) - total_commission - total_funding

        print("> Total value in BTC", -total_value, "commission (to subtract)", total_commission, "funding", total_funding)
        print("> Total gain / loss (in BTC) (outcome):", gain)   # that's calculated ok

        results_dict['position_diff'] = -total_value
        results_dict['commission'] = total_commission
        results_dict['funding'] = total_funding
        results_dict['total_outcome'] = gain

        result = results_dict
        return result

    ############################################################################
    ############# Common functions for all exchanges ##################################
    ############# For robot to work, all the data should be in the same format ################
    ############################################################################
    # can also create a wrapper to check that this is not None (robot.py, coinigylib)

    # A function returning try counters
    def keep_trying(self, attempt, error):
        attempt_continue = True
        attempt +=1
        attempt_limit = 200
        sleep_time = 5

        print("Retrying (full error):", error)
        err_message = str(error)

        time.sleep(sleep_time)
        if attempt > attempt_limit:
            print(("Terminating after {} tries. {}".format(attempt, err_message)))
            attempt_continue = False

        # If api key failure 
        if (err_message.lower().find('invalid api key') >= 0) or (err_message.lower().find('unauthorized') >= 0):
            print("Terminating because of the incorrect key")
            attempt_continue = False     
        
        return attempt_continue, attempt

    ### Func wrapper
    def func_wrapper(self, func_name, exchange, market, param1=None, param2=None, param3=None):

        tries, done = 0, False
        while not done:
            try:
                ### Main functions block
                if exchange not in ['bitmex', 'oanda']:
                    result = None

                # Get ticker
                if func_name == 'is_market_open':
                    if exchange == 'bitmex':
                        result = True
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_market_hours(market)
                        done = True

                # Get ticker
                if func_name == 'getticker':
                    if exchange == 'bitmex':
                        result = self.bitmex_ticker(market)
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_ticker(market)
                        done = True

                # Getopenorders
                if func_name == 'getopenorders':
                    if exchange == 'bitmex':
                        result = self.bitmex_openorders(market)
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_openorders(market)
                        done = True

                # Cancel
                if func_name == 'cancel':
                    if exchange == 'bitmex':
                        result = self.bitmex_cancel(market, param1)
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_cancel(market, param1)
                        done = True

                # Getorderhistory
                if func_name == 'getorderhistory':
                    if exchange == 'bitmex':
                        result = self.bitmex_get_sell_ordhist(market)
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_get_sell_ordhist(market, param1)
                        done = True

                # Getorder
                if func_name == 'getorder':
                    if exchange == 'bitmex':
                        result = self.bitmex_get_order(market, param1)
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_get_order(market, param1)
                        done = True

                # Getbalance
                if func_name == 'getbalance':
                    if exchange == 'bitmex':
                        result = self.bitmex_get_balance(param1)
                        done = True
                    elif exchange == 'oanda':  # traditional market balance is always in fiat
                        result = self.oanda_balance()
                        done = True

                # Getorderbook
                if func_name == 'getorderbook':
                    if exchange == 'bitmex':
                        result = self.bitmex_orderbook(market, param1)  # will process depending on the type
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_orderbook(market, param1)  # will process depending on the type
                        done = True

                # Getorderbook
                if func_name == 'results_over_time':
                    if exchange == 'bitmex':
                        result = self.bitmex_results_over_time(market, param1, param2)
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_results_over_time(market, param1, param2, lastid=param3)
                        done = True

                # Detailed trade hist
                if func_name == 'detailed_trade_history':
                    if exchange == 'bitmex':
                        market = self.market_std(market)
                        result = self.bitmex.Execution.Execution_getTradeHistory(symbol=market, reverse=True, count=500).result()[0]
                        done = True

                # Getpositions
                if func_name == 'getpositions':
                    if exchange == 'bitmex':
                        result = self.bitmex_openpositions(market)
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_getpositions(market)
                        done = True

                # Closepositions
                if func_name == 'closepositions':
                    if exchange == 'bitmex':
                        result = self.bitmex_closepositions(param1, market, param2)
                        done = True
                    elif exchange == 'oanda':
                        result = self.oanda_closepositions(param1, market, param2, short_flag=param3)
                        done = True

                # Cancel orders
                if func_name == 'cancel_orders':
                    if exchange in ['bitmex', 'oanda']:
                        my_orders = self.getopenorders(exchange, market)
                        if my_orders != '':
                            for val in my_orders:
                                print("Cancelling open order: {}, quantity {}, remaining {}, price {}".format(
                                    val['OrderUuid'],
                                    val['Quantity'],
                                    val['QuantityRemaining'],
                                    val['Price']))
                                self.cancel(exchange, market, val['OrderUuid'])
                        result = 'completed'
                        done = True
                        return result

                # Return result for all cases
                return result

                ### End of main functions block

            # Errors handled with bravado for bitmex
            except  bravado.exception.HTTPError as error:
                try: # cause this could be None
                    error_msg = str(error.swagger_result['error']['message'])
                except:
                    error_msg = '\n---\n{}\n---'.format(str(error))
                attempt_continue, tries = self.keep_trying(tries, error_msg)
                if not attempt_continue:
                    return None
            except V20Error as e:
                # Errors 500, 503, 502, 504 are related to availability
                if int(e.code) in [500, 502, 503, 504]:
                    attempt_continue, tries = self.keep_trying(tries, e.msg)
                    if not attempt_continue:
                        return None
                else:
                    print(("Oanda exchange error {:d} {:s}".format(e.code, e.msg)))
                    return None
            except:
                err_msg = traceback.format_exc()
                print(("Different error occured: {}".format(err_msg)))
                return None

    ### Functions mapped to the wrapper
    # Market hours
    def is_market_open(self, exchange, market):
        return self.func_wrapper('is_market_open', exchange, market)

    # Price ticker
    def getticker(self, exchange, market):
        return self.func_wrapper('getticker', exchange, market)

    # Open orders
    def getopenorders(self, exchange, market):
        return self.func_wrapper('getopenorders', exchange, market)

    # Cancel order by id
    def cancel(self, exchange, market, orderid):
        return self.func_wrapper('cancel', exchange, market, orderid)

    # Order history
    def getorderhistory(self, exchange, market, lastid=0):  # getting orders history; this is only used to get sell orders (in robot.py)
        return self.func_wrapper('getorderhistory', exchange, market, lastid)

    # Order info
    def getorder(self, exchange, market, item):
        return self.func_wrapper('getorder', exchange, market, item)

    # Balance
    def getbalance(self, exchange, currency = None):
        return self.func_wrapper('getbalance', exchange, market = None, param1 = currency)

    # Order book
    def getorderbook(self, exchange, market, type='bids'):  # can also be 'asks' in the type
        return self.func_wrapper('getorderbook', exchange, market, type)

    # Results over time
    def results_over_time(self, exchange, market, timestamp_from, timestamp_to, lastid=0):
        return self.func_wrapper('results_over_time', exchange, market, timestamp_from, timestamp_to, lastid)

    # Detailed trade hist
    def detailed_trade_history(self, exchange, market=None):
        return self.func_wrapper('detailed_trade_history', exchange, market)

    # Get positions
    def getpositions(self, exchange, market=None, do_retry=True):
        return self.func_wrapper('getpositions', exchange, market, do_retry)

    # Close positions
    def closepositions(self, exchange, positions=None, market=None, price=None, short_flag=None):
        return self.func_wrapper('closepositions', exchange, market, param1=positions, param2=price, param3=short_flag)

    # Cancel orders
    def cancel_orders(self, exchange, market):
        return self.func_wrapper('cancel_orders', exchange, market)


    ### Buy and sell - a bit specific

    # Limit sell order
    def selllimit(self, exchange, market, sell_q_step, price_to_sell, contracts=None, postonly=False):
        tries, done = 0, False
        if self.contracts_to_use is None:
            self.contracts_to_use = contracts
        while not done:
            try:
                if exchange == 'bitmex':
                    if not postonly:
                        result = self.bitmex_selllimit(market, sell_q_step, price_to_sell, self.contracts_to_use, postonly)
                        done = True
                        self.contracts_to_use = None
                        return result
                    else:   # going into a pricing cycle in postonly
                        tick = self.bitmex_ticksize(market)
                        print("(i) ticksize:", tick)
                        print("(i) price", price_to_sell)   
                        pricing_cycle = True
                        while pricing_cycle:
                            result = self.bitmex_selllimit(market, sell_q_step, price_to_sell, self.contracts_to_use, postonly)
                            if type(result) != type('str'):
                                if result['ordStatus'] == 'Canceled':
                                    print('(i) order canceled because of post-only flag')
                                    price_to_sell += tick
                                    print('(i) price changed to:', price_to_sell)
                                else:
                                    pricing_cycle = False
                                time.sleep(1)
                        done = True
                        self.contracts_to_use = None
                        return result
                elif exchange == 'oanda': # traditional market - there is no post-only there 
                    result = self.oanda_selllimit(market, sell_q_step, price_to_sell, postonly_flag=postonly)
                    done = True
                    return result         
                else:   # not supported exchange
                    return None
            # Errors handled with bravado for bitmex
            except  bravado.exception.HTTPError as error:
                try: # cause this could be None
                    error_msg = str(error.swagger_result['error']['message'])
                except:
                    error_msg = '\n---\n{}\n---'.format(str(error))

                # Could be related to the balance due to prices switching. decrease contracts then and trying again
                if (error_msg.lower().find('available balance') >= 0) or (error_msg.lower().find('invalid order') >= 0):
                    self.contracts_to_use = int(self.contracts_to_use * 0.98)
                    print('(i) decreased the number of contracts to', self.contracts_to_use)
                # until the decreased quantity is zero
                if self.contracts_to_use == 0:
                    return None

                # Check attempts to continue
                attempt_continue, tries = self.keep_trying(tries, error_msg)
                if not attempt_continue:
                    return None

            # Errors handling for OANDA
            except V20Error as e:
                # Errors 500, 503, 502, 504 are related to availability
                if int(e.code) in [500, 502, 503, 504]:
                    attempt_continue, tries = self.keep_trying(tries, e.msg)
                    if not attempt_continue:
                        return None
                else:
                    print(("Oanda exchange error {:d} {:s}".format(e.code, e.msg)))
                    return None

            # Other unknown error
            except:
                err_msg = traceback.format_exc()
                print(("Different error occured: {}".format(err_msg)))
                return None
                    
    # Limit buy order
    def buylimit(self, exchange, market, quantity, buy_rate, contracts=None, postonly=False):

        tries, done = 0, False
        if self.contracts_to_use is None:
            self.contracts_to_use = contracts
        while not done:
            try:
                if exchange == 'bitmex':
                    if not postonly:
                        result = self.bitmex_buylimit(market, quantity, buy_rate, self.contracts_to_use, postonly)
                        done = True
                        self.contracts_to_use = None
                        return result
                    else:   # going into a pricing cycle in postonly
                        tick = self.bitmex_ticksize(market)
                        print("(i) ticksize:", tick)
                        print("(i) price", buy_rate)                      
                        pricing_cycle = True
                        while pricing_cycle:
                            result = self.bitmex_buylimit(market, quantity, buy_rate, contracts, postonly)
                            if type(result) != type('str'):
                                if result['ordStatus'] == 'Canceled':
                                    print('(i) order canceled because of post-only flag')
                                    buy_rate -= tick
                                    print('(i) price changed to:', buy_rate)
                                else:
                                    pricing_cycle = False
                                time.sleep(1)
                        done = True
                        self.contracts_to_use = None
                        return result
                elif exchange == 'oanda': # traditional market - there is no post-only there 
                    result = self.oanda_buylimit(market, quantity, buy_rate, postonly_flag=postonly)
                    done = True
                    return result                            
                else:   # not supported exchange
                    return None

            # Errors handled with bravado for bitmex
            except  bravado.exception.HTTPError as error:
                try: # cause this could be None
                    error_msg = str(error.swagger_result['error']['message'])
                except:
                    error_msg = '\n---\n{}\n---'.format(str(error))

                # Could be related to the balance due to prices switching. decrease contracts then and trying again
                if (error_msg.lower().find('available balance') >= 0) or (error_msg.lower().find('invalid order') >= 0):
                    self.contracts_to_use = int(self.contracts_to_use * 0.98)
                    print('(i) decreased the number of contracts to', self.contracts_to_use)
                # until the decreased quantity is zero
                if self.contracts_to_use == 0:
                    return None

                # Check attempts to continue
                attempt_continue, tries = self.keep_trying(tries, error_msg)
                if not attempt_continue:
                    return None

            # Errors handling for OANDA
            except V20Error as e:
                # Errors 500, 503, 502, 504 are related to availability
                if int(e.code) in [500, 502, 503, 504]:
                    attempt_continue, tries = self.keep_trying(tries, e.msg)
                    if not attempt_continue:
                        return None
                else:
                    print(("Oanda exchange error {:d} {:s}".format(e.code, e.msg)))
                    return None

            # Other unknown error
            except:
                err_msg = traceback.format_exc()
                print(("Different error occured: {}".format(err_msg)))
                return None
