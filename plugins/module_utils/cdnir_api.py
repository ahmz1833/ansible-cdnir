# -*- coding: utf-8 -*-

"""
CDN.ir (Asiatech Cloud) API Client for Ansible Modules and Python Tooling
Copyright (c) 2026 AH MZ <ahmz.ut@gmail.com>
"""

import os
import json
import base64
import time
import datetime
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple


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
            "User-Agent": "Ansible-CDNir-Provider/1.0",
        }

        # Validate token expiration
        is_expired, remaining_secs, exp_dt = self.check_token_expiration(self.api_token)
        if is_expired:
            raise CDNirAPIError(
                f"CDN.ir API token is EXPIRED! Expired at {exp_dt} UTC. Please obtain a fresh token."
            )

    @staticmethod
    def check_token_expiration(token: str) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Parses the JWT token without verification to inspect expiration time.
        Returns: (is_expired, remaining_seconds, formatted_expiry_utc)
        """
        try:
            parts = token.split(".")
            if len(parts) >= 2:
                # Add padding if needed
                padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
                exp = payload.get("exp")
                if exp:
                    now = int(time.time())
                    remaining = exp - now
                    exp_dt = datetime.datetime.fromtimestamp(exp, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    return (remaining <= 0, remaining, exp_dt)
        except Exception:
            pass
        return (False, None, None)

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

    # ==================== Zone / Domain Methods ====================

    def list_domains(self, search: Optional[str] = None, page: int = 1, per_page: int = 100) -> List[Dict[str, Any]]:
        params = {"page": page, "per_page": per_page}
        if search:
            params["search"] = search
        resp = self._request("GET", "/domain/index", params=params)
        return resp.get("response", {}).get("data", [])

    def get_domain(self, domain_name: str) -> Optional[Dict[str, Any]]:
        normalized = domain_name.rstrip(".")
        domains = self.list_domains(search=normalized)
        for d in domains:
            if d.get("name", "").rstrip(".") == normalized:
                return d
        return None

    def create_domain(self, domain_name: str) -> Dict[str, Any]:
        normalized = domain_name.rstrip(".")
        return self._request("POST", "/domain/create", data={"name": normalized})

    def delete_domain(self, domain_name: str) -> Dict[str, Any]:
        normalized = domain_name.rstrip(".")
        return self._request("DELETE", f"/domain/delete-domain/{normalized}")

    def verify_domain(self, domain_name: str) -> Dict[str, Any]:
        normalized = domain_name.rstrip(".")
        return self._request("POST", "/domain/verify", data={"name": normalized})

    def whois_domain(self, domain_name: str) -> List[str]:
        normalized = domain_name.rstrip(".")
        resp = self._request("GET", f"/domain/whois/{normalized}")
        return resp.get("response", [])

    # ==================== Record Methods ====================

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
