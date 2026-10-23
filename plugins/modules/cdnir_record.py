#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, AH MZ <ahmz.ut@gmail.com>
# MIT License (see LICENSE or https://opensource.org/licenses/MIT)

DOCUMENTATION = r'''
---
module: cdnir_record
short_description: Manage DNS records on CDN.ir / Asiatech Cloud (alias for cdnir_dns)
description:
  - Create, update, or delete DNS records within a zone on CDN.ir (Asiatech Cloud).
  - Main module is C(cdnir_dns), this module is provided as an alias.
version_added: "1.0.0"
options:
  zone:
    description:
      - The name of the parent domain zone (e.g. C(example.com) or C(example.ir)).
    required: true
    type: str
  record:
    description:
      - The record name.
      - Can be a relative subdomain (e.g. C(www), C(api), C(_acme-challenge)), C(@) for the zone root, or a fully qualified domain name (FQDN).
    required: true
    type: str
  type:
    description:
      - DNS record type.
    required: true
    choices: [A, AAAA, CNAME, TXT, MX, SRV, CAA, NS, ALIAS, SPF]
    type: str
  value:
    description:
      - The record content/value.
      - Required when C(state=present).
      - For C(TXT), text string without extra outer quotes.
      - For C(MX), format as C("<priority> <server>").
      - For C(SRV), format as C("<priority> <weight> <port> <target>").
      - For C(CAA), format as C("<flag> <tag> <value>").
    aliases: [content]
    type: str
  ttl:
    description:
      - Time to live in seconds.
    default: 3600
    type: int
  solo:
    description:
      - Whether the record should be the only record for that name and type.
    default: false
    type: bool
  disabled:
    description:
      - Whether the DNS record is disabled in DNS responses.
    default: false
    type: bool
  state:
    description:
      - Whether the record should be present or absent.
    default: present
    choices: [present, absent]
    type: str
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
- name: Add an A record
  cdnir_record:
    zone: example.ir
    record: api
    type: A
    value: 192.0.2.1
    ttl: 300
    state: present
    api_token: "{{ cdnir_token }}"

- name: Add apex A record
  cdnir_record:
    zone: example.ir
    record: "@"
    type: A
    value: 192.0.2.1
    state: present

- name: Add a TXT record for ACME challenge
  cdnir_record:
    zone: example.ir
    record: _acme-challenge.api
    type: TXT
    value: "abc123xyzToken"
    ttl: 120
    state: present

- name: Delete a specific record
  cdnir_record:
    zone: example.ir
    record: test
    type: A
    value: 192.0.2.1
    state: absent
'''

RETURN = r'''
record:
  description: The created or updated record object.
  type: dict
  returned: always
'''

# Forward execution to cdnir_dns
from .cdnir_dns import run_module, main

if __name__ == '__main__':
    main()
