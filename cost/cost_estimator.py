#!/usr/bin/env python3
"""
cost_estimator.py
Parses an OpenTofu/Terraform JSON plan and estimates monthly OCI costs
based on known pricing for common resource types.
"""
import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict
import click
from rich.console import Console
from rich.table import Table

console = Console()

# Simplified OCI pricing (EUR/month, eu-paris-1)
# Source: https://www.oracle.com/cloud/price-list/
OCI_PRICING: Dict[str, dict] = {
    "oci_core_instance": {
        "VM.Standard.E4.Flex":  {"ocpu": 0.025, "ram_gb": 0.0015},
        "VM.Standard.E3.Flex":  {"ocpu": 0.025, "ram_gb": 0.0015},
        "VM.Standard3.Flex":    {"ocpu": 0.038, "ram_gb": 0.0025},
        "VM.Standard.A1.Flex":  {"ocpu": 0.01,  "ram_gb": 0.0006},  # Ampere (ARM)
        "default":              {"ocpu": 0.03,  "ram_gb": 0.002},
    },
    "oci_core_volume": {
        "price_per_gb": 0.0255,  # Block Volume per GB/month
    },
    "oci_objectstorage_bucket": {
        "price_per_gb": 0.0255,  # Object Storage per GB/month (estimated)
    },
    "oci_core_nat_gateway": {
        "flat": 0.0,   # Free in OCI
    },
    "oci_core_internet_gateway": {
        "flat": 0.0,   # Free in OCI
    },
    "oci_load_balancer": {
        "base": 10.0,  # LBaaS base per month
    },
}

HOURS_PER_MONTH = 730


@dataclass
class CostLine:
    address: str
    resource_type: str
    description: str
    monthly_cost: float


def estimate_instance(attrs: dict, address: str) -> CostLine:
    shape = attrs.get("shape", "default")
    shape_config = attrs.get("shape_config", [{}])
    if isinstance(shape_config, list):
        shape_config = shape_config[0] if shape_config else {}

    ocpus = float(shape_config.get("ocpus", 1))
    ram_gb = float(shape_config.get("memory_in_gbs", 8))

    pricing = OCI_PRICING["oci_core_instance"]
    rates = pricing.get(shape, pricing["default"])

    monthly = (ocpus * rates["ocpu"] + ram_gb * rates["ram_gb"]) * HOURS_PER_MONTH
    desc = f"{shape} — {ocpus} oCPU, {ram_gb} GB RAM"
    return CostLine(address, "oci_core_instance", desc, monthly)


def estimate_volume(attrs: dict, address: str) -> CostLine:
    size_gb = float(attrs.get("size_in_gbs", 50))
    monthly = size_gb * OCI_PRICING["oci_core_volume"]["price_per_gb"]
    return CostLine(address, "oci_core_volume", f"{size_gb} GB Block Volume", monthly)


def estimate_bucket(attrs: dict, address: str) -> CostLine:
    # Plan doesn't know data size — estimate 100 GB as baseline
    monthly = 100 * OCI_PRICING["oci_objectstorage_bucket"]["price_per_gb"]
    return CostLine(address, "oci_objectstorage_bucket", "Object Storage (100 GB baseline estimate)", monthly)


def estimate_load_balancer(attrs: dict, address: str) -> CostLine:
    monthly = OCI_PRICING["oci_load_balancer"]["base"]
    return CostLine(address, "oci_load_balancer", "Load Balancer (base)", monthly)


ESTIMATORS = {
    "oci_core_instance":        estimate_instance,
    "oci_core_volume":          estimate_volume,
    "oci_objectstorage_bucket": estimate_bucket,
    "oci_load_balancer":        estimate_load_balancer,
}


def parse_plan(plan_path: str) -> List[dict]:
    path = Path(plan_path)
    if not path.exists():
        console.print(f"[red]Plan file not found: {plan_path}[/red]")
        sys.exit(1)
    with open(path) as f:
        plan = json.load(f)
    return [
        r for r in plan.get("resource_changes", [])
        if "create" in r.get("change", {}).get("actions", [])
    ]


def estimate(resources: List[dict]) -> List[CostLine]:
    lines = []
    for res in resources:
        estimator = ESTIMATORS.get(res["type"])
        if estimator:
            attrs = res.get("change", {}).get("after", {})
            lines.append(estimator(attrs, res["address"]))
    return lines


def print_report(lines: List[CostLine]):
    if not lines:
        console.print("[yellow]No priceable resources found in plan.[/yellow]")
        return

    table = Table(title="💰 OCI Cost Estimate (Monthly)", show_lines=True)
    table.add_column("Resource", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Description")
    table.add_column("Est. Monthly (€)", style="green", justify="right")

    total = 0.0
    for line in sorted(lines, key=lambda x: x.monthly_cost, reverse=True):
        table.add_row(
            line.address,
            line.resource_type,
            line.description,
            f"€{line.monthly_cost:.2f}",
        )
        total += line.monthly_cost

    table.add_section()
    table.add_row("", "", "[bold]TOTAL[/bold]", f"[bold]€{total:.2f}[/bold]")
    console.print(table)
    console.print(
        "\n[dim]⚠️  Estimates are approximations based on public OCI pricing (eu-paris-1).\n"
        "Object Storage costs depend on actual data volume. Always verify on oracle.com/cloud/price-list[/dim]\n"
    )


@click.command()
@click.option("--plan", "-p", required=True, help="Path to tofu/terraform show -json output")
def main(plan):
    """Estimate monthly OCI costs from an OpenTofu/Terraform JSON plan."""
    console.print(f"[bold]💰 OCI Cost Estimator[/bold] — plan: {plan}\n")
    resources = parse_plan(plan)
    console.print(f"[dim]Found {len(resources)} resource(s) to create[/dim]\n")
    lines = estimate(resources)
    print_report(lines)


if __name__ == "__main__":
    main()
