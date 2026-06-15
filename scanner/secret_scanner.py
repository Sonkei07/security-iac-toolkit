#!/usr/bin/env python3
"""
secret_scanner.py
Scans Terraform (.tf) files for potential secret leakage:
hardcoded passwords, tokens, private keys, and sensitive patterns.
"""
import re
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List
import click
from rich.console import Console
from rich.table import Table

console = Console()

PATTERNS = [
    # Generic
    ("Private Key",           re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Password",              re.compile(r'(?i)(password|passwd|pwd)\s*=\s*"[^${\s"][^"]{3,}"')),
    ("Token/API Key",         re.compile(r'(?i)(token|api_key|apikey|secret_key)\s*=\s*"[^${\s"][^"]{8,}"')),
    ("Base64 Secret",         re.compile(r'(?i)(secret|credential)\s*=\s*"[A-Za-z0-9+/]{20,}={0,2}"')),
    # AWS
    ("AWS Access Key",        re.compile(r'AKIA[0-9A-Z]{16}')),
    # OCI
    ("OCI Fingerprint",       re.compile(r'[0-9a-f]{2}(:[0-9a-f]{2}){15}')),
    # Azure
    ("Azure Client Secret",   re.compile(r'(?i)client_secret\s*=\s*"[^${\s"][^"]{8,}"')),
    ("Azure Storage Key",     re.compile(r'(?i)(storage_account_key|account_key)\s*=\s*"[^${\s"][^"]{20,}"')),
    ("Azure SAS Token",       re.compile(r'(?i)sas_token\s*=\s*"[^${\s"][^"]{10,}"')),
    ("Azure Connection String",re.compile(r'(?i)connection_string\s*=\s*"[^${\s"][^"]{20,}"')),
    ("Azure AD App Secret",   re.compile(r'(?i)(application_secret|app_secret)\s*=\s*"[^${\s"][^"]{8,}"')),
]

SAFE_PATTERNS = [
    re.compile(r'var\.'),
    re.compile(r'local\.'),
    re.compile(r'data\.'),
    re.compile(r'\$\{'),
]


@dataclass
class Finding:
    file: str
    line: int
    pattern_name: str
    snippet: str


def is_safe(line: str) -> bool:
    return any(p.search(line) for p in SAFE_PATTERNS)


def scan_file(path: Path) -> List[Finding]:
    findings = []
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return findings

    for i, line in enumerate(lines, start=1):
        if line.strip().startswith("#"):
            continue
        if is_safe(line):
            continue
        for name, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(Finding(str(path), i, name, line.strip()[:120]))
                break

    return findings


def scan_directory(root: Path) -> List[Finding]:
    all_findings = []
    tf_files = list(root.rglob("*.tf"))
    console.print(f"[dim]Scanning {len(tf_files)} .tf file(s) in {root}[/dim]\n")
    for f in tf_files:
        all_findings.extend(scan_file(f))
    return all_findings


def print_report(findings: List[Finding]):
    if not findings:
        console.print("[bold green]✅ No secrets detected.[/bold green]")
        return

    table = Table(title=f"🔐 Secret Leakage Report — {len(findings)} finding(s)", show_lines=True)
    table.add_column("File", style="cyan")
    table.add_column("Line", style="yellow", width=6)
    table.add_column("Pattern", style="magenta")
    table.add_column("Snippet")

    for f in findings:
        table.add_row(f.file, str(f.line), f.pattern_name, f.snippet)

    console.print(table)


@click.command()
@click.option("--path", "-p", default=".", help="Path to scan (file or directory)")
@click.option("--fail-on-findings", is_flag=True, help="Exit code 1 if findings exist (CI mode)")
def main(path, fail_on_findings):
    """Scan Terraform files for hardcoded secrets and sensitive values."""
    root = Path(path)
    if not root.exists():
        console.print(f"[red]Path not found: {root}[/red]")
        sys.exit(1)

    findings = scan_file(root) if root.is_file() else scan_directory(root)
    print_report(findings)

    if fail_on_findings and findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
