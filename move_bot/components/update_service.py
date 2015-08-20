"""
Component of the move bot that will load up the data from the update service.
"""
import moves
from rdflib.namespace import Namespace, RDFS
from move_bot.test_data.robert_01 import data as test_data
from sleekxmpp.plugins.base import base_plugin
from rhobot.components.configuration import BotConfiguration
from move_bot.components.configuration_enums import CLIENT_SECRET_KEY, IDENTIFIER_KEY, CLIENT_TOKEN_KEY
from move_bot.components.events import OAUTH_DETAILS_UPDATED
import logging


logger = logging.getLogger(__name__)
WGS84_POS_NAMESPACE = Namespace('http://www.w3.org/2003/01/geo/wgs84_pos#')

class UpdateService(base_plugin):

    name = 'update_service'
    description = 'Service that will update data store from move api'
    dependencies = {'rho_bot_scheduler', 'rho_bot_configuration', }

    def plugin_init(self):
        """
        Initialize the plugin.
        :return:
        """
        self._cancel_handler = None
        self.client = None
        self.xmpp.add_event_handler(BotConfiguration.CONFIGURATION_RECEIVED_EVENT, self._configuration_updated)
        self.xmpp.add_event_handler(OAUTH_DETAILS_UPDATED, self._configuration_updated)

        self._segment_queue = []

    def _configuration_updated(self, event=None):
        self.xmpp['rho_bot_scheduler'].schedule_task(self.check_configuration, delay=5.0, repeat=False)

    def check_configuration(self):
        """
        Check to see if the configuration is up to date.  Doesn't need to be rescheduled because won't execute again
        unless the configuration has been updated.
        :return:
        """
        # Stop the current execution cycle if it is currently running.
        if self._cancel_handler:
            self._cancel_handler()

        configuration = self.xmpp['rho_bot_configuration'].get_configuration()
        identifier = configuration.get(IDENTIFIER_KEY, None)
        secret = configuration.get(CLIENT_SECRET_KEY, None)
        client_token = configuration.get(CLIENT_TOKEN_KEY, None)

        # Validate the configuration details.
        if identifier is None or secret is None or client_token is None:
            logger.error('Configuration is not defined')
            return

        if not self.xmpp['rho_bot_storage_client'].has_store():
            logger.error('Storage Client doesnt exist')
            return

        # Validate the token
        self.client = moves.MovesClient(identifier, secret, client_token)
        token_validity = self.client.tokeninfo()

        if 'error' in token_validity:
            logger.error('Token is not valid')
            return

        # if all is good with the world, start executing the update thread.
        # Determine if the token should be updated or not
        logger.info('Token Validity Information: %s' % token_validity)

        self._cancel_handler = self.xmpp['rho_bot_scheduler'].schedule_task(self.update_database, delay=10.0,
                                                                            repeat=False, execute_now=False)

    def update_database(self):
        logger.info('Task Executing')

        parameters = dict(pastDays=7)

        #results = self.client.user_places_daily(**parameters)
        results = test_data

        logger.info('Update Results: %s' % results)

        for date_result in results:
            segments = date_result['segments']
            date = date_result['date']
            last_update = date_result['lastUpdate']

            if segments is not None:
                for segment in segments:
                    self._segment_queue.append(segment)

        if len(self._segment_queue):
            self._cancel_handler = self.xmpp['rho_bot_scheduler'].schedule_task(self._update_segment)

    def _update_segment(self):
        """
        Updating segment code.
        :param segment:
        :return:
        """
        segment = self._segment_queue.pop(0)

        logger.info('Running update on segment: %s' % segment)

        if segment['place']['type'] == 'foursquare':
            payload = self.xmpp['rho_bot_storage_client'].create_payload()
            payload.add_type(WGS84_POS_NAMESPACE.SpatialThing)
            payload.add_reference(RDFS.seeAlso,
                                  'https://api.foursquare.com/v2/venues/%s' % segment['place']['foursquareId'])

            self.xmpp['rho_bot_storage_client'].find_node(payload)

        # Reschedule the event as long as the queue exists.
        if len(self._segment_queue):
            self._cancel_handler = self.xmpp['rho_bot_scheduler'].schedule_task(self._update_segment)
        else:
            self._cancel_handler = self.xmpp['rho_bot_scheduler'].schedule_task(self.update_database)


update_service = UpdateService
