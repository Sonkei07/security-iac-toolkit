package terraform.azure.network

test_deny_nsg_open_ssh {
    count(deny) == 1 with input as {
        "resource_changes": [{
            "address": "azurerm_network_security_rule.allow_ssh",
            "type": "azurerm_network_security_rule",
            "change": {"after": {
                "direction": "Inbound",
                "access": "Allow",
                "source_address_prefix": "*",
                "destination_port_range": "22"
            }}
        }]
    }
}

test_allow_nsg_restricted_ssh {
    count(deny) == 0 with input as {
        "resource_changes": [{
            "address": "azurerm_network_security_rule.allow_ssh",
            "type": "azurerm_network_security_rule",
            "change": {"after": {
                "direction": "Inbound",
                "access": "Allow",
                "source_address_prefix": "10.0.0.0/8",
                "destination_port_range": "22"
            }}
        }]
    }
}
