import pandas as pd 

from datetime import datetime


# TD analysis library
import tdlib as tdlib
td_info = tdlib.tdlib()

## Backtest import
import backtest
b_test = backtest.backtesting()

b_test.init_testing(datetime(2017, 6, 30), datetime(2017, 7, 1), 'bmex', 'usd-btc')  # to enable backtesting
barsb = td_info.stats('USD-BTC', 'bmex', '4h', 100000, 55, False, b_test = b_test)      # this works fine;

print barsb.tail(20)


#barsb = td_info.stats('USD-BTC', 'bmex', '4h', 150000, 15, True, 'BTC-USD', 'bitf')      # this works fine; 
#barsb = td_info.stats_rsi_only('USD-BTC', 'bmex', '1h', 150000, 200, False)      # this works fine; 
#barsb = td_info.stats('NEOG18', 'bmex', '1h', 150000, 10, False)      # this works fine; 
