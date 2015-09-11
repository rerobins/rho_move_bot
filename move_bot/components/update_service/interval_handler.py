"""
Handler method that will provide a promise to handle the creation/update of an interval object.
"""
from rhobot.components.storage import StoragePayload

from move_bot.components.namespace import TIMELINE
from rdflib.namespace import DCTERMS
import logging

logger = logging.getLogger(__name__)


class IntervalHandler:

    def __init__(self, bot):
        self._scheduler = bot['rho_bot_scheduler']
        self._storage_client = bot['rho_bot_storage_client']
        self._representation_manager = bot['rho_bot_representation_manager']
        self._rdf_publish = bot['rho_bot_rdf_publish']

    def __call__(self, node_identifier=None, start_time=None, end_time=None):
        """
        This will return a promise that will resolve to the identifier of the node that was modified.  This will also
        take responsibility for scheduling of the creation and update methods.
        :param node_identifier:
        :param start_time:
        :param end_time:
        :return:
        """
        logger.info('node_identifier: %s' % (node_identifier, ))
        if node_identifier:
            return self._update_node(node_identifier, start_time, end_time)
        else:
            return self._create_node(start_time, end_time)

    @staticmethod
    def _handle_result(result):
        """
        Retrieve the about field in the result collection and resolve the promise with the result.
        :param result:
        :return:
        """
        if result.results:
            return [rdf.about for rdf in result.results]

        raise RuntimeError('Invalid update/create result size')

    def _update_node(self, node_identifier, start_time, end_time):
        """
        Update the node and schedule the publishing of the update method.
        :param start_time:
        :param end_time:
        :return:
        """
        payload = StoragePayload()
        payload.about = node_identifier
        payload.add_type(TIMELINE.Interval)
        if start_time:
            payload.add_property(TIMELINE.start, start_time)

        if end_time:
            payload.add_property(TIMELINE.end, end_time)

        promise = self._storage_client.update_node(payload)

        promise.then(self._scheduler.generate_promise_handler(self._rdf_publish.publish_all_results, created=False))

        return promise.then(self._handle_result)

    def _create_node(self, start_time, end_time):
        """
        Create the node and schedule the publishing of the update method.
        :param start_time:
        :param end_time:
        :return:
        """
        payload = StoragePayload()
        payload.add_type(TIMELINE.Interval)
        if start_time:
            payload.add_property(TIMELINE.start, start_time)

        if end_time:
            payload.add_property(TIMELINE.end, end_time)

        creator = self._representation_manager.representation_uri
        if creator:
            payload.add_property(DCTERMS.creator, creator)

        promise = self._storage_client.create_node(payload)

        promise.then(self._scheduler.generate_promise_handler(self._rdf_publish.publish_all_results, created=True))

        return promise.then(self._handle_result)
