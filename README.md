# CDN.ir (Asiatech Cloud) Ansible Module & Collection

[![CI](https://github.com/ahmz1833/ansible-cdnir/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmz1833/ansible-cdnir/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Ansible tooling for managing DNS zones and records on **CDN.ir** (`bss.asiatech.cloud`). Designed as a direct peer to the Cloudflare DNS module (`cloudflare_dns`).

## Features

- **`cdnir_dns`**: Manage individual DNS records with full idempotency, TTL updates, diff output, check mode, and `solo` mode (mirrors `cloudflare_dns`).
- **`cdnir_zone`**: Manage DNS zones (`present`, `absent`, `verify`).
- **`cdnir_record_info`**: Query and filter records in any zone.
- **Zero External Dependencies**: Works out-of-the-box using the Python standard library. Can be used either as an **Ansible Galaxy collection** or dropped as a **standalone module** into your `./library` folder!

---

## Installation

### Method A: Install via Ansible Galaxy (Recommended)
```bash
ansible-galaxy collection install ahmz1833.cdnir
```

### Method B: Use as Standalone Module
Copy `plugins/modules/cdnir_dns.py` into your playbook's `library/` folder:
```bash
mkdir -p library
cp plugins/modules/cdnir_dns.py library/
```

---

## Authentication

Set your CDN.ir API Bearer token in the environment:
```bash
export CDNIR_API_TOKEN="your_jwt_token_here"
```
Or pass `api_token` directly in the task parameters.

---

## Usage Examples

### 1. Basic DNS Records (Mirroring `cloudflare_dns`)
```yaml
---
- name: Manage CDN.ir DNS Infrastructure
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    domain_zone: "example.ir"

  tasks:
    - name: Ensure Apex A record exists
      cdnir_dns:
        zone: "{{ domain_zone }}"
        record: "@"
        type: A
        value: 192.0.2.1
        ttl: 300
        state: present

    - name: Ensure CNAME record with solo mode (removes conflicting records)
      cdnir_dns:
        zone: "{{ domain_zone }}"
        record: www
        type: CNAME
        value: "{{ domain_zone }}."
        solo: true
        state: present

    - name: Add mail server MX record
      cdnir_dns:
        zone: "{{ domain_zone }}"
        record: "@"
        type: MX
        value: "10 mail.{{ domain_zone }}."
        state: present

    - name: Add SPF TXT record
      cdnir_dns:
        zone: "{{ domain_zone }}"
        record: "@"
        type: TXT
        value: "v=spf1 mx -all"
        state: present

    - name: Delete a stale test record
      cdnir_dns:
        zone: "{{ domain_zone }}"
        record: staging
        type: A
        state: absent
```

### 2. Zone Management
```yaml
- name: Create DNS Zone
  cdnir_zone:
    name: example.ir
    state: present
    verify: true
```

### 3. Query Zone Records
```yaml
- name: Get all TXT records
  cdnir_record_info:
    zone: example.ir
    type: TXT
  register: txt_records

- name: Display records
  ansible.builtin.debug:
    var: txt_records.records
```

---

## Module Parameters: `cdnir_dns`

| Parameter | Type | Default | Choices / Description |
| :--- | :--- | :--- | :--- |
| `zone` | str | *(required)* | Name of the parent domain zone (e.g. `example.ir`). |
| `record` | str | *(required)* | Record name (`@` for apex, subname e.g. `api`, or FQDN). |
| `type` | str | *(required)* | `A`, `AAAA`, `CNAME`, `TXT`, `MX`, `SRV`, `CAA`, `NS`, `ALIAS`, `SPF`. |
| `value` | str | `None` | Record target/value (alias: `content`). Required when `state=present`. |
| `ttl` | int | `3600` | Time to live in seconds. |
| `solo` | bool | `false` | If `true`, removes all other records with matching name and type. |
| `disabled` | bool | `false` | Disable record from resolving. |
| `state` | str | `present` | `present`, `absent`. |
| `api_token`| str | `None` | CDN.ir JWT Bearer token (or set `CDNIR_API_TOKEN`). |
| `api_endpoint` | str | `https://bss.asiatech.cloud/api/v3` | Base API URL. |

---

## License

MIT License. Copyright (c) 2026 AH MZ.
