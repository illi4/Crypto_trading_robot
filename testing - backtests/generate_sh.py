import itertools

asset = 'usdjpy'
string_starter = 'gnome-terminal -e "python /home/ubuntu/Robot/current/robot.py process s oanda usdjpy'
prices_years = [
    ['112.6 80 200 500', '--start=01.01.2016:00.00 --end=01.01.2017:00.00', '2016'], 
    ['116 50 200 500', '--start=09.01.2017:00.00 --end=01.01.2018:00.00', '2017'], 
    ['112.8 10 200 500', '--start=09.01.2018:00.00 --end=08.09.2018:00.00', '2018']
]
params_group = {
    ##'buy_delta':[0.001, 0.0015, 0.002],
    ##'take_profit_threshold':['0.03 --take_profit_secondary=0.029', '0.04 --take_profit_secondary=0.039'],
    ##'strategy_confirm_high':['high --strategy_confirm_low=low', 'close --strategy_confirm_low=close'],
    ##'entry_cutoff_level':[-0.0025, -0.0035, -0.0015]
    'buy_delta':[0.002, 0.0035],
    'cutoff_confirmations_no':[1,2,3],
    'control_bars_period':['4h', '1h'],
    'rsi_higher_up_extreme': [
        '70 --rsi_lower_up_extreme=70 --rsi_higher_down_extreme=35 --rsi_lower_down_extreme=35 --rsi_higher_up_exit=75 --rsi_lower_up_exit=75 --rsi_lower_down_exit=30 --rsi_higher_down_exit=30',
        '75 --rsi_lower_up_extreme=75 --rsi_higher_down_extreme=30 --rsi_lower_down_extreme=30 --rsi_higher_up_exit=80 --rsi_lower_up_exit=80 --rsi_lower_down_exit=25 --rsi_higher_down_exit=25',
        '80 --rsi_lower_up_extreme=80 --rsi_higher_down_extreme=20 --rsi_lower_down_extreme=20 --rsi_higher_up_exit=85 --rsi_lower_up_exit=85 --rsi_lower_down_exit=15 --rsi_higher_down_exit=15'
    ]
}

keys, values = zip(*params_group.items())
experiments = [dict(zip(keys, v)) for v in itertools.product(*values)]

# Create a list of commands 
commands_list = []

for elem in prices_years: 
    i = 0
    for paramval in experiments: 
        i += 1
        codename_str = ''.join([elem[2],'_v', str(i)])
        paramstring = '--'
        paramstring += ' --'.join("%s=%r" % (key,val) for (key,val) in paramval.iteritems())
        paramstring = paramstring.replace("'", "")
        command_str = '{} {} {} {} --codename={} --core_strategy=traditional"'.format(
            string_starter, 
            elem[0], 
            elem[1],
            paramstring,
            codename_str
        )
        commands_list.append(command_str)
    
# Process the result 
for elem in commands_list: 
    print elem 
