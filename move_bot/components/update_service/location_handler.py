from rhobot.components.storage import StoragePayload
from rhobot.namespace import WGS_84, LOCATION, SCHEMA
from rdflib.namespace import RDFS


class LocationHandler:

    def __init__(self, bot, owner):
        self._rdf_publisher = bot['rho_bot_rdf_publish']
        self._storage_client = bot['rho_bot_storage_client']
        self._scheduler = bot['rho_bot_scheduler']
        self._owner = owner

    def __call__(self, place_definition):
        """
        Find the place associated with the segment.
        :param place definition:
        :return: promise that provides a uri that represents the place definition
        """
        if place_definition['type'] == 'foursquare':
            promise = self._process_foursquare(place_definition['foursquareId'])
        elif place_definition['type'] == 'home':
            promise = self._process_home_location()
        else:
            promise = self._scheduler.promise()
            promise.resolved([])

        return promise

    def _process_foursquare(self, foursquare_id):
        """
        Process the foursquare identifier and request that a different bot provide information about it.
        :param foursquare_id:
        :return:
        """
        location_request = StoragePayload()
        location_request.add_type(WGS_84.SpatialThing)
        location_request.add_property(RDFS.seeAlso,
                                      'foursquare://venues/%s' % foursquare_id)

        promise = self._rdf_publisher.send_out_request(location_request)
        promise = promise.then(self._handle_foursquare_result)

        return promise

    @staticmethod
    def _handle_foursquare_result(result):
        """
        Handle the result from the rdf request.
        :param result: result from the request.
        :return:
        """
        return [rdf.about for rdf in result.results]

    def _process_home_location(self):
        # Ask the owner if it has an address
        get_request = StoragePayload()
        get_request.about = self._owner
        promise = self._storage_client.get_node(get_request).then(self._handle_home_result)

        return promise

    @staticmethod
    def _handle_home_result(result):
        """
        Look in the owner details and see if any of the references for a home address is found.
        :param result: result to process.
        :return: list of locations that can be used as a home address.
        """
        if str(LOCATION.address) in result.references:
            return result.references[str(LOCATION.address)]
        elif str(SCHEMA.homeLocation):
            return result.references[str(SCHEMA.homeLocation)]

        return []
