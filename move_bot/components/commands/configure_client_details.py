import logging
from sleekxmpp.plugins.base import base_plugin

logger = logging.getLogger(__name__)

class ConfigureClientDetails(base_plugin):
    """
    Plugin that will configure the client details for the service to connect to the google apis.
    """

    name = 'configure_client_details'
    description = 'Configure Client Details'
    dependencies = {'xep_0050', 'rho_bot_configuration'}

    def plugin_init(self):
        self.xmpp.add_event_handler('session_start', self._start)

    def _start(self, event):
        """
        Notify the command service of all commands that this plugin will provide.
        :param event:
        :return:
        """
        self.xmpp['xep_0050'].add_command(node=self.name, name='Configure Client Details', handler=self._starting_point)

    def _starting_point(self, iq, initial_session):
        """
        Create the form that asks for the clientId, clientSecret,
        :param iq:
        :param initial_session:
        :return:
        """
        form = self.xmpp['xep_0004'].make_form()

        previous_identifier = self.xmpp['rho_bot_configuration'].get_value('identifier', 'unset')
        previous_secret = self.xmpp['rho_bot_configuration'].get_value('secret', 'unset')

        form.add_field(var='client_id', ftype='text-single', label='Client Identifier',
                       desc='Client Identifier from Move API Console',
                       required=True,
                       value=previous_identifier)
        form.add_field(var='client_secret', ftype='text-single', label='Client Secret',
                       desc='Client Secret from Move API Console',
                       required=True,
                       value=previous_secret)

        initial_session['payload'] = form
        initial_session['next'] = self._process_initial_form
        initial_session['has_next'] = False

        return initial_session

    def _process_initial_form(self, payload, session):
        """
        Copy the contents out of the session form and place it in the configuration details of this bot.
        :param payload:
        :param session:
        :return:
        """

        identifier = payload['values']['client_id']
        secret = payload['values']['client_secret']

        logger.info('Secret: %s, Identifier: %s' % (secret, identifier))

        self.xmpp['rho_bot_configuration'].merge_configuration({'identifier': identifier, 'secret': secret})

        session['has_next'] = False
        session['payload'] = None
        session['next'] = None

        return session

configure_client_details = ConfigureClientDetails
