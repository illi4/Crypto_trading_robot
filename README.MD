# Crypto trading robot

Note: If you are a customer, please do the following: 

- check the chat id for your user account by writing /my_id to telegram bot [@get_id_bot](https://telegram.me/get_id_bot) 
- create bitmex api keys with 'order' access 
- send your keys and chat id to me (illi4) in a secret chat 

As a user, you would not worry about setting a bot and configuring scripts. 

## Background 

This robot was created to help me to exit positions (trailing stops) better, to buy at more appropriate points then 'right now', and also to execute stop losses thoroughly. Out of curiosity, I have also created an integration with Telegram and implemented time analysis to predict price moves inspired by a variation of a well-performing [time series indicator](https://oxfordstrat.com/indicators/td-sequential-2/) used by Tone Vays. The scripts were written for Python 2.7 and have not been tested on Python 3. Currently, 3 exchanges are supported: bitmex, bittrex, and binance. I have not been testing the latter two for a while so I highly recommend to experiment with small amounts first if you run it on bittrex or binance. 

Provided that you are running price_logger to collect price data (see clarifications further), you can just leave the bot running for pretty much forever - it will monitor price action on candles of specified lengths (default it 4 hours and 9 hours) and will open / close long and short positions (shorts are supported on bitmex only). Current rules are set as follows: 

- Price action is analysed on shorter (4-hour) and longer (9-hour) intervals (configurable). 
- When first launched in 'initiate' mode with 'fullta' parameter, buyer() function opens a position when the indicator is consistent on both time intervals and 4h candle starts trading beyond the previous one (hereinafter - plus or minus default contingency % configured in the scripts). Both TD setup and TD countdown are analysed (countdown can be disabled in config). It does not enter on sequential 7, 8, 9 (can be configured). 
- When the job is running, profit can be taken or the position can be stopped with loss if: 
    * There is a price flip in the opposite direction on 4h (configurable), the current 4h starts trading beyond the previous one +/- a threshold (configurable), and two consecutive closes of 10-minute candles stay beyond the cut-off line. 
    * There is an exhaustion momentum indicator 9 on 4h bars (can be disabled). 
    * RSI reaches extreme values on both 4h and 1h intervals (configurable). 
    * Price falls back back to the entry point. 
    * There is an extreme move piercing through the whole price setup starting from the number one (this is highly unlikely as it stops at the entry point). 
    * Take profit value is reached and the price stops moving in the required direction. 
    * If 'limit losses' parameter is enabled and the price on 5-min intervals falls below the limit loss value. 
- After closing a position, buy_back() function is running to re-enter or open a position in the opposite direction. The automatic buyback logic is equivalent to initiating robot with the fullta parameter. If there was a case of price falling back back to the entry point, then 30-min candles are monitored to be in line with the trend from the previous stopped task (same direction, closing above each other); however, if this fallback happened two times already, scripts just start monitoring 4h and 9h candles. Note the parameter ride_pullbacks in the config. 

The image below illustrates some (but certainly not all) of this logic: 

![candles_logic](images/candles_upd_z.png?raw=true "Candles_logic")

## Files 

There are quite a number of files and folders in the repository - all of them are needed for the robot to work. All this may look confusing so here is a clarification. 

Folders:. 

- 'ccxt' is a fork of the huge [ccxt library](https://github.com/ccxt/ccxt) which I used to integrate binance and bitmex. Note that the bitmex file is modified to add additional functionality (I will commit to the original ccxt later, but you could use the one located here for now). 
- 'exchanges' includes a few libraries to work with crypto exchanges. In the current version, it is only needed for bittrex to work whereas the binance and bitmex functions were rewritten to work with ccxt. 

The following scripts are used: 

- Exch_api.py includes wrappers for functions of specific exchanges (from the 'exchange' folder) so that the data has the same format to be processed by other scripts. **Note** that your API keys for exchanges should be specified in config.py.
- Loglib.py is a library with a few logging functions. Similarly, aux_functions.py includes a few auxiliary functions used in the scripts. 
- Platformlib.py is a library to detect your OS and return proper folders to launch scripts.
- Price_logger.py gets price ticker for various exchanges from coinigy api and saves data in price_log folder. **Note** that you will need to configure the list of tokens and exchanges for which you would like to collect price data in config.py. 
- Sqltools.py included a few functions to work with workflow.db sqlite database.
- Gif.py is a wrapper for posting gifs 
- Tdlib.py is used to analyse the price data and return values of time analysis indicators.
- Telegramlib.py works with telegram messages (used mostly in daemon). **Note** that you would need to register a telegram bot and configure your tokens / chat id in config.py.
- Robo_class.py describes the robot class and its attributes. 
- Backtest.py is a class which enables backtesting by generating new prices and dates from the existing historical file. 
- **Robot.py** is a core script which performs the monitoring of position prices, sells or buys (incl. buying back), executes stop orders. 
- **Config.py** includes all the settings you need to configure (e.g. time zone, api keys, chat id for telegram, and so on). Timers and price analysis periods are also specified in this file. 
 
## Scripts logic and working scripts 

I was too busy writing the code and did not document what logic had been implemented. You could take a look at the scripts to check this out. Just briefly, the following features are implemented in robot and smart_buy scripts:

- Chat notifications when market price info is not available and sleeping until trading resumes 
- Error handling (checking if there is enough balance, sum above minimum traded amount, amount is fine, etc.) and logging or actions
- Speedrun mode and simulation mode 
- 'Quick' (5-min interval-based) analysis of confirmations on buys and sells, preventing from being shaken out easily 
- Larger-interval (currently 4H) analysis of price action based on a well-performing indicator for entering and exiting the positions as well as dynamic adjustment of stop loss 
- Dynamic price changes when buying and selling using orderbooks and time elapsed since the start of the task
- Pre-profit and post-profit buybacks after exiting the positions 
- Writing results (gains and losses) in a summary xls file 

Ideally, you should run price_logger non-stop so that you collect historical data which is then used in time analysis. Also, you should run daemon.py which will monitor requests sent through a Telegram chat. **The scripts are much more useful if you have price_logger running so that the robot can use the price data.**

## How to set things up 

After registering your API keys on exchanges, you would need to specify them in config.py. Also, if you want to use Telegram functionality, create a bot (via botfather), and configure your tokens and chat id in the same file (config.py). 

For price logging, you would need a [Coinigy](https://www.coinigy.com/) account and api keys. I really recommend using Coinigy because otherwise you could be blocked from an exchange api even if you run few robots in parallel. Generally, grabbing prices frequently from exchanges is not a proper solution as they block too frequent requests. Coinigy allows for sending requests quite often so I switched to using it. Note that you can use the robot without having price data, but this would not be as effective as results based on time analysis. 

A few other tips which are important: 

- Make sure that you specify a personal chat id (not a group chat id) in the config.py
- Default terminal to launch the commands is gnome-terminal. If you do not have it, either install it in your environment or change the commands in config.py. On my machine, I am also using a separate profile which specifies that the window should be kept open after a program exits so I see if anything goes wrong. See this [stackoverflow topic](https://stackoverflow.com/questions/4465930/prevent-gnome-terminal-from-exiting-after-execution) for details. 
- If you are using Nix, ensure that you specify the correct path to scripts in config.py. 

Note that bitmex has a testnet so that you can reconfigure tokens and try these scripts without risking any of your real crypto. 

### Setting a telegram bot 

Feel free to use the @Cryptotrader_illi4_bot from telegram. You would need to get the chat id for your user account by writing /my_id to telegram bot @get_id_bot. This chat id should be then specified in configs. 

Then you would need to run daemon.py (which processes telegram commands). When running, daemon.py would supports the following commands sent in a Telegram chat:

- auto - this is the easiest and the most productive way to use the bot. In this mode, you would need to specify contract and btc amount (for example 'usd-btc 0.15') and the robot will start doing its thing using strategy parameters defined in config. I have only been using this piece of functionality lately.   
- status - show running tasks
- new - run a new take profit (trailing stop) / stop loss task 
- abort - cancel running tasks 
- balance - check your balances on exchanges 
- initiate_position - initiate a position; various modes are supported (including buying in simulation, on breakout, in a regular mode, and immediately)
- close_position - close a position (from running tp/sl task) immediately 
- markets - show info on contracts traded on bitmex 
- workflow - launch a workflow which includes starting a buy task and then a take profit (trailing stop) / stop loss task 
- nlong - create a new record about a long-term holding without any buy/sell tasks
- rmlong - delete records from longs table (I should have probably called it hodl)
- stoplistener - stop the monitoring bot 
- help - get information on commands parameters and available commands 

You can get clarification on the modes (r/s/rnts and so on) by sending the help command to a telegram bot. 

### Setting an environment 

I would recommend setting up a virtual machine or using a cloud VM (AWS or Azure) so that popping screens do not distract you at your usual working environment. You would need to launch daemon.py (for processing your telegram messages) and price_logger.py (for price updates feeding to tdlib). Eventually, you would have an environment like this:  

![screen_example](images/screen_upd.png?raw=true "Screen")

Alternatively, you can contact me in order to configure this for you. 

### Backtesting 

For backtesting, change 'backtesting_enabled' to True in config.py and set up the dates accordingly. When calling the script, almost strategy parameters with start/end dates could be passed through command line. For example, you can write a bat (or an sh) file with the following set of commands: 

start cmd /k python C:\Robot\robot.py process s bmex usd-btc 1100 3000 300 0.5 --codename=main_backtest --td_period=2h --td_period_extended=12h --limit_loss=1


start cmd /k python C:\Robot\robot.py process s bmex usd-btc 400 3000 100 0.5 --codename=main_backtest_2016  --start=01.01.2016:00.00 --end=01.04.2017:00.00

Note that 0 or 1 is used for bool parameters. The full list of params is: 

'take_profit_threshold', 
'take_profit_secondary', 
'buy_delta', 
'entry_cutoff_level', 
'cutoff_confirmations_no', 
'ma_period', 
'td_period', 
'rsi_4h_up_extreme', 
'rsi_1h_up_extreme', 
'rsi_4h_down_extreme', 
'rsi_1h_down_extreme', 
'wait_after_losing_trade_h',
'enter_on_rsi_8020_target', 
'limit_losses_val'

And bools (call with 0\1): 
'consider_countdown', 
'resume_bback_entry_hit', 
'early_entries_enabled', 
'consider_ma', 
'trade_flips', 
'exit_on_nines', 
'limit_losses', 
'wait_after_losing_trade',
'enter_on_rsi_8020'

## Using the scripts 

### Some examples of how to use all this 

**Example 1**: You are keen to run a task in simulation mode to see how the robot works. The assumption is that you bought 30 LTC on bittrex for your BTC thinking that selling it later would be a profitable trade. Your price was 0.017, take profit target is 0.02, and stop loss level is 0.015. You only want to test it for the quantity of 20 LTC. You will then have the following lovely chat with the configured Telegram bot: 

![chat_example_1](images/chat_example_1.png?raw=true "Chat_1")

The task will be launched in simulation (even for buybacks). 

**Example 2**: Still careful with actually using this tool, you decide to test buying functionality. Let's say that you are collecting price data through price_logger and that you would like to buy based on 4-hour price action method. You are keen to buy BTC for 5500 USDT on binance for a market price on 4-hour confirmation. Then your chat would be: 

![chat_example_2](images/chat_example_2.png?raw=true "Chat_2")

Similarly, the task will be launched in simulation. 

**Example 3**: Now you see that this stuff works fine and would like to configure something more advanced. For instance, you see that BTC/USDT is looking really bullish and you would like to buy on the breakout at the level of 19650. You consider that your initial take profit target is 20000, you would like to put a tight initial stop loss at 19500, and you are going to spend 5500 USDT. Easy!

![chat_example_3](images/chat_example_3.png?raw=true "Chat_2")

Note that your stop loss will be dynamically reconfigured if you are collecting price data with the price_logger script. 

**Example 4**: You would like to set up fully automatic task which works on the USD/BTC pair on bitmex (for 0.5 btc) and enjoy life. For this, call the command /bitmex_fullta_real and then respond with 'usd-btc 0.5'. Similarly, you can do this for other contracts (e.g. 'ETHM18 0.5' where 0.5 is the value in BTC). 

**Additional examples of supported Telegram commands** :

Open long contracts on bitmex for XBT (BTC) with the total cost of 0.3 BTC (hereinafter, x times the configured margin) with the regular 5-minute candles based confirmation: 
> /buy 

> reg bmex usd-btc 0.3

Open short contracts on bitmex for Ripple (XRPH18) with the total cost of 0.1 BTC immediately: 
> /buy 

> now bmex XRPH18 -0.1 

Open short contracts on bitmex for Ripple (XRPH18) with the total cost of 0.05 BTC on the time-based (default 4H) candles confirmation: 
> /buy 

> 4h bmex XRPH18 -0.05

Buy POWR tokens on bittrex on the breakout of 0.000095 for 0.5 BTC: 
> /buy 

> brk btrx btc-powr 0.5 0.000095

For the whole balance of 25 LTC on the binance exchange, start a task with the entry price of 0.015, take profit price of 0.019, and stop loss level of 0.013. 
> /new

> r bina btc-ltc 0.015 0.019 0.013

Open long contracts for BTC on bitmex on the confirmation of bullishness on 4-hour candles for the total of 0.5 BTC, with the take profit level of 18850 and the stop loss of 15400 
> /workflow

> r bmex 18850 15400

> 4h bmex usd-btc 0.5

### Editing the workflow database

This repo includes a dummy database with no records which is a sqlite database (more than enough for the purpose of personal use). You can use any software working with sqlite to edit the tables in case anything goes wrong. 

## Terms of use and non-responsibility clause

Please use the scripts at your own risk. I am not responsible for your API keys being lost or intercepted, as well as your funds lost as a consequence of using the scripts. These scripts have some 'fool or fat fingers' protection included - however, you are fully responsible for secure storage of the scripts and for your course of actions. 

## Contributions 

As there are many other exchanges out there except for included ones, I would appreciate anyone's help in including other exchange APIs and writing a wrapper in exchange_func.py. Moreover, even scripts working with the current exchanges could be improved - in particular, bitmex commission and realised PNL calculation should be done and tested thoroughly; margin size can be calculated rather than fixed, and additional indicators could be used in combination with time analysis to make better probabilistic trades automatically. Robot messages currently do not correctly show values based on margins and also do not really reflect shorts. All this can be improved.   
Additionally, I would appreciate help in more thorough processing of price/time data and developing a predictive model using sklearn. This would require getting historical data, for example, from [kaggle](https://www.kaggle.com/mczielinski/bitcoin-historical-data), using tdlib for the calculation of parameters, and then training a model based on the data. An example of how this could be done is available at my [Enron project repository](https://github.com/illi4/Enron_fraud). 

Moreover, the code can definitely be cleaned and improved further.  

Feel free to contact me via Telegram (illi4).
