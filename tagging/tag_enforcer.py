#!/usr/bin/env python3
"""
tag_enforcer.py
Enforces OCI tagging and naming conventions on Terraform/OpenTofu .tf files.
- Required freeform tags: environment, owner, project
- Naming convention: <project>-<environment>-<resource_type>-<name>
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

NAMING_PATTERN = re.compile(
    r'^[a-z][a-z0-9]+-[a-z]+-[a-z]+-[a-z0-9-]+$'
)

RESOURCE_TYPES_WITH_NAMES = [
    "oci_core_instance",
    "oci_core_vcn",
    "oci_core_subnet",
    "oci_core_security_list",
    "oci_objectstorage_bucket",
    "oci_core_volume",
    "oci_load_balancer",
]

# Regex to extract resource blocks from .tf files
RESOURCE_BLOCK_RE = re.compile(
    r'resource\s+"([\w]+)"\s+"([\w-]+)"\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
    re.DOTALL,
)

TAG_RE = re.compile(r'freeform_tags\s*=\s*\{([^}]*)\}', re.DOTALL)
TAG_KEY_RE = re.compile(r'"?([\w]+)"?\s*=')
DISPLAY_NAME_RE = re.compile(r'display_name\s*=\s*"([^"${}]+)"')
ENV_VALUE_RE = re.compile(r'"environment"\s*=\s*"([^"]+)"')


@dataclass
class Violation:
    file: str
    resource: str
    rule: str
    detail: str


def check_resource(file: str, res_type: str, res_name: str, body: str) -> List[Violation]:
    violations = []
    address = f"{res_type}.{res_name}"

    # Skip resources that don't support freeform_tags
    if res_type not in RESOURCE_TYPES_WITH_NAMES:
        return violations

    # 1. Check required tags
    tag_match = TAG_RE.search(body)
    if not tag_match:
        violations.append(Violation(file, address, "missing_tags_block",
                                    f"No freeform_tags block found"))
    else:
        tag_block = tag_match.group(1)
        present_keys = set(TAG_KEY_RE.findall(tag_block))
        for required in REQUIRED_TAGS:
            if required not in present_keys:
                violations.append(Violation(file, address, "missing_required_tag",
                                            f"Missing required tag: '{required}'"))

        # 2. Check environment value
        env_match = ENV_VALUE_RE.search(tag_block)
        if env_match:
            env_val = env_match.group(1)
            if env_val not in VALID_ENVIRONMENTS and not env_val.startswith("$"):
                violations.append(Violation(file, address, "invalid_environment",
                                            f"environment='{env_val}' not in {VALID_ENVIRONMENTS}"))

    # 3. Check naming convention
    name_match = DISPLAY_NAME_RE.search(body)
    if name_match:
        display_name = name_match.group(1)
        if not NAMING_PATTERN.match(display_name):
            violations.append(Violation(
                file, address, "naming_convention",
                f"display_name '{display_name}' does not match pattern: "
                f"<project>-<env>-<type>-<name> (e.g. cnaf-prod-instance-web)"
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
        console.print("[bold green]✅ All resources comply with tagging and naming conventions.[/bold green]")
        return

    table = Table(title=f"🏷️  Tagging & Naming Report — {len(violations)} violation(s)", show_lines=True)
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
    """Enforce OCI tagging and naming conventions on Terraform files."""
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
