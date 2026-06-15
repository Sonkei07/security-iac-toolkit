package terraform.oci.network

import future.keywords.if
import future.keywords.in

sensitive_ports := {22, 3389, 5432, 3306}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "oci_core_security_list"
    rule := resource.change.after.ingress_security_rules[_]
    rule.source == "0.0.0.0/0"
    port := rule.tcp_options[_].min
    port in sensitive_ports
    msg := sprintf(
        "❌ [%s] Security list exposes port %d to 0.0.0.0/0. Restrict to known CIDRs.",
        [resource.address, port]
    )
}
