"""
MemoQ REST API Client
Handles authentication, TM and TB lookups
"""

import os
import time
import requests
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

@dataclass
class MemoQConfig:
    """MemoQ server configuration"""
    base_url: str = ""
    username: str = ""
    password: str = ""
    domain: str = ""
    timeout: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> 'MemoQConfig':
        """Create config from environment variables"""
        return cls(
            base_url=os.getenv("MEMOQ_BASE_URL", ""),
            username=os.getenv("MEMOQ_USERNAME", ""),
            password=os.getenv("MEMOQ_PASSWORD", ""),
            domain=os.getenv("MEMOQ_DOMAIN", ""),
            timeout=int(os.getenv("MEMOQ_TIMEOUT", "120")),
            verify_ssl=os.getenv("MEMOQ_VERIFY_SSL", "true").lower() == "true"
        )

class MemoQClient:
    """MemoQ REST API client"""
    
    def __init__(self, cfg: MemoQConfig):
        self.cfg = cfg
        self._token: Optional[str] = None
        self._token_expiry_ts: float = 0
    
    def _url(self, path: str) -> str:
        """Construct full URL from base URL and path"""
        return f"{self.cfg.base_url.rstrip('/')}/{path.lstrip('/')}"
    
    def _headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests"""
        if not self._token or time.time() > self._token_expiry_ts:
            self.login()
        return {"Authorization": f"MQS-API {self._token}", "Accept": "application/json"}
    
    def login(self):
        """Authenticate with MemoQ server"""
        url = self._url("/auth/login")
        payload = {
            "UserName": self.cfg.username, 
            "Password": self.cfg.password, 
            "Domain": self.cfg.domain or ""
        }
        r = requests.post(url, json=payload, timeout=self.cfg.timeout, verify=self.cfg.verify_ssl)
        r.raise_for_status()
        data = r.json()
        self._token = data.get("AccessToken")
        self._token_expiry_ts = time.time() + 50 * 60
        if not self._token:
            raise RuntimeError("MemoQ login succeeded but no AccessToken in response")
    
    def list_tms(self, source_lang: str = "", target_lang: str = "") -> List[Dict[str, Any]]:
        """List available Translation Memories"""
        params = {}
        if source_lang: params["sourceLanguage"] = source_lang
        if target_lang: params["targetLanguage"] = target_lang
        r = requests.get(self._url("/tms"), headers=self._headers(), params=params,
                         timeout=self.cfg.timeout, verify=self.cfg.verify_ssl)
        r.raise_for_status()
        return r.json()
    
    def list_tbs(self, langs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """List available Term Bases"""
        params = {}
        if langs: params["lang"] = langs
        r = requests.get(self._url("/tbs"), headers=self._headers(), params=params,
                         timeout=self.cfg.timeout, verify=self.cfg.verify_ssl)
        r.raise_for_status()
        return r.json()
    
    def get_tm_guid_by_name(self, name: str, src: str, tgt: str) -> Optional[str]:
        """Get TM GUID by name"""
        for tm in self.list_tms(src, tgt):
            if (tm.get("Name") or tm.get("FriendlyName")) == name:
                return tm.get("Guid") or tm.get("TMGuid")
        return None
    
    def get_tb_guid_by_name(self, name: str, langs: List[str]) -> Optional[str]:
        """Get TB GUID by name"""
        for tb in self.list_tbs(langs):
            if (tb.get("Name") or tb.get("FriendlyName")) == name:
                return tb.get("Guid")
        return None
    
    def tm_lookup_segments(self, tm_guid: str, source_text: str, source_lang: str, target_lang: str,
                           max_results: int = 5, lookup_mode: str = "Default") -> List[Dict[str, Any]]:
        """Look up segments in TM"""
        url = self._url(f"/tms/{tm_guid}/lookupsegments")
        payload = {
            "LookupSegments": [{
                "SourceText": source_text,
                "SourceLanguage": source_lang,
                "TargetLanguage": target_lang,
                "LookupMode": lookup_mode
            }],
            "MaxResultCount": max_results
        }
        r = requests.post(url, headers=self._headers(), json=payload,
                          timeout=self.cfg.timeout, verify=self.cfg.verify_ssl)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return data[0].get("Results", []) or data[0].get("TMHits", [])
        if isinstance(data, dict) and "Result" in data:
            items = data["Result"]
            if items and "TMHits" in items[0]:
                return items[0]["TMHits"]
        return []
    
    def tb_lookup_terms(self, tb_guid: str, source_text: str, source_lang: str, target_lang: str,
                        max_results: int = 50) -> List[Dict[str, Any]]:
        """Look up terms in TB"""
        url = self._url(f"/tbs/{tb_guid}/lookupterms")
        payload = {
            "SourceText": source_text,
            "SourceLanguage": source_lang,
            "TargetLanguage": target_lang,
            "MaxResultCount": max_results
        }
        r = requests.post(url, headers=self._headers(), json=payload,
                          timeout=self.cfg.timeout, verify=self.cfg.verify_ssl)
        r.raise_for_status()
        return r.json()

# Test function
if __name__ == "__main__":
    config = MemoQConfig.from_env()
    client = MemoQClient(config)
    
    try:
        client.login()
        print("✅ MemoQ connection successful")
        
        tm_guid = client.get_tm_guid_by_name("SV_test_TM_Finance", "en", "es")
        tb_guid = client.get_tb_guid_by_name("Finance_TB", ["en", "es"])
        
        print(f"TM GUID: {tm_guid}")
        print(f"TB GUID: {tb_guid}")
        
    except Exception as e:
        print(f"❌ MemoQ connection failed: {e}")
        print("Will use CSV fallback system")