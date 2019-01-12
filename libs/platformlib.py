# Simplistic library to detect Nix / Win and return proper commands 
import platform 
import config 

class platformlib(object):
    def __init__(self):
        self.public = ['initialise']
        self.nix_home_folder = config.nix_folder        # where the scripts are stored if you are using Linux 
        
    def initialise(self):
        platform_run = platform.system()
        if platform_run == 'Windows': 
            cmd_init = 'start cmd /K python robot.py '
        else: 
            cmd_init = config.cmd_init
        
        return platform_run, cmd_init

