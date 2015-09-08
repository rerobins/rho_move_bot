"""
Component of the move bot that will load up the data from the update service.
"""
import moves
from rdflib.namespace import Namespace, FOAF
from rhobot.namespace import RHO
from rhobot.components.storage import StoragePayload
from sleekxmpp.plugins.base import base_plugin
from rhobot.components.configuration import BotConfiguration
from move_bot.components.configuration_enums import CLIENT_SECRET_KEY, IDENTIFIER_KEY, CLIENT_TOKEN_KEY
from move_bot.components.update_service.process_segment import ProcessSegment
import logging


logger = logging.getLogger(__name__)
WGS84_POS_NAMESPACE = Namespace('http://www.w3.org/2003/01/geo/wgs84_pos#')

class UpdateService(base_plugin):
    """
    Service that will create a group of promises that can be used to insert the data from the moves-app.com API.
    """

    name = 'update_service'
    description = 'Service that will update data store from move api'
    dependencies = {'rho_bot_scheduler', 'rho_bot_configuration', 'rho_bot_rdf_publish', }

    _delay = 600.0
    _past_days = 31

    def plugin_init(self):
        """
        Initialize the plugin.
        :return:
        """
        self.xmpp.add_event_handler(BotConfiguration.CONFIGURATION_RECEIVED_EVENT, self._configuration_updated)
        # self.xmpp.add_event_handler(OAUTH_DETAILS_UPDATED, self._configuration_updated)

    def _configuration_updated(self, *args, **kwargs):
        """
        Callback when the configuration details have been received by the bot.
        :param args:
        :param kwargs:
        :return:
        """
        logger.debug('Rescheduling task for time: %s' % self._delay)
        self.xmpp['rho_bot_scheduler'].schedule_task(self._start, delay=self._delay, repeat=False)

    def _start(self):
        """
        Entry point.

        Generates the basic chain of promises that will be used.  Each of the promises should return the session
        variable that will be updated by all of the individual tasks so that each of the following tasks will have
        access to all of the work that has been done before it.
        :return:
        """
        promise = self.xmpp['rho_bot_scheduler'].defer(self._create_session)
        promise = promise.then(self._build_client)
        promise = promise.then(self._get_owner)
        promise = promise.then(self._get_data)
        promise = promise.then(self._process_data)

        # Reschedule the whole thing again
        promise.then(self._configuration_updated, self._configuration_updated)

    def _create_session(self):
        """
        Creates the session variable that will be used throughout all of the promises.
        :return: session dictionary
        """
        logger.debug('Creating session')
        return dict()

    def _build_client(self, session):
        """
        Create the client.

        Look into the configuration details of the bot and get the attributes required to access the data API.  This
        will also check to see if there is a valid data store for storing the data.
        :param session: session variable
        :return:
        """
        logger.debug('Creating the client')
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
        logger.debug('Token Validity Information: %s' % token_validity)

        session['client'] = client

        return session

    def _get_owner(self, session):
        """
        Look up the owner information from one of the other bots in the channel.
        :param session: session variable
        :return:
        """
        logger.debug('Getting the owner information from other bot')
        payload = StoragePayload()
        payload.add_type(FOAF.Person, RHO.Owner)

        def set_owner_session(owner):
            logger.info('Configuring session owner')

            if owner.results:
                session['owner'] = owner.results[0].about
            else:
                raise RuntimeError('No owners defined')

            return session

        return self.xmpp['rho_bot_rdf_publish'].send_out_request(payload).then(set_owner_session)

    def _get_data(self, session):
        """
        Retrieve the data from the API service and store them in the session variable.
        :param session:
        :return:
        """
        logger.debug('Task Executing: %s' % session)
        session['segments'] = []

        parameters = dict(pastDays=self._past_days)

        last_update = self.xmpp['rho_bot_configuration'].get_value(key='last_update', default=None,
                                                                   persist_if_missing=False)
        if last_update:
            parameters['updatedSince'] = last_update
            session['last_update'] = last_update

        results = session['client'].user_places_daily(**parameters)

        logger.debug('Update Results: %s' % results)

        for date_result in results:
            segments = date_result['segments']

            if session.get('last_update', None) is None or session['last_update'] < date_result['lastUpdate']:
                session['last_update'] = date_result['lastUpdate']

            if segments is not None:
                for segment in segments:
                    session['segments'].append(segment)

        return session

    def _process_data(self, session):
        """
        Break apart each of the data segments into callables for execution.  This should serialize all of the data to
        be processed, but instead of executing in a giant execution, will break apart the code so that other events can
        be processed by the bot.
        :param session: session variable.
        :return: promise that will be resolved once all of the segments have been processed.
        """
        session['promise'] = self.xmpp['rho_bot_scheduler'].promise()

        promise = None
        for segment in session['segments']:
            if not promise:
                execution = ProcessSegment(segment, session['owner'], self.xmpp['rho_bot_scheduler'],
                                           self.xmpp['rho_bot_storage_client'], self.xmpp['rho_bot_rdf_publish'])
                promise = self.xmpp['rho_bot_scheduler'].defer(execution)
            else:
                execution = ProcessSegment(segment, session['owner'], self.xmpp['rho_bot_scheduler'],
                                           self.xmpp['rho_bot_storage_client'], self.xmpp['rho_bot_rdf_publish'])
                promise = promise.then(execution)

        # Save off the configuration details from this update cycle, and then resolve or reject the session promise.
        if promise is not None:
            promise.then(
                lambda s: self._update_configuration(session)).then(lambda s: session['promise'].resolved(session),
                                                                    lambda s: session['promise'].rejected(s))
        else:
            session['promise'].resolved(session)

        return session['promise']

    def _update_configuration(self, session):
        """
        Used to update the internal configuration details of the bot so that data isn't pulled down that hasn't been
        updated.
        :param session: session variable.
        :return: session variable
        """
        self.xmpp['rho_bot_configuration'].merge_configuration({'last_update': session['last_update']})

        return session


update_service = UpdateService
