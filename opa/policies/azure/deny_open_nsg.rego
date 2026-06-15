# Policy: azure/deny_open_nsg
# Denies Azure NSG rules that allow inbound traffic from * (any)
# on sensitive ports: 22/SSH, 3389/RDP, 5432/Postgres, 3306/MySQL, 1433/MSSQL

package terraform.azure.network

import future.keywords.if
import future.keywords.in

sensitive_ports := {"22", "3389", "5432", "3306", "1433"}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "azurerm_network_security_rule"
    attrs := resource.change.after
    attrs.direction == "Inbound"
    attrs.access == "Allow"
    attrs.source_address_prefix in {"*", "Internet", "0.0.0.0/0"}
    attrs.destination_port_range in sensitive_ports
    msg := sprintf(
        "❌ [%s] NSG rule allows inbound port %s from any source. Restrict to known CIDRs.",
        [resource.address, attrs.destination_port_range]
    )
}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "azurerm_network_security_group"
    rule := resource.change.after.security_rule[_]
    rule.direction == "Inbound"
    rule.access == "Allow"
    rule.source_address_prefix in {"*", "Internet", "0.0.0.0/0"}
    rule.destination_port_range in sensitive_ports
    msg := sprintf(
        "❌ [%s] Inline NSG rule allows inbound port %s from any source.",
        [resource.address, rule.destination_port_range]
    )
}
