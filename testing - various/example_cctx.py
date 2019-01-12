## Standard libraries 
import os
import time
import sys
from sys import exit, argv
from time import localtime, strftime
import subprocess   
import math
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import urllib2
import decimal
from decimal import Decimal 
from decimal import getcontext
from openpyxl import Workbook, load_workbook   
from openpyxl.styles import Font, Fill
import json # requests
from shutil import copyfile # to copy files
import numpy as np

from decimal import getcontext


## Example 

# Universal functions for all exchanges 
from exchange_func import getticker, getopenorders, cancel, getorderhistory, getorder, getbalance, selllimit, getorderbook, buylimit, getbalances, binance_price_precise, binance_quantity_precise, getpositions, closepositions    

import ccxt   

from coinigylib import coinigy
coinigy = coinigy()
''' 
price = coinigy.price('BITS', 'BTC/USD')
print price
price = coinigy.price('BITF', 'BTC/USD')
print price
''' 
#ticker_upd = getticker('bitmex', 'USD-BTC') 
# print coinigy.price('bmex', 'USD-BTC')
#print getorderhistory('bitmex', 'USD-BTC')
# print getpositions('bitmex', 'USD-BTC')
    
positions = getpositions('bitmex', 'BTC/USD') 
print positions 
positions = getpositions('bitmex', 'XRPH18') 
print positions 

if positions != []: 
    print 'PFF'

exit(0) 

'''
market = 'USDT-BTC'
exchange = 'binance'
#print getorder(exchange, market, '187df2ce-f56e-4546-8e4f-25c0470026c6') , '\n\n' 
#print getorder(exchange, market, 'be02aa96-e1ec-4e73-a416-4d0af1433c8a')  , '\n\n' 
#print getorder(exchange, market, 'ccbb2b18-0f43-47ca-a443-eacb46787d7a')  , '\n\n' 

orders_opening = getorderhistory(exchange, market)  
print orders_opening

# Test issues with orders - this works fine... 
 
orders_new = set()
orders_start = set()

orders_opening = getorderhistory(exchange, market)  
for elem in orders_opening: 
    orders_start.add(elem['OrderUuid'])

print orders_start

sell_result = selllimit(exchange, market, 0.003, 19000, 0.003) 
time.sleep(60) 
sell_result = selllimit(exchange, market, 0.003, 15560, 0.003) 
time.sleep(30) 
    
print "\n\nNow sold, get the difference\n\n"  

# Getting information on sell orders executed
orders_opening_upd = getorderhistory(exchange, market) 

for elem in orders_opening_upd: 
    orders_new.add(elem['OrderUuid'])
    
print orders_new
    
orders_executed = orders_new.symmetric_difference(orders_start) 

print '\n\n Orders new (executed)\n', orders_executed 
'''
 

################################################################
''' 
# ccxt installed  - TESTINT BITSTAMP
import ccxt 
 
###
trade ='USD'
currency = 'BTC' 
market = 'USD-BTC'
exchange = 'bitstamp'
 

# Ticker  
#tick = getticker(exchange, market)  
#print tick 

# Getbalances 
#balances = getbalances(exchange)
#print balances

# Getbalance 
print getbalance(exchange, 'btc') 

# Getorderbook 
#print getorderbook(exchange, market) 

#Getopenorders 
print getopenorders(exchange, market) 

#Getorder 
print getorder(exchange, market, '681977016')  #681977016 is without anything 
#print getorder(exchange, market, '681952152')   #  681952152 is successfully completed 

#Cancel 
#time.sleep(5) 
#print cancel(exchange, market, '682090426') 
'''
''' 
bitstamp = ccxt.bitstamp ({
    'apiKey': '1Bx47cdmIulpMwC7mOTIJkt0z9FM3olP',
    'secret': 'oUQMwGcJC2ir2VKHeI3fXpiMigdnPtCF',
    'uid': 'jqah5913', 
})

z = bitstamp.fetch_my_trades('BTC/USD')   # that's ok to use for get order too. if not found in there - means it was not filled 
for a in z:
    print a 
''' 
 

''' 
print getorder(exchange, market, '61047555-c721-1407-64f9-695786500fee') 
print getorder(exchange, market, 'd1d7bc06-e8ad-23be-c603-27b0a481409b') 
print getorder(exchange, market, '073d688b-083c-dc23-4303-e0c36d671a6b') 
print getorder(exchange, market, '06a502c6-f959-1e59-2361-00dda60545d7') 
''' 

orderbook = getorderbook(exchange, market)
for elem in orderbook: 
    print elem 

#print getorder(exchange, market, '6af79c32-f982-2fe4-c447-d323392943e2')
#print getorder(exchange, market, '2537d075-0f75-53b6-d5bd-80bab6b059e5') 
#> 0c238062-734a-32b0-90bf-129c7251c686 price 12383 quantity sold 1910
#> 4066ddee-d68d-1a91-f5f2-68aa841182b6 price 11809 quantity sold 7
# print getopenorders(exchange, market)
 
# >> CCXT test - bitmex 

#tick = getticker(exchange, market)
#print tick 

#print getbalance('bitmex', 'xbt')

# Closing positions with the current price 
#positions = getpositions(exchange, market)
#print 'Positions', positionspositions

''' 
tick = getticker(exchange, market)
print 'Ticker', tick 

test = closepositions(exchange, positions, market, tick)
print test 
''' 
exit(0) 


#z = getpositions(exchange, market) #[0]['contracts']  # in contracts 
#print z  
 
print getorderhistory(exchange, market)
 
order_info = getorder(exchange, market, 'f65d7ce3-1db8-df1e-3e04-ca99bb8244c5')
print '>>>> Order info:', order_info

#f65d7ce3-1bd8-df1e-3e04-ca99bb8244c5
#f65d7ce3-1db8-df1e-3e04-ca99bb8244c5

#print selllimit(exchange, market, None, 30000, 10)    

'''
quantity_filled = order_info['Quantity'] - order_info['QuantityRemaining']
print quantity_filled

price_unit = order_info['PricePerUnit']
price_order = order_info['Price']

if price_unit is None: 
    price_unit = 0

source_filled = Decimal(str(price_unit * quantity_filled))
sum_paid = Decimal(str(source_filled))   # for averaging of price 
sum_quantity = quantity_filled  # for averaging of price 

str_status = '{} filled {}, {} filled: {}'.format(currency, quantity_filled, trade, source_filled) 
print str_status 
'''

# print buylimit('bitmex', 'USD-BTC', 0.05, 11000, 500)

# print buylimit('bitmex', 'USD-BTC', 0.01, 14056)

# print getorder(exchange, market, 'c33defe8-a7b2-6b58-268f-49f7f150d1ae')
# print cancel(exchange, market, 'bd4a61ca-ef46-f208-3799-6c3dabfe58f6') 
# print selllimit(exchange, market, 0.11, 30000)    

#test = getorderbook(exchange, market) 
#print test 

 
exit(0) 

##############################################################

trade ='USD'
currency = 'XBT' 
market = 'USD-XBT'
exchange = 'bitmex'

# Ticker 
tick = getticker(exchange, market)
print tick 

# Balance 



exit(0)


#

# KEY Kf6nvKfs_BWWnFw5NZuXKwrX
# Secret zVuOcHL7i5EFhiYgVJzjSBK7aQZWfbpXVrhuUCr0msd354gj

price_exchange = float(getticker(exchange, 'USDT-ETH')) * 2  # test 
test = selllimit('binance', 'USDT-ETH', 0.1742135, price_exchange)
print test

exit(0) 

''' 
markets = binance.load_markets()
market_symb = binance.markets['BTC/USDT'] 

print market_symb
''' 
 
''' 
print 'CCTX ', binance.fetch_balance()
'''  
''' 
print 'Binance' 
print(binance.fetch_ticker('BTC/USDT'))['info']

bittrex = ccxt.bittrex ()
markets = bittrex.load_markets ()
 
print '\n\n Bittrex'
print(bittrex.fetch_ticker('BTC/USDT'))['info']
''' 

 
''' ##
price_exchange = float(getticker(exchange, 'USDT-ETH')) * 0.466777
test = buylimit('binance', 'USDT-ETH', 0.5, price_exchange)
print test
''' 


 
''' 
getcontext().prec = 25
getcontext().rounding = 'ROUND_DOWN'

kozel = '0.0010000'  #!!!! 
kozel = kozel.rstrip("0")
print kozel 

d = Decimal(str(2.005678111224324232))
d = d.quantize(Decimal('0.0010000'))
print d
exit(0) 
'''  
 
''' 
order_one = getorder(exchange, market, 11872179)
print 'Order info (getorder)', order_one
''' 
 


'''
precision = binance_precision('USDT-NEO')
precision = precision.find('1') - 1 # what is the rounding 
format_string = '.' + str(precision) + 'f'
print precision, format_string
''' 
'''
getcontext().prec = 25
getcontext().rounding = 'ROUND_DOWN'
a = Decimal('0.075924666')
b = Decimal('0.00000100') 
c = (a/b).quantize(Decimal('1'))
print a, b, c 

z = b * int(c)
print z

exit(0) 
'''
#a = (binance_price_precise(market, 12839.22232325543))
#b = (binance_quantity_precise(market, 0.075924666))
#print a, b
'''
test = selllimit(exchange, market, 0.07592415, 22333.22)
print test 

exit(0) 

price_exchange = getticker(exchange, market) 
time.sleep(2)
price_last = get_last_price(market) 
print price_exchange, price_last
print binance_price_precise(market, price_last)

# balance = getbalance(exchange, currency)
# print balance 

print "Quantity corrected", binance_quantity_precise(market, 112.075924666)
'''
#test = selllimit(exchange, market, 0.075924, 12600.99)
#print test 

''' 
price_last = format(price_last, format_string)
print price_last
'''
#test = buylimit(exchange, 'USDT-NEO', 3, price_last)
#print test 

'''
multiple_value = Decimal(err_str[position:])
sell_qty = Decimal(sell_q_step)
multiplier = 0
if sell_qty > multiple_value:
    multiplier = int(sell_qty/multiple_value)
elif sell_qty < multiple_value:
    multiplier = 1
new_sell_qty = multiplier * multiple_value
print "Creating New Order with quantity:", new
'''

 
#price_exchange = getticker(exchange, 'USDT-ETH') 
#price_last = get_last_price('USDT-ETH') 
#print price_exchange, price_last

test = selllimit(exchange, 'USDT-BTC', 0.004543346, 23000.22)
#test = selllimit(exchange, 'USDT-BTC', 0.00400015, 22000.22)
print test

exit(0)

price_exchange = getticker(exchange, 'USDT-ETH') * 0.5
test = buylimit('binance', 'USDT-ETH', 0.2, price_exchange)
print test




''' 
price_exchange = getticker(exchange, 'USDT-ETH')
price_to_buy = float(11500.023123444324)

print price_exchange, price_to_buy 

len_use = len(str(price_exchange))  
price_to_buy = str(Decimal(price_to_buy)) 
# print 'Requested price to sell converted', price_to_buy # DEBUG 
price_to_buy = price_to_buy[:len_use]

print ">>>>", price_exchange, type(price_exchange) 
 
print ">>> TESTING BUY" 
test = buylimit(exchange, 'USDT-ETH', 0.2, price_exchange)
print '\n\n\n', test 
'''  

exit(0) 
'''
balance = getbalance('bittrex', 'USDT')
print balance['Available']

balance = getbalance('binance', 'USDT')
print balance['Available']
'''
 

''' 
print getticker(exchange, 'BTC-CTR')
# getticker ok 

balance = getbalance(exchange, currency)
print balance 
# Correctly work with decimal numbers 
balance_start  = Decimal('{0:.8f}'.format(balance['Available']))
print balance_start #DEBUG
# getbalance ok 

balances = getbalances(exchange)
print balances
# getbalances ok 
'''


'''
z = cancel(exchange, market, 2062976) 
print z
# cancel ok 
''' 
'''
print 'Order history (executed)' 
l = getorderhistory(exchange, market)
print l 
# OK 
'''
''' 
order_one = getorder(exchange, market, 2064477)
print 'Order info (getorder)', order_one
# OK 
'''
''' 
test = selllimit(exchange, market, 34, 0.001199)
print test 
# OK 
''' 
''' 
print ">>> TESTING BUY" 
test = buylimit(exchange, 'BTC-CTR', 100, 0.00002)
print '\n\n\n', test 
# OK
'''

z = getticker(exchange, 'BTC-CTR')
len_use = len(str(z))
getcontext().prec = len_use
#

dex = Decimal(z)
dex_new = str(dex)
print z, len_use, dex, dex_new[:len_use+1]


print ">>> TESTING SELL" 
test = selllimit(exchange, 'BTC-LINK', 100, 0.000055884445611)
#print '\n\n\n', test 

#test = getorderbook(exchange, market) 
#print test 

''' 
def binance_ticker(market): 
    market_str = market.split('-')
    market = market_str[1] + market_str[0]
    tickers = client.get_all_tickers()
    new_dict = {}
    for item in tickers:
       symbol = item['symbol']
       new_dict[symbol] = item['price']
    return new_dict[market]
''' 



''' 
def binance_balance(): 
    balances_return = []
    acc = client.get_account()['balances']    
    for elem in acc: 
        balance_total = elem['locked'] + elem['free']
        arr_row = {'Currency':elem['asset'], 'Balance':balance_total, 'Available':elem['free']}
        balances_return.append(arr_row)
    return balances_return
''' 
       
# balances = binance_balance()
# print balances

# print acc['balances'][1]['asset'] 
#print acc['balances'][1]['asset'] 
   
# ready 


