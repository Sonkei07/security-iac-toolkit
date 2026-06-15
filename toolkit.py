#!/usr/bin/env python3
"""
security-iac-toolkit
All-in-one CLI for OCI and Azure IaC security and governance.
"""
import click
from rich.console import Console

console = Console()


@click.group()
def cli():
    """🔐 security-iac-toolkit — OCI & Azure IaC Security & Governance CLI"""
    pass


@cli.command()
@click.option("--path", "-p", default=".", help="Path to scan (file or directory)")
@click.option("--fail-on-findings", is_flag=True)
def scan(path, fail_on_findings):
    """Scan Terraform files for hardcoded secrets (OCI + Azure patterns)."""
    from scanner.secret_scanner import main as _main
    ctx = click.get_current_context()
    ctx.invoke(_main, path=path, fail_on_findings=fail_on_findings)


@cli.command()
@click.option("--state", "-s", required=True, help="Path to terraform.tfstate")
@click.option("--cloud", "-c", type=click.Choice(["oci", "azure"]), default="oci")
@click.option("--region", "-r", default="eu-paris-1", help="OCI region (OCI only)")
@click.option("--subscription-id", "-sub", default=None, help="Azure Subscription ID (Azure only)")
@click.option("--fail-on-drift", is_flag=True)
def drift(state, cloud, region, subscription_id, fail_on_drift):
    """Detect drift between Terraform state and live OCI or Azure infra."""
    if cloud == "oci":
        from drift.drift_detector import main as _main
        ctx = click.get_current_context()
        ctx.invoke(_main, state=state, region=region, fail_on_drift=fail_on_drift)
    else:
        if not subscription_id:
            console.print("[red]--subscription-id is required for Azure drift detection[/red]")
            raise SystemExit(1)
        from drift.azure_drift_detector import main as _main
        ctx = click.get_current_context()
        ctx.invoke(_main, state=state, subscription_id=subscription_id, fail_on_drift=fail_on_drift)


@cli.command()
@click.option("--plan", "-p", required=True, help="Path to tofu show -json output")
@click.option("--cloud", "-c", type=click.Choice(["oci", "azure"]), default="oci")
def cost(plan, cloud):
    """Estimate monthly OCI or Azure costs from a Terraform/OpenTofu plan."""
    if cloud == "oci":
        from cost.cost_estimator import main as _main
    else:
        from cost.azure_cost_estimator import main as _main
    ctx = click.get_current_context()
    ctx.invoke(_main, plan=plan)


@cli.command()
@click.option("--path", "-p", default=".", help="Path to scan")
@click.option("--cloud", "-c", type=click.Choice(["oci", "azure", "both"]), default="both")
@click.option("--fail-on-violations", is_flag=True)
def tags(path, cloud, fail_on_violations):
    """Enforce tagging and naming conventions for OCI and/or Azure."""
    ctx = click.get_current_context()
    if cloud in ("oci", "both"):
        console.rule("[bold]OCI")
        from tagging.tag_enforcer import main as _oci
        ctx.invoke(_oci, path=path, fail_on_violations=False)
    if cloud in ("azure", "both"):
        console.rule("[bold]Azure")
        from tagging.azure_tag_enforcer import main as _azure
        ctx.invoke(_azure, path=path, fail_on_violations=False)
    # Apply fail flag after both run
    if fail_on_violations:
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
