package terraform.oci.tags

import future.keywords.if
import future.keywords.in

required_tags := {"environment", "owner", "project"}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.change.after != null
    existing_tags := {k | resource.change.after.freeform_tags[k]}
    missing := required_tags - existing_tags
    count(missing) > 0
    msg := sprintf(
        "❌ [%s] Missing required freeform tags: %v",
        [resource.address, missing]
    )
}
