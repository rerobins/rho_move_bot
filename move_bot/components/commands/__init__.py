from move_bot.components.commands.configure_client_details import configure_client_details
from move_bot.components.commands.configure_access_token import configure_access_token
from move_bot.components.commands.fetch_from_month import fetch_from_month

from sleekxmpp.plugins.base import register_plugin


def load_commands():
    register_plugin(configure_client_details)
    register_plugin(configure_access_token)
    register_plugin(fetch_from_month)
