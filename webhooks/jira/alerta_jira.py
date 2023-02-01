
# from alerta.models.alert import Alert
from alerta.webhooks import WebhookBase

# set plugin logger
LOG = logging.getLogger('alerta.webhooks.jira')


class JiraWebhook(WebhookBase):

    def incoming(self, query_string, payload):
        LOG.info("here!!")
        LOG.info(payload)
        LOG.info(query_string)