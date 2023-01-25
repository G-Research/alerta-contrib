# unit test for jira plugin
# Path: plugins/jira/test_alerta_jira.py

import unittest
from alertaclient.models.alert import Alert
from mock import MagicMock, mock, patch
from alerta_jira import JiraCreate


class TestJiraPlugin(unittest.TestCase):
    sample_jira_config = {
        "user": "test",
        "url": "http://wwww.example.com",
        "api token": "test",
        "triggers": [
            {
                "matches": {
                    "event": "http(.*)"
                },
                "assignee": {
                    "project": "THJ",
                    "issue-type": "Task",
                    "user": "generalfuzz@gmail.com"
                }
            },
            {
                "matches": {
                    "event": "ht(.*)"
                },
                "assignee": {
                    "project": "THJ",
                    "issue-type": "Task",
                    "user": "headphonejames@gmail.com"
                }
            }
        ]
    }

    def test_json_config(self):
        # test that the required properties are defined in the json config file
        jira_config = {"user": "test"}
        with self.assertRaises(RuntimeError):
            self.create_jira = JiraCreate(config=jira_config)
        jira_config = {"user": "test", "url": "http://wwww.example.com"}
        with self.assertRaises(RuntimeError):
            self.create_jira = JiraCreate(jira_config)
        jira_config = {"url": "http://wwww.example.com", "api token": "test"}
        with self.assertRaises(RuntimeError):
            self.create_jira = JiraCreate(jira_config)

        jira_config = {"user": "test", "url": "http://wwww.example.com", "api token": "test"}
        self.create_jira = JiraCreate(jira_config)

    def test_ignored_alerts(self):
        alert = Alert(resource='test', event='http500', environment='test', severity='critical', service=['test'],
                      group='test', value='test', text='test', tags=['test'], attributes={'test': 'test'},
                      origin='test', type='test', raw_data='test', status='ack', duplicate_count=0, id='test')
        jira = JiraCreate(self.sample_jira_config)
        jira._get_jira_connection = mock.Mock()
        jira.post_receive(alert)
        jira._get_jira_connection.assert_not_called()

        alert.duplicate_count = 1
        alert.status = 'new'

        jira = JiraCreate(self.sample_jira_config)
        jira._get_jira_connection = mock.Mock()
        jira.post_receive(alert)
        jira._get_jira_connection.assert_not_called()

    def test_post_receive_valid(self):
        alert = Alert(id='test', resource='test', event='http500', environment='test', severity='critical',
                      service=['test'],
                      group='test', value='test', text='test', tags=['test'], attributes={'test': 'test'},
                      origin='test', type='test', raw_data='test', status='new', duplicate_count=0)

        jira = JiraCreate(self.sample_jira_config)
        with mock.patch.object(jira, '_get_jira_connection') as mock_get_jira_connection:
            class JiraIssue:
                def __init__(self):
                    self.id = 'jira-id'
                    self.key = 'jira-1234'

            mock_get_jira_connection.return_value.create_issue = MagicMock(return_value=JiraIssue())
            updated_alert = jira.post_receive(alert)
            assert updated_alert.attributes['jira']['id'] == 'jira-id'
            mock_get_jira_connection.assert_called()


    def test_jira_plugin(self):
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
