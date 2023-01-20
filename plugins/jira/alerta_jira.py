import logging
import os
from jira import JIRA
import re
import traceback

try:
    from alerta.plugins import app  # alerta >= 5.0
except ImportError:
    from alerta.app import app  # alerta < 5.0
from alerta.plugins import PluginBase

# set plugin logger
LOG = logging.getLogger('alerta.plugins.jira')

# retrieve plugin configurations
JIRA_URL = app.config.get('JIRA_URL') or os.environ.get('JIRA_URL')
JIRA_PROJECT = app.config.get('JIRA_PROJECT') or os.environ.get('JIRA_PROJECT')
JIRA_API_TOKEN = app.config.get('JIRA_API_TOKEN') or os.environ.get('JIRA_API_TOKEN')
JIRA_USER = app.config.get('JIRA_USER') or os.environ.get('JIRA_USER')
JIRA_ISSUE_TYPE = app.config.get('JIRA_ISSUE_TYPE') or os.environ.get('JIRA_ISSUE_TYPE')

# jira creation filters when alerta received
JIRA_TRIGGER_ISSUE_RESOURCE = app.config.get('JIRA_TRIGGER_ISSUE_RESOURCE') or os.environ.get(
    'JIRA_TRIGGER_ISSUE_RESOURCE')
JIRA_TRIGGER_ISSUE_ENVIRONMENT = app.config.get('JIRA_TRIGGER_ISSUE_ENVIRONMENT') or os.environ.get(
    'JIRA_TRIGGER_ISSUE_ENVIRONMENT')
JIRA_TRIGGER_ISSUE_SEVERITY = app.config.get('JIRA_TRIGGER_ISSUE_SEVERITY') or os.environ.get(
    'JIRA_TRIGGER_ISSUE_SEVERITY')
JIRA_TRIGGER_ISSUE_EVENT = app.config.get('JIRA_TRIGGER_ISSUE_EVENT') or os.environ.get('JIRA_TRIGGER_ISSUE_EVENT')
JIRA_TRIGGER_ISSUE_SERVICE = app.config.get('JIRA_TRIGGER_ISSUE_SERVICE') or os.environ.get(
    'JIRA_TRIGGER_ISSUE_SERVICE')
JIRA_TRIGGER_ISSUE_GROUP = app.config.get('JIRA_TRIGGER_ISSUE_GROUP') or os.environ.get('JIRA_TRIGGER_ISSUE_GROUP')
JIRA_TRIGGER_ISSUE_VALUE = app.config.get('JIRA_TRIGGER_ISSUE_VALUE') or os.environ.get('JIRA_TRIGGER_ISSUE_VALUE')
JIRA_TRIGGER_ISSUE_ORIGIN = app.config.get('JIRA_TRIGGER_ISSUE_ORIGIN') or os.environ.get('JIRA_TRIGGER_ISSUE_ORIGIN')
JIRA_TRIGGER_ISSUE_TYPE = app.config.get('JIRA_TRIGGER_ISSUE_TYPE') or os.environ.get('JIRA_TRIGGER_ISSUE_TYPE')
JIRA_TRIGGER_ISSUE_TEXT = app.config.get('JIRA_TRIGGER_ISSUE_TEXT') or os.environ.get('JIRA_TRIGGER_ISSUE_TEXT')

if not JIRA_ISSUE_TYPE:
    JIRA_ISSUE_TYPE = "Task"

class JiraCreate(PluginBase):
    def _createJiraSummary(self, host, alert, chart, severity):
        return "Server {server}: alert {alert} in chart {chart} - Severity: {severity}".format(server=host.upper(),
                                                                                               alert=alert.upper(),
                                                                                               chart=chart.upper(),
                                                                                               severity=severity.upper())

    def _create_jira(self, jira_connection, host, event, value, chart, text, severity):
        LOG.info('JIRA: Create task ...')

        summary = self._createJiraSummary(host=host, alert=event, chart=chart, severity=severity)
        description = "The chart {chart} INFO: {info}. \nVALUE: {value}.".format(chart=chart, info=text, value=value)

        issue_dict = {
            'project': {'key': JIRA_PROJECT},
            "summary": summary,
            "description": description,
            'issuetype': {'name': JIRA_ISSUE_TYPE},
        }

        return jira_connection.create_issue(fields=issue_dict)

    def _re_check(self, pattern, value):
        if pattern and value:
            if re.search(pattern, str(value)):
                LOG.debug("Jira: pattern: {pattern} matched value: {value}".format(pattern=pattern, value=value))
                return True
        return False

    def _create_issue(self, alert, host, event, chart):
        # create connection to jira api
        jira_connection = JIRA(basic_auth=(JIRA_USER, JIRA_API_TOKEN), server=JIRA_URL)
        # create jira ticket
        task = self._create_jira(jira_connection, host, event, alert.value, chart, alert.text, alert.severity)
        # add jira ticket info to event obj
        task_url = "{url}/browse/{task}".format(url=JIRA_URL, task=task)
        alert.attributes = {'jira':
            {
                'url': task_url,
                'key': task.key,
                'id': task.id
            }
        }
        return alert

    # reject or modify an alert before it hits the database
    def pre_receive(self, alert):
        return alert

    def post_receive(self, alert):
        try:
            # if the alert is critical and don't duplicate, create task in Jira
            if alert.status not in ['ack', 'closed', 'shelved'] and alert.duplicate_count == 0:
                LOG.info("Jira: Received an alert")
                LOG.debug("Jira: ALERT       {}".format(alert))
                LOG.debug("Jira: ID          {}".format(alert.id))
                LOG.debug("Jira: RESOURCE    {}".format(alert.resource))
                LOG.debug("Jira: EVENT       {}".format(alert.event))
                LOG.debug("Jira: SEVERITY    {}".format(alert.severity))
                LOG.debug("Jira: TEXT        {}".format(alert.text))

                # get basic info from alert
                host = alert.resource.split(':')[0]
                LOG.debug("Jira: HOST        {}".format(host))
                chart = ".".join(alert.event.split('.')[:-1])
                LOG.debug("Jira: CHART       {}".format(chart))
                event = alert.event.split('.')[-1]
                LOG.debug("Jira: EVENT       {}".format(event))

                # check filters to create ticket automatically
                create_issue = self._re_check(JIRA_TRIGGER_ISSUE_RESOURCE, alert.resource)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_SEVERITY, alert.severity)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_ENVIRONMENT, alert.resource)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_EVENT, alert.event)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_SERVICE, alert.service)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_GROUP, alert.group)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_VALUE, alert.value)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_ORIGIN, alert.origin)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_TYPE, alert.type)
                create_issue = create_issue or self._re_check(JIRA_TRIGGER_ISSUE_TEXT, alert.text)

                if create_issue:
                    return self._create_issue(alert=alert, host=host, event=event, chart=chart)
        except Exception as ex:
            LOG.error('Jira: Failed to create task: %s', ex)
            LOG.error(''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__)))
        return alert

    # triggered by external status changes, used by integrations
    def status_change(self, alert, status, text):
        return

    def take_action(self, alert, action, text):
        # create connection to jira api
        jira_connection = JIRA(basic_auth=(JIRA_USER, JIRA_API_TOKEN), server=JIRA_URL)

        # todo parse text as json, try retrieve alerta obj
        # if action == "refreshJira":
        #     jira_tickets = jira_connection.search_issues("summary ~ \"{summary}\"".format(summary=text))
        #
        #     if len(jira_tickets) > 0:
        #         # update the ticket
        #         pass
        #
        # if action == "createJira":
        #     pass
