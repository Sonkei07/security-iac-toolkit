package terraform.oci.compute

import future.keywords.if
import future.keywords.in

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "oci_core_instance"
    resource.change.after.create_vnic_details[_].assign_public_ip == true
    msg := sprintf(
        "❌ [%s] OCI instance must not have a public IP. Use a NAT Gateway instead.",
        [resource.address]
    )
}
