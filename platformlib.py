import platform # for Nix / Win detection

# TD analysis
class platformlib(object):
    def __init__(self):
        self.public = ['initialise']
        self.nix_home_folder = '/home/illi4/Robot/'   # where the scripts are stored if you are using Linux 
        
    def initialise(self):
        platform_run = platform.system()
        if platform_run == 'Windows': 
            cmd_init = 'start cmd /K python robot.py '
            cmd_init_buy = 'start cmd /K python smart_buy.py '
        else: 
            # Nix. You can also add profile for gnome terminal by specifying --tab --profile NAME -e ... 
            cmd_init = 'gnome-terminal --tab -e "python ' + self.nix_home_folder + 'robot.py '   # we will also need to add params and close with " later 
            cmd_init_buy = 'gnome-terminal --tab -e "python ' + self.nix_home_folder + 'smart_buy.py '  # --profile Active could be added
        
        return platform_run, cmd_init, cmd_init_buy

