# unit test for jira plugin
# Path: plugins/jira/test_alerta_jira.py
import json
import unittest
from alertaclient.models.alert import Alert
from mock import MagicMock, mock, patch
from alerta_jira import JiraCreate
from jira import JIRAError


class TestJiraPlugin(unittest.TestCase):
    def __get_default_asignee(self):
        return {
            "project": "THJ",
            "issue-type": "Task",
            "assignee": "matcher@gmail.com"
        }

    def __get_default_jira_key(self):
        return "THJ-1234"

    def __get_default_jira_id(self):
        return "jira-1234"

    def __get_default_url(self):
        return "http://wwww.example.com"

    def __get_browse_url(self, url, key):
        return "{}/browse/{}".format(url, key)

    def __get_jira_config_single_match(self, matches={"event": "http(.*)"}):
        return {
            "user": "test",
            "url": self.__get_default_url(),
            "api token": "test",
            "finished transition": "Done",
            "triggers": [
                {
                    "matches": matches,
                    "assignee": self.__get_default_asignee()
                },
            ]
        }

    def __get_jira_config_two_matches(self,
                                      first_match={"event": "http(.*)"},
                                      second_match={"event": "sms(.*)"}):
        return {
            "user": "test",
            "url": "http://wwww.example.com",
            "api token": "test",
            "finished transition": "Done",
            "triggers": [
                {
                    "matches": first_match,
                    "assignee": self.__get_default_asignee()
                },
                {
                    "matches": second_match,
                    "assignee": {
                        "project": "THJ",
                        "issue-type": "Task",
                        "user": "secondmatch@gmail.com"
                    }
                },
            ]
        }

    def test_incomplete_json_config(self):
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

        jira_config = {"user": "test",
                       "url": "http://wwww.example.com",
                       "api token": "test",
                       "finished transition": "Done"}
        self.create_jira = JiraCreate(jira_config)

    def __generate_alert_obj(self, status='new', duplicate_count=0):
        return Alert(resource='test', event='http500', environment='test', severity='critical', service=['test'],
                     group='test', value='test', text='test', tags=['test'], attributes={'test': 'test'},
                     origin='test', type='test', raw_data='test', status=status, duplicate_count=duplicate_count,
                     id='test')

    def __generate_jira_create_obj(self, jira_config=None):
        if not jira_config:
            jira_config = self.__get_jira_config_single_match()
        return JiraCreate(jira_config)

    def test_pre_receieve(self):
        alert = self.__generate_alert_obj()
        jira = self.__generate_jira_create_obj()
        updated_alert = jira.pre_receive(alert)
        assert alert == updated_alert

    def __assert_jira_creation_not_executed(self, alert=None, jira_obj=None):
        if not jira_obj:
            jira_obj = self.__generate_jira_create_obj()
        jira_obj._get_jira_connection = mock.Mock()
        jira_obj.post_receive(alert)
        jira_obj._get_jira_connection.assert_not_called()

    def test_ignored_alerts(self):
        # test that alerts with 'ack', 'shelved', and 'closed' statue are ignored
        alert = self.__generate_alert_obj(status='closed')
        alert.status = 'ack'
        self.__assert_jira_creation_not_executed(alert=alert)
        alert.status = 'shelved'
        self.__assert_jira_creation_not_executed(alert=alert)
        # test that duplicate alerts are ignored
        alert.status = 'new'
        alert.duplicate_count = 1
        self.__assert_jira_creation_not_executed(alert=alert)

    def __assert_jira_creation_not_executed_single_match(self, matches=None):
        jira_config = self.__get_jira_config_single_match(matches=matches)
        self.__assert_jira_create_not_triggered(jira_config)

    def __assert_jira_create_not_triggered(self, jira_config):
        alert = self.__generate_alert_obj()
        jira_obj = self.__generate_jira_create_obj(jira_config=jira_config)
        self.__assert_jira_creation_not_executed(alert=alert, jira_obj=jira_obj)

    def test_post_receive_not_creating_jira(self):
        not_matches = [{"resource": "cr.tical"}, {"event": "sms(.*)"}, {"event": "http501"}, {"event": "h(.*)1"},
                       {"environment": "production"}, {"environment": "...s"}, {"severity": "urgent"},
                       {"severity": ".o(.*)"}, {"group": "top tier"}, {"group": "a(.*)"}, {"value": "worthy"},
                       {"value": "(.*)a"}, {"text": "was destroyed"}, {"text": "was(.*)"}, {"origin": "story"},
                       {"service": 'production'}, {"service": '(.*)w'}, {"service": "test", "origin": "story"},
                       {"status": "test", "type": "test", "origin": "test", "service": "tast"}]
        for not_match in not_matches:
            self.__assert_jira_creation_not_executed_single_match(matches=not_match)

    def __create_jira_issue_mock(self, jira_id, jira_key):
        class JiraIssue:
            def __init__(self):
                self.id = jira_id
                self.key = jira_key

        return JiraIssue()

    def __assert_post_receive_creates_jira_connection(self, jira_config=None):
        alert = self.__generate_alert_obj()
        jira_obj = self.__generate_jira_create_obj(jira_config=jira_config)
        jira_id = self.__get_default_jira_id()
        jira_key = self.__get_default_jira_key()
        with mock.patch.object(jira_obj, '_get_jira_connection') as mock_get_jira_connection:
            jira_issue = self.__create_jira_issue_mock(jira_id, jira_key)
            mock_get_jira_connection.return_value.create_issue = MagicMock(return_value=jira_issue)
            updated_alert = jira_obj.post_receive(alert)
            mock_get_jira_connection.assert_called()
            # test that the jira id is added to the alert attributes
            assert updated_alert.attributes['jira']['id'] == jira_id
            # test that the jira id is added to the alert attributes
            assert updated_alert.attributes['jira']['url'] == self.__get_browse_url(self.__get_default_url(), jira_key)
            assert updated_alert.attributes['jira']['key'] == jira_key

    def __assert_jira_single_matching_config(self, matches=None):
        jira_config = self.__get_jira_config_single_match(matches={"resource": "test"})
        self.__assert_post_receive_creates_jira_connection(jira_config=jira_config)

    def test_post_receive_creates_jira(self):
        self.__assert_post_receive_creates_jira_connection()
        matches = [{"service": "test"}, {"service": "(.*)"}, {"service": "(.*)t"}, {"event": "http500"},
                   {"event": "http([0-9]{3})"}, {"event": "(.*)500"}, {"environment": "test"}, {"environment": "(.*)"},
                   {"environment": "(.*)t"}, {"severity": "critical"}, {"severity": "(.*)"}, {"severity": "c(.*)"},
                   {"severity": "c[a-z]*"}, {"severity": "cr.tical"}, {"service": "test"},
                   {"service": "test", "event": "http500"},
                   {"service": "test", "event": "http500", "environment": "test"}, {"group": "test"}, {"value": "test"},
                   {"text": "test"}, {"origin": "test"}, {"type": "test"}, {"status": "test"},
                   {"status": "test", "type": "test", "origin": "test", "service": "test"}]
        for match in matches:
            self.__assert_jira_single_matching_config(matches=match)

    def test_two_match_defined(self):
        # positive tests
        jira_config = self.__get_jira_config_two_matches(
            first_match={"service": "tast"}, second_match={"service": ".*"})
        self.__assert_post_receive_creates_jira_connection(jira_config=jira_config)
        jira_config = self.__get_jira_config_two_matches(
            first_match={"service": "test"}, second_match={"service": "s.*"})
        self.__assert_post_receive_creates_jira_connection(jira_config=jira_config)
        jira_config = self.__get_jira_config_two_matches(
            first_match={"service": "nodles"}, second_match={"service": ".*t"})
        self.__assert_post_receive_creates_jira_connection(jira_config=jira_config)
        # negative tests
        jira_config = self.__get_jira_config_two_matches(
            first_match={"service": "tast"}, second_match={"service": "j.*"})
        self.__assert_jira_create_not_triggered(jira_config=jira_config)
        jira_config = self.__get_jira_config_two_matches(
            first_match={"service": "tester"}, second_match={"service": "..et"})
        self.__assert_jira_create_not_triggered(jira_config=jira_config)

    def __assert_jira_attributes_match_expected_jira_obj(self, jira_id, jira_key, updated_alert):
        assert updated_alert.attributes['jira']['id'] == jira_id
        assert updated_alert.attributes['jira']['url'] == self.__get_browse_url(self.__get_default_url(), jira_key)
        assert updated_alert.attributes['jira']['key'] == jira_key

    def test_take_action_create_jira(self):
        alert = self.__generate_alert_obj()
        jira_obj = self.__generate_jira_create_obj()
        assignee_str = json.dumps(self.__get_default_asignee())
        jira_id = self.__get_default_jira_id()
        jira_key = self.__get_default_jira_key()

        # negative test
        jira_obj._get_jira_connection = mock.Mock()
        updated_alert = jira_obj.take_action(alert, "casreateJira", assignee_str)
        jira_obj._get_jira_connection.assert_not_called()
        assert alert == updated_alert

        # positive test
        jira_obj = self.__generate_jira_create_obj()
        with mock.patch.object(jira_obj, '_get_jira_connection') as mock_get_jira_connection:
            jira_issue = self.__create_jira_issue_mock(jira_id, self.__get_default_jira_key())
            mock_get_jira_connection.return_value.create_issue = MagicMock(return_value=jira_issue)
            updated_alert = jira_obj.take_action(alert, "createJira", assignee_str)
            mock_get_jira_connection.assert_called()
            # test that the jira id is added to the alert attributes
            self.__assert_jira_attributes_match_expected_jira_obj(jira_id, jira_key, updated_alert)

    def test_take_action_detach_jira(self):
        alert = self.__generate_alert_obj()
        jira_attributes = {'id': self.__get_default_jira_id(),
                           'key': self.__get_default_jira_key(),
                           'url': self.__get_browse_url(self.__get_default_url(), self.__get_default_jira_key())}
        alert.attributes['jira'] = jira_attributes
        jira_attributes_str = json.dumps(jira_attributes)
        jira_obj = self.__generate_jira_create_obj()

        # negative tests
        updated_alert = jira_obj.take_action(alert, "dewtachJira", jira_attributes_str)
        assert alert == updated_alert

        bad_jira_attributes = {'id': self.__get_default_jira_id(),
                               'key': 'fake-key',
                               'url': self.__get_browse_url(self.__get_default_url(),
                                                            self.__get_default_jira_key())}
        bad_jira_attributes_str = json.dumps(bad_jira_attributes)
        updated_alert = jira_obj.take_action(alert, "detachJira", bad_jira_attributes_str)
        assert alert == updated_alert

        # positive test
        updated_alert = jira_obj.take_action(alert, "detachJira", jira_attributes_str)
        assert alert != updated_alert
        assert not hasattr(updated_alert.attributes, "jira")

    def test_take_action_attach_jira(self):
        alert = self.__generate_alert_obj()
        url = self.__get_browse_url(self.__get_default_url(),
                                    self.__get_default_jira_key())
        jira_attributes = {'id': self.__get_default_jira_id(),
                           'key': self.__get_default_jira_key(),
                           'url': url}
        alert.attributes['jira'] = jira_attributes
        jira_obj = self.__generate_jira_create_obj()
        jira_id = self.__get_default_jira_id()
        jira_key = self.__get_default_jira_key()

        # negative tests
        updated_alert = jira_obj.take_action(alert, "attacgsJira", jira_key)
        assert alert == updated_alert

        # positive test
        with mock.patch.object(jira_obj, '_get_jira_connection') as mock_get_jira_connection:
            jira_issue = self.__create_jira_issue_mock(jira_id, self.__get_default_jira_key())
            mock_get_jira_connection.return_value.issue = MagicMock(return_value=jira_issue)
            updated_alert = jira_obj.take_action(alert, "attachJira", jira_key)
            assert alert != updated_alert
            # test that the jira id is added to the alert attributes
            self.__assert_jira_attributes_match_expected_jira_obj(jira_id, jira_key, updated_alert)

        # test with url as jira key
        with mock.patch.object(jira_obj, '_get_jira_connection') as mock_get_jira_connection:
            jira_issue = self.__create_jira_issue_mock(jira_id, self.__get_default_jira_key())
            mock_get_jira_connection.return_value.issue = MagicMock(return_value=jira_issue)
            updated_alert = jira_obj.take_action(alert, "attachJira", url)
            assert alert != updated_alert
            # test that the jira id is added to the alert attributes
            self.__assert_jira_attributes_match_expected_jira_obj(jira_id, jira_key, updated_alert)

    def test_delete(self):
        alert = self.__generate_alert_obj()
        jira_attributes = {'id': self.__get_default_jira_id(),
                           'key': self.__get_default_jira_key(),
                           'url': self.__get_browse_url(self.__get_default_url(),
                                                        self.__get_default_jira_key())}
        alert.attributes['jira'] = jira_attributes
        jira_obj = self.__generate_jira_create_obj()
        jira_id = self.__get_default_jira_id()

        with mock.patch.object(jira_obj, '_get_jira_connection') as mock_get_jira_connection:
            jira_issue = self.__create_jira_issue_mock(jira_id, self.__get_default_jira_key())
            mock_get_jira_connection.return_value.issue = MagicMock(return_value=jira_issue)
            mock_get_jira_connection.return_value.transitions = MagicMock(return_value=[{'id': '1', 'name': 'Open'},
                                                                                        {'id': '2', 'name': 'Done'}])
            mock_get_jira_connection.return_value.add_comment = MagicMock()
            mock_get_jira_connection.return_value.transition_issue = MagicMock()

            is_deleted = jira_obj.delete(alert)
            mock_get_jira_connection.return_value.add_comment.assert_called()
            mock_get_jira_connection.return_value.transition_issue.assert_called_with(jira_issue, transition='2')
            assert is_deleted


if __name__ == '__main__':
    unittest.main()
