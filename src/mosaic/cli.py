"""MOSAIC command-line interface.

Commands:
  mosaic chat    — interactive REPL or single prompt
  mosaic serve   — run FastAPI server via uvicorn
  mosaic eval    — evaluate model against benchmark
  mosaic guard   — inspect guardrail decision for a prompt
  mosaic reset   — clear session memory
  mosaic config  — validate and dump merged config
  mosaic audit   — tail ArkLedger
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from mosaic.adapters.base import Message
from mosaic.audit.ark_ledger import get_ledger
from mosaic.core.config import load_config
from mosaic.guardrails.engine import GuardrailPipeline
from mosaic.inference.staff_decoder import DecodeRequest, InferenceMode, StaffDecoder
from mosaic.tools.registry import registry as tool_registry

console = Console()


@click.group()
@click.version_option(version="0.3.0", prog_name="mosaic")
def cli():
    """MOSAIC — Multi-Origin Synthesis of Intelligent Capabilities."""
    pass


@cli.group("tools")
def tools_group():
    """Tool execution and management."""
    pass


@tools_group.command("list")
@click.option("--layer", help="Filter by layer (recon, vuln, scan, utility, etc.)")
def tools_list_cmd(layer):
    """List available tools."""
    names = tool_registry.list_tools(layer=layer)
    table = Table(title=f"Tools ({layer or 'all'})")
    table.add_column("Name")
    table.add_column("Layer")
    table.add_column("Description")
    for name in names:
        spec = tool_registry.get(name)
        table.add_row(name, spec.layer, spec.description[:60])
    console.print(table)


@tools_group.command("run")
@click.argument("tool_name")
@click.argument("params", nargs=-1)
def tools_run_cmd(tool_name, params):
    """Run a tool. Params as key=value pairs."""
    params_dict = {}
    for p in params:
        if "=" not in p:
            console.print(f"[red]Invalid param {p} — use key=value[/red]")
            return
        k, v = p.split("=", 1)
        params_dict[k] = v
    import asyncio

    async def run():
        try:
            result = await tool_registry.execute(tool_name, **params_dict)
            console.print(json.dumps(result.as_dict(), indent=2))
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    asyncio.run(run())


@cli.command("chat")
@click.argument("prompt", required=False)
@click.option(
    "--mode",
    type=click.Choice(["fast", "deliberate", "search", "agent", "memory"]),
    help="Inference mode",
)
@click.option("--config", default="configs/serve/local.yaml", help="YAML config path")
@click.option(
    "--adapter",
    "provider",
    default="openai",
    type=click.Choice(["openai", "anthropic", "ollama", "local"]),
)
@click.option("--model", default=None, help="Model name to use")
@click.option("--no-guard", is_flag=True, default=False, help="Disable guardrails")
def chat_cmd(prompt: str | None, mode, config, provider, model, no_guard):
    """Start a chat session.  If PROMPT is omitted, enters REPL mode."""
    cfg = load_config(config)
    decoder = StaffDecoder(cfg)

    mode_enum = InferenceMode(mode) if mode else None
    guardrails = not no_guard

    async def run_chat(p: str):
        req = DecodeRequest(
            messages=[Message(role="user", content=p)],
            mode=mode_enum,
            guardrails=guardrails,
        )
        resp = await decoder.decode(req)
        console.print(f"\n[bold cyan]{resp.content}[/bold cyan]\n")
        console.print(
            f"[dim]mode={resp.mode_used.value}  stability={resp.stability:.2f}  tokens={resp.usage}[/dim]\n"
        )

    if prompt:
        asyncio.run(run_chat(prompt))
    else:
        console.print("[bold]MOSAIC REPL — type 'exit' or Ctrl-D to quit[/bold]\n")
        try:
            while True:
                p = Prompt.ask("[green]You[/green]")
                if p.strip().lower() in ("exit", "quit"):
                    break
                asyncio.run(run_chat(p))
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold]Bye.[/bold]")


@cli.command("serve")
@click.option("--host", default="0.0.0.0", help="Bind address")
@click.option("--port", default=8000, type=int, help="Bind port")
@click.option("--config", default="configs/serve/local.yaml", help="YAML config path")
@click.option(
    "--reload", is_flag=True, default=False, help="Auto-reload on source changes"
)
def serve_cmd(host, port, config, reload):
    """Start the FastAPI service with uvicorn."""
    import uvicorn

    console.print(f"[bold]Starting MOSAIC API on http://{host}:{port}[/bold]")
    uvicorn.run("mosaic.api:app", host=host, port=port, reload=reload, log_level="info")


@cli.command("eval")
@click.argument(
    "benchmark", type=click.Choice(["mmlu", "gsm8k", "humaneval", "custom"])
)
@click.option("--config", default="configs/eval/release_gates.yaml")
@click.option("--output", default="reports/", help="Directory for results")
def eval_cmd(benchmark, config, output):
    """Run evaluation benchmark."""
    import asyncio

    from mosaic.eval.runner import run_eval

    cfg = load_config(config)
    console.print(f"[bold]Running {benchmark.upper()} evaluation…[/bold]")
    results = asyncio.run(run_eval(cfg))

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    console.print(f"\nResults: {passed}/{total} passed")
    Path(output).mkdir(parents=True, exist_ok=True)
    out_path = Path(output) / f"{benchmark}_{int(time.time())}.json"
    out_path.write_text(json.dumps([r.__dict__ for r in results], indent=2))
    console.print(f"[dim]Report saved to {out_path}[/dim]")


@cli.command("guard")
@click.argument("text")
@click.option("--mode", type=click.Choice(["input", "output"]), default="input")
def guard_cmd(text, mode):
    """Inspect guardrail decisions for TEXT."""

    async def run():
        if mode == "input":
            pipeline = GuardrailPipeline.default_input()
            results = await pipeline.check_input(text)
        else:
            pipeline = GuardrailPipeline.default_output()
            results = await pipeline.check_output(text)

        table = Table(title=f"Guardrail {mode.upper()} scan")
        table.add_column("Rail")
        table.add_column("Passed")
        table.add_column("Score")
        table.add_column("Severity")
        table.add_column("Reason")
        for r in results:
            col = "green" if r.passed else "red"
            table.add_row(
                r.name,
                str(r.passed),
                f"{r.score:.2f}",
                r.severity,
                r.reason or "-",
                style=col,
            )
        console.print(table)

    asyncio.run(run())


@cli.command("config")
@click.argument("path", default="configs/serve/local.yaml")
def config_cmd(path):
    """Validate and print merged configuration."""
    try:
        cfg = load_config(path)
        console.print(json.dumps(cfg.model_dump(), indent=2))
    except Exception as e:
        console.print(f"[red]Config error: {e}[/red]")
        sys.exit(1)


@cli.command("audit")
@click.option("--lines", "-n", default=20, help="Number of recent entries")
def audit_cmd(lines):
    """Tail the ArkLedger audit log."""
    ledger = get_ledger()
    entries = ledger.tail(lines)
    for e in entries:
        ts = datetime.fromtimestamp(e.timestamp, tz=UTC).strftime("%H:%M:%S")
        console.print(f"[dim]{ts}[/dim]  [bold]{e.action.value}[/bold]  {e.details}")


@cli.command("reset")
def reset_cmd():
    """Clear current session memory (Exodus scratch + episode)."""
    # This requires decoder; make a temporary one just to clear?  Better to persist a global.
    console.print(
        "[yellow]Not implemented in standalone CLI - use /reset API endpoint or restart process.[/yellow]"
    )


if __name__ == "__main__":
    cli()
