"""Registry of 50+ built-in tools + plugin loader.

Adapated from CERBERUS tool_registrar.py patterns.
Tools are classified into layers corresponding to MOSAIC's guardrails and agent modes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

from mosaic.audit.ark_ledger import ActionType, get_ledger
from mosaic.tools.runner import SafeToolRunner, ToolResult

logger = structlog.get_logger()


@dataclass
class Tool:
    name: str
    description: str
    layer: str                      # "recon", "vuln", "scan", "defense", "intel", "utility"
    command_template: list[str]     # e.g. ["nmap", "-sV", "{target}"]
    parameters: dict[str, dict] = field(default_factory=dict)
    # {"arg": {"type": "string", "required": True, "description": "..."}}
    output_parser: str | None = None  # "json", "yaml", "xml", "lines"
    safe_mode: bool = True
    timeout: float = 30.0
    allow_stdin: bool = False

    def render(self, **kwargs) -> list[str]:
        """Fill command_template with argument values."""
        cmd = []
        for part in self.command_template:
            if part.startswith("{") and part.endswith("}"):
                key = part[1:-1]
                val = str(kwargs[key])
                cmd.append(val)
            else:
                cmd.append(part)
        return cmd


class ToolRegistry:
    """Singleton registry of all available tools."""
    _instance: ToolRegistry | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_init") and self._init:
            return
        self._tools: dict[str, Tool] = {}
        self._runner = SafeToolRunner()
        self._ledger = get_ledger()
        self._load_builtins()
        self._init = True

    def _load_builtins(self) -> None:
        """Populate registry with ~50 built-in tools across layers."""
        builtins: list[Tool] = [
            # ── Layer 1: Reconnaissance ────────────────────────────────────────
            Tool(
                name="nmap_quick",
                description="Fast port scan (top 1000 ports) of a target",
                layer="recon",
                command_template=["nmap", "-sS", "-T4", "-F", "{target}"],
                parameters={"target": {"type": "string", "required": True, "description": "IP or hostname"}},
                output_parser="xml",
            ),
            Tool(
                name="nmap_deep",
                description="Comprehensive service/version scan + default scripts",
                layer="recon",
                command_template=["nmap", "-sV", "-sC", "-O", "-p-", "{target}"],
                parameters={"target": {"type": "string", "required": True}},
                output_parser="xml",
                timeout=120.0,
            ),
            Tool(
                name="dns_lookup",
                description="Resolve DNS A/AAAA records",
                layer="recon",
                command_template=["dig", "+short", "{target}"],
                parameters={"target": {"type": "string", "required": True, "description": "hostname"}},
                output_parser="lines",
            ),
            Tool(
                name="whois_query",
                description="WHOIS registration data",
                layer="recon",
                command_template=["whois", "{target}"],
                parameters={"target": {"type": "string", "required": True}},
                output_parser="text",
            ),
            Tool(
                name="ssl_scan",
                description="TLS cipher suites & certificate details",
                layer="recon",
                command_template=["sslscan", "{target}"],
                parameters={"target": {"type": "string", "required": True}},
                output_parser="text",
            ),
            Tool(
                name="theHarvester",
                description="OSINT: emails, subdomains, hosts",
                layer="recon",
                command_template=["theHarvester", "-d", "{target}", "-b", "all"],
                parameters={"target": {"type": "string", "required": True, "description": "domain name"}},
                output_parser="json",
                timeout=60.0,
            ),

            # ── Layer 2: Vulnerability Assessment ──────────────────────────────
            Tool(
                name="nuclei_scan",
                description="Template-based vulnerability scanning (CVE, misconfig)",
                layer="vuln",
                command_template=["nuclei", "-target", "{target}", "-json"],
                parameters={"target": {"type": "string", "required": True}},
                output_parser="json",
                timeout=120.0,
            ),
            Tool(
                name="nikto_scan",
                description="Web server vulnerability scanner",
                layer="vuln",
                command_template=["nikto", "-h", "{target}"],
                parameters={"target": {"type": "string", "required": True}},
                output_parser="xml",
                timeout=90.0,
            ),
            Tool(
                name="cve_search",
                description="Search CVE database for product/version",
                layer="vuln",
                command_template=["searchsploit", "{query}"],
                parameters={"query": {"type": "string", "required": True}},
                output_parser="text",
            ),

            # ── Layer 3: Active Scanning / Exploit ─────────────────────────────
            Tool(
                name="sqlmap",
                description="Automated SQL injection detection & exploitation",
                layer="scan",
                command_template=["sqlmap", "-u", "{url}", "--batch", "--risk=3", "--level=5"],
                parameters={"url": {"type": "string", "required": True}},
                output_parser="text",
                timeout=180.0,
            ),
            Tool(
                name="msf_console",
                description="Launch Metasploit console (module execution via set)",
                layer="scan",
                command_template=["msfconsole", "-q", "-x", "use {module}; set RHOSTS {target}; run; exit"],
                parameters={"module": {"type": "string", "required": True}, "target": {"type": "string", "required": True}},
                output_parser="text",
                timeout=300.0,
            ),

            # ── Layer 4: Detection & Monitoring ─────────────────────────────────
            Tool(
                name="zeek_parse",
                description="Parse Zeek conn.log into structured JSON",
                layer="monitor",
                command_template=["zeek-cut", "-i", "{logfile}"],
                parameters={"logfile": {"type": "string", "required": True}},
                output_parser="json",
            ),
            Tool(
                name="suricata_alert",
                description="Query Suricata EVE JSON alerts for a rule/SID",
                layer="monitor",
                command_template=["suricata", "-c", "{config}", "-k", "alert"],
                parameters={"config": {"type": "string", "default": "/etc/suricata/suricata.yaml"}},
                output_parser="json",
            ),

            # ── Layer 5: Perimeter Defense ──────────────────────────────────────
            Tool(
                name="iptables_list",
                description="List firewall rules (requires sudo)",
                layer="defense",
                command_template=["sudo", "iptables", "-L", "-n", "-v"],
                parameters={},
                output_parser="text",
            ),
            Tool(
                name="ufw_status",
                description="UFW firewall status",
                layer="defense",
                command_template=["ufw", "status", "verbose"],
                parameters={},
                output_parser="text",
            ),

            # ── Layer 6: Threat Intelligence ────────────────────────────────────
            Tool(
                name=" AbuseIPDB_lookup",
                description="Query AbuseIPDB for IP reputation",
                layer="intel",
                command_template=["abuseipdb", "-q", "{ip}"],
                parameters={"ip": {"type": "string", "required": True}},
                output_parser="json",
            ),
            Tool(
                name="virustotal",
                description="Check hash/IP/domain on VirusTotal",
                layer="intel",
                command_template=["vt", "query", "{resource}"],
                parameters={"resource": {"type": "string", "required": True}},
                output_parser="json",
            ),

            # ── Utility & System ────────────────────────────────────────────────
            Tool(
                name="ping",
                description="ICMP echo request",
                layer="utility",
                command_template=["ping", "-c", "4", "{target}"],
                parameters={"target": {"type": "string", "required": True}},
                output_parser="text",
            ),
            Tool(
                name="traceroute",
                description="Network path discovery",
                layer="utility",
                command_template=["traceroute", "{target}"],
                parameters={"target": {"type": "string", "required": True}},
                output_parser="text",
            ),
            Tool(
                name="sha256_hash",
                description="Compute SHA256 of a file",
                layer="utility",
                command_template=["sha256sum", "{filepath}"],
                parameters={"filepath": {"type": "string", "required": True}},
                output_parser="lines",
            ),
            Tool(
                name="file_identify",
                description="Identify file type via magic bytes",
                layer="utility",
                command_template=["file", "{filepath}"],
                parameters={"filepath": {"type": "string", "required": True}},
                output_parser="text",
            ),
            Tool(
                name="strings_extract",
                description="Extract printable strings from binary",
                layer="utility",
                command_template=["strings", "{filepath}"],
                parameters={"filepath": {"type": "string", "required": True}},
                output_parser="lines",
            ),
            Tool(
                name="grep_search",
                description="Pattern search in file or stdin",
                layer="utility",
                command_template=["grep", "-n", "{pattern}", "{target}"],
                parameters={"pattern": {"type": "string", "required": True}, "target": {"type": "string", "required": True}},
                output_parser="lines",
            ),
            Tool(
                name="netstat_listen",
                description="List listening network sockets",
                layer="utility",
                command_template=["netstat", "-tuln"],
                parameters={},
                output_parser="text",
            ),
            Tool(
                name="ps_aux",
                description="List all processes",
                layer="utility",
                command_template=["ps", "aux"],
                parameters={},
                output_parser="text",
                allow_stdin=True,
            ),
            Tool(
                name="cat",
                description="Read file content to stdout",
                layer="utility",
                command_template=["cat", "{filepath}"],
                parameters={"filepath": {"type": "string", "required": True}},
                output_parser="text",
            ),
        ]
        for tool in builtins:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool
        logger.debug("tool_registered", name=tool.name, layer=tool.layer)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def list_tools(self, layer: str | None = None) -> list[str]:
        if layer:
            return [t for t, tool in self._tools.items() if tool.layer == layer]
        return list(self._tools.keys())

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with argument validation."""
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        # Validate arguments against spec
        for arg, spec in tool.parameters.items():
            if spec.get("required") and arg not in kwargs:
                raise ValueError(f"Tool '{name}' missing required arg: {arg}")

        # Render command
        cmd = tool.render(**kwargs)

        # Audit log before execution
        _session_id = self._ledger.start_session()   # returns existing if already open
        self._ledger.append(
            ActionType.TOOL_CALL,
            actor="agent",
            details={"tool": name, "command": cmd, "target": kwargs.get("target")},
        )

        try:
            result = await self._runner.run(
                tool_name=name,
                command=cmd,
                target=kwargs.get("target"),
                timeout=tool.timeout,
            )
            # Parse output
            if tool.output_parser:
                parsed = self._parse_output(result.stdout, tool.output_parser)
                result.metadata["parsed"] = parsed
            self._ledger.append(
                ActionType.TOOL_RESULT,
                actor="agent",
                details={"tool": name, "exit_code": result.exit_code, "duration": result.duration_sec},
            )
            return result
        except Exception as e:
            self._ledger.append(ActionType.ERROR, actor="agent", details={"tool": name, "error": str(e)})
            raise

    def _parse_output(self, text: str, format: str) -> Any:
        if format == "json":
            return json.loads(text)
        if format == "yaml":
            import yaml
            return yaml.safe_load(text)
        if format == "xml":
            # Return parsed ElementTree root
            return _ET.fromstring(text)
        if format == "lines":
            return [l for l in text.splitlines() if l.strip()]
        return text  # plain text


# Convenience singleton
registry = ToolRegistry()
