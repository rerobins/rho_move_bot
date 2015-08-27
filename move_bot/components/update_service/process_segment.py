"""
Encapsulate the methodology to process a segment from the moves-api.

Builds rdf triples based on:
http://motools.sourceforge.net/event/event.html
"""
from rhobot.components.storage import StoragePayload
from move_bot.components.namespace import EVENT, MOVES_SEGMENT, WGS_84, LOCATION, SCHEMA
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
        payload = StoragePayload()
        payload.add_type(EVENT.Event)
        payload.add_property(RDFS.seeAlso, MOVES_SEGMENT[self._segment['startTime']])

        result = self._storage_client.find_nodes(payload)

        task_promise = self._scheduler.defer(self._start_process).then(self._find_place)

        if result.results:
            self._node_id = result.results[0].about
            task_promise = task_promise.then(self._update_node)
        else:
            task_promise = task_promise.then(self._create_node)

        task_promise.then(self._finish_process, lambda s: self._promise.rejected(s))

        return self._promise

    def _finish_process(self, session=None):
        """
        Common exit point for the promise chain.
        :param session:
        :return:
        """
        self._promise.resolved(session)
        return None

    def _start_process(self):
        return dict()

    def _find_place(self, session):
        """
        Find the place associated with the segment.
        :param session:
        :return:
        """
        if self._segment['place']['type'] == 'foursquare':
            location_request = StoragePayload()
            location_request.add_type(WGS_84.SpatialThing)
            location_request.add_property(RDFS.seeAlso,
                                          'foursquare://venues/%s' % self._segment['place']['foursquareId'])
            promise = self._publisher.send_out_request(location_request).then(
                self._generate_promise_foursquare(session))

        elif self._segment['place']['type'] == 'home':
            # Ask the owner if it has an address
            get_request = StoragePayload()
            get_request.about = self._owner
            result = self._storage_client.get_node(get_request)

            if str(LOCATION.address) in result.references:
                session['location'] = result.references[str(LOCATION.address)]
            elif str(SCHEMA.homeLocation):
                session['location'] = result.references[str(SCHEMA.homeLocation)]
            else:
                session['location'] = []

            promise = self._scheduler.promise()
            promise.resolved(session)
        else:
            session['location'] = []
            promise = self._scheduler.promise()
            promise.resolved(session)

        return promise

    def _generate_promise_foursquare(self, session):
        """
        Generate a promise listener that will find the locations retrieved by a lookup and then return the session
        variable.
        :param session:
        :return:
        """
        def _promise_foursquare_location(result):
            """
            Closure that will attempt to update the session variable based on the results of a promise lookup.
            """
            session['location'] = result

            return session

        return _promise_foursquare_location

    def _create_node(self, session):
        """
        Create a new node based and add additional properties based on the session.
        :param session:
        :return:
        """
        logger.debug('Creating Node')
        payload = self._convert_segment_to_payload(session)
        result = self._storage_client.create_node(payload)

        storage_payload = self._storage_client.create_payload()
        storage_payload.about = result.results[0].about
        storage_payload.add_type(EVENT.Event)
        self._publisher.publish_create(storage_payload)

        return result.results[0].about

    def _update_node(self, session):
        """
        Method to be used in a deferred that will update the node responsible for execution.
        :return:
        """
        logger.info('Updating Node')
        payload = self._convert_segment_to_payload(session)
        payload.about = self._node_id
        result = self._storage_client.update_node(payload)

        storage_payload = StoragePayload()
        storage_payload.about = result.results[0].about
        storage_payload.add_type(EVENT.Event)
        self._publisher.publish_update(storage_payload)

        return result.results[0].about

    def _convert_segment_to_payload(self, session):
        """
        Convert the segment details into a payload object.
        :return:
        """
        payload = StoragePayload()
        payload.add_type(EVENT.Event)
        payload.add_reference(key=EVENT.agent, value=self._owner)
        payload.add_property(RDFS.seeAlso, MOVES_SEGMENT[self._segment['startTime']])

        if session['location']:
            payload.add_reference(key=EVENT.place, value=session['location'][0])

        place_name = self._segment['place'].get('name', 'Unknown')
        payload.add_property(key=DC.title, value=place_name)

        return payload
