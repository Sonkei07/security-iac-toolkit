#!/usr/bin/env python3
"""
azure_cost_estimator.py
Parses an OpenTofu/Terraform JSON plan and estimates monthly Azure costs
based on known pricing for common resource types (West Europe region).
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

# Simplified Azure pricing (EUR/month, West Europe)
# Source: https://azure.microsoft.com/en-us/pricing/
AZURE_PRICING: Dict[str, dict] = {
    "azurerm_linux_virtual_machine": {
        # price per hour
        "Standard_B2s":    0.0416,
        "Standard_B4ms":   0.166,
        "Standard_D2s_v3": 0.096,
        "Standard_D4s_v3": 0.192,
        "Standard_D8s_v3": 0.384,
        "Standard_E2s_v3": 0.126,
        "Standard_F2s_v2": 0.085,
        "default":         0.10,
    },
    "azurerm_windows_virtual_machine": {
        "Standard_B2s":    0.0756,
        "Standard_D2s_v3": 0.188,
        "Standard_D4s_v3": 0.376,
        "default":         0.18,
    },
    "azurerm_managed_disk": {
        # price per GB/month by sku
        "Premium_LRS":     0.135,
        "Standard_LRS":    0.043,
        "StandardSSD_LRS": 0.075,
        "UltraSSD_LRS":    0.30,
        "default":         0.075,
    },
    "azurerm_storage_account": {
        # price per GB/month (LRS, hot tier)
        "Standard_LRS":  0.018,
        "Standard_GRS":  0.036,
        "Premium_LRS":   0.17,
        "default":       0.018,
    },
    "azurerm_kubernetes_cluster": {
        # AKS control plane is free; charge for system node pool
        "system_node_hourly": 0.096,  # Standard_D2s_v3 equivalent
        "system_node_count":  2,
    },
    "azurerm_load_balancer": {
        "Basic":    0.0,
        "Standard": 18.0,
        "default":  18.0,
    },
    "azurerm_key_vault": {
        "flat": 4.0,  # Base fee per vault/month
    },
}

HOURS_PER_MONTH = 730
DEFAULT_DISK_GB = 128
DEFAULT_STORAGE_GB = 100


@dataclass
class CostLine:
    address: str
    resource_type: str
    description: str
    monthly_cost: float


def estimate_vm(attrs: dict, address: str, pricing_key: str) -> CostLine:
    size = attrs.get("size", attrs.get("vm_size", "default"))
    rates = AZURE_PRICING[pricing_key]
    hourly = rates.get(size, rates["default"])
    monthly = hourly * HOURS_PER_MONTH
    os = "Linux" if pricing_key == "azurerm_linux_virtual_machine" else "Windows"
    return CostLine(address, pricing_key, f"{size} ({os})", monthly)


def estimate_disk(attrs: dict, address: str) -> CostLine:
    sku = attrs.get("storage_account_type", "default")
    size_gb = float(attrs.get("disk_size_gb") or DEFAULT_DISK_GB)
    rates = AZURE_PRICING["azurerm_managed_disk"]
    price_gb = rates.get(sku, rates["default"])
    monthly = price_gb * size_gb
    return CostLine(address, "azurerm_managed_disk", f"{size_gb} GB ({sku})", monthly)


def estimate_storage(attrs: dict, address: str) -> CostLine:
    sku = attrs.get("account_replication_type", "LRS")
    tier = attrs.get("account_tier", "Standard")
    key = f"{tier}_{sku}"
    rates = AZURE_PRICING["azurerm_storage_account"]
    price_gb = rates.get(key, rates["default"])
    monthly = price_gb * DEFAULT_STORAGE_GB
    return CostLine(address, "azurerm_storage_account",
                    f"{DEFAULT_STORAGE_GB} GB baseline ({key})", monthly)


def estimate_aks(attrs: dict, address: str) -> CostLine:
    p = AZURE_PRICING["azurerm_kubernetes_cluster"]
    monthly = p["system_node_hourly"] * p["system_node_count"] * HOURS_PER_MONTH
    return CostLine(address, "azurerm_kubernetes_cluster",
                    f"AKS ({p['system_node_count']}x system nodes, control plane free)", monthly)


def estimate_lb(attrs: dict, address: str) -> CostLine:
    sku = attrs.get("sku", "Standard")
    rates = AZURE_PRICING["azurerm_load_balancer"]
    monthly = rates.get(sku, rates["default"])
    return CostLine(address, "azurerm_load_balancer", f"Load Balancer ({sku})", monthly)


def estimate_keyvault(attrs: dict, address: str) -> CostLine:
    monthly = AZURE_PRICING["azurerm_key_vault"]["flat"]
    return CostLine(address, "azurerm_key_vault", "Key Vault (base fee)", monthly)


ESTIMATORS = {
    "azurerm_linux_virtual_machine":   lambda a, addr: estimate_vm(a, addr, "azurerm_linux_virtual_machine"),
    "azurerm_windows_virtual_machine": lambda a, addr: estimate_vm(a, addr, "azurerm_windows_virtual_machine"),
    "azurerm_managed_disk":            estimate_disk,
    "azurerm_storage_account":         estimate_storage,
    "azurerm_kubernetes_cluster":      estimate_aks,
    "azurerm_load_balancer":           estimate_lb,
    "azurerm_key_vault":               estimate_keyvault,
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
        console.print("[yellow]No priceable Azure resources found in plan.[/yellow]")
        return

    table = Table(title="💰 Azure Cost Estimate (Monthly, West Europe)", show_lines=True)
    table.add_column("Resource", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Description")
    table.add_column("Est. Monthly (€)", style="green", justify="right")

    total = 0.0
    for line in sorted(lines, key=lambda x: x.monthly_cost, reverse=True):
        table.add_row(line.address, line.resource_type, line.description, f"€{line.monthly_cost:.2f}")
        total += line.monthly_cost

    table.add_section()
    table.add_row("", "", "[bold]TOTAL[/bold]", f"[bold]€{total:.2f}[/bold]")
    console.print(table)
    console.print(
        "\n[dim]⚠️  Estimates based on public Azure pricing (West Europe, pay-as-you-go).\n"
        "Storage costs depend on actual data volume. Always verify at azure.microsoft.com/pricing[/dim]\n"
    )


@click.command()
@click.option("--plan", "-p", required=True, help="Path to tofu/terraform show -json output")
def main(plan):
    """Estimate monthly Azure costs from an OpenTofu/Terraform JSON plan."""
    console.print(f"[bold]💰 Azure Cost Estimator[/bold] — plan: {plan}\n")
    resources = parse_plan(plan)
    console.print(f"[dim]Found {len(resources)} resource(s) to create[/dim]\n")
    lines = estimate(resources)
    print_report(lines)


if __name__ == "__main__":
    main()
