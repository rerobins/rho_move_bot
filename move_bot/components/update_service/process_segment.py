"""
Encapsulate the methodology to process a segment from the moves-api.

Builds rdf triples based on:
http://motools.sourceforge.net/event/event.html
"""
import logging

from rhobot.components.storage import StoragePayload

from move_bot.components.update_service.interval_handler import IntervalHandler
from move_bot.components.update_service.location_handler import LocationHandler
from move_bot.components.namespace import EVENT, MOVES_SEGMENT
from rdflib.namespace import RDFS, DC, DCTERMS

logger = logging.getLogger(__name__)


class ProcessSegment:
    """
    Callable that encapsulates the work that needs to be done to insert an event into the data store inside a promise.

    These steps are:

    If there is an event that already exists that needs to be updated.
        Update the contents of that event.
    Else:
        Create the new event.
    """

    def __init__(self, segment, owner, xmpp):
        """
        Construct the callable.
        :param segment: segment to process.
        :param owner: owner of the installation
        :param xmpp: bot details
        """
        self._segment = segment
        self._scheduler = xmpp['rho_bot_scheduler']
        self._storage_client = xmpp['rho_bot_storage_client']
        self._promise = None
        self._publisher = xmpp['rho_bot_rdf_publish']
        self._representation_manager = xmpp['rho_bot_representation_manager']
        self._owner = owner
        self._node_id = None
        self.xmpp = xmpp

        self.interval_handler = IntervalHandler(xmpp)
        self.location_handler = LocationHandler(xmpp, owner)

    def __call__(self, *args):
        """
        Executable method for the instance.  This will look up to see if the object needs to be updated or created, then
        instantiate the correct promise chain which will accomplish the task.
        :param args:
        :return:
        """
        logger.info('Processing segment: %s' % self._segment)

        self._promise = self._scheduler.promise()

        # Check in the database to see if there is anything that currently has the segment defined in it
        payload = StoragePayload()
        payload.add_type(EVENT.Event)
        payload.add_property(RDFS.seeAlso, MOVES_SEGMENT[self._segment['startTime']])

        self._storage_client.find_nodes(payload).then(self._handle_find_result)

        return self._promise

    def _finish_process(self, session=None):
        """
        Common exit point for the promise chain.
        :param session:
        :return:
        """
        self._promise.resolved(session)
        return None

    def _handle_find_result(self, result):
        if result.results:
            self._node_id = result.results[0].about
            update_promise = self._scheduler.defer(self.start_session).then(self._find_place)
            update_promise = update_promise.then(self._get_interval).then(self._update_node)
            update_promise.then(self._finish_process, lambda s: self._promise.rejected(s))
            return update_promise
        else:
            create_promise = self._scheduler.defer(self.start_session).then(self._find_place)
            create_promise = create_promise.then(self._create_interval).then(self._create_node)
            create_promise.then(self._finish_process, lambda s: self._promise.rejected(s))
            return create_promise

    def start_session(self):
        return dict()

    def _find_place(self, session):
        """
        Find the place associated with the segment.
        :param session:
        :return:
        """
        logger.debug('Finding place: %s' % session)
        location_promise = self.location_handler(self._segment['place']).then(
            self._scheduler.generate_promise_handler(self._update_session, session, 'location'))

        return location_promise

    def _get_interval(self, session):
        """
        Get the event node to be updated, then update the interval object, and put the result into the session value.
        :param session: session variable.
        :return:
        """
        logger.debug('Get Interval: %s' % session)

        def update_interval(result):
            interval_reference = result.references.get(str(EVENT.time), None)

            if interval_reference:
                interval_reference = interval_reference[0]

            interval_promise = self.interval_handler(interval_reference,
                                                     self._segment['startTime'],
                                                     self._segment['endTime'])
            interval_promise = interval_promise.then(
                self._scheduler.generate_promise_handler(self._update_session, session, 'interval'))
            return interval_promise

        payload = StoragePayload()
        payload.about = self._node_id

        promise = self._storage_client.get_node(payload).then(update_interval)
        return promise

    def _create_interval(self, session):
        """
        Create a new interval and add it to the session variable.
        :param session:
        :return:
        """
        logger.debug('Create Interval: %s' % session)
        interval_promise = self.interval_handler(None, self._segment['startTime'], self._segment['endTime'])
        interval_promise = interval_promise.then(
            self._scheduler.generate_promise_handler(self._update_session, session, 'interval'))

        return interval_promise

    @staticmethod
    def _update_session(interval_result, session, key):
        """
        Process the results of the creation.
        """
        session[key] = interval_result
        return session

    def _create_node(self, session):
        """
        Create a new node based and add additional properties based on the session.
        :param session:
        :return:
        """
        logger.debug('Creating Node')
        payload = self._convert_segment_to_payload(session)

        # Only set the title when first creating it.  The update might override a field that has been changed by the
        # user.
        place_name = self._segment['place'].get('name', 'Unknown')
        payload.add_property(key=DC.title, value=place_name)

        promise = self._storage_client.create_node(payload).then(
            self._scheduler.generate_promise_handler(self._publish_modifications, created=True)).then(
            lambda s: s.results[0].about)

        return promise

    def _update_node(self, session):
        """
        Method to be used in a deferred that will update the node responsible for execution.
        :return:
        """
        logger.info('Updating Node')
        payload = self._convert_segment_to_payload(session)

        # Update that about field so that the node can be updated.
        payload.about = self._node_id

        promise = self._storage_client.update_node(payload).then(
            self._scheduler.generate_promise_handler(self._publish_modifications, created=False)).then(
            lambda s: s.results[0].about)

        return promise

    def _convert_segment_to_payload(self, session):
        """
        Convert the segment details into a payload object.
        :return:
        """
        payload = StoragePayload()
        payload.add_type(EVENT.Event)
        payload.add_reference(key=EVENT.agent, value=self._owner)
        payload.add_reference(key=DCTERMS.creator, value=self._representation_manager.representation_uri)
        payload.add_property(RDFS.seeAlso, MOVES_SEGMENT[self._segment['startTime']])

        if session['location']:
            payload.add_reference(key=EVENT.place, value=session['location'][0])

        if session['interval']:
            payload.add_reference(key=EVENT.time, value=session['interval'][0])

        return payload

    def _publish_modifications(self, result, created=True):
        self._publisher.publish_all_results(result, created=created)
        return result
