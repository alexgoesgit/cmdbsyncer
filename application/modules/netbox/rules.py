#!/usr/bin/env python3
"""
Netbox Rules
"""
#pylint: disable=too-few-public-methods
import ast
from application.modules.rule.rule import Rule
from application.helpers.syncer_jinja import render_jinja

#   . -- Devices
class NetboxVariableRule(Rule):# pylint: disable=too-few-public-methods
    """
    Add custom Variables for Netbox Devices
    """

    name = "Netbox -> DCIM Device Attributes"

    def add_outcomes(self, _rule, rule_outcomes, outcomes):
        """
        Filter if labels match to a rule
        """
        # pylint: disable=too-many-nested-blocks
        sub_values = [
            'model'
        ]
        outcomes.setdefault('fields', {})
        outcomes.setdefault('custom_fields', {})
        outcomes.setdefault('do_not_update_keys', [])
        outcomes.setdefault('sub_fields', {})
        for outcome in rule_outcomes:
            action_param = outcome['param']
            field = outcome['action']
            if field == 'update_optout':
                fields = [str(x).strip() for x in action_param.split(',')]
                outcomes['do_not_update_keys'] += fields
            elif field == 'custom_field':
                try:
                    new_value  = render_jinja(action_param, mode="nullify",
                                             HOSTNAME=self.hostname, **self.attributes)
                    custom_key, custom_value = new_value.split(':')
                    outcomes['custom_fields'][custom_key] = {'value': custom_value}
                except ValueError:
                    continue
            else:
                new_value  = render_jinja(action_param, mode="nullify",
                                         HOSTNAME=self.hostname, **self.attributes)

                if new_value in ['None', '']:
                    continue

                if field == 'serial':
                    new_value = new_value[:50]

                if field in sub_values:
                    outcomes['sub_fields'][field] = {'value': new_value.strip()}
                else:
                    outcomes['fields'][field] = {'value': new_value.strip()}

        return outcomes
#.
#   . -- IP Addresses
class NetboxIpamIPaddressRule(NetboxVariableRule):
    """
    Rules for IP Addresses 
    """
    name = "Netbox -> IPAM IP Attributes"


    def add_outcomes(self, rule, rule_outcomes, outcomes):
        """
        Filter if labels match to a rule
        """
        # pylint: disable=too-many-nested-blocks
        outcomes.setdefault('ips', [])
        sub_fields = [
        ]
        outcome_object = {}
        outcome_subfields_object = {}
        rule_name = rule['name']
        ignored_ips = []

        outcome_selection, ignored_ips =\
                self.get_multilist_outcomes(rule_outcomes, 'ignore_ip')

        for entry in outcome_selection:
            outcome_object = {}
            outcome_subfields_object = {}
            for key, value in entry.items():
                if key == 'name' and value in ignored_ips:
                    break
                if key in sub_fields:
                    outcome_subfields_object[key] = {'value': value}
                else:
                    outcome_object[key] = {'value': value}

            outcomes['ips'].append({'fields': outcome_object,
                                           'sub_fields': outcome_subfields_object,
                                           'by_rule': rule_name})
        return outcomes
#.
#   . -- Interfaces
class NetboxDevicesInterfaceRule(NetboxVariableRule):
    """
    Rules for Device Interfaces
    """
    name = "Netbox -> DCIM Interfaces"


    def handle_fields(self, field_name, field_value):
        """
        Special Ops for Interfaces
        """
        if field_name == 'name' and not field_value:
            return "SKIP_RULE"

        field_value = field_value.strip()
        if field_value == "None":
            field_value = None
        if field_name == 'mac_address':
            if not field_value:
                return "SKIP_FIELD"
            field_value = field_value.upper()
        if field_name == 'mtu':
            if not field_value:
                return "SKIP_FIELD"
            field_value = int(field_value)

        return field_value


    def add_outcomes(self, rule, rule_outcomes, outcomes):
        """
        Filter if labels match to a rule
        """
        # pylint: disable=too-many-nested-blocks
        rule_name = rule['name']
        outcomes.setdefault('interfaces', [])
        sub_fields = [
            'ip_address',
            'netbox_device_id',
        ]

        outcome_selection, ignored_interfaces =\
                self.get_multilist_outcomes(rule_outcomes, 'ignore_interface')

        for entry in outcome_selection:
            outcome_object = {}
            outcome_subfields_object = {}
            for key, value in entry.items():
                if key == 'name' and value in ignored_interfaces:
                    break
                if key in sub_fields:
                    outcome_subfields_object[key] = {'value': value}
                else:
                    outcome_object[key] = {'value': value}

            outcomes['interfaces'].append({'fields': outcome_object,
                                           'sub_fields': outcome_subfields_object,
                                           'by_rule': rule_name})
        return outcomes
#.
#   . -- Contacts
class NetboxContactRule(NetboxVariableRule):
    """
    Attribute Options for a Contact
    """
    name = "Netbox -> Tenancy Contacts"

    def add_outcomes(self, _rule, rule_outcomes, outcomes):
        """
        Filter if labels match to a rule
        """
        # pylint: disable=too-many-nested-blocks
        outcomes.setdefault('fields', {})
        for outcome in rule_outcomes:
            action_param = outcome['param']
            action = outcome['action']

            hostname = self.db_host.hostname

            new_value  = render_jinja(action_param, mode="nullify",
                                     HOSTNAME=hostname, **self.attributes).strip()

            if action == 'email':
                if not '@' in new_value:
                    continue
                if not new_value or new_value == '':
                    continue

            outcomes['fields'][action] = {'value': new_value}
        return outcomes
#.
#   . -- Dataflow
class NetboxDataflowRule(NetboxVariableRule):
    """
    Attribute Options for a Dataflow
    """
    name = "Netbox -> Dataflow"

    def add_outcomes(self, rule, rule_outcomes, outcomes):
        """
        Filter if labels match to a rule
        """
        # pylint: disable=too-many-nested-blocks
        outcomes.setdefault('rules', [])
        rule_name = rule['name']
        unique_fields = {}
        multiply_fields = []
        for outcome in rule_outcomes:
            field_name = outcome['field_name']
            field_value = outcome['field_value']

            hostname = self.db_host.hostname

            new_value  = render_jinja(field_value, mode="nullify",
                                     HOSTNAME=hostname, **self.attributes).strip()
            if not new_value:
                continue

            if outcome['expand_value_as_list']:
                for list_value in new_value.split(','):
                    if not list_value:
                        continue
                    outcome_object = {}
                    outcome_object[field_name] = {
                            'value': list_value.strip(),
                            'use_to_identify': outcome['use_to_identify'],
                            'expand_value_as_list': outcome['expand_value_as_list'],
                            }
                    multiply_fields.append(outcome_object)
            else:
                unique_fields[field_name] = {
                        'value': new_value,
                        'use_to_identify': outcome['use_to_identify'],
                        'expand_value_as_list': outcome['expand_value_as_list'],
                        'is_list': outcome['is_netbox_list_field'],
                        }

        if multiply_fields:
            for field in multiply_fields:
                new_dict = field
                new_dict.update(unique_fields)
                outcome_object = {
                    'rule': rule_name,
                    'fields': new_dict,
                }
                outcomes['rules'].append(outcome_object)
        else:
            outcome_object = {
                'rule': rule_name,
                'fields': unique_fields,
            }
            outcomes['rules'].append(outcome_object)
        return outcomes
#.
