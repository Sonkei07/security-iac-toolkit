package terraform.oci.tags

test_deny_missing_tags {
    count(deny) > 0 with input as {
        "resource_changes": [{
            "address": "oci_core_instance.web",
            "type": "oci_core_instance",
            "change": {"after": {"freeform_tags": {"environment": "prod"}}}
        }]
    }
}

test_allow_all_tags_present {
    count(deny) == 0 with input as {
        "resource_changes": [{
            "address": "oci_core_instance.web",
            "type": "oci_core_instance",
            "change": {"after": {"freeform_tags": {
                "environment": "prod",
                "owner": "amine",
                "project": "cnaf"
            }}}
        }]
    }
}
