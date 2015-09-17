import logging
from rhobot.components.commands.base_command import BaseCommand
from move_bot.components.configuration_enums import IDENTIFIER_KEY, CLIENT_SECRET_KEY
from move_bot.components.events import OAUTH_DETAILS_UPDATED


logger = logging.getLogger(__name__)

class ConfigureClientDetails(BaseCommand):
    """
    Plugin that will configure the client details for the service to connect to the google apis.
    """

    name = 'configure_client_details'
    description = 'Configure Client Details'
    dependencies = BaseCommand.default_dependencies.union({'rho_bot_configuration'})

    def post_init(self):
        super(ConfigureClientDetails, self).post_init()
        self._configuration = self.xmpp['rho_bot_configuration']

    def command_start(self, iq, initial_session):
        """
        Create the form that asks for the clientId, clientSecret,
        :param iq:
        :param initial_session:
        :return:
        """
        form = self._forms.make_form()

        previous_identifier = self._configuration.get_value(IDENTIFIER_KEY, 'unset')
        previous_secret = self._configuration.get_value(CLIENT_SECRET_KEY, 'unset')

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

        self._configuration.merge_configuration({IDENTIFIER_KEY: identifier, CLIENT_SECRET_KEY: secret})

        session['has_next'] = False
        session['payload'] = None
        session['next'] = None

        self.xmpp.event(OAUTH_DETAILS_UPDATED)

        return session

configure_client_details = ConfigureClientDetails
