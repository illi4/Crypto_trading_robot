### IMPORTS

import sqlite3
from datetime import datetime, timedelta
from sys import exit
import matplotlib.pyplot as plt
from matplotlib.pylab import rcParams
import backtest
import libs.sqltools as sqltools
import libs.tdlib as tdlib
from multiprocessing import Pool
import argparse

# ML Stuff
import pickle
import xgboost as xgb
import pandas as pd
import numpy as np
from xgboost.sklearn import XGBClassifier
from sklearn.model_selection import KFold, train_test_split, GridSearchCV
from sklearn.metrics import precision_score, f1_score

''' 
import os
os.environ["PATH"] += os.pathsep + 'C:/Program Files (x86)/Graphviz2.38/bin/'
'''

b_test = backtest.backtesting()
sql = sqltools.sql()
td_info = tdlib.tdlib()

### PARAMS SET UP ###
# Number if you only want to train on a cut from the dataset. Otherwise put None

limit_dataset =  None
boost_rounds = 500 #  this is ok
early_stopping = 50 # tune this

### Set optimisation params for gridsearch here
# Tuning sequence see https://www.analyticsvidhya.com/blog/2016/03/complete-guide-parameter-tuning-xgboost-with-codes-python/
def set_gridsearch_params():
    params = {
        'n_estimators':[30],
        'max_depth':[9],
        'min_child_weight':[1],
        'gamma':[0.0],
        'subsample':[i/10.0 for i in range(6,10)],
        'colsample_bytree':[i/10.0 for i in range(6,10)]
        # 'subsample':[0.95],
        # 'colsample_bytree':[0.95],
    }
    return params

### Set the best parameters here when step 2 is finished
def set_best_params():
    best_params = {
        'max_depth': 9,
        'min_child_weight': 1,
        'gamma': 0.0,
        'subsample': 0.95,
        'colsample_bytree': 0.95,
        'reg_alpha': 0.001,
        'learning_rate': 0.01,  # fixed
        'silent': 1,  # logging mode - quiet
        'objective': 'multi:softprob',  # error evaluation for multiclass training
        'num_class': 3 # the number of classes that exist in this datset
    }
    return best_params

###### Functions ######

### Data preparation ###
def df_perc_calc(df):
    # close percent change
    df['close_shifted'] = df['close'].shift(1)
    df['close_percent_change'] = 100*(df['close'] - df['close_shifted'])/df['close']
    # rsi percent change
    df['rsi_shifted'] = df['rsi'].shift(1)
    df['rsi_percent_change'] = 100*(df['rsi'] - df['rsi_shifted'])/df['rsi']   # New
    # High to close and low to close should be a feature (could be useful)
    df['high_to_close'] = df['high']/df['close']
    df['low_to_close'] = df['low']/df['close']
    # Close below/above MAs or % to MA should be a feature (%)
    df['close_to_ma10'] = df['close']/df['ma_10']
    df['close_to_ma20'] = df['close']/df['ma_20']
    try: #to skip 30d if there are errors
        df['close_to_ma30'] = df['close']/df['ma_30']
    except:
        pass
    # Change to numeric
    df['td_direction'] = (df['td_direction'] == 'green').astype(int)        # 1 for green, 0 for red

    # Drop unnecessary columns
    for colname in ['open', 'high', 'low', 'close', 'move_extreme','close_shifted', 'rsi_shifted']:  #, 'if_countdown_up', 'if_countdown_down']:
        df.drop(colname, axis=1, inplace=True)

    return df.tail(1)

### Check if current time is in trading hours for the traditional market
def is_trading_hours(b_test, exchange_abbr):

    curr_date_time = datetime.strptime(b_test.strftime("%d-%m-%Y %H:%M"), "%d-%m-%Y %H:%M")
    curr_hour = (b_test.strftime("%H"))

    # Syd time: closing Sat 8am, opening Mon 8am, plus extra few hours just in case
    if exchange_abbr == 'oanda':
        weekday = curr_date_time.weekday()
        if (weekday == 5 and curr_hour >= 7) or (weekday == 6) or (weekday == 0 and curr_hour <= 9):
            return False
        else:
            return True
    else:
        return True
 
##################
def item_analyse(point):

    date_point = point[0]  # need to get data half through the 1h candle
    exchange = point[1]
    market = point[2]

    period_arr =  ['1h', '4h', '1d'] # ['1h', '4h', '12h', '1d']
    bars_temp = None

    skip_adding = False

    #try:
    conn = sqlite3.connect("workflow.db")
    for period in period_arr:
        print("Date/time {}, period {}".format(point, period))

        # Bars - this is ok
        b_test.init_testing(date_point, date_point + timedelta(days = 15), exchange, market)  # to enable backtesting; 10 days because of data quality / breaks
        # ^ values will be calculated until exaclty the timestamp related to the data point (!)
        td_info.init_source(b_test) # for testing

        barsb = td_info.stats(market, exchange, period, 0, 2, True, b_test=b_test)  # this works fine;
        # ^ need 2 for close percent change

        #print(barsb.tail())

        # Checks for 1H
        if (period == '1h'):
            compare_right_h = int(barsb.index.tolist()[1].hour)   # taking the second (last) index
            compare_left_h = int(date_point.hour)
            compare_right_day = int(barsb.index.tolist()[1].day)
            compare_left_day = int(date_point.day)
            if (compare_left_h !=  compare_right_h) or ((compare_right_day != compare_left_day) and (compare_right_h == compare_left_h)):
                print('(i) skipping because of incomplete data: D{}-H{} vs index D{}-H{}'.format(
                    compare_left_day, compare_left_h, compare_right_day, compare_right_h))
                skip_adding = True
                pass

        if not skip_adding:
            bars_ma_30 = td_info.stats_MA_only(market, exchange, period, 30, 0, 2, False, b_test = b_test)  # comment if do not need 30ma
            barsb['ma_30'] = bars_ma_30

            bars_ma_20 = td_info.stats_MA_only(market, exchange, period, 20, 0, 2, False, b_test = b_test)
            bars_ma_10 = td_info.stats_MA_only(market, exchange, period, 10, 0, 2, False, b_test = b_test)

            barsb['ma_20'] = bars_ma_20
            barsb['ma_10'] = bars_ma_10
            barsb = df_perc_calc(barsb)   # get values

        # Reset index
        barsb.reset_index(drop=True, inplace=True)

        barsb.columns = [str(col) + '_' + period for col in barsb.columns]

        if bars_temp is None:
            bars_temp = barsb.copy()
        else:
            bars_temp = pd.concat([bars_temp, barsb], axis=1)

    if not skip_adding:
        # Add index back (and label)
        bars_temp['timestamp'] = date_point
        bars_temp.set_index('timestamp', inplace=True)
        bars_temp['exchange'] = exchange
        bars_temp['market'] = market

        #print bars_temp.head()

        bars_temp.to_sql("labels_generated", conn, if_exists='append')  # replace or append !!!!!!!!!!!!!!!!

    conn.commit()
    conn.close()

    #except:
    #    print "Error for the datapoint processing"

    return None


# Function to generate data points and save them in DB - working Ok
def generate_datapoints(time_date, finish_date, exchange_abbr, market, processors_no):

    pools_no = processors_no*4        # c5.18xlarge has 72 processors

    #b_test.init_testing(time_date, finish_date, exchange_abbr, market)   # to enable backtesting
    #td_info.init_source(b_test) # for testing

    bars_result = None

    p = Pool(pools_no) # multiprocessing
    time_interval = 30   # in minutes to add

    i = 0

    while time_date < finish_date:
        # Generate time intervals
        curr_set = []
        for pool_r in range(0, time_interval*pools_no, time_interval):
            curr_set.append([time_date + timedelta(minutes =pool_r), exchange_abbr, market])

        # Threading
        p.map(item_analyse, curr_set)
        time_date += timedelta(minutes=time_interval*pools_no)

        # DEBUG block
        '''
        item_analyse(curr_set[0])
        time_date += timedelta(minutes=time_interval*pools_no)
        i += 1
        if i > 15:
            exit(0)
        '''

### Input check
def check_input_var(exch_abbr, market, pickle_name, file_name_labels, step, processors_no, step_0_start_date, step_0_finish_date, modelname):

    if step is None:
        return False

    if step == 0:
        if None in [exch_abbr, market, file_name_labels, processors_no, step_0_start_date, step_0_finish_date]:
            return False
    elif step == 1:
        if None in [exch_abbr, market, pickle_name, file_name_labels, step_0_start_date, step_0_finish_date]:
            return False
    elif step == 2:
        if None in  [pickle_name]:
            return False
    elif step == 3:
        if None in [pickle_name, modelname]:
            return False

    return True

### Process the input
def process_input():

    file_name_labels_validate, pickle_validate = None, None

    # Input params reminder
    start_text = '''
> ML workflow 
--step: 0, 1, 2, 3
   0: generate datapoints from start date to finish date appending to DB with 30min intervals
   1: glue generated points with labels and save to pickle 
   2: model tuning  
   3: model finalisation and saving 
--exch [all steps]: oanda / bmex  
--market [all steps]: e.g. USD-BTC 
--pickle [step 1-3]: pickle_name (e.g. btc_data) 
--pickle_validate [step 1-3]: pickle_name for validation set (e.g. btc_data_validate) 
--labels [step 1]: filename - interval data (e.g. ML/interval_data.csv)
--validate_labels [step 1]: filename - interval data for validation (e.g. ML/interval_data_validate.csv)
--proc [step 0]: number of processors for calc on step 0. E.g. c5.18xlarge has 72 processors
--start [step 0-1]: date (format 2016-12-15-00:25)
--end [step 0-1]: date (format 2018-09-20-00:55)
        '''
    print(start_text)

    # Parse input params
    parser = argparse.ArgumentParser()
    parser.add_argument('--exch', type=str, help="Exchange (oanda / bmex)")
    parser.add_argument('--market', type=str, help="Market (e.g. USD-BTC)")
    parser.add_argument('--pickle', type=str, help="Pickle_name (e.g. btc_data)")
    parser.add_argument('--pickle_validate', type=str, help="Pickle_name for validation (e.g. btc_data_validate)")
    parser.add_argument('--labels', type=str, help="Filename - interval data train/test (e.g. interval_data.csv)")
    parser.add_argument('--validate_labels', type=str, help="Filename - interval data, validation dataset (e.g. interval_data_validate.csv)")
    parser.add_argument('--step', type=int, help="Workflow step")
    parser.add_argument('--proc', type=int, help="Number of processors")
    parser.add_argument('--start', type=str)
    parser.add_argument('--end', type=str)
    parser.add_argument('--modelname', type=str)

    args, unknown = parser.parse_known_args()
    exch_abbr = getattr(args, 'exch')
    market = getattr(args, 'market')

    pickle_name = getattr(args, 'pickle')
    pickle_validate = getattr(args, 'pickle_validate')

    file_name_labels = getattr(args, 'labels')
    file_name_labels_validate = getattr(args, 'validate_labels')

    step = getattr(args, 'step')
    processors_no = getattr(args, 'proc')
    start_date = getattr(args, 'start')
    end_date = getattr(args, 'end')
    modelname = getattr(args, 'modelname')

    if start_date is not None and end_date is not None:
        step_0_start_date = datetime.strptime(start_date, '%Y-%m-%d-%H:%M')
        step_0_finish_date = datetime.strptime(end_date, '%Y-%m-%d-%H:%M')
    else:
        step_0_start_date, step_0_finish_date = None, None

    print(
        "Input: exchange {}, market {}, pickle_name {}, file_name labels {}, validation {}\nStep {}, processors {} model {}\n\n> Dates {} - {}".format(
            exch_abbr, market, pickle_name, file_name_labels, file_name_labels_validate, step, processors_no, modelname,
            step_0_start_date, step_0_finish_date
        ))

    # Check input
    check_input_ok = check_input_var(exch_abbr, market, pickle_name,
        file_name_labels, step, processors_no,
        step_0_start_date, step_0_finish_date, modelname)

    if not check_input_ok:
        print("Specify the input")
        exit(0)

    return exch_abbr, market, pickle_name, file_name_labels, step, processors_no, modelname, step_0_start_date, step_0_finish_date, file_name_labels_validate, pickle_validate

### Plot results
def plot_train_results(progress):

        global pickle_validate

        eval_result = progress['eval']['merror']
        train_result = progress['train']['merror']
        x_range = list(range(1, len(progress['eval']['merror']) + 1, 1))
        p1 = plt.plot(x_range,eval_result, c='blue', label='eval')
        p2 = plt.plot(x_range,train_result, c='orange', label='train')

        if pickle_validate is not None:
            validate_result = progress['validation']['merror']
            p3 = plt.plot(x_range,validate_result, c='red', label='validate')

        plt.xlabel("Rounds")
        plt.ylabel("Error")
        plt.legend(loc='upper right')
        plt.show()

### Intervals and labels
def intervals_labels(db_name, labels_file, pickle_to_save):

        print("Generating a pickle for {}:{}".format(labels_file, pickle_to_save))

        labels_arr = pd.read_csv(labels_file) #, names=['timestamp','label']).set_index('timestamp')

        arr_labels = []
        for index, row in labels_arr.iterrows():
            date_start = datetime.strptime(row['start'], '%d-%m-%Y %H:%M')
            date_end = datetime.strptime(row['end'], '%d-%m-%Y %H:%M')
            time_range = pd.date_range(date_start, date_end, freq='30min')
            for x in time_range:
                try:
                    arr_labels.append([str(x), int(row['label'])])
                except:
                    pass

        arr_labels = pd.DataFrame(arr_labels, columns=['timestamp', 'label'])

        conn = sqlite3.connect(db_name)
        sql_text = "SELECT * FROM labels_generated where market = '{}' and exchange = '{}'".format(market, exch_abbr)
        train = pd.read_sql(sql_text, conn, index_col='timestamp')

        train.index = pd.to_datetime(train.index)
        train = train.sort_index()

        conn.close()

        # Glue this with btc_data_points_30min, each should be within the range
        labeled_dataset = None

        for index, row in arr_labels.iterrows():
            timest_conv = datetime.strptime(row['timestamp'], '%Y-%m-%d %H:%M:%S')
            print(">", index, row['label'], timest_conv)

            bars_tmp = train[train.index < timest_conv][-1:] # get only the last point; put this into new df

            #bars_tmp.reset_index(drop=True, inplace=True)
            bars_tmp['label'] = row['label']
            if labeled_dataset is None:
                labeled_dataset = bars_tmp.copy()
            else:
                labeled_dataset = labeled_dataset.append(bars_tmp.copy())

        print(labeled_dataset.info())
        print(labeled_dataset.head())

        labeled_dataset.to_pickle(pickle_to_save)

### Dataset prepare
def dataset_prepare(pickle_name):

    train = pd.read_pickle(pickle_name)  # load from prepared
    #train['label'] = pd.to_numeric(train['label'], errors='coerce')    # it is numeric
    target = 'label'

    train.dropna(inplace=True)

    # If we need to limit the dataset
    if limit_dataset is not None:
        train = train[:limit_dataset]

    # Print size
    print("> Dataset size:", len(train), "records\n-----------------")

    # Due to missing points and types (absolute values like MA)
    columns_drop = [
        'ma_10_1h', 'ma_20_1h', 'ma_30_1h',
        'ma_10_4h', 'ma_20_4h', 'ma_30_4h',
        'ma_10_12h', 'ma_20_12h', 'ma_30_12h',
        'ma_10_1d', 'ma_20_1d', 'ma_30_1d',
        'market', 'exchange'
    ]
    for colname in columns_drop:
        try:
            train.drop(colname, axis=1, inplace=True)
        except:
            pass

    #Choose all predictors
    X_col = [x for x in train.columns if x not in target]
    Y_col = [x for x in train.columns if x in target]

    X = train[X_col]
    Y = train[Y_col]

    print(X.tail())
    print(Y.tail())

    return X, Y

### Train and test prepare
def train_test_prepare(pickle_name):

    '''
    train = pd.read_pickle(pickle_name)  # load from prepared
    #train['label'] = pd.to_numeric(train['label'], errors='coerce')    # it is numeric
    target = 'label'

    train.dropna(inplace=True)

    # If we need to limit the dataset
    if limit_dataset is not None:
        train = train[:limit_dataset]

    # Print size
    print("> Dataset size:", len(train), "records\n-----------------")

    # Due to missing points and types (absolute values like MA)
    columns_drop = [
        'ma_10_1h', 'ma_20_1h', 'ma_30_1h',
        'ma_10_4h', 'ma_20_4h', 'ma_30_4h',
        'ma_10_12h', 'ma_20_12h', 'ma_30_12h',
        'ma_10_1d', 'ma_20_1d', 'ma_30_1d',
        'market', 'exchange'
    ]
    for colname in columns_drop:
        try:
            train.drop(colname, axis=1, inplace=True)
        except:
            pass

    #Choose all predictors
    X_col = [x for x in train.columns if x not in target]
    Y_col = [x for x in train.columns if x in target]

    X = train[X_col]
    Y = train[Y_col]

    print(X.tail())
    print(Y.tail())
    '''

    X, Y = dataset_prepare(pickle_name)

    X_train, X_test, y_train, y_test = train_test_split(X, Y, test_size=0.3, random_state=42)

    dtrain = xgb.DMatrix(X_train, label=y_train)
    dtest = xgb.DMatrix(X_test, label=y_test)

    return dtrain, dtest, X_train, X_test, y_train, y_test

### Validation set prepare
def validation_prepare(pickle_name):
    X, Y = dataset_prepare(pickle_name)
    dval = xgb.DMatrix(X, label=Y)

    return dval, X, Y


### Gridsearch
def gridsearch_run(X_train, y_train):

    # Default classified which will be tuned
    xgb_model = XGBClassifier(
        n_estimators=100,
        max_depth=8,
        min_child_weight=1,
        gamma=0,
        subsample=0.5,
        colsample_bytree=0.5,
        learning_rate=0.1, # ok for Gridsearch
        objective='multi:softprob',
        silent=True,
        nthread=1,
        num_class=3
        )

    # A parameter grid for XGBoost
    params = set_gridsearch_params()

    clf = GridSearchCV(xgb_model,
        params,
        cv=list(KFold(n_splits=5, shuffle=True).split(X_train)), # at least 5 splits
        verbose=2,
        scoring='neg_log_loss',
        n_jobs=-1
        )

    grid_result = clf.fit(X_train, y_train.values.ravel())

    print("\n\nBest score: %f using %s" % (grid_result.best_score_, grid_result.best_params_))
    means = grid_result.cv_results_['mean_test_score']
    stds = grid_result.cv_results_['std_test_score']
    params = grid_result.cv_results_['params']
    print("\nStats:")
    for mean, stdev, param in zip(means, stds, params):
        print("%f (%f) with: %r" % (mean, stdev, param))

### Train - test and save
def train_test():
    # Using the result
    params = set_best_params()

    if pickle_validate is None:
        watchlist =  [(dtest, 'eval'), (dtrain, 'train')]
    else:
        watchlist =  [(dtest, 'eval'), (dtrain, 'train'), (dvalidate, 'validation')]

    progress = dict()

    # Train and predict with early stopping
    xg_reg = xgb.train(
        params=params,
        dtrain=dtrain, num_boost_round=boost_rounds,
        evals=watchlist,    # using validation on a test set for early stopping; ideally should be a separate validation set
        early_stopping_rounds=early_stopping,
        evals_result=progress)

    # Plots
    plot_train_results(progress)

    ypred = np.array(xg_reg.predict(dtest))
    ypred_transformed = np.argmax(ypred, axis=1)

    #print ypred_transformed
    #print y_test.values.ravel()

    print('Precision', precision_score(y_test, ypred_transformed, average=None))
    print('F1', f1_score(y_test, ypred_transformed, average=None))
    importance = xg_reg.get_score(importance_type='gain')

    print('Feature importance')
    for elem in importance:
        print(elem)

    #Save the model
    xg_reg.save_model('models/{}.model'.format(modelname))


### MAIN ###
if __name__ == "__main__":

    # Pre: input
    exch_abbr, market, pickle_name, file_name_labels, step, processors_no, modelname, step_0_start_date, step_0_finish_date, file_name_labels_validate, pickle_validate = process_input()

    # 0. Create features set
    if step == 0:
        generate_datapoints(step_0_start_date, step_0_finish_date, exch_abbr, market, processors_no) # do this for training points mapping to features, preferably on AWS

    # 1. Read labels intervals file to generate labels
    if step == 1:
        # Train/test - always
        intervals_labels("workflow.db", file_name_labels, pickle_name)
        # Validation: if provided (preferably)
        if file_name_labels_validate is not None:
            print("Generating a pickle for the validation set")
            intervals_labels("workflow.db", file_name_labels_validate, pickle_validate)

    # 2: Load data points prepared on the step 0
    if (step == 2) or (step == 3):
        # Train / test
        dtrain, dtest, X_train, X_test, y_train, y_test  = train_test_prepare(pickle_name)
        # Validation
        if pickle_validate is not None:
            print('Adding the validation set')
            dvalidate, X_validate, Y_validate = validation_prepare(pickle_validate)


    # 2: Gridsearch
    if (step == 2): 
        gridsearch_run(X_train, X_test, y_train, y_test )
 
    # 3: Finish up and save the model 
    if step == 3:
        train_test()