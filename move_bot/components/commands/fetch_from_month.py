"""
Command that will add the data from a specific month.
"""
from rhobot.components.commands.base_command import BaseCommand
from sleekxmpp.plugins.xep_0122 import FormValidation
import logging
import isodate

logger = logging.getLogger(__name__)


class FetchFromMonth(BaseCommand):

    name = 'fetch_from_month'
    description = 'Fetch From Month'
    dependencies = BaseCommand.default_dependencies.union({'update_service', 'rho_bot_scheduler'})

    def post_init(self):
        super(FetchFromMonth, self).post_init()
        self._update_service = self.xmpp['update_service']
        self._scheduler = self.xmpp['rho_bot_scheduler']

    def command_start(self, request, initial_session):
        """
        Send out a form that asks for the date.
        :param request:
        :param initial_session:
        :return:
        """
        form = self._forms.make_form()
        month_field = form.add_field(var='month', label='Month', type='text-single', required=True)

        validation = FormValidation()
        validation['datatype'] = 'xs:date'
        validation.set_basic(True)

        month_field.append(validation)

        initial_session['payload'] = form
        initial_session['next'] = self._parse_form
        initial_session['has_next'] = False

        return initial_session

    def _parse_form(self, payload, session):
        """
        Parse the form and start the process of executing the update.
        :param payload: payload from the command
        :param session: session value to update.
        :return: session to return to the requester
        """
        logger.debug('Retrieve values for: %s' % payload.get_values()['month'])

        try:
            date = isodate.parse_date(payload.get_values()['month'])
            promise = self._update_service.fetch_for_month(date)
            promise = promise.then(lambda s: session)
        except ValueError:
            promise = self._scheduler.promise()
            promise.rejected(ValueError())

        session['payload'] = None
        session['next'] = None
        session['has_next'] = False

        return promise


fetch_from_month = FetchFromMonth
