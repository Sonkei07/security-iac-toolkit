package terraform.oci.compute

test_deny_instance_with_public_ip {
    count(deny) == 1 with input as {
        "resource_changes": [{
            "address": "oci_core_instance.web",
            "type": "oci_core_instance",
            "change": {"after": {"create_vnic_details": [{"assign_public_ip": true}]}}
        }]
    }
}

test_allow_instance_without_public_ip {
    count(deny) == 0 with input as {
        "resource_changes": [{
            "address": "oci_core_instance.web",
            "type": "oci_core_instance",
            "change": {"after": {"create_vnic_details": [{"assign_public_ip": false}]}}
        }]
    }
}
