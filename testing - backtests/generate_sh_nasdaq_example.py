import itertools

asset = 'nasdaq'
string_starter = 'gnome-terminal -e "python /home/ubuntu/Robot/current/robot.py process s oanda nasdaq'
prices_years = [
    ['6471 100000 5000 500', '--start=01.01.2018:00.00 --end=27.08.2018:00.00', '2018'], 
    ['4900 10000 1000 500', '--start=05.01.2017:00.00 --end=01.01.2018:00.00', '2017'], 
    ['4610 10000 1000 500', '--start=24.12.2015:00.00 --end=01.01.2017:00.00', '2016']
]
params_group = {
    #'in_profit_tp':[0.005, 0.0025, 0.0035, 0.0065], 
    #'in_profit_tp_cut':[0.0045, 0.002, 0.003, 0.006], 
    'limit_losses':[ 
        '1 --limit_losses_val=0.005', 
        '1 --limit_losses_val=0.01', 
        '1 --limit_losses_val=0.003',
        '1 --limit_losses_val=0.015', 
        '1 --limit_losses_val=0.02'
    ] 
    #'take_profit_threshold':['0.05 --take_profit_secondary=0.049', '0.03 --take_profit_secondary=0.029', 
    #                         '0.07 --take_profit_secondary=0.069'], 
    #'strategy_confirm_high':['high --strategy_confirm_low=low', 'close --strategy_confirm_low=close'],
    #'entry_cutoff_level':[-0.0035, -0.0015, -0.0055], 
    #'cutoff_confirmations_no':[1,2,3], 
    #'rsi_higher_up_extreme': [
    #    '70 --rsi_lower_up_extreme=70 --rsi_higher_down_extreme=35 --rsi_lower_down_extreme=35 --rsi_higher_up_exit=75 --rsi_lower_up_exit=75 --rsi_lower_down_exit=30 --rsi_higher_down_exit=30',
    #    '75 --rsi_lower_up_extreme=75 --rsi_higher_down_extreme=30 --rsi_lower_down_extreme=30 --rsi_higher_up_exit=80 --rsi_lower_up_exit=80 --rsi_lower_down_exit=25 --rsi_higher_down_exit=25',
    #    '80 --rsi_lower_up_extreme=80 --rsi_higher_down_extreme=20 --rsi_lower_down_extreme=20 --rsi_higher_up_exit=85 --rsi_lower_up_exit=85 --rsi_lower_down_exit=15 --rsi_higher_down_exit=15' 
    #]
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
