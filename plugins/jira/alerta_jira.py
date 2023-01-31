import json
import copy
import logging
import os
from jira import JIRA, JIRAError
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
    _jira_finished_transition_str = "Done"

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
        required_properties = ["user", "url", "api token", "finished transition"]
        for required_property in required_properties:
            if required_property not in config:
                raise RuntimeError(
                    "missing property [{}] in config file ".format(required_property))

    def __create_jira_url(self, key: str):
        return "{url}/browse/{task}".format(url=self.jira_config["url"], task=key)

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
        alert.attributes = {'jira':
            {
                'url': self.__create_jira_url(task.key),
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
                    # check if property is a list or a string
                    if isinstance(prop_value, list):
                        for value in prop_value:
                            if not re.search(trigger[alert_property], value):
                                return False
                    elif not re.search(trigger[alert_property], prop_value):
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
        LOG.debug("Jira: status change: {} alert status: {} text: {}".format(alert.id, status, text))
        return alert

    def delete(self, alert: 'Alert', **kwargs) -> bool:
        if alert.attributes and 'jira' in alert.attributes:
            jira_key = alert.attributes["jira"]["key"]
            jira_connection = self._get_jira_connection()
            jira_issue = jira_connection.issue(jira_key)
            if jira_issue:
                transitions = jira_connection.transitions(jira_issue)
                for t in transitions:
                    if t["name"] == self._jira_finished_transition_str:
                        LOG.info("Jira: closed issue {}".format(jira_key))
                        jira_connection.add_comment(jira_issue, "Alert {} deleted, closing jira ticket".format(alert.id))
                        jira_connection.transition_issue(jira_issue, transition=t["id"])
                        return True
        return False

    def _get_jira_connection(self):
        return JIRA(basic_auth=(self.jira_config["user"], self.jira_config["api token"]), server=self.jira_config["url"])

    def _attach_jira_to_alert(self, alert: Alert, jira_key: str):
        try:
            # check if key is valid
            jira_connection = self._get_jira_connection()
            LOG.debug("Jira: attach issue, looking up key: {}".format(jira_key))
            # check if jira ticket exists
            issue = jira_connection.issue(jira_key)
            if issue:
                # attach jira ticket to alert
                updated_alert = copy.deepcopy(alert)
                updated_alert.attributes["jira"] = {
                    "key": jira_key,
                    "url": self.__create_jira_url(jira_key),
                    "id": issue.id
                }
                return updated_alert
        except JIRAError:
            LOG.debug("Jira issue: {} not found".format(jira_key))

    def take_action(self, alert: Alert, action: str, text: str, **kwargs) -> Any:
        LOG.debug("Jira: take_action alert: {} action: {} text {}".format(alert.id, action, text))
        if action == "createJira":
            # create connection to jira api
            data = json.loads(text)
            return self._create_jira_ticket(alert=alert, assignee=data)
        if action == "detachJira":
            # check if jira is attached to ticket
            data = json.loads(text)
            if data["key"] == alert.attributes["jira"]["key"]:
                # detach jira ticket from alert without modifying the initial alert obj
                updated_alert = copy.deepcopy(alert)
                del updated_alert.attributes["jira"]
                return updated_alert
        if action == "attachJira":
            jira_key = text
            # Also accept a URL string
            if text.startswith("https:") or text.startswith("http:"):
                jira_key = text.rsplit('/', 1)[-1]
            return self._attach_jira_to_alert(alert=alert, jira_key=jira_key)

        return alert
