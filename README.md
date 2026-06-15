# security-iac-toolkit

> A collection of security and governance tools for OCI Infrastructure-as-Code — secret scanning, drift detection, cost estimation, OPA policy enforcement, and tagging compliance.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![OCI](https://img.shields.io/badge/OCI-F80000?style=flat-square&logo=oracle&logoColor=white)
![OPA](https://img.shields.io/badge/OPA-Policy-7B61FF?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Tools

| Tool | Description | Command |
|---|---|---|
| 🔐 Secret Scanner | Detects hardcoded passwords, tokens, and keys in `.tf` files | `python toolkit.py scan` |
| 🔍 Drift Detector | Compares Terraform state against live OCI resources | `python toolkit.py drift` |
| 💰 Cost Estimator | Estimates monthly OCI costs from a Terraform JSON plan | `python toolkit.py cost` |
| 🏷️ Tag Enforcer | Enforces required tags and naming conventions on OCI resources | `python toolkit.py tags` |
| 📋 OPA Policies | Rego policies for plan-time enforcement via CI/CD | `opa eval` / `conftest` |

---

## Architecture

```
security-iac-toolkit/
├── toolkit.py                      # Unified CLI entrypoint
├── scanner/
│   └── secret_scanner.py           # Regex-based secret leakage detection
├── drift/
│   └── drift_detector.py           # State vs live OCI resource comparison
├── cost/
│   └── cost_estimator.py           # Monthly cost estimation from JSON plan
├── tagging/
│   └── tag_enforcer.py             # Tag completeness + naming convention checks
└── opa/
    ├── policies/
    │   ├── deny_public_ip.rego          # No direct public IPs on instances
    │   ├── enforce_tags.rego            # Required freeform tags
    │   ├── deny_open_security_list.rego # No 0.0.0.0/0 on sensitive ports
    │   └── deny_unencrypted_storage.rego # CMK required on volumes/buckets
    └── tests/
        ├── test_deny_public_ip.rego
        └── test_enforce_tags.rego
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

Scans `.tf` files for hardcoded credentials, API keys, tokens, and private keys.

```bash
# Scan a directory
python toolkit.py scan --path ./my-terraform-modules

# CI mode (exits with code 1 if findings)
python toolkit.py scan --path . --fail-on-findings
```

**Detected patterns:** Private keys · Passwords · API tokens · AWS access keys · OCI fingerprints · Base64 secrets

Safe references using `var.`, `local.`, `data.`, or `${}` are automatically ignored.

---

### 🔍 Drift Detector

Compares your Terraform state file against live OCI resources and reports any discrepancies.

```bash
python toolkit.py drift --state ./terraform.tfstate --region eu-paris-1

# CI mode
python toolkit.py drift --state ./terraform.tfstate --fail-on-drift
```

**Checks:** Instance existence & lifecycle state · VCN CIDR drift · display_name mismatches

> Requires `oci-sdk`: `pip install oci`

---

### 💰 Cost Estimator

Parses an OpenTofu/Terraform JSON plan and estimates monthly OCI costs.

```bash
# Generate the plan JSON first
tofu plan -out=plan.bin
tofu show -json plan.bin > plan.json

# Estimate costs
python toolkit.py cost --plan ./plan.json
```

**Supported resources:** `oci_core_instance` · `oci_core_volume` · `oci_objectstorage_bucket` · `oci_load_balancer`

Pricing based on OCI public price list (eu-paris-1). Estimates only — always verify at [oracle.com/cloud/price-list](https://oracle.com/cloud/price-list).

---

### 🏷️ Tag Enforcer

Validates that all OCI resources in your `.tf` files have required tags and follow the naming convention.

```bash
python toolkit.py tags --path ./modules/

# CI mode
python toolkit.py tags --path . --fail-on-violations
```

**Required tags:** `environment` · `owner` · `project`

**Valid environments:** `dev` · `staging` · `preprod` · `prod`

**Naming convention:** `<project>-<environment>-<type>-<name>`
Example: `cnaf-prod-instance-web`, `cnaf-dev-vcn-main`

---

### 📋 OPA Policies

Enforce policies at plan time using [OPA](https://www.openpolicyagent.org/) or [Conftest](https://conftest.dev/).

```bash
# Run OPA unit tests
opa test opa/policies/ opa/tests/ -v

# Evaluate a policy against a plan
tofu show -json plan.bin | opa eval -d opa/policies/ -I data.terraform.oci.compute.deny

# With conftest
conftest test plan.json --policy opa/policies/
```

**Policies included:**

| Policy | What it enforces |
|---|---|
| `deny_public_ip` | No direct public IPs on compute instances |
| `enforce_tags` | Required freeform tags on all resources |
| `deny_open_security_list` | No 0.0.0.0/0 on ports 22, 3389, 5432, 3306 |
| `deny_unencrypted_storage` | CMK required on Block Volumes and Object Storage |

---

## CI/CD Integration

Run all checks in your GitLab CI pipeline:

```yaml
iac-security:
  stage: validate
  image: python:3.11
  script:
    - pip install -r requirements.txt
    - python toolkit.py scan --path . --fail-on-findings
    - python toolkit.py tags --path . --fail-on-violations
    - tofu show -json $PLAN_BINARY > plan.json
    - python toolkit.py cost --plan plan.json
```

---

## Author

**Amine Moueqqit** — Cloud Platform Engineer  
[LinkedIn](https://linkedin.com/in/amine-moueqqit) · [GitHub](https://github.com/Sonkei07)

---

## License

MIT
