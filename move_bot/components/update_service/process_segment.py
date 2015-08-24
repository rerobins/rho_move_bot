"""
Encapsulate the methodology to process a segment from the moves-api.
"""
from move_bot.components.namespace import EVENT, MOVES_SEGMENT
from rdflib.namespace import RDFS, DC
import logging

logger = logging.getLogger(__name__)

class ProcessSegment:
    """
    Callable that encapsulates the work that needs to be done to insert an event into the data store inside a promise.

    These steps are:

    If there is an event that already exists that needs to be updated.
        Update the contents of that event.
    Else:
        Create the new event.

    TODO: Create a location object to reference inside the event
    TODO: Create an interval object to reference inside the event
    """

    def __init__(self, segment, owner, scheduler, storage_client, publisher):
        """
        Construct the callable.
        :param segment: segment to process.
        :param owner: owner of the installation
        :param scheduler: scheduler for creating promises/defers
        :param storage_client: storage client for storing new/updated data.
        :param publisher: publisher service.
        """
        self._segment = segment
        self._scheduler = scheduler
        self._storage_client = storage_client
        self._promise = None
        self._publisher = publisher
        self._owner = owner
        self._node_id = None

    def __call__(self, *args):
        """
        Executable method for the instance.  This will look up to see if the object needs to be updated or created, then
        instantiate the correct promise chain which will accomplish the task.
        :param args:
        :return:
        """
        self._promise = self._scheduler.promise()

        # Check in the database to see if there is anything that currently has the segment defined in it
        payload = self._storage_client.create_payload()
        payload.add_type(EVENT.Event)
        payload.add_property(RDFS.seeAlso, MOVES_SEGMENT[self._segment['startTime']])

        result = self._storage_client.find_nodes(payload)

        task_promise = self._scheduler.defer(self._start_process)

        if result.results():
            self._node_id = result.results()[0].about
            task_promise.then(self._update_node).then(self._finish_process)
        else:
            task_promise.then(self._create_node).then(self._finish_process)

        return self._promise

    def _finish_process(self, session=None):
        """
        Common exit point for the promise chain.
        :param session:
        :return:
        """
        self._promise.resolved(session)
        return None

    def _update_node(self, session):
        """
        Method to be used in a deferred that will update the node responsible for execution.
        :return:
        """
        logger.info('Updating Node')
        payload = self._convert_segment_to_payload()
        payload.about = self._node_id

        result = self._storage_client.update_node(payload)

        storage_payload = self._storage_client.create_payload()
        storage_payload.about = result.results()[0].about
        storage_payload.add_type(EVENT.Event)

        self._publisher.publish_update(storage_payload)

        return result.results()[0].about

    def _start_process(self):
        return dict()

    def _create_node(self, session):
        """
        Create a new node based and add additional properties based on the session.
        :param session:
        :return:
        """
        logger.debug('Creating Node')
        payload = self._convert_segment_to_payload()

        result = self._storage_client.create_node(payload)

        storage_payload = self._storage_client.create_payload()
        storage_payload.about = result.results()[0].about
        storage_payload.add_type(EVENT.Event)

        self._publisher.publish_create(storage_payload)

        return result.results()[0].about

    def _convert_segment_to_payload(self):
        """
        Convert the segment details into a payload object.
        :return:
        """
        payload = self._storage_client.create_payload()
        payload.add_type(EVENT.Event)
        payload.add_reference(key=EVENT.agent, value=self._owner)
        payload.add_property(RDFS.seeAlso, MOVES_SEGMENT[self._segment['startTime']])

        place_name = self._segment['place'].get('name', 'Unknown')
        payload.add_property(key=DC.title, value=place_name)

        return payload