"""
Component of the move bot that will load up the data from the update service.
"""
import moves
from rdflib.namespace import Namespace, FOAF
from rhobot.namespace import RHO
from move_bot.test_data.robert_01 import data as test_data
from rhobot.components.storage import StoragePayload
from sleekxmpp.plugins.base import base_plugin
from rhobot.components.configuration import BotConfiguration
from move_bot.components.configuration_enums import CLIENT_SECRET_KEY, IDENTIFIER_KEY, CLIENT_TOKEN_KEY
from move_bot.components.update_service.process_segment import ProcessSegment
import logging


logger = logging.getLogger(__name__)
WGS84_POS_NAMESPACE = Namespace('http://www.w3.org/2003/01/geo/wgs84_pos#')

class UpdateService(base_plugin):

    name = 'update_service'
    description = 'Service that will update data store from move api'
    dependencies = {'rho_bot_scheduler', 'rho_bot_configuration', 'rho_bot_rdf_publish', }

    def plugin_init(self):
        """
        Initialize the plugin.
        :return:
        """
        self.xmpp.add_event_handler(BotConfiguration.CONFIGURATION_RECEIVED_EVENT, self._configuration_updated)
        # self.xmpp.add_event_handler(OAUTH_DETAILS_UPDATED, self._configuration_updated)

    def _configuration_updated(self, *args, **kwargs):
        self.xmpp['rho_bot_scheduler'].schedule_task(self._start, delay=5.0, repeat=False)

    def _start(self):
        promise = self.xmpp['rho_bot_scheduler'].defer(self._create_session)
        promise = promise.then(self._build_client)
        promise = promise.then(self._get_owner)
        promise = promise.then(self._get_data)
        promise = promise.then(self._process_data)

        # Reschedule the whole thing again
        promise.then(self._configuration_updated)

    def _build_client(self, session):
        logger.info('Creating the client')
        configuration = self.xmpp['rho_bot_configuration'].get_configuration()
        identifier = configuration.get(IDENTIFIER_KEY, None)
        secret = configuration.get(CLIENT_SECRET_KEY, None)
        client_token = configuration.get(CLIENT_TOKEN_KEY, None)

        # Validate the configuration details.
        if identifier is None or secret is None or client_token is None:
            logger.error('Configuration is not defined')
            raise RuntimeError('Configuration is not defined')

        if not self.xmpp['rho_bot_storage_client'].has_store():
            logger.error('Storage Client doesnt exist')
            raise RuntimeError('Storage Client doesn\'t exist')

        # Validate the token
        client = moves.MovesClient(identifier, secret, client_token)
        token_validity = client.tokeninfo()

        if 'error' in token_validity:
            logger.error('Token is not valid')
            raise RuntimeError('Token is not valid')

        # if all is good with the world, start executing the update thread.
        # Determine if the token should be updated or not
        logger.info('Token Validity Information: %s' % token_validity)

        session['client'] = client

        return session

    def _create_session(self):
        logger.info('Creating session')
        return dict()

    def _get_owner(self, session):
        logger.info('Getting the owner information from other bot')
        payload = StoragePayload(self.xmpp['xep_0004'].make_form(ftype='form'))
        payload.add_type(FOAF.Person, RHO.Owner)

        def set_owner_session(owner):
            logger.info('Configuring session owner')

            if owner:
                session['owner'] = owner[0]
            else:
                raise RuntimeError('No owners defined')

            return session

        return self.xmpp['rho_bot_rdf_publish'].send_out_request(payload).then(set_owner_session)

    def _get_data(self, session):
        logger.info('Task Executing: %s' % session)
        session['segments'] = []

        parameters = dict(pastDays=7)

        #results = self.client.user_places_daily(**parameters)
        results = test_data

        logger.info('Update Results: %s' % results)

        for date_result in results:
            segments = date_result['segments']
            date = date_result['date']
            session['last_update'] = date_result['lastUpdate']

            if segments is not None:
                for segment in segments:
                    session['segments'].append(segment)

        return session

    def _process_data(self, session):

        session['promise'] = self.xmpp['rho_bot_scheduler'].promise()

        promise = None
        for segment in session['segments']:
            if not promise:
                promise = self.xmpp['rho_bot_scheduler'].defer(self._generate_processor(segment, session))
            else:
                promise = promise.then(self._generate_processor(segment, session))

        # Save off the configuration details from this update cycle, and then resolve or reject the session promise.
        promise.then(lambda s: self._update_configuration(session)).then(lambda s: session['promise'].resolved(session),
                                                                         lambda s: session['promise'].rejected(s))

        return session['promise']

    def _generate_processor(self, segment, session):

        return ProcessSegment(segment, session['owner'], self.xmpp['rho_bot_scheduler'],
                              self.xmpp['rho_bot_storage_client'])

    def _update_configuration(self, session):
        logger.info('TODO: Set the last update time to be: %s' % session['last_update'])


update_service = UpdateService
