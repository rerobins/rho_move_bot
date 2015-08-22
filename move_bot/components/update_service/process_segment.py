"""
Encapsulate the methodology to process a segment from the moves-api.
"""
from move_bot.components.namespace import EVENT, MOVES_SEGMENT
from rdflib.namespace import RDFS, RDF, DC
import logging

logger = logging.getLogger(__name__)

class ProcessSegment:

    def __init__(self, segment, owner, scheduler, storage_client):
        self._segment = segment
        self._scheduler = scheduler
        self._storage_client = storage_client
        self._promise = None
        self._owner = owner
        self._node_id = None

    def __call__(self, *args):
        self._promise = self._scheduler.promise()

        # Check in the database to see if there is anything that currently has the segment defined in it
        payload = self._storage_client.create_payload()
        payload.add_type(RDFS.Resource)
        payload.add_property(RDFS.seeAlso, MOVES_SEGMENT[self._segment['lastUpdate']])

        result = self._storage_client.find_nodes(payload)

        if result.results():
            # payload = self._storage_client.create_payload()
            # payload.add_type(EVENT.Event)
            # payload.add_reference(RDFS.seeAlso, result.results()[0].about)
            #
            # result = self._storage_client.find_nodes(payload)
            #
            # if result.results():
            #     self._node_id = result.results()[0].about
            #     self._scheduler.defer(self._update_node).then(self._finish_process)
            self._promise.resolved(None)
        else:
            self._scheduler.defer(self._create_resource_node).then(self._create_node).then(self._finish_process)

        return self._promise

    def _finish_process(self, session=None):
        self._promise.resolved(session)
        return None

    def _update_node(self):
        logger.info('Updating Node')
        return None

    def _create_resource_node(self):
        logger.info('Creating Resource Node')
        payload = self._storage_client.create_payload()
        payload.add_type(RDFS.Resource)
        payload.add_property(RDFS.seeAlso, MOVES_SEGMENT[self._segment['lastUpdate']])

        result = self._storage_client.create_node(payload)

        return result.results()[0].about

    def _create_node(self, resource_node_id):
        logger.info('Creating Node')
        payload = self._storage_client.create_payload()
        payload.add_type(EVENT.Event)
        payload.add_reference(key=EVENT.agent, value=self._owner)
        payload.add_reference(key=RDFS.seeAlso, value=resource_node_id)

        place_name = self._segment['place'].get('name', 'Unknown')
        payload.add_property(key=DC.title, value=place_name)

        result = self._storage_client.create_node(payload)

        return result.results()[0].about
