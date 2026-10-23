#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2026, AH MZ <ahmz.ut@gmail.com>
# MIT License (see LICENSE or https://opensource.org/licenses/MIT)

DOCUMENTATION = r'''
---
module: cdnir_dns
short_description: Manage DNS records on CDN.ir / Asiatech Cloud
description:
  - Create, update, or delete DNS records within a zone on CDN.ir (Asiatech Cloud).
  - Designed to mirror the Cloudflare DNS module (C(cloudflare_dns)) interface.
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
      - Only applicable when C(state=present). If set to C(true), all other records with the same name and type will be removed.
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
- name: Add an A record for apex
  cdnir_dns:
    zone: example.ir
    record: "@"
    type: A
    value: 192.0.2.1
    state: present
    api_token: "{{ cdnir_token }}"

- name: Add an A record for a subdomain
  cdnir_dns:
    zone: example.ir
    record: api
    type: A
    value: 192.0.2.2
    ttl: 300
    state: present

- name: Ensure single CNAME record exists (solo mode)
  cdnir_dns:
    zone: example.ir
    record: www
    type: CNAME
    value: example.ir.
    solo: true
    state: present

- name: Add a TXT record for ACME challenge
  cdnir_dns:
    zone: example.ir
    record: _acme-challenge.api
    type: TXT
    value: "abc123challengeToken"
    ttl: 120
    state: present

- name: Delete a specific record
  cdnir_dns:
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

import sys
import os
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, List, Optional

from ansible.module_utils.basic import AnsibleModule


# ==================== Standalone API Client ====================

class CDNirAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class CDNirClient:
    def __init__(self, api_token: Optional[str] = None, api_endpoint: str = "https://bss.asiatech.cloud/api/v3"):
        self.api_token = api_token or os.environ.get("CDNIR_API_TOKEN") or os.environ.get("ASIATECH_API_TOKEN") or os.environ.get("TOKEN")
        if not self.api_token:
            raise CDNirAPIError("API token is required (pass api_token or set CDNIR_API_TOKEN environment variable)")

        self.api_endpoint = api_endpoint.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "User-Agent": "Ansible-CDNir-DNS/1.0",
        }

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.api_endpoint}/{path.lstrip('/')}"
        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            if query:
                url = f"{url}?{query}"

        encoded_data = None
        if data is not None:
            encoded_data = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(url, data=encoded_data, headers=self.headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_text = resp.read().decode("utf-8")
                if not resp_text.strip():
                    return {"status_code": resp.status}
                try:
                    return json.loads(resp_text)
                except json.JSONDecodeError:
                    return {"status_code": resp.status, "raw_response": resp_text}
        except urllib.error.HTTPError as err:
            err_text = err.read().decode("utf-8")
            error_msg = f"HTTP Error {err.code}: {err.reason}"
            try:
                err_json = json.loads(err_text)
                if isinstance(err_json, dict) and "error" in err_json and "message" in err_json["error"]:
                    error_msg = err_json["error"]["message"]
                elif isinstance(err_json, dict) and "message" in err_json:
                    error_msg = err_json["message"]
            except Exception:
                pass
            raise CDNirAPIError(error_msg, status_code=err.code, response_body=err_text)
        except urllib.error.URLError as err:
            raise CDNirAPIError(f"Network error communicating with CDN.ir API: {err.reason}")

    @staticmethod
    def ensure_trailing_dot(domain_name: str) -> str:
        return domain_name if domain_name.endswith(".") else f"{domain_name}."

    @staticmethod
    def strip_trailing_dot(name: str) -> str:
        return name.rstrip(".")

    @classmethod
    def normalize_record_name(cls, record_name: str, zone_name: str) -> str:
        r = cls.strip_trailing_dot(record_name.strip())
        z = cls.strip_trailing_dot(zone_name.strip())

        if r == "" or r == "@" or r == z:
            return "@"

        suffix = f".{z}"
        if r.endswith(suffix):
            relative = r[:-len(suffix)]
            return relative if relative else "@"

        return r

    @classmethod
    def get_fqdn(cls, record_name: str, zone_name: str) -> str:
        rel = cls.normalize_record_name(record_name, zone_name)
        z = cls.strip_trailing_dot(zone_name)
        if rel == "@":
            return f"{z}."
        return f"{rel}.{z}."

    def list_records(self, domain_name: str, record_type: Optional[str] = None) -> List[Dict[str, Any]]:
        zone_with_dot = self.ensure_trailing_dot(domain_name)
        params = {}
        if record_type:
            params["type"] = record_type.upper()
        resp = self._request("GET", f"/domain/{zone_with_dot}", params=params)
        return resp.get("response", [])

    def add_record(self, domain_name: str, record_name: str, record_type: str, content: str, ttl: int = 3600) -> Dict[str, Any]:
        zone_with_dot = self.ensure_trailing_dot(domain_name)
        rel_name = self.normalize_record_name(record_name, domain_name)
        
        clean_content = str(content)
        if record_type.upper() == "TXT":
            if clean_content.startswith('"') and clean_content.endswith('"') and len(clean_content) >= 2:
                clean_content = clean_content[1:-1]

        data = {
            "domain_name": zone_with_dot,
            "record_name": rel_name,
            "type": record_type.upper(),
            "ttl": str(ttl),
            "content": clean_content
        }
        return self._request("POST", "/domain/add-record", data=data)

    def update_record(self, record_id: int, domain_name: str, record_name: str, record_type: str, content: str, ttl: int = 3600, disabled: bool = False) -> Dict[str, Any]:
        zone_with_dot = self.ensure_trailing_dot(domain_name)
        rel_name = self.normalize_record_name(record_name, domain_name)

        clean_content = str(content)
        if record_type.upper() == "TXT":
            if clean_content.startswith('"') and clean_content.endswith('"') and len(clean_content) >= 2:
                clean_content = clean_content[1:-1]

        data = {
            "domain_name": zone_with_dot,
            "record_name": rel_name,
            "type": record_type.upper(),
            "ttl": str(ttl),
            "content": clean_content,
            "disabled": disabled
        }
        return self._request("PUT", f"/domain/update-record/{record_id}", data=data)

    def delete_record(self, domain_name: str, record_id: int) -> Dict[str, Any]:
        zone_with_dot = self.ensure_trailing_dot(domain_name)
        return self._request("DELETE", f"/domain/delete-record/{zone_with_dot}/{record_id}")


# ==================== Helpers ====================

def normalize_content(content_str: str, rec_type: str) -> str:
    if not content_str:
        return ""
    s = content_str.strip()
    if rec_type.upper() == "TXT":
        if s.startswith('"') and s.endswith('"') and len(s) >= 2:
            s = s[1:-1]
    return s


def contents_match(existing: str, desired: str, rec_type: str) -> bool:
    norm_exist = normalize_content(existing, rec_type)
    norm_desire = normalize_content(desired, rec_type)
    if rec_type.upper() in ["CNAME", "ALIAS", "NS"]:
        return norm_exist.rstrip('.').lower() == norm_desire.rstrip('.').lower()
    return norm_exist == norm_desire


# ==================== Main Module Logic ====================

def run_module():
    module_args = dict(
        zone=dict(type='str', required=True),
        record=dict(type='str', required=True),
        type=dict(type='str', required=True, choices=['A', 'AAAA', 'CNAME', 'TXT', 'MX', 'SRV', 'CAA', 'NS', 'ALIAS', 'SPF']),
        value=dict(type='str', aliases=['content'], default=None),
        ttl=dict(type='int', default=3600),
        solo=dict(type='bool', default=False),
        disabled=dict(type='bool', default=False),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
        api_token=dict(type='str', no_log=True, default=None),
        api_endpoint=dict(type='str', default='https://bss.asiatech.cloud/api/v3'),
    )

    result = dict(
        changed=False,
        record={},
        diff={},
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[('state', 'present', ['value'])]
    )

    zone = module.params['zone'].strip().rstrip('.')
    raw_record = module.params['record'].strip()
    rec_type = module.params['type'].upper()
    val = module.params['value']
    ttl = module.params['ttl']
    solo = module.params['solo']
    disabled = module.params['disabled']
    state = module.params['state']

    try:
        client = CDNirClient(
            api_token=module.params['api_token'],
            api_endpoint=module.params['api_endpoint']
        )
    except CDNirAPIError as e:
        module.fail_json(msg=str(e), **result)

    rel_name = CDNirClient.normalize_record_name(raw_record, zone)
    target_fqdn = CDNirClient.get_fqdn(raw_record, zone)

    try:
        existing_records = client.list_records(zone, record_type=rec_type)
    except CDNirAPIError as e:
        module.fail_json(msg=f"Failed to list records for zone '{zone}': {e}", **result)

    matching_by_name = [
        r for r in existing_records
        if r.get('name', '').rstrip('.').lower() == target_fqdn.rstrip('.').lower()
    ]

    matching_by_value = [
        r for r in matching_by_name
        if val is not None and contents_match(r.get('content', ''), val, rec_type)
    ]

    if state == 'present':
        desired_content_clean = normalize_content(val, rec_type)

        if matching_by_value:
            rec = matching_by_value[0]
            existing_ttl = int(rec.get('ttl', 3600))
            existing_disabled = bool(rec.get('disabled', False))

            needs_update = (existing_ttl != ttl) or (existing_disabled != disabled)
            if needs_update:
                result['diff'] = {
                    'before': {'ttl': existing_ttl, 'disabled': existing_disabled, 'content': rec.get('content')},
                    'after': {'ttl': ttl, 'disabled': disabled, 'content': desired_content_clean}
                }
                if not module.check_mode:
                    try:
                        client.update_record(
                            record_id=rec['id'],
                            domain_name=zone,
                            record_name=rel_name,
                            record_type=rec_type,
                            content=desired_content_clean,
                            ttl=ttl,
                            disabled=disabled
                        )
                        rec['ttl'] = str(ttl)
                        rec['disabled'] = disabled
                    except CDNirAPIError as e:
                        module.fail_json(msg=f"Failed to update record '{target_fqdn}': {e}", **result)
                result['changed'] = True

            result['record'] = rec

            # Solo mode: delete any other records with this name & type
            if solo and len(matching_by_name) > 1:
                conflicting = [r for r in matching_by_name if r['id'] != rec['id']]
                if not result['diff']:
                    result['diff'] = {
                        'before': {'records': matching_by_name},
                        'after': {'records': [rec]}
                    }
                for extra in conflicting:
                    if not module.check_mode:
                        try:
                            client.delete_record(domain_name=zone, record_id=extra['id'])
                        except CDNirAPIError as e:
                            module.fail_json(msg=f"Solo mode failed to delete extra record {extra['id']}: {e}", **result)
                    result['changed'] = True

        elif (rec_type in ['CNAME', 'ALIAS'] or solo) and matching_by_name:
            # Single value or solo mode: update existing record to new content
            rec = matching_by_name[0]
            result['diff'] = {
                'before': {'content': rec.get('content'), 'ttl': rec.get('ttl')},
                'after': {'content': desired_content_clean, 'ttl': ttl}
            }
            if not module.check_mode:
                try:
                    client.update_record(
                        record_id=rec['id'],
                        domain_name=zone,
                        record_name=rel_name,
                        record_type=rec_type,
                        content=desired_content_clean,
                        ttl=ttl,
                        disabled=disabled
                    )
                    rec['content'] = desired_content_clean
                    rec['ttl'] = str(ttl)
                    rec['disabled'] = disabled
                except CDNirAPIError as e:
                    module.fail_json(msg=f"Failed to update record '{target_fqdn}': {e}", **result)
            result['changed'] = True
            result['record'] = rec

            # Solo mode: delete any remaining extras beyond the first
            if solo and len(matching_by_name) > 1:
                for extra in matching_by_name[1:]:
                    if not module.check_mode:
                        try:
                            client.delete_record(domain_name=zone, record_id=extra['id'])
                        except CDNirAPIError as e:
                            module.fail_json(msg=f"Solo mode failed to delete extra record {extra['id']}: {e}", **result)
                    result['changed'] = True

        else:
            # Add new record
            result['diff'] = {
                'before': {},
                'after': {
                    'name': target_fqdn,
                    'type': rec_type,
                    'content': desired_content_clean,
                    'ttl': ttl,
                    'disabled': disabled
                }
            }
            if not module.check_mode:
                try:
                    client.add_record(
                        domain_name=zone,
                        record_name=rel_name,
                        record_type=rec_type,
                        content=desired_content_clean,
                        ttl=ttl
                    )
                    updated_records = client.list_records(zone, record_type=rec_type)
                    new_matches = [
                        r for r in updated_records
                        if r.get('name', '').rstrip('.').lower() == target_fqdn.rstrip('.').lower()
                        and contents_match(r.get('content', ''), desired_content_clean, rec_type)
                    ]
                    if new_matches:
                        result['record'] = new_matches[0]
                    else:
                        result['record'] = {'name': target_fqdn, 'type': rec_type, 'content': desired_content_clean}
                except CDNirAPIError as e:
                    module.fail_json(msg=f"Failed to add record '{target_fqdn}': {e}", **result)
            result['changed'] = True

    elif state == 'absent':
        targets_to_delete = matching_by_value if val is not None else matching_by_name

        if targets_to_delete:
            result['diff'] = {
                'before': {'records': targets_to_delete},
                'after': {'records': []}
            }
            if not module.check_mode:
                for rec in targets_to_delete:
                    rec_id = rec.get('id')
                    if rec_id:
                        try:
                            client.delete_record(domain_name=zone, record_id=rec_id)
                        except CDNirAPIError as e:
                            module.fail_json(msg=f"Failed to delete record ID {rec_id} for '{target_fqdn}': {e}", **result)
            result['changed'] = True
            result['record'] = {}

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
