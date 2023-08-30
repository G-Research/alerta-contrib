Jira Plugin 
===========

Creates a task in Jira and adds the Jira Task attribute in alarm. The created attribute is a link to the Jira task and opens in a new tab.

The integration works in 2 ways:
Automated mode (i.e. a Jira issue is raised automatically from an incoming Alerta alert based on certain matching alert field criteria)
Manual mode (i.e. a Jira issue is raised for a given Alerta alert when a NetOps operator clicks on a "Create Jira" button and selects a Jira Project on the alert details part of the UI)
In both the above cases, on successful creation of a Jira issue, the "Jira" alert field will contain a link to the new Jira issue:

Installation
------------

Clone the GitHub repo and run:

    $ python setup.py install

Or, to install remotely from GitHub run:

    $ pip install git+https://github.com/alerta/alerta-contrib.git#subdirectory=plugins/jira

Note: If Alerta is installed in a python virtual environment then plugins
need to be installed into the same environment for Alerta to dynamically
discover them.

Configuration
-------------

Add `jira` to the list of enabled `PLUGINS` in `alertad.conf` server
configuration file and set plugin-specific variables in the
server configuration file.

The "triggers" config applies only to Jira issues that are raised automatically based on alert field values

```python
PLUGINS = ['jira']

JIRA = {
    "token_auth": { "token": "<some valid token>" }, 
    "url": "<jira url>", 
    "no_verify_ssl": <"True" or "False">,
    "finished transition": "Done", 
    "triggers": [{ 
        "matches": {"<alert field>": "<alert field value>"}, 
        "assignee": {"project": "<jira project name>", "issue-type": "<e.g. Task>"}
        }
    ]
}

Add configuration to the web config.json file to display drop-down values for the "Create Jira" button in the alert details part of the UI.

"jira": {
      "assignees": [
        {
          "project": "<some Jira project>",
          "issue-type": "Task"
        }
      ]
  }
```

Troubleshooting
---------------

Restart Alerta API and confirm that the plugin has been loaded and enabled.

Set `DEBUG=True` in the `alertad.conf` configuration file and look for log
entries similar to below:

```
--------------------------------------------------------------------------------
2021-04-28 13:43:43,185 alerta.plugins[35]: [DEBUG] Server plugin 'jira' found. [in /venv/lib/python3.7/site-packages/alerta/utils/plugin.py:34]
--------------------------------------------------------------------------------
2021-04-28 13:43:43,707 alerta.plugins[35]: [INFO] Server plugin 'jira' loaded. [in /venv/lib/python3.7/site-packages/alerta/utils/plugin.py:42]
--------------------------------------------------------------------------------
2021-04-28 13:43:43,707 alerta.plugins[35]: [INFO] All server plugins enabled: reject, heartbeat, blackout, telegram, logstash, jira [in /venv/lib/python3.7/site-packages/alerta/utils/plugin.py:45]
--------------------------------------------------------------------------------
2021-04-28 13:43:54,540 alerta.plugins.jira[50]: [INFO] Jira: Received an alert request_id=dbf9e6a1-2c65-4284-887f-792873981c49 ip=10.100.100.239
--------------------------------------------------------------------------------
2021-04-28 13:43:54,541 alerta.plugins.jira[50]: [INFO] JIRA: Create task ... request_id=dbf9e6a1-2c65-4284-887f-792873981c49 ip=10.100.100.239
--------------------------------------------------------------------------------

```

References
----------

  * Jira REST API: https://blog.developer.atlassian.com/creating-a-jira-cloud-issue-in-a-single-rest-call/



Copyright (c) 2021 Alexandre Azedo.
