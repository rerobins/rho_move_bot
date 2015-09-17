from move_bot.components.update_service import update_service

from sleekxmpp.plugins.base import register_plugin


def load_components():
    register_plugin(update_service)
