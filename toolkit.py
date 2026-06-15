#!/usr/bin/env python3
"""
security-iac-toolkit
All-in-one CLI for OCI IaC security and governance.
"""
import click
from rich.console import Console

console = Console()


@click.group()
def cli():
    """🔐 security-iac-toolkit — OCI IaC Security & Governance CLI"""
    pass


@cli.command()
@click.option("--path", "-p", default=".", help="Path to scan (file or directory)")
@click.option("--fail-on-findings", is_flag=True)
def scan(path, fail_on_findings):
    """Scan Terraform files for hardcoded secrets."""
    from scanner.secret_scanner import main as _main
    from click.testing import CliRunner
    ctx = click.get_current_context()
    ctx.invoke(_main, path=path, fail_on_findings=fail_on_findings)


@cli.command()
@click.option("--state", "-s", required=True, help="Path to terraform.tfstate")
@click.option("--region", "-r", default="eu-paris-1")
@click.option("--fail-on-drift", is_flag=True)
def drift(state, region, fail_on_drift):
    """Detect drift between Terraform state and live OCI infra."""
    from drift.drift_detector import main as _main
    ctx = click.get_current_context()
    ctx.invoke(_main, state=state, region=region, fail_on_drift=fail_on_drift)


@cli.command()
@click.option("--plan", "-p", required=True, help="Path to tofu show -json output")
def cost(plan):
    """Estimate monthly OCI costs from a Terraform/OpenTofu plan."""
    from cost.cost_estimator import main as _main
    ctx = click.get_current_context()
    ctx.invoke(_main, plan=plan)


@cli.command()
@click.option("--path", "-p", default=".", help="Path to scan")
@click.option("--fail-on-violations", is_flag=True)
def tags(path, fail_on_violations):
    """Enforce OCI tagging and naming conventions."""
    from tagging.tag_enforcer import main as _main
    ctx = click.get_current_context()
    ctx.invoke(_main, path=path, fail_on_violations=fail_on_violations)


if __name__ == "__main__":
    cli()
