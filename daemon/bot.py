from telegram.ext import Updater, CommandHandler
from handlers import SigInt

class Manager(SigInt):
    def __init__(self, token):
        global bot
        super(Manager, self).__init__()
        self.__updater = Updater(token)

    def on_start(self, app):
        self.log.info("Staring polling Telegram for messages...")
        self.__updater.start_polling()
        self.log.info("Started!")

    def on_exit(self):
        self.log.info("Stopping telegram bot...")
        self.__updater.stop()
        self.log.info("Stopped!")

    def handle(self, cmd, callback):
        self.__updater.dispatcher.add_handler(CommandHandler(cmd, callback))
        return self

    @staticmethod
    def forToken(token):
        return Manager(token)
