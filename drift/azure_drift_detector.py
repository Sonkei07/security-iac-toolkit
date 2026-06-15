#!/usr/bin/env python3
"""
azure_drift_detector.py
Compares a Terraform/OpenTofu state file against live Azure resources
and reports drift using the Azure SDK (azure-mgmt-compute, azure-mgmt-network).
"""
import json
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import click
from rich.console import Console
from rich.table import Table

console = Console()

AZURE_SDK_AVAILABLE = False
try:
    from azure.identity import DefaultAzureCredential
    from azure.mgmt.compute import ComputeManagementClient
    from azure.mgmt.network import NetworkManagementClient
    from azure.mgmt.resource import ResourceManagementClient
    AZURE_SDK_AVAILABLE = True
except ImportError:
    pass


@dataclass
class DriftFinding:
    resource_address: str
    resource_type: str
    detail: str


def load_state(state_path: str) -> dict:
    path = Path(state_path)
    if not path.exists():
        console.print(f"[red]State file not found: {state_path}[/red]")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def extract_resources(state: dict) -> List[dict]:
    resources = []
    for res in state.get("resources", []):
        if res.get("mode") != "managed":
            continue
        for instance in res.get("instances", []):
            resources.append({
                "address": f"{res['type']}.{res['name']}",
                "type": res["type"],
                "attributes": instance.get("attributes", {}),
            })
    return resources


def parse_resource_group(resource_id: str) -> Optional[str]:
    """Extract resource group name from an Azure resource ID."""
    parts = resource_id.split("/")
    try:
        idx = parts.index("resourceGroups")
        return parts[idx + 1]
    except (ValueError, IndexError):
        return None


def check_vm(attrs: dict, subscription_id: str) -> Optional[str]:
    if not AZURE_SDK_AVAILABLE:
        return "azure-sdk not installed — run: pip install azure-mgmt-compute azure-identity"
    vm_id = attrs.get("id", "")
    rg = parse_resource_group(vm_id)
    name = attrs.get("name")
    if not rg or not name:
        return "missing resource_group or name in state"
    try:
        credential = DefaultAzureCredential()
        client = ComputeManagementClient(credential, subscription_id)
        vm = client.virtual_machines.get(rg, name)
        state_size = attrs.get("vm_size") or (attrs.get("size", ""))
        if vm.hardware_profile.vm_size.lower() != state_size.lower():
            return f"vm_size mismatch: state='{state_size}' live='{vm.hardware_profile.vm_size}'"
        ps = vm.provisioning_state
        if ps != "Succeeded":
            return f"provisioning_state is '{ps}' (expected Succeeded)"
        return None
    except Exception as e:
        return f"Azure API error: {e}"


def check_vnet(attrs: dict, subscription_id: str) -> Optional[str]:
    if not AZURE_SDK_AVAILABLE:
        return "azure-sdk not installed — run: pip install azure-mgmt-network azure-identity"
    vnet_id = attrs.get("id", "")
    rg = parse_resource_group(vnet_id)
    name = attrs.get("name")
    if not rg or not name:
        return "missing resource_group or name in state"
    try:
        credential = DefaultAzureCredential()
        client = NetworkManagementClient(credential, subscription_id)
        vnet = client.virtual_networks.get(rg, name)
        state_cidrs = set(attrs.get("address_space", []))
        live_cidrs = set(vnet.address_space.address_prefixes or [])
        if state_cidrs != live_cidrs:
            return f"address_space mismatch: state={state_cidrs} live={live_cidrs}"
        return None
    except Exception as e:
        return f"Azure API error: {e}"


def check_resource_group(attrs: dict, subscription_id: str) -> Optional[str]:
    if not AZURE_SDK_AVAILABLE:
        return "azure-sdk not installed"
    name = attrs.get("name")
    if not name:
        return "missing name in state"
    try:
        credential = DefaultAzureCredential()
        client = ResourceManagementClient(credential, subscription_id)
        rg = client.resource_groups.get(name)
        if rg.properties.provisioning_state != "Succeeded":
            return f"provisioning_state='{rg.properties.provisioning_state}'"
        state_location = attrs.get("location", "").replace(" ", "").lower()
        live_location = rg.location.replace(" ", "").lower()
        if state_location and state_location != live_location:
            return f"location mismatch: state='{state_location}' live='{live_location}'"
        return None
    except Exception as e:
        return f"Azure API error: {e}"


CHECKERS = {
    "azurerm_linux_virtual_machine":   check_vm,
    "azurerm_windows_virtual_machine": check_vm,
    "azurerm_virtual_network":         check_vnet,
    "azurerm_resource_group":          check_resource_group,
}


def detect_drift(resources: List[dict], subscription_id: str) -> List[DriftFinding]:
    findings = []
    for res in resources:
        checker = CHECKERS.get(res["type"])
        if not checker:
            continue
        drift_msg = checker(res["attributes"], subscription_id)
        if drift_msg:
            findings.append(DriftFinding(res["address"], res["type"], drift_msg))
    return findings


def print_report(findings: List[DriftFinding], total: int):
    clean = total - len(findings)
    console.print(f"\n[dim]Checked {total} resource(s) — {clean} clean, {len(findings)} with drift[/dim]\n")
    if not findings:
        console.print("[bold green]✅ No drift detected.[/bold green]")
        return
    table = Table(title=f"⚠️  Azure Drift Report — {len(findings)} finding(s)", show_lines=True)
    table.add_column("Resource", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Detail", style="yellow")
    for f in findings:
        table.add_row(f.resource_address, f.resource_type, f.detail)
    console.print(table)


@click.command()
@click.option("--state", "-s", required=True, help="Path to terraform.tfstate")
@click.option("--subscription-id", "-sub", required=True, help="Azure Subscription ID")
@click.option("--fail-on-drift", is_flag=True, help="Exit code 1 if drift found (CI mode)")
def main(state, subscription_id, fail_on_drift):
    """Detect drift between Terraform state and live Azure infrastructure."""
    console.print(f"[bold]🔍 Azure Drift Detector[/bold] — state: {state}\n")
    raw_state = load_state(state)
    resources = extract_resources(raw_state)
    console.print(f"[dim]Found {len(resources)} managed resource(s) in state[/dim]")
    findings = detect_drift(resources, subscription_id)
    print_report(findings, len(resources))
    if fail_on_drift and findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
