#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, AH MZ <ahmz.ut@gmail.com>
# MIT License (see LICENSE or https://opensource.org/licenses/MIT)

DOCUMENTATION = r'''
---
module: cdnir_record_info
short_description: Gather information about DNS records on CDN.ir / Asiatech Cloud
description:
  - Query DNS records for a given domain zone on CDN.ir (Asiatech Cloud).
version_added: "1.0.0"
options:
  zone:
    description:
      - The name of the parent domain zone (e.g. C(example.com) or C(example.ir)).
    required: true
    type: str
  record:
    description:
      - Optional filter for specific record name or FQDN.
    type: str
  type:
    description:
      - Optional filter by DNS record type (e.g. C(A), C(TXT)).
    choices: [A, AAAA, CNAME, TXT, MX, SRV, CAA, NS, ALIAS, SPF]
    type: str
  api_token:
    description:
      - CDN.ir / Asiatech Bearer API token.
    type: str
    no_log: true
  api_endpoint:
    description:
      - Base URL of the CDN.ir API.
    default: "https://bss.asiatech.cloud/api/v3"
    type: str
author:
  - AH MZ (@ahmz1833) <ahmz.ut@gmail.com>
'''

EXAMPLES = r'''
- name: Query all records in zone
  cdnir_record_info:
    zone: example.ir
    api_token: "{{ cdnir_token }}"
  register: zone_records

- name: Query all TXT records
  cdnir_record_info:
    zone: example.ir
    type: TXT
    api_token: "{{ cdnir_token }}"
  register: txt_records
'''

RETURN = r'''
records:
  description: List of matched record objects.
  type: list
  returned: always
'''

import sys
import os

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ahmz1833.cdnir.plugins.module_utils.cdnir_api import CDNirClient, CDNirAPIError
except ImportError:
    try:
        from ansible_collections.community.cdnir.plugins.module_utils.cdnir_api import CDNirClient, CDNirAPIError
    except ImportError:
        try:
            from ansible.module_utils.cdnir_api import CDNirClient, CDNirAPIError
        except ImportError:
            sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'module_utils')))
            from cdnir_api import CDNirClient, CDNirAPIError


def run_module():
    module_args = dict(
        zone=dict(type='str', required=True),
        record=dict(type='str', default=None),
        type=dict(type='str', choices=['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'SRV', 'CAA', 'NS', 'ALIAS', 'SPF'], default=None),
        api_token=dict(type='str', no_log=True, default=None),
        api_endpoint=dict(type='str', default='https://bss.asiatech.cloud/api/v3'),
    )

    result = dict(
        changed=False,
        records=[]
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    zone = module.params['zone'].strip().rstrip('.')
    filter_record = module.params['record']
    filter_type = module.params['type']

    try:
        client = CDNirClient(
            api_token=module.params['api_token'],
            api_endpoint=module.params['api_endpoint']
        )
    except CDNirAPIError as e:
        module.fail_json(msg=str(e), **result)

    try:
        records = client.list_records(zone, record_type=filter_type)
    except CDNirAPIError as e:
        module.fail_json(msg=f"Failed to query records for zone '{zone}': {e}", **result)

    if filter_record:
        target_fqdn = CDNirClient.get_fqdn(filter_record, zone).rstrip('.').lower()
        records = [
            r for r in records
            if r.get('name', '').rstrip('.').lower() == target_fqdn
        ]

    result['records'] = records
    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
