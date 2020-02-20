# -*- coding: utf-8 -*-
"""
Data for icinga_mock.
"""

import base64
import json

# Defaults
DEFAULTS = {
	"auth": f"Basic {base64.b64encode(b'user:pass').decode('utf-8')}"  # "Basic dXNlcjpwYXNz"
}

# Errors
ERRORS = {
	400: {
		"reason": "Bad request"
	},
	401: {
		"reason": "Unauthorized",
		"headers": {"WWW-Authenticate": "Basic realm=\"Icinga 2\""},
		"body": "<h1>Unauthorized. Please check your user credentials.</h1>"
	},
	404: {
		"reason": "No such path for mocked Icinga instance",
		"body": json.dumps({
			"error": 404,
			"status": "The requested path 'v1/bla/bla' could not be found for mocked Icinga."
		}),
	},
}


def get_error(status_code):
	err = ERRORS.get(status_code, dict())
	err["status_code"] = status_code
	return err


OBJECTS = {
	"hosts": {
		"localhost": {
			"name": "localhost",
			"type": "Host",
			"attrs": {
				'__name': 'localhost',
				'acknowledgement': 0.0, 'acknowledgement_expiry': 0.0, 'action_url': '', 'active': True,
				'address': '::1', 'address6': '', 'check_attempt': 1.0, 'check_command': 'hostalive',
				'check_interval': 60.0, 'check_period': '', 'check_timeout': None, 'command_endpoint': '',
				'display_name': 'localhost', 'downtime_depth': 0.0, 'enable_active_checks': True,
				'enable_event_handler': True, 'enable_flapping': False, 'enable_notifications': True,
				'enable_passive_checks': True, 'enable_perfdata': True, 'event_command': '', 'flapping': False,
				'flapping_current': 5.2, 'flapping_last_change': 0.0, 'flapping_threshold': 0.0,
				'flapping_threshold_high': 30.0, 'flapping_threshold_low': 25.0, 'force_next_check': False,
				'force_next_notification': False, 'groups': [], 'ha_mode': 0.0, 'handled': False, 'icon_image': '',
				'icon_image_alt': '', 'last_check': 1580784206.72453,
				'last_check_result': {
					'active': True, 'check_source': 'icinga',
					'command': [
						'/usr/lib64/nagios/plugins/check_ping', '-H', '::1', '-c', '5000,100%', '-w', '3000,80%'
					],
					'execution_end': 1580784206.724489,
					'execution_start': 1580784202.58688,
					'exit_status': 0.0,
					'output': 'PING OK - Packet loss = 0%, RTA = 0.03 ms',
					'performance_data': [
						'rta=0.028000ms;3000.000000;5000.000000;0.000000', 'pl=0%;80;100;0'
					],
					'schedule_end': 1580784206.72453,
					'schedule_start': 1580784202.586596,
					'state': 0.0,
					'ttl': 0.0,
					'type': 'CheckResult',
					'vars_after': {
						'attempt': 1.0, 'reachable': True, 'state': 0.0, 'state_type': 1.0
					},
					'vars_before': {
						'attempt': 1.0, 'reachable': True, 'state': 0.0, 'state_type': 1.0
					}
				},
				'last_hard_state': 0.0, 'last_hard_state_change': 1580783769.028527, 'last_reachable': True,
				'last_state': 0.0, 'last_state_change': 1580783769.028527, 'last_state_down': 0.0,
				'last_state_type': 1.0, 'last_state_unreachable': 0.0, 'last_state_up': 1580784206.724542,
				'max_check_attempts': 3.0, 'name': 'localhost', 'next_check': 1580784265.1145582, 'notes': '',
				'notes_url': '', 'original_attributes': None, 'package': '_etc', 'paused': False,
				'previous_state_change': 1580783769.028527, 'problem': False, 'retry_interval': 30.0, 'severity': 8.0,
				'source_location': {
					'first_column': 1.0, 'first_line': 53.0, 'last_column': 23.0, 'last_line': 53.0,
					'path': '/etc/icinga2/conf.d/hosts.conf'
				},
				'state': 0.0, 'state_type': 1.0, 'templates': ['localhost', 'generic-host'], 'type': 'Host',
				'vars': None, 'version': 0.0, 'volatile': False, 'zone': ''
			}
		}
	}
}
