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
JIRA_CONFIG = app.config.get('JIRA') or os.environ.get('JIRA')

alert_properties = ["resource", "severity", "environment", "event", "service", "group", "value", "origin", "type",
                    "text"]
class JiraCreate(PluginBase):
    """
    Jira alerta plugin
    Automatically generate Jira tickets and manage create requests from API
    """
    _jira_finished_transition_str = "Done"

    def __init__(self):
        self.jira_config = JIRA_CONFIG
        self._validate_config_params(self.jira_config)
        super().__init__()

    def __init__(self, config=None):
        if config is None:
            config = JIRA_CONFIG

        self.jira_config = config
        self._validate_config_params(self.jira_config)
        super().__init__()

    def _validate_config_params(self, configParams):
        # validate that required properties are defined
        required_properties = ["url"]
        for required_property in required_properties:
            if required_property not in configParams:
                raise RuntimeError(
                    f"missing property [{required_property}] in config file ")
        auth_methods = ["basic_auth", "token_auth"]
        match = False
        for auth_method in auth_methods:
            if auth_method in configParams:
                match = True
        if not match:
            raise RuntimeError(
                f"missing auth method in config file, must be one of {auth_methods}")
        if "basic_auth" in configParams:
            basic_auth = configParams["basic_auth"]
            if "username" not in basic_auth or "password" not in basic_auth:
                raise RuntimeError(
                    f"missing property [username] or [password] in basic_auth")
        if "token_auth" in configParams:
            token_auth = configParams["token_auth"]
            if "token" not in token_auth:
                raise RuntimeError(
                    f"missing property [token] in token_auth")

    def _get_jira_connection(self):
        try:
            options = {}
            if "cert" in self.jira_config:
                options = {'verify': self.jira_config["cert"]}
                LOG.debug(f"Jira: use cert with authentication {options}")
            if "basic_auth" in self.jira_config:
                basic_auth = self.jira_config["basic_auth"]
                LOG.debug("Jira: using basic auth")
                return JIRA(basic_auth=(basic_auth["username"], basic_auth["password"]), server=self.jira_config["url"], options=options)
            if "token_auth" in self.jira_config:
                token_auth = self.jira_config["token_auth"]
                if "no_verify_ssl" in self.jira_config and self.jira_config["no_verify_ssl"]:
                    options = {'verify': False}
                LOG.debug("Jira: using api token")
                return JIRA(token_auth=(token_auth["token"]), server=self.jira_config["url"],  options=options)
        except Exception as ex:
            LOG.error('Jira: Failed to connect to Jira: %s', ex)
            LOG.error(''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__)))
            raise ex

    def __create_jira_url(self, key: str):
        return f"{self.jira_config['url']}browse/{key}"

    def _create_jira_ticket(self, alert: Alert, assignee: any):
        # create connection to jira api
        jira_connection = self._get_jira_connection()
        # get basic info from alert
        host = alert.resource.split(':')[0]
        LOG.debug(f"Jira: HOST        {host}")
        event = alert.event.split('.')[-1]
        LOG.debug(f"Jira: EVENT       {event}")
        # create jira ticket
        LOG.info(f"JIRA: Creating Jira ticket for alert: {alert.id}")

        # Specify format for summary and description fields
        summary = f"Severity: {alert.severity}: Resource {host} Event {event} - "
        description = f"ALERTA: Resource: {host} Event: {event} \n Text: {alert.text}. \n Alert ID {alert.id}"

        issue_dict = {
            'project': {'key': assignee["project"]},
            'summary': summary,
            'description': description,
            'issuetype': {'name': assignee["issue-type"]}
        }
        
        # check for customfields from the alertad.conf config file.....
        customfields = assignee["customfields"]
        if customfields:
            for custom_key, custom_value in customfields.items():
                LOG.debug(f"Custom Field Key: {custom_key}, Value: {custom_value}")
                issue_dict[custom_key] = custom_value

        for key, value in issue_dict.items():
            LOG.info(f"Issue Dict; Key: {key}, Value: {value}")

        task = jira_connection.create_issue(fields=issue_dict)

        jira_obj = {
            'url': self.__create_jira_url(task.key),
            'key': task.key,
            'id': task.id
        }

        if "user" in assignee:
            jira_connection.assign_issue(task, assignee["user"])
            jira_obj["user"] = assignee["user"]

        alert.attributes = {'jira': jira_obj}

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
                    LOG.debug(f"Jira: prop_value       {prop_value}")
                    if isinstance(prop_value, list):
                        for value in prop_value:
                            LOG.debug(f"Jira: value       {value}")
                            if not re.search(trigger[alert_property], value):
                                return False
                    elif not re.search(trigger[alert_property], prop_value):
                        LOG.debug(f"Jira: checking trigger string       {trigger[alert_property]} : {prop_value}")                        
                        return False
        return True

    def post_receive(self, alert: Alert):
        try:
            # if the alert is critical and don't duplicate, create task in Jira
            if alert.status not in ['ack', 'closed', 'shelved'] and alert.duplicate_count == 0:
                LOG.info("Jira: Received an alert")
                LOG.debug(f"Jira: ALERT       {alert}")
                LOG.debug(f"Jira: ID          {alert.id}")
                LOG.debug(f"Jira: RESOURCE    {alert.resource}")
                LOG.debug(f"Jira: EVENT       {alert.event}")
                LOG.debug(f"Jira: SEVERITY    {alert.severity}")
                LOG.debug(f"Jira: TEXT        {alert.text}")

                # iterate through configured triggers
                for trigger in self.jira_config["triggers"]:
                    # the first match triggers jira issue creation
                    if self._check_trigger(trigger["matches"], alert):
                        # validate that resource doesn't have a jira ticket already
                        jira_connection = self._get_jira_connection()
                        issues = jira_connection.search_issues(jql_str=f"summary ~ {alert.resource} AND summary ~ {alert.event} AND NOT status = 'Closed'")
                        if len(issues) == 0:
                            return self._create_jira_ticket(alert=alert, assignee=trigger["assignee"])
                        else:
                            LOG.info(f"Jira: Jira ticket already exists for resource: {alert.resource} with event: {alert.event}. Not creating a new one.")
        except Exception as ex:
            LOG.error('Jira: Failed to create task: %s', ex)
            LOG.error(''.join(traceback.format_exception(etype=type(ex), value=ex, tb=ex.__traceback__)))
        return alert

    # triggered by external status changes, used by integrations
    def status_change(self, alert, status, text):
        LOG.debug(f"Jira: status change: {alert.id} alert status: {status} text: {text}")
        return alert

    # ununsed for now
    def delete(self, alert: 'Alert', **kwargs) -> bool:
        if alert.attributes and 'jira' in alert.attributes:
            jira_key = alert.attributes["jira"]["key"]
            jira_connection = self._get_jira_connection()
            jira_issue = jira_connection.issue(jira_key)
            if jira_issue:
                transitions = jira_connection.transitions(jira_issue)
                for t in transitions:
                    if t["name"] == self._jira_finished_transition_str:
                        LOG.info(f"Jira: closed issue {jira_key}")
                        jira_connection.add_comment(jira_issue, f"Alert {alert.id} deleted, closing jira ticket")
                        jira_connection.transition_issue(jira_issue, transition=t["id"])
                        return True
        return False

    def _attach_jira_to_alert(self, alert: Alert, jira_key: str):
        try:
            # check if key is valid
            jira_connection = self._get_jira_connection()
            LOG.debug(f"Jira: attach issue, looking up key: {jira_key}")
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
            LOG.debug(f"Jira issue: {jira_key} not found")
            return alert

    def take_action(self, alert: Alert, action: str, text: str, **kwargs) -> Any:
        LOG.debug(f"Jira: take_action alert: {alert.id} action: {action} text {text}")
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
