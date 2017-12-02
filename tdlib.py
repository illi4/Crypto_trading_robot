import time
from time import localtime, strftime
from sys import exit, argv
import pandas as pd 

import warnings
warnings.filterwarnings("ignore")

# TD analysis
class tdlib(object):
    def __init__(self):
        self.public = ['stats']
        
    def stats(self, market, period = '1h', nentries = 100000, tail = 10):
        # example period = '5min' , '1h' 
        filename = 'price_log/' + market + '.csv'
        try: 
            transactions_all = pd.read_csv(filename, skiprows=1, names=['timestamp','price']).set_index('timestamp')
        except: 
            return None 
        transactions_all.index = pd.to_datetime(transactions_all.index, unit='s')  
        transactions_all.index = transactions_all.index + pd.Timedelta('11:00:00')  # convert to Sydney time 
        transactions = transactions_all.tail(nentries)   # take the last N of 30-sec records
        
        bars = transactions.price.resample(period).ohlc()   
        
        # Initial conditions 
        bearish_flip = False 
        bullish_flip = False 
        setup_up = 0 
        setup_down = 0 
        
        size = bars['close'].size
        # print "TDLib: Bars df size:", size
        
        bars.loc[:, 'td_setup'] = None    # additional column: td setup number 
        bars.loc[:, 'td_direction'] = None  # td setup direction 
        bars.loc[:, 'td_perfected'] = None # td setup perfection
        bars.loc[:, 'td_next_beyond'] = None # whether a candle with number 2 or later is going beyond 1      
        bars.loc[:, 'td_down_1_high'] = None # for the bearish setup storing info on 1's high       
        bars.loc[:, 'td_up_2_cl_abv_1'] = None # for the bullish setup checking if 2 closed higher than 1  
        bars.loc[:, 'td_up_2_close'] = None # for the further comparison  

        # Initial direction and values 
        direction_up = False 
        direction_down = False 
        nextbar_beyond = False 
        up_2_cl_abv_1 = False
        td_up_2_close = None
        td_down_1_high = None

        if (bars['close'].iloc[5] > bars['close'].iloc[4]): 
            direction_up = True
        elif (bars['close'].iloc[5] < bars['close'].iloc[4]): 
            direction_down = True 
            td_down_1_high = bars['high'].iloc[0]
         
        ## Getting through an array (data) and calculating values 
        for i in range(0 + 6, size): # 6 candles are needed for detecting the first price flip 
            
            ## Price flip 
            bearish_flip = False 
            bullish_flip = False 

            if setup_up == 9: 
                setup_up = 0 # restart count 
                nextbar_beyond = False 
            if setup_down == 9: 
                setup_down = 0 # restart count 
                nextbar_beyond = False 
            
            if (bars['close'].iloc[i - 1] > bars['close'].iloc[i - 5]) and (bars['close'].iloc[i] < bars['close'].iloc[i - 4]): 
                bearish_flip = True     #bearish flip
                nextbar_beyond = False 
                direction_down = True           
                bullish_flip = False 
                
            if (bars['close'].iloc[i - 1] < bars['close'].iloc[i - 5]) and (bars['close'].iloc[i] > bars['close'].iloc[i - 4]): 
                bullish_flip = True     #bullish flip
                td_up_2_close = None 
                up_2_cl_abv_1 = False 
                nextbar_beyond = False 
                direction_up = True        
                bearish_flip = False 
           
            if bearish_flip and direction_up: 
                #print 'Bearish flip 1', bars['close'].index[i]
                direction_up = False
                setup_down = 1 
                td_down_1_high = bars['high'].iloc[i]
                
            if bullish_flip and direction_down: 
                #print 'Bullish flip 1', bars['close'].index[i]
                direction_down = False      
                setup_up = 1 
            
            ## TD Setup (sequential) 
            if direction_down and not bearish_flip: 
                if (bars['close'].iloc[i] > bars['close'].iloc[i - 4]):   # restarting if a condition is not met 
                    setup_down = 1
                    nextbar_beyond = False
                else: 
                    setup_down += 1
                #print "Bearish CD ",  setup_down, bars['close'].index[i]
            
            if direction_up and not bullish_flip: 
                if (bars['close'].iloc[i] < bars['close'].iloc[i - 4]):  # restarting if a condition is not met 
                    setup_up = 1
                    nextbar_beyond = False
                else: 
                    setup_up += 1
                #print "Bullish CD ",  setup_up, bars['close'].index[i]
            
            ## Check when 2 or later gets traded beyond 1 
            if (direction_down and (setup_down > 1) and (bars['low'].iloc[i] < bars['low'].iloc[i - setup_down + 1])): 
                nextbar_beyond = True   #print "Next red is trading below 1" 
            if (direction_up and (setup_up > 1) and (bars['high'].iloc[i] > bars['high'].iloc[i - setup_up + 1])):
                nextbar_beyond = True    # print "Next green is trading above 1" 

            ## Check when 2 closes higher than 1 for the bullish setup, also store 2 close 
            if (direction_up and (setup_up == 2)):
                td_up_2_close = bars['close'].iloc[i]
                if (bars['close'].iloc[i] > bars['close'].iloc[i - 1]):
                    up_2_cl_abv_1 = True
            
            # Perfected buy of sell 
            # TD buy setup 
            if setup_down == 9: 
                if ((bars['close'].iloc[i] <= bars['close'].iloc[i - 2]) and (bars['close'].iloc[i] <= bars['close'].iloc[i - 3])) or  \
                ((bars['close'].iloc[i - 1] <= bars['close'].iloc[i - 2]) and (bars['close'].iloc[i - 1] <= bars['close'].iloc[i - 3])): 
                    #print 'Perfected buy'   
                    bars['td_perfected'].iloc[i] = True
      
            # TD sell setup 
            if setup_up == 9: 
                if ((bars['close'].iloc[i] >= bars['close'].iloc[i - 2]) and (bars['close'].iloc[i] >= bars['close'].iloc[i - 3])) or  \
                ((bars['close'].iloc[i - 1] >= bars['close'].iloc[i - 2]) and (bars['close'].iloc[i - 1] >= bars['close'].iloc[i - 3])): 
                    #print 'Perfected sell'
                    bars['td_perfected'].iloc[i] = True
            
            # Updating the dataframe 
            if direction_down:
                bars['td_setup'].iloc[i] = setup_down
                bars['td_direction'].iloc[i] = 'down' 
                bars['td_down_1_high'].iloc[i] = td_down_1_high
            if direction_up: 
                bars['td_setup'].iloc[i] = setup_up
                bars['td_direction'].iloc[i] = 'up' 
                bars['td_up_2_cl_abv_1'].iloc[i] = up_2_cl_abv_1
                bars['td_up_2_close'].iloc[i] = td_up_2_close
            # common for any direction     
            bars['td_next_beyond'].iloc[i] = nextbar_beyond
        
        # Return all except for the last one because we need info on the whole period not just the part                 
        return bars.tail(tail)[:-1]    
        
    
