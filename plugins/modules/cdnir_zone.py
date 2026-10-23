#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, AH MZ <ahmz.ut@gmail.com>
# MIT License (see LICENSE or https://opensource.org/licenses/MIT)

DOCUMENTATION = r'''
---
module: cdnir_zone
short_description: Manage DNS zones on CDN.ir / Asiatech Cloud
description:
  - Create, delete, or verify DNS zones on CDN.ir (Asiatech Cloud).
version_added: "1.0.0"
options:
  name:
    description:
      - The name of the domain zone (e.g. C(example.com) or C(example.ir)).
    required: true
    type: str
  state:
    description:
      - Whether the zone should exist or not.
    default: present
    choices: [present, absent]
    type: str
  verify:
    description:
      - If true, requests verification of domain NS delegation.
    default: false
    type: bool
  api_token:
    description:
      - CDN.ir / Asiatech Bearer API token.
      - Can also be set using the C(CDNIR_API_TOKEN) or C(ASIATECH_API_TOKEN) environment variables.
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
- name: Ensure DNS zone exists
  cdnir_zone:
    name: example.ir
    state: present
    api_token: "{{ cdnir_token }}"

- name: Delete DNS zone
  cdnir_zone:
    name: example.ir
    state: absent
    api_token: "{{ cdnir_token }}"

- name: Verify domain NS delegation
  cdnir_zone:
    name: example.ir
    state: present
    verify: true
    api_token: "{{ cdnir_token }}"
'''

RETURN = r'''
zone:
  description: Domain zone details.
  returned: when state is present
  type: dict
  sample:
    id: 10001
    name: "example.ir"
    status: "active"
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
        name=dict(type='str', required=True),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        verify=dict(type='bool', default=False),
        api_token=dict(type='str', no_log=True, default=None),
        api_endpoint=dict(type='str', default='https://bss.asiatech.cloud/api/v3'),
    )

    result = dict(
        changed=False,
        zone={},
        diff={},
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    domain_name = module.params['name'].strip().rstrip('.')
    state = module.params['state']
    verify = module.params['verify']

    try:
        client = CDNirClient(
            api_token=module.params['api_token'],
            api_endpoint=module.params['api_endpoint']
        )
    except CDNirAPIError as e:
        module.fail_json(msg=str(e), **result)

    try:
        existing_domain = client.get_domain(domain_name)
    except CDNirAPIError as e:
        module.fail_json(msg=f"Failed to query domain '{domain_name}': {e}", **result)

    if state == 'present':
        if not existing_domain:
            result['diff'] = {
                'before': {},
                'after': {'name': domain_name, 'state': 'present'}
            }
            if not module.check_mode:
                try:
                    client.create_domain(domain_name)
                    existing_domain = client.get_domain(domain_name) or {'name': domain_name}
                except CDNirAPIError as e:
                    module.fail_json(msg=f"Failed to create domain '{domain_name}': {e}", **result)
            result['changed'] = True

        result['zone'] = existing_domain or {'name': domain_name}

        if verify and not module.check_mode:
            try:
                client.verify_domain(domain_name)
            except CDNirAPIError:
                pass

    elif state == 'absent':
        if existing_domain:
            result['diff'] = {
                'before': existing_domain,
                'after': {}
            }
            if not module.check_mode:
                try:
                    client.delete_domain(domain_name)
                except CDNirAPIError as e:
                    module.fail_json(msg=f"Failed to delete domain '{domain_name}': {e}", **result)
            result['changed'] = True
            result['zone'] = {}

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
