# security-iac-toolkit

> A collection of security and governance tools for OCI & Azure Infrastructure-as-Code — secret scanning, drift detection, cost estimation, OPA policy enforcement, and tagging compliance.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![OCI](https://img.shields.io/badge/OCI-F80000?style=flat-square&logo=oracle&logoColor=white)
![Azure](https://img.shields.io/badge/Azure-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)
![OPA](https://img.shields.io/badge/OPA-Policy-7B61FF?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Tools

| Tool | Description | Command |
|---|---|---|
| 🔐 Secret Scanner | Detects hardcoded passwords, tokens, and keys in `.tf` files (OCI + Azure patterns) | `python toolkit.py scan` |
| 🔍 Drift Detector | Compares Terraform state against live OCI or Azure resources | `python toolkit.py drift --cloud oci\|azure` |
| 💰 Cost Estimator | Estimates monthly OCI or Azure costs from a Terraform JSON plan | `python toolkit.py cost --cloud oci\|azure` |
| 🏷️ Tag Enforcer | Enforces required tags and naming conventions on OCI and Azure resources | `python toolkit.py tags --cloud oci\|azure\|both` |
| 📋 OPA Policies | Rego policies for plan-time enforcement via CI/CD (OCI + Azure) | `opa eval` / `conftest` |

---

## Architecture

```
security-iac-toolkit/
├── toolkit.py                          # Unified CLI entrypoint (--cloud flag)
├── scanner/
│   └── secret_scanner.py               # Regex-based secret leakage detection (OCI + Azure)
├── drift/
│   ├── drift_detector.py               # State vs live OCI resource comparison
│   └── azure_drift_detector.py         # State vs live Azure resource comparison
├── cost/
│   ├── cost_estimator.py               # Monthly OCI cost estimation from JSON plan
│   └── azure_cost_estimator.py         # Monthly Azure cost estimation from JSON plan
├── tagging/
│   ├── tag_enforcer.py                 # OCI tag completeness + naming convention checks
│   └── azure_tag_enforcer.py           # Azure tag completeness + naming convention checks
└── opa/
    ├── policies/
    │   ├── deny_public_ip.rego             # OCI: no direct public IPs on instances
    │   ├── enforce_tags.rego               # OCI: required freeform tags
    │   ├── deny_open_security_list.rego    # OCI: no 0.0.0.0/0 on sensitive ports
    │   ├── deny_unencrypted_storage.rego   # OCI: CMK required on volumes/buckets
    │   └── azure/
    │       ├── deny_public_ip.rego         # Azure: no public IP on NICs
    │       ├── enforce_tags.rego           # Azure: required tags on all resources
    │       ├── deny_open_nsg.rego          # Azure: no * source on sensitive ports
    │       └── deny_unencrypted_storage.rego # Azure: HTTPS, TLS 1.2, CMK, KV purge
    └── tests/
        ├── test_deny_public_ip.rego
        ├── test_enforce_tags.rego
        └── azure/
            └── test_deny_open_nsg.rego
```

---

## Quickstart

```bash
git clone https://github.com/Sonkei07/security-iac-toolkit.git
cd security-iac-toolkit
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

### 🔐 Secret Scanner

Scans `.tf` files for hardcoded credentials, API keys, tokens, and private keys — covers both OCI and Azure specific patterns.

```bash
# Scan a directory
python toolkit.py scan --path ./my-terraform-modules

# CI mode (exits with code 1 if findings)
python toolkit.py scan --path . --fail-on-findings
```

**Detected patterns:** Private keys · Passwords · API tokens · AWS access keys · OCI fingerprints · Azure client secrets · Azure storage keys · Azure SAS tokens · Azure connection strings

Safe references using `var.`, `local.`, `data.`, or `${}` are automatically ignored.

---

### 🔍 Drift Detector

Compares your Terraform state file against live OCI or Azure resources and reports discrepancies.

```bash
# OCI
python toolkit.py drift --cloud oci --state ./terraform.tfstate --region eu-paris-1

# Azure
python toolkit.py drift --cloud azure --state ./terraform.tfstate --subscription-id <sub-id>

# CI mode
python toolkit.py drift --cloud oci --state ./terraform.tfstate --fail-on-drift
```

**OCI checks:** Instance lifecycle state · VCN CIDR drift · display_name mismatches
> Requires `oci-sdk`: `pip install oci`

**Azure checks:** VM size & provisioning state · VNet address space · Resource Group location
> Requires Azure SDK: `pip install azure-identity azure-mgmt-compute azure-mgmt-network azure-mgmt-resource`

---

### 💰 Cost Estimator

Parses an OpenTofu/Terraform JSON plan and estimates monthly costs.

```bash
# Generate the plan JSON first
tofu plan -out=plan.bin
tofu show -json plan.bin > plan.json

# OCI estimate (eu-paris-1)
python toolkit.py cost --cloud oci --plan ./plan.json

# Azure estimate (West Europe)
python toolkit.py cost --cloud azure --plan ./plan.json
```

**OCI supported resources:** `oci_core_instance` · `oci_core_volume` · `oci_objectstorage_bucket` · `oci_load_balancer`

**Azure supported resources:** `azurerm_linux_virtual_machine` · `azurerm_windows_virtual_machine` · `azurerm_managed_disk` · `azurerm_storage_account` · `azurerm_kubernetes_cluster` · `azurerm_load_balancer` · `azurerm_key_vault`

Estimates only — always verify at [oracle.com/cloud/price-list](https://oracle.com/cloud/price-list) and [azure.microsoft.com/pricing](https://azure.microsoft.com/pricing).

---

### 🏷️ Tag Enforcer

Validates that all resources in your `.tf` files have required tags and follow the naming convention.

```bash
# OCI only
python toolkit.py tags --cloud oci --path ./modules/

# Azure only
python toolkit.py tags --cloud azure --path ./modules/

# Both clouds at once
python toolkit.py tags --cloud both --path ./modules/

# CI mode
python toolkit.py tags --cloud both --path . --fail-on-violations
```

**Required tags:** `environment` · `owner` · `project`

**Valid environments:** `dev` · `staging` · `preprod` · `prod`

**Naming convention:** `<project>-<environment>-<type>-<name>`

Examples: `cnaf-prod-instance-web` · `cnaf-dev-vcn-main` · `myproject-prod-vm-web`

---

### 📋 OPA Policies

Enforce policies at plan time using [OPA](https://www.openpolicyagent.org/) or [Conftest](https://conftest.dev/).

```bash
# Run all OPA unit tests
opa test opa/policies/ opa/tests/ -v

# OCI — evaluate against a plan
tofu show -json plan.bin | opa eval -d opa/policies/ -I data.terraform.oci.compute.deny

# Azure — evaluate against a plan
tofu show -json plan.bin | opa eval -d opa/policies/azure/ -I data.terraform.azure.network.deny

# With conftest
conftest test plan.json --policy opa/policies/
```

**OCI policies:**

| Policy | What it enforces |
|---|---|
| `deny_public_ip` | No direct public IPs on compute instances |
| `enforce_tags` | Required freeform tags on all resources |
| `deny_open_security_list` | No 0.0.0.0/0 on ports 22, 3389, 5432, 3306 |
| `deny_unencrypted_storage` | CMK required on Block Volumes and Object Storage |

**Azure policies:**

| Policy | What it enforces |
|---|---|
| `azure/deny_public_ip` | No public IP attached directly to NICs |
| `azure/enforce_tags` | Required tags on all taggable Azure resources |
| `azure/deny_open_nsg` | No `*` source on ports 22, 3389, 5432, 3306, 1433 |
| `azure/deny_unencrypted_storage` | HTTPS-only storage · TLS 1.2 · CMK on disks · Key Vault purge protection |

---

## CI/CD Integration

```yaml
iac-security:
  stage: validate
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - python toolkit.py scan --path . --fail-on-findings
    - python toolkit.py tags --cloud both --path . --fail-on-violations
    - tofu show -json $PLAN_BINARY > plan.json
    - python toolkit.py cost --cloud oci --plan plan.json
    - python toolkit.py cost --cloud azure --plan plan.json
```

---

## Author

**Amine Moueqqit** — Cloud Platform Engineer  
[LinkedIn](https://linkedin.com/in/amine-moueqqit) · [GitHub](https://github.com/Sonkei07)

---

## License

MIT
