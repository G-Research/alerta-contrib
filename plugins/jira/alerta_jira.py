import json
import logging
import os
from jira import JIRA
import re
import traceback
from typing import Any
from alerta.models.alert import Alert

try:
    from alerta.plugins import app  # alerta >= 5.0
except ImportError:
    from alerta.app import app  # alerta < 5.0
from alerta.plugins import PluginBase

# set plugin logger
LOG = logging.getLogger('alerta.plugins.jira')

# retrieve plugin configurations
JIRA_CONFIG_JSON = app.config.get('ALERTA_JIRA_CONFIG') or os.environ.get(
    'ALERTA_JIRA_CONFIG') or "alerta-jira-config.json"

alert_properties = ["resource", "severity", "environment", "event", "service", "group", "value", "origin", "type",
                    "text"]

class JiraCreate(PluginBase):
    """
    Jira alerta plugin
    Automatically generate Jira tickets and manage create requests from API
    """

    def __init__(self):
        self.jira_config = self._load_config_from_json()
        self._validate_config_params(self.jira_config)
        super().__init__()

    def __init__(self, config={}):
        if config == {}:
            config = self._load_config_from_json()
        self.jira_config = config
        self._validate_config_params(self.jira_config)
        super().__init__()

    def _load_config_from_json(self):
        LOG.debug("Jira: loading json config file: {}".format(JIRA_CONFIG_JSON))
        # load json config
        jira_config_file = open(JIRA_CONFIG_JSON)
        return json.load(jira_config_file)

    def _validate_config_params(self, config):
        # validate that required properties are defined
        required_properties = ["user", "url", "api token"]
        for required_property in required_properties:
            if required_property not in config:
                raise RuntimeError(
                    "missing property [{}] in config file ".format(required_property))

    def _create_jira_ticket(self, alert: Alert, assignee: any):
        # create connection to jira api
        jira_connection = self._get_jira_connection()
        # get basic info from alert
        host = alert.resource.split(':')[0]
        LOG.debug("Jira: HOST        {}".format(host))
        chart = ".".join(alert.event.split('.')[:-1])
        LOG.debug("Jira: CHART       {}".format(chart))
        event = alert.event.split('.')[-1]
        LOG.debug("Jira: EVENT       {}".format(event))
        # create jira ticket
        LOG.info("JIRA: Creating Jira ticket for alert: {alert}".format(alert=alert.id))

        summary = "Server {server}: alert {alert} in chart {chart} - Severity: {severity}". \
            format(server=host.upper(),
                   alert=alert.id.upper(),
                   chart=chart.upper(),
                   severity=alert.severity.upper())

        description = "The chart {chart} INFO: {info}. \nVALUE: {value}.".format(chart=chart, info=alert.text,
                                                                                 value=alert.value)

        issue_dict = {
            'project': {'key': assignee["project"]},
            "summary": summary,
            "description": description,
            'issuetype': {'name': assignee["issue-type"]},
        }

        task = jira_connection.create_issue(fields=issue_dict)

        # add jira ticket info to event obj
        task_url = "{url}/browse/{task}".format(url=self.jira_config["url"], task=task.key)
        alert.attributes = {'jira':
            {
                'url': task_url,
                'key': task.key,
                'id': task.id
            }
        }
        return alert

    # reject or modify an alert before it hits the database
    def pre_receive(self, alert: Alert):
        return alert

    def _check_trigger(self, trigger, alert: Alert):
        for alert_property in alert_properties:
            if alert_property in trigger:
                prop_value = getattr(alert, alert_property)
                if prop_value:
                    if not re.search(trigger[alert_property], prop_value):
                        return False
        return True

    def post_receive(self, alert: Alert):
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

                # iterate through configured triggers
                for trigger in self.jira_config["triggers"]:
                    # the first match triggers jira issue creation
                    if self._check_trigger(trigger["matches"], alert):
                        return self._create_jira_ticket(alert=alert, assignee=trigger["assignee"])
        except Exception as ex:
            LOG.error('Jira: Failed to create task: %s', ex)
            LOG.error(''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__)))
        return alert

    # triggered by external status changes, used by integrations
    def status_change(self, alert, status, text):
        return

    def _get_jira_connection(self):
        return JIRA(basic_auth=(self.jira_config["user"], self.jira_config["api token"]), server=self.jira_config["url"])

    def take_action(self, alert: Alert, action: str, text: str, **kwargs) -> Any:
        if action == "createJira":
            # create connection to jira api
            assignment_data = json.loads(text)
            LOG.debug("Jira: take_action alert: {} action: {} data {}".format(alert.id, action, assignment_data))
            return self._create_jira_ticket(alert=alert, assignee=assignment_data)

    # if action == "refreshJira":
    #     jira_tickets = jira_connection.search_issues("summary ~ \"{summary}\"".format(summary=text))
    #
    #     if len(jira_tickets) > 0:
    #         # update the ticket
    #         pass
    #
    # if action == "removeJira":
    #     pass
