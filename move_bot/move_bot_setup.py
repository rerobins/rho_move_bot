"""
Set up the bot for execution.
"""
from rhobot.application import Application
from move_bot.components.commands import load_commands
from move_bot.components import load_components


application = Application()

# Register all of the components that are defined in this application.
application.pre_init(load_commands)
application.pre_init(load_components)

@application.post_init
def register_plugins(bot):
    # Components
    bot.register_plugin('update_service')

    # Commands
    bot.register_plugin('configure_client_details')
    bot.register_plugin('configure_access_token')
    bot.register_plugin('fetch_from_month')
