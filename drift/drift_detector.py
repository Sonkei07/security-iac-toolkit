#!/usr/bin/env python3
"""
drift_detector.py
Compares a Terraform/OpenTofu state file against live OCI resources
and reports any drift (resources present in state but missing in OCI,
or attributes that differ).
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

OCI_SDK_AVAILABLE = False
try:
    import oci
    OCI_SDK_AVAILABLE = True
except ImportError:
    pass


@dataclass
class DriftFinding:
    resource_address: str
    resource_type: str
    drift_type: str   # "missing" | "attribute_mismatch"
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


def check_oci_instance(attrs: dict, oci_client) -> Optional[str]:
    """Verify an OCI compute instance exists and is RUNNING."""
    if not OCI_SDK_AVAILABLE:
        return "oci SDK not installed — install oci-sdk to enable live checks"
    instance_id = attrs.get("id")
    if not instance_id:
        return "no OCID in state"
    try:
        response = oci_client.get_instance(instance_id)
        instance = response.data
        if instance.lifecycle_state == "TERMINATED":
            return f"instance is TERMINATED (was {attrs.get('display_name', '?')})"
        if instance.display_name != attrs.get("display_name"):
            return f"display_name mismatch: state='{attrs.get('display_name')}' live='{instance.display_name}'"
        return None
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            return "instance not found in OCI (404)"
        return f"OCI API error: {e.message}"


def check_oci_vcn(attrs: dict, oci_client) -> Optional[str]:
    if not OCI_SDK_AVAILABLE:
        return "oci SDK not installed"
    vcn_id = attrs.get("id")
    if not vcn_id:
        return "no OCID in state"
    try:
        response = oci_client.get_vcn(vcn_id)
        vcn = response.data
        if vcn.lifecycle_state == "TERMINATED":
            return "VCN is TERMINATED"
        if vcn.cidr_block != attrs.get("cidr_block"):
            return f"cidr_block mismatch: state='{attrs.get('cidr_block')}' live='{vcn.cidr_block}'"
        return None
    except oci.exceptions.ServiceError as e:
        if e.status == 404:
            return "VCN not found in OCI (404)"
        return f"OCI API error: {e.message}"


CHECKERS = {
    "oci_core_instance": check_oci_instance,
    "oci_core_vcn": check_oci_vcn,
}


def detect_drift(resources: List[dict], region: str) -> List[DriftFinding]:
    findings = []

    oci_client = None
    if OCI_SDK_AVAILABLE:
        try:
            config = oci.config.from_file()
            config["region"] = region
            oci_client = oci.core.ComputeClient(config)
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not initialize OCI client: {e}[/yellow]")

    for res in resources:
        checker = CHECKERS.get(res["type"])
        if not checker:
            continue

        drift_msg = checker(res["attributes"], oci_client)
        if drift_msg:
            findings.append(DriftFinding(
                resource_address=res["address"],
                resource_type=res["type"],
                drift_type="drift_detected",
                detail=drift_msg,
            ))

    return findings


def print_report(findings: List[DriftFinding], total: int):
    clean = total - len(findings)
    console.print(f"\n[dim]Checked {total} resource(s) — {clean} clean, {len(findings)} with drift[/dim]\n")

    if not findings:
        console.print("[bold green]✅ No drift detected.[/bold green]")
        return

    table = Table(title=f"⚠️  Drift Report — {len(findings)} finding(s)", show_lines=True)
    table.add_column("Resource", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Detail", style="yellow")

    for f in findings:
        table.add_row(f.resource_address, f.resource_type, f.detail)

    console.print(table)


@click.command()
@click.option("--state", "-s", required=True, help="Path to terraform.tfstate file")
@click.option("--region", "-r", default="eu-paris-1", help="OCI region")
@click.option("--fail-on-drift", is_flag=True, help="Exit code 1 if drift found (CI mode)")
def main(state, region, fail_on_drift):
    """Detect drift between Terraform state and live OCI infrastructure."""
    console.print(f"[bold]🔍 Drift Detector[/bold] — state: {state} | region: {region}\n")

    raw_state = load_state(state)
    resources = extract_resources(raw_state)
    console.print(f"[dim]Found {len(resources)} managed resource(s) in state[/dim]")

    findings = detect_drift(resources, region)
    print_report(findings, len(resources))

    if fail_on_drift and findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
