package terraform.oci.storage

import future.keywords.if

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "oci_core_volume"
    not resource.change.after.kms_key_id
    msg := sprintf("❌ [%s] Block Volume must use a customer-managed KMS key.", [resource.address])
}

deny[msg] if {
    resource := input.resource_changes[_]
    resource.type == "oci_objectstorage_bucket"
    not resource.change.after.kms_key_id
    msg := sprintf("❌ [%s] Object Storage bucket must use a customer-managed KMS key.", [resource.address])
}
