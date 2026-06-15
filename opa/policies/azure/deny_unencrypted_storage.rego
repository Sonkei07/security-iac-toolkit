# Policy: azure/deny_unencrypted_storage
# Azure Storage Accounts must enforce HTTPS only.
# Managed Disks must use a customer-managed key (CMK).
# Key Vaults must have soft delete and purge protection enabled.

package terraform.azure.storage

import future.keywords.if

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "azurerm_storage_account"
    resource.change.after.enable_https_traffic_only == false
    msg := sprintf(
        "❌ [%s] Storage Account must enforce HTTPS only (enable_https_traffic_only = true).",
        [resource.address]
    )
}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "azurerm_storage_account"
    resource.change.after.min_tls_version != "TLS1_2"
    msg := sprintf(
        "❌ [%s] Storage Account must use TLS 1.2 minimum (min_tls_version = \"TLS1_2\").",
        [resource.address]
    )
}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "azurerm_managed_disk"
    not resource.change.after.disk_encryption_set_id
    msg := sprintf(
        "❌ [%s] Managed Disk must use a customer-managed key via disk_encryption_set_id.",
        [resource.address]
    )
}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "azurerm_key_vault"
    resource.change.after.soft_delete_retention_days < 7
    msg := sprintf(
        "❌ [%s] Key Vault soft_delete_retention_days must be at least 7.",
        [resource.address]
    )
}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "azurerm_key_vault"
    not resource.change.after.purge_protection_enabled
    msg := sprintf(
        "❌ [%s] Key Vault must have purge_protection_enabled = true.",
        [resource.address]
    )
}
