#!/usr/bin/env python3
"""
azure_tag_enforcer.py
Enforces Azure tagging and naming conventions on Terraform/OpenTofu .tf files.
- Required tags: environment, owner, project
- Naming convention: <project>-<environment>-<resource_type>-<name>
- Valid environments: dev, staging, preprod, prod
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

REQUIRED_TAGS = ["environment", "owner", "project"]
VALID_ENVIRONMENTS = {"dev", "staging", "preprod", "prod"}

NAMING_PATTERN = re.compile(r'^[a-z][a-z0-9]+-[a-z]+-[a-z]+-[a-z0-9-]+$')

AZURE_RESOURCE_TYPES = {
    "azurerm_linux_virtual_machine",
    "azurerm_windows_virtual_machine",
    "azurerm_resource_group",
    "azurerm_storage_account",
    "azurerm_managed_disk",
    "azurerm_kubernetes_cluster",
    "azurerm_key_vault",
    "azurerm_virtual_network",
    "azurerm_subnet",
    "azurerm_network_security_group",
    "azurerm_load_balancer",
}

RESOURCE_BLOCK_RE = re.compile(
    r'resource\s+"([\w]+)"\s+"([\w-]+)"\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
    re.DOTALL,
)

# Azure uses `tags = { key = "value" }` syntax
TAGS_BLOCK_RE = re.compile(r'\btags\s*=\s*\{([^}]*)\}', re.DOTALL)
TAG_KEY_RE = re.compile(r'"?([\w]+)"?\s*=')
NAME_RE = re.compile(r'\bname\s*=\s*"([^"${}]+)"')
ENV_VALUE_RE = re.compile(r'"?environment"?\s*=\s*"([^"]+)"')


@dataclass
class Violation:
    file: str
    resource: str
    rule: str
    detail: str


def check_resource(file: str, res_type: str, res_name: str, body: str) -> List[Violation]:
    violations = []
    if res_type not in AZURE_RESOURCE_TYPES:
        return violations

    address = f"{res_type}.{res_name}"

    # 1. Check tags block exists
    tag_match = TAGS_BLOCK_RE.search(body)
    if not tag_match:
        violations.append(Violation(file, address, "missing_tags_block",
                                    "No tags block found"))
        return violations

    tag_block = tag_match.group(1)
    present_keys = set(TAG_KEY_RE.findall(tag_block))

    # 2. Check required tags
    for required in REQUIRED_TAGS:
        if required not in present_keys:
            violations.append(Violation(file, address, "missing_required_tag",
                                        f"Missing required tag: '{required}'"))

    # 3. Validate environment value
    env_match = ENV_VALUE_RE.search(tag_block)
    if env_match:
        env_val = env_match.group(1)
        if env_val not in VALID_ENVIRONMENTS and not env_val.startswith("$"):
            violations.append(Violation(file, address, "invalid_environment",
                                        f"environment='{env_val}' not in {VALID_ENVIRONMENTS}"))

    # 4. Naming convention check on `name` attribute
    name_match = NAME_RE.search(body)
    if name_match:
        name_val = name_match.group(1)
        if not NAMING_PATTERN.match(name_val):
            violations.append(Violation(
                file, address, "naming_convention",
                f"name='{name_val}' must match <project>-<env>-<type>-<name> "
                f"(e.g. myproject-prod-vm-web)"
            ))

    return violations


def scan_file(path: Path) -> List[Violation]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    violations = []
    for match in RESOURCE_BLOCK_RE.finditer(content):
        res_type, res_name, body = match.group(1), match.group(2), match.group(3)
        violations.extend(check_resource(str(path), res_type, res_name, body))
    return violations


def scan_directory(root: Path) -> List[Violation]:
    all_violations = []
    tf_files = list(root.rglob("*.tf"))
    console.print(f"[dim]Scanning {len(tf_files)} .tf file(s)[/dim]\n")
    for f in tf_files:
        all_violations.extend(scan_file(f))
    return all_violations


def print_report(violations: List[Violation]):
    if not violations:
        console.print("[bold green]✅ All Azure resources comply with tagging and naming conventions.[/bold green]")
        return

    table = Table(title=f"🏷️  Azure Tagging & Naming Report — {len(violations)} violation(s)", show_lines=True)
    table.add_column("File", style="cyan")
    table.add_column("Resource", style="magenta")
    table.add_column("Rule", style="yellow")
    table.add_column("Detail")

    for v in violations:
        table.add_row(v.file, v.resource, v.rule, v.detail)

    console.print(table)


@click.command()
@click.option("--path", "-p", default=".", help="Path to scan (file or directory)")
@click.option("--fail-on-violations", is_flag=True, help="Exit code 1 if violations found (CI mode)")
def main(path, fail_on_violations):
    """Enforce Azure tagging and naming conventions on Terraform files."""
    root = Path(path)
    if not root.exists():
        console.print(f"[red]Path not found: {root}[/red]")
        sys.exit(1)
    violations = scan_file(root) if root.is_file() else scan_directory(root)
    print_report(violations)
    if fail_on_violations and violations:
        sys.exit(1)


if __name__ == "__main__":
    main()
