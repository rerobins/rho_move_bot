from move_bot.components.commands.configure_client_details import configure_client_details
from move_bot.components.commands.configure_access_token import configure_access_token

from sleekxmpp.plugins.base import register_plugin


def load_commands():
    register_plugin(configure_client_details)
    register_plugin(configure_access_token)
