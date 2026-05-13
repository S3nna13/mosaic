# Tool Authoring — MOSAIC

## Built-in Tool Registry

MOSAIC ships with ~50 security and utility tools across 6 layers:
 - **recon**: nmap_quick, nmap_deep, dns_lookup, whois_query, ssl_scan, theHarvester
 - **vuln**: nuclei_scan, nikto_scan, cve_search
 - **scan**: sqlmap, msf_console
 - **monitor**: zeek_parse, suricata_alert
 - **defense**: iptables_list, ufw_status
 - **utility**: ping, traceroute, sha256_hash, cat, grep_search

All tools are managed by `SafeToolRunner` — they execute in isolated subprocesses with:
 - Safe-mode IP/hostname validation (blocks external scans)
 - Environment filtering (secrets stripped)
 - Timeouts (default 30s) and output size caps
 - Structured output parsing (JSON, YAML, XML, lines)
 - Audit logging to ArkLedger

## Custom Tool Registration

```python
from mosaic.tools.registry import registry, Tool
from mosaic.tools.runner import ToolResult

my_tool = Tool(
    name="my_scanner",
    description="Scan for open ports",
    layer="recon",
    command_template=["nmap", "-sV", "{target}"],
    parameters={"target": {"type": "string", "required": True}},
    output_parser="xml",
)
registry.register(my_tool)
result: ToolResult = await registry.execute("my_scanner", target="127.0.0.1")
print(result.stdout)
```

## Safe Execution Guarantees

- **Blocklist**: `runner.block_tool("rm")` prevents dangerous commands
- **Env filtering**: No API keys/secrets leak into subprocesses
- **Network guards**: `safe_mode=True` (default) blocks connections outside private ranges
- **Audit trail**: Every call is appended to ArkLedger

## Output Parsing

Set `output_parser` to one of: `"text"`, `"json"`, `"yaml"`, `"xml"`, `"lines"`.
