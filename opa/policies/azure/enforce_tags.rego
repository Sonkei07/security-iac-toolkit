# Policy: azure/enforce_tags
# All Azure resources must have the required tags:
# environment, owner, project

package terraform.azure.tags

import future.keywords.if
import future.keywords.in

required_tags := {"environment", "owner", "project"}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.change.after != null
    # Only check resources that support tags
    resource.change.after.tags != null
    existing := {k | resource.change.after.tags[k]}
    missing := required_tags - existing
    count(missing) > 0
    msg := sprintf(
        "❌ [%s] Missing required Azure tags: %v",
        [resource.address, missing]
    )
}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.change.after != null
    not resource.change.after.tags
    # Exclude resources that don't support tags
    supported_types := {
        "azurerm_virtual_machine", "azurerm_linux_virtual_machine",
        "azurerm_windows_virtual_machine", "azurerm_resource_group",
        "azurerm_storage_account", "azurerm_managed_disk",
        "azurerm_kubernetes_cluster", "azurerm_key_vault"
    }
    resource.type in supported_types
    msg := sprintf(
        "❌ [%s] No tags block found. Required tags: %v",
        [resource.address, required_tags]
    )
}
