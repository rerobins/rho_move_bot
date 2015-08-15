import logging
import moves
from sleekxmpp.plugins.base import base_plugin
from move_bot.components.configuration_enums import IDENTIFIER_KEY, CLIENT_SECRET_KEY, CLIENT_TOKEN_KEY

logger = logging.getLogger(__name__)

class ConfigureAccessToken(base_plugin):
    """
    Plugin that will configure the client details for the service to connect to the google apis.
    """

    name = 'configure_access_token'
    description = 'Configure Access Token'
    dependencies = {'xep_0050', 'rho_bot_configuration'}

    def plugin_init(self):
        self.xmpp.add_event_handler('session_start', self._start)

    def _start(self, event):
        """
        Notify the command service of all commands that this plugin will provide.
        :param event:
        :return:
        """
        self.xmpp['xep_0050'].add_command(node=self.name, name='Configure Access Token', handler=self._starting_point)

    def _starting_point(self, iq, initial_session):
        """
        Create the form that asks for the clientId, clientSecret,
        :param iq:
        :param initial_session:
        :return:
        """
        form = self.xmpp['xep_0004'].make_form()

        previous_identifier = self.xmpp['rho_bot_configuration'].get_value(IDENTIFIER_KEY, 'unset')
        previous_secret = self.xmpp['rho_bot_configuration'].get_value(CLIENT_SECRET_KEY, 'unset')

        moves_client = moves.MovesClient()
        moves_client.client_id = previous_identifier
        moves_client.client_secret = previous_secret

        form.add_field(var='login', ftype='fixed', label='Access Login',
                       desc='Authorization URL',
                       required=True,
                       value=moves_client.build_oauth_url())
        form.add_field(var='token', ftype='text-single', label='Client Token URL Response',
                       desc='Client Token',
                       required=True,
                       value='')

        initial_session['payload'] = form
        initial_session['next'] = self._process_initial_form
        initial_session['has_next'] = False
        initial_session['moves'] = moves_client

        return initial_session

    def _process_initial_form(self, payload, session):
        """
        Copy the contents out of the session form and place it in the configuration details of this bot.
        :param payload:
        :param session:
        :return:
        """
        from urlparse import urlparse, parse_qs
        mc = session['moves']

        token = payload['values']['token']

        logger.info('URL: %s' % token)
        logger.info('MC ClientId: %s' % mc.client_id)
        logger.info('MC Secret: %s' % mc.client_secret)

        # Attempt to get the proper tokens and store them in the database.
        parts = urlparse(token)
        code = parse_qs(parts.query)['code'][0]
        mc.access_token = mc.get_oauth_token(code)

        self.xmpp['rho_bot_configuration'].merge_configuration({CLIENT_TOKEN_KEY: mc.access_token})
        # TODO: Submit merge request to get the refresh token as well
        #self.xmpp['rho_bot_configuration'].merge_configuratoin({'refresh_token': mc.refresh_token})

        session['has_next'] = False
        session['payload'] = None
        session['next'] = None

        return session

configure_access_token = ConfigureAccessToken
