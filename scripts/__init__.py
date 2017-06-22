"""Define application variables."""

import os

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

SALESFORCE_CREDENTIALS = {
    'USERNAME': os.getenv('OK_WATCH_SALESFORCE_USERNAME'),
    'PASSWORD': os.getenv('OK_WATCH_SALESFORCE_PASSWORD'),
    'SECURITY_TOKEN': os.getenv('OK_WATCH_SALESFORCE_SECURITY_TOKEN')}

SLACK_ACCESS_TOKEN = os.getenv('SLACK_THOMASTHOREN_ACCESS_TOKEN')
SLACK_CHANNEL = 'ok_watch_salesforce'
