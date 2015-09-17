from rhobot.bot import RhoBot
from rhobot import configuration
import optparse

from move_bot.components import load_components
from move_bot.components.commands import load_commands

load_commands()
load_components()

parser = optparse.OptionParser()
parser.add_option('-c', dest="filename", help="Configuration file for the bot", default='movebot.rho')
(options, args) = parser.parse_args()

configuration.load_file(options.filename)

bot = RhoBot()
bot.register_plugin('configure_client_details')
bot.register_plugin('configure_access_token')
bot.register_plugin('update_service')

# Connect to the XMPP server and start processing XMPP stanzas.
if bot.connect():
    bot.process(block=True)
else:
    print("Unable to connect.")
