"""MITRE ATT&CK Technique Mapper — classifies security findings.

Minimal implementation: maps guardrail findings and tool results to ATT&CK
technique IDs via keyword matching. In production, replace with
mitreattack-python library for accurate STIX-based mapping.

Mapping categories:
  • Initial Access (TA0001)
  • Execution (TA0002)
  • Persistence (TA0003)
  • Privilege Escalation (TA0004)
  • Defense Evasion (TA0005)
  • Credential Access (TA0006)
  • Discovery (TA0007)
  • Lateral Movement (TA0008)
  • Collection (TA0009)
  • Exfiltration (TA0010)
  • Impact (TA0011)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class Technique:
    id: str              # e.g. "T1190"
    name: str            # e.g. "Exploit Public-Facing Application"
    tactic: str          # e.g. "Initial Access"
    description: str = ""


class MITREMapper:
    """Maps behavior patterns to ATT&CK technique IDs."""
    def __init__(self):
        self._techniques: dict[str, Technique] = self._bootstrap_common()
        self._keyword_map: dict[str, list[str]] = self._bootstrap_keywords()

    def _bootstrap_common(self) -> dict[str, Technique]:
        # ~20 most common techniques — can be expanded later
        common = [
            ("T1190", "Exploit Public-Facing Application", "Initial Access"),
            ("T1059", "Command and Scripting Interpreter", "Execution"),
            ("T1055", "Process Injection", "Defense Evasion"),
            ("T1078", "Valid Accounts", "Persistence"),
            ("T1110", "Brute Force", "Credential Access"),
            ("T1087", "Account Discovery", "Discovery"),
            ("T1071", "Application Layer Protocol", "Command and Control"),
            ("T1566", "Phishing", "Initial Access"),
            ("T1498", "Network Denial of Service", "Impact"),
            ("T1485", "Data Destruction", "Impact"),
            ("T1020", "Automated Exfiltration", "Exfiltration"),
            ("T1003", "OS Credential Dumping", "Credential Access"),
            ("T1083", "File and Directory Discovery", "Discovery"),
            ("T1105", "Ingress Tool Transfer", "Command and Control"),
            ("T1053", "Scheduled Task/Job", "Persistence"),
            ("T1543", "Create or Modify System Process", "Persistence"),
            ("T1136", "Create Account", "Persistence"),
            ("T1070", "Indicator Removal on Host", "Defense Evasion"),
            ("T1218", "Signed Binary Proxy Execution", "Defense Evasion"),
            ("T1562", "Impair Defenses", "Defense Evasion"),
            ("T1486", "Data Encrypted for Impact", "Impact"),
            ("T1489", "Service Stop", "Impact"),
        ]
        return {tid: Technique(tid, name, tactic) for tid, name, tactic in common}

    def _bootstrap_keywords(self) -> dict[str, list[str]]:
        # Simple keyword → technique mapping for fast lookup
        return {
            "T1190": ["public facing", "web shell", "rce", "remote code", "exploit", "vulnerability"],
            "T1059": ["command", "script", "powershell", "bash", "shell", "eval"],
            "T1055": ["injection", "dll", "process hollow", "thread hijack"],
            "T1078": ["valid account", "legitimate credentials", "compromised account"],
            "T1110": ["brute force", "password spray", "credential stuffing"],
            "T1087": ["discover account", "enumerate users", "get users"],
            "T1071": ["http", "https", "dns", "tcp", "network protocol"],
            "T1566": ["phishing", "spear phishing", "malicious attachment"],
            "T1498": ["dos", "denial of service", "flood", "bandwidth"],
            "T1485": ["destroy", "wipe", "shred", "overwrite"],
            "T1020": ["exfiltrate", "upload", "data theft", "steal"],
            "T1003": ["dump credentials", "lsass", "sam", "hashes"],
            "T1083": ["find files", "directory listing", "locate"],
            "T1105": ["download", "fetch", "wget", "curl"],
            "T1053": ["cron", "schedule", "at job", "task scheduler"],
            "T1543": ["service create", "systemd", "init script"],
            "T1136": ["create user", "add account", "new user"],
            "T1070": ["clear log", "log deletion", "wevtutil"],
            "T1218": ["msbuild", "certutil", "regsvr32", "rundll32"],
            "T1562": ["disable antivirus", "kill process", "defender"],
            "T1486": ["ransomware", "encrypt", "ransom note"],
            "T1489": ["stop service", "kill process", "shutdown"],
        }

    def map_finding(self, finding: dict[str, Any]) -> list[Technique]:
        """Given a guardrail/tool finding, return matched ATT&CK techniques."""
        text = f"{finding.get('reason','')} {finding.get('type','')}".lower()
        matched: list[Technique] = []
        for tid, keywords in self._keyword_map.items():
            if any(kw in text for kw in keywords):
                matched.append(self._techniques[tid])
        return matched

    def map_findings_batch(self, findings: list[dict[str, Any]]) -> dict[str, list[Technique]]:
        """Batch mapping: { finding_id -> [Techniques] }."""
        results = {}
        for i, f in enumerate(findings):
            fid = f.get("id", str(i))
            results[fid] = self.map_finding(f)
        return results

    def get_tactic_coverage(self, techniques: list[Technique]) -> dict[str, int]:
        """Count techniques per tactic."""
        from collections import Counter
        return dict(Counter(t.tactic for t in techniques))

    def to_stix(self) -> str:
        """Export loaded techniques as STIX bundle (stub)."""
        # In real implementation: use mitreattack-python to generate STIX
        return "STIX bundle placeholder — install mitreattack-python for full export"
