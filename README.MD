# Trading bot 

'UAT' telegram bot token: 707003851:AAH3-v2jluWU1ItJ9AgCyTm_88sghgONpWw 
Code should be modified on UAT to use testnets instead of live - the keys for testnet are currently **hardcoded** in exch_api.py. 

## Files 

**Note**: workflow.db and models were moved to a [dropbox share](https://www.dropbox.com/sh/8zdibi63k65kndu/AAAhJMi1W5LAknhFqzSrw62Ya?dl=0). Please download them from there and put in the same folder as the repo clone for stuff to work. 

Folder **ccxt** is a fork of the huge [ccxt library](https://github.com/ccxt/ccxt) which I used to integrate exchanges such as bitmex. Note that the bitmex file is modified to add additional functionality. It would be a good idea to stop using it and just swith to pure bitmex api instead. 

Folder **libs**: 

- aux_functions.py: some of helping (auxiliary) functions for message processing, sequences checking etc. 
- coinigylib.py: class which returns price data and includes a few functions to work with price information.  
- lambobot.py: class to work with telegram 
- loglib.py: logger. used to print & log data, as well as log summaries when backtesting 
- platformlib.py: functions to detect the platform scripts are launched on and to change the terminal commands accordingly  
- sqltools.py: functions to work with sqlite 
- tdlib.py: class to perform calculations of technicals (Demark indicator, MA, RSI)
- telegramlib.py: a lib to work with telegram. can be deprecated if everything is reworked to use the python-telegram-bot lib. 

Folder **testing - various** includes some testing scripts. An important folder is **testing - backtests** where you could find a bunch of files related to backtesting: 

- td_stat_backfill.py calculates technical indicators from price log files and writes parameters in the workflow.db so that backtesting uses pre-calculated values (makes things fast). Price log should just be a csv file with timestamp and price, see examples shared [on my dropbox](https://www.dropbox.com/sh/77njh1iezxjvm3r/AAAiGKyNs06pw2TImvnwPpUza?dl=0) 
- generate_sh.py is used to generate testing bash with the combination of parameters specified there (for example, see the output test_nasdaq.sh) 
- result_transform.py is used to grab all summary logs and put them as columns in an xls file for further analysis. 

**Main folder**: 

- backtest.py is a class which enables backtesting by generating new prices and dates from the existing historical data. 
- **config.py** includes all the settings you need to configure (e.g. time zone, api keys, chat id for telegram, and so on). Timers and price analysis periods are also specified in this file. Note that the user keys are stored in the database. 
- daemon.py processes user messages and launches new scripts based on telegram commands. 
- exch_api.py includes wrappers for functions of specific exchanges (from the 'exchange' folder) so that the data has the same format to be processed by other scripts.  
- price_log_n_update.py gets price ticker for various exchanges and saves data in price_log folder + updated the current price in DB. **Note** that you need to configure the list of tokens and exchanges for which you would like to collect price data in config.py. 
- ml_workflow.py is used to generate datapoints, train and test ML models 
- robo_class.py describes the robot class and its attributes. 
- **robot.py** is the main script where the magic happens. 
- predictions_update.py analyses price information (using price log csvs) and updates predictions for used assets in the database. 
 
Ideally, you should run price_logger non-stop so that you collect historical data which is then used in time analysis. Also, you should run daemon.py which will monitor requests sent through a Telegram chat.  

## How to set things up 

After registering your API keys on exchanges, you would need to specify them in config.py. Also, if you want to use Telegram functionality, create a bot (via botfather), and configure your tokens and chat id in the same file (config.py). 

A few other tips which are important: 

- Make sure that you specify a personal chat id (not a group chat id) in the config.py
- Default terminal to launch the commands is gnome-terminal. If you do not have it, either install it in your environment or change the commands in config.py. On my machine, I am also using a separate profile which specifies that the window should be kept open after a program exits so I see if anything goes wrong. See this [stackoverflow topic](https://stackoverflow.com/questions/4465930/prevent-gnome-terminal-from-exiting-after-execution) for details. 
- If you are using Nix, ensure that you specify the correct path to scripts in config.py. 

Note that bitmex and oanda have a testnet so that you can reconfigure tokens and try these scripts without risking any of your real assets. The type would have to be changed in exch_api, though. 

### Setting a telegram bot 

Feel free to use the @Cryptotrader_illi4_bot from telegram. You would need to get the chat id for your user account by writing /my_id to telegram bot @get_id_bot. This chat id should be then specified in configs. 

Then you would need to run daemon.py (which processes telegram commands).   

### Setting an environment 

I would recommend setting up a virtual machine or using a cloud VM (AWS or Azure) so that popping screens do not distract you at your usual working environment. You would need to launch daemon.py (for processing your telegram messages) and price_logger.py (for price updates feeding to tdlib).  

## Training / testing models  

The workflow is as follows: 

**Step 0**

Generates datapoints (pre-calculated features) and saves them in workflow.db. Skip this step if you have the database populated with features already.  

Run ml_workflow.py for this with the --step=0 parameter. Example - run: 

```
python D:\Crypto\Robot\ml_workflow.py --exch=bmex --market=btc/usd --pickle=ML/btc_data_all_upd --proc=4 --start=2014-01-01-00:25 --end=2018-09-20-00:55 --step=0 
```

For nasdaq you would use --market=NAS100_USD --exch=oanda. Check out see the script output for the explanation of parameters.  

This will generate records in the workflow.db database which will be used on the next steps. 

**Step 1**

Using generated datapoints, run step 1 to read labels intervals file to generate labels and save them to pickle used to train / test the model. Same parameters but use --step=1. The pickle will be created at the path specified in --pickle (ML/btc_data_all_upd). The intervals (csv) file is specified in --labels=...

The generated data will be saved to the specified pickle file.  **Use the same --start and --end as on the step 1 or like in your labeled csv**. 

Exemplary command: 
```
python D:\Crypto\Robot\ml_workflow.py --exch=bmex --market=btc/usd --pickle=ML/btc_data_all_upd --labels=ML/interval_data_btc.csv --proc=4 --start=2014-01-01-00:25 --end=2018-09-20-00:55 --step=1
```

Except for train/test CSV, you should (ideally) have a separate CSV which will only be used for validation. If you have it, specify the paths in the command as well, like this: 
```
python D:\Crypto\Robot\ml_workflow.py --exch=bmex --market=btc/usd --pickle=ML/btc_data_all_upd --labels=ML/interval_data_btc.csv --proc=4 --start=2014-01-01-00:25 --end=2018-09-20-00:55 --step=1 --validate_labels=ML/interval_data_btc_validate.csv --pickle_validate=ML/btc_data_all_10_11_validate
```

This will create a separate pickle for further validation. 


**Step 2**

Run --step=2 which requires manipulations with the source code of ml_workflow.py. Note that you only need to input pickle and step so your command would be something like: 
```
python ml_workflow.py --pickle=ML/btc_data_all_upd --step=2
```

Go to the section ### PARAMS SET UP on the top of the script. 

Follow the instructions below and put mentioned parameters inside the set_gridsearch_params function. As soon as you complete one parameter, just fix it in params = { ...} and move to the next.  


A. Broader depth / child width: 
```
'max_depth':range(3,12,2),
'min_child_weight':range(1,6,2)
```

B. More specific depth / child width. Example: 
```
'max_depth':[8,9,10], 
'min_child_weight':[1,2,3]
```

Let's say you detected that best params are max_depth 8 and min_child_weight of 3. When you move to the next parameter tuning, fix these 2. Your params will look like: 
```
params = {
     'max_depth':[8],
     'min_child_weight':[3], 
    ...
    }
```

C. Gamma: 
```
'gamma':[i/10.0 for i in range(0,5)]
```

Note: you should have max_depth and min_child_weight specified too. For example: 
```
params = {
     'max_depth':[8],
     'min_child_weight':[3], 
     'gamma':[i/10.0 for i in range(0,5)]
    }
```

D. Sampling: 
```
'subsample':[i/10.0 for i in range(6,10)],
'colsample_bytree':[i/10.0 for i in range(6,10)] 
```

E. Sampling - more specific values. E.g.:
```
'subsample':[i/100.0 for i in range(75,90,5)],
'colsample_bytree':[i/100.0 for i in range(75,90,5)]
```

F. Reg alpha: 
```
'reg_alpha':[1e-5, 1e-2, 0.1, 1, 100]
```
 
G. More specific reg_alpha. E.g.: 
```
'reg_alpha':[0, 0.001, 0.005, 0.01, 0.05]
```

 
**Step 3**

It is preferable if you generated a validation pickle on the step 1 so that it could be used now. 

When you finished with finding the best params, look again at the code of ml_workflow.py and find the function set_best_params. In there, specify the optimal parameters you discovered. Set_best_params would look like: 
```
### Set the best parameters here when step 2 is finished
def set_best_params():
    best_params = {
        'max_depth': 8,
        'min_child_weight': 1,
        'gamma': 0.1,
        'subsample': 0.95,
        'colsample_bytree': 0.9,
        'reg_alpha': 0,
        'scale_pos_weight': 0,
        'learning_rate': 0.01, # appropriate for our XGBoost and features config 
        'silent': 1,  # logging mode - quiet
        'objective': 'multi:softprob',  # error evaluation for multiclass training
        'num_class': 3 # the number of classes that exist in this datset
    }
    return best_params
```

Then run the command from p.1 specifying --step=3 and putting the model name in --modelname=... 
You can omit other params so your command would be (if you have a validation dataset): 
```
python ml_workflow.py --pickle=ML/btc_data_all_upd --pickle_validate=ML/btc_data_all_10_11_validate --step=3 --modelname=btc_new_model 
```
If you do not have a validation pickle, just omit the --pickle_validate parameter. 

**Note that** boost_rounds and early_stopping should be tuned to prevent overfitting. Here is an example of what happend with too many boost_rounds and no early stopping - at some point train and test continue to decline but error on the validation dataset starts going up and up: 

![overfit](https://i.imgur.com/rCg0MiR.png)

Generally, put ~ 500 boost_rounds and set early_stopping to 50-100. The number of boosters should not be too low (there should be at least ~100) and not too high (not above ~300). 
It is better to generate several models with boot_rounds around 100 (e.g. 80, 100, 120, 150) and check which performs better on a backtest (see the next section on backtesting). 


**Step 4**

Make sure that you change active model name for the asset in config.py. See this block in config: 

```
# Dictionary with market parameters
param_dict  = {
    'btc/usd': {
        'model_name': 'btc_18-10-27.model',
        'feature_periods': ['1h', '4h', '1d'],
```

## Backtesting 

**(!)** Set run_testmode in config to False because it disables backtesting.

For backtesting, change 'backtesting_enabled' to True in config.py and set up the dates accordingly. Also, change use_db_labels to True (this uses pre-calculated features from the DB). Your setting should look like: 
```
## Backtesting mode
backtesting_enabled = True      # remember to switch commission to 0 when testing
backtesting_use_db_labels = True   # to use pre-calculated labels from DB or to calculate on the fly
use_testnet = True # change to true for testing
run_testmode = False     ### Testmode control if needed
```

When calling the script, almost strategy parameters with start/end dates could be passed through command line. For example, you can write a bat (or an sh) file with the following command: 

python C:\Robot\robot.py process s bmex btc/usd 400 0.5 --codename=main_backtest_2016  --start=01.01.2016:00.00 --end=31.04.2017:00.00

^ there, 400 is the entry price and 0.5 is the starting amount (btc) 

Traditional markets would be similar, e.g.: 
python C:\Robot\robot.py process s oanda usd_jpy 112.3 1000 --codename=joy_main_backtest_2016  --start=01.01.2016:00.00 --end=01.04.2017:00.00 --limit_losses=1 --limit_losses_val=0.03 --predicted_confidence_threshold=0.55
 
Other parameters you could specify are 
--limit_losses=0/1 (limit losses, config default is 0)
--limit_losses_val=0.XXXX (that's %, like 0.03 means 3%: what is the limit for limiting losses)
--predicted_confidence_threshold=0.XX (that's %, like 0.3 means 30%: what is the threshold to enter positions)
--exit_confidence_threshold=0.XX (% threshold to exit positions)
--modelname=xxxxx.model (use a different model from the models folder)

*Note*: Results will be slightly different on each run because of a random time lag in backtesting simulating delays when executing orders (2 to 10 minutes). 

**Examples** of commands and intervals (used currently): 

```
python3 /home/ubuntu/Robot/current/robot.py process s bmex btc/usd 557 0.5 --codename=btc_backtest_ml_2014_prob0.4 --start=01.01.2016:00.00 --end=01.01.2017:00.00  --predicted_confidence_threshold=0.4
python3 /home/ubuntu/Robot/current/robot.py process s bmex btc/usd 240 0.5 --codename=btc_backtest_ml_2015_prob0.4 --start=01.04.2015:00.00 --end=01.01.2016:00.00  --predicted_confidence_threshold=0.4
python3 /home/ubuntu/Robot/current/robot.py process s bmex btc/usd 400 0.5 --codename=btc_backtest_ml_2016_prob0.4 --start=01.01.2016:00.00 --end=01.01.2017:00.00  --predicted_confidence_threshold=0.4
python3 /home/ubuntu/Robot/current/robot.py process s bmex btc/usd 1100 0.5 --codename=btc_backtest_ml_2017_prob0.4 --start=02.04.2017:00.00 --end=30.03.2018:22.00  --predicted_confidence_threshold=0.4
python3 /home/ubuntu/Robot/current/robot.py process s bmex btc/usd 11600 0.5 --codename=btc_backtest_ml_2018_prob0.4 --start=06.03.2018:00.00 --end=27.10.2018:00.00  --predicted_confidence_threshold=0.4

python3 /home/ubuntu/Robot/current/robot.py process s oanda nas100_usd 6471 500 --start=01.01.2018:00.00 --end=27.10.2018:00.00 --codename=nas_2018_thr_0.5 --core_strategy=traditional --predicted_confidence_threshold=0.5
python3 /home/ubuntu/Robot/current/robot.py process s oanda nas100_usd 4900 500 --start=05.01.2017:00.00 --end=01.01.2018:00.00 --codename=nas_2017_thr_0.5 --core_strategy=traditional --predicted_confidence_threshold=0.5
```


Logs (detailed and summary) will be generated in the folder logs_trade. 

You can then run result_transform.py specifying folder with the --folder prefix. E.g.: 
```
python result_transform.py --folder="/home/ubuntu/Robot/current/results_folder"
```

This will put all the logs as columns in the file so they are easier to read and compare. The filename "results_processed.xlsx" will be created in the specified folder. 


### Editing the workflow database

This repo includes a dummy database with no records which is a sqlite database (more than enough for the purpose of personal use). You can use any software working with sqlite to edit the tables in case anything goes wrong. 
