# Policy: azure/deny_public_ip
# Azure VMs must not have a public IP associated directly.
# Use a load balancer or Azure Bastion for external access.

package terraform.azure.compute

import future.keywords.if
import future.keywords.in

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "azurerm_network_interface"
    config := resource.change.after.ip_configuration[_]
    config.public_ip_address_id != null
    config.public_ip_address_id != ""
    msg := sprintf(
        "❌ [%s] NIC must not have a public IP attached. Use Azure Bastion or a Load Balancer.",
        [resource.address]
    )
}
