# Authentication

This project supports multiple OCI authentication methods. The CLI auto-detects when possible, but also allows explicit selection via flags and environment variables.

Supported methods:
- config: API key via ~/.oci/config (profile selection)
- instance: Instance Principals (running on OCI Compute)
- resource: Resource Principals (OCI Functions, OKE workloads, etc.)
- security_token: Session profile stored in ~/.oci/config
- auto (default): Tries Resource Principals, then Instance Principals, then Config-file auth

Never print secrets. Never commit credentials to the repository.

## Choosing an auth method

Use the `--auth` flag:
- `--auth auto` (default)
- `--auth config --profile DEFAULT`
- `--auth instance`
- `--auth resource`
- `--auth security_token --profile DEFAULT`

Environment variables can also be used:
- `OCI_INV_AUTH`: auto|config|instance|resource|security_token
- `OCI_INV_PROFILE`: profile name for config-file auth
- `OCI_TENANCY_OCID`: tenancy OCID for auth flows that don't infer it from a config file

Note: For operations like listing regions and compartments, the tenancy OCID must be known. When using config-file auth, it is read from the profile. For signer-based methods (instance/resource principals), provide `--tenancy` if the tenancy cannot be inferred.
Signer-based auth also requires a region. Set `OCI_REGION` (or `OCI_CLI_REGION`) or pass a region explicitly to avoid SDK initialization errors.

## Config-file auth (API keys)

Configure `~/.oci/config`:
```
[DEFAULT]
user=ocid1.user.oc1..aaaa...
tenancy=ocid1.tenancy.oc1..aaaa...
region=us-ashburn-1
fingerprint=aa:bb:cc:...
key_file=/path/to/oci_api_key.pem
```

Then run:
```
oci-inv validate-auth --auth config --profile DEFAULT
```

Keep your key files secure and never commit them.

## Instance Principals

When running on an OCI compute instance with appropriate dynamic group and policies, instance principals can be used:
```
oci-inv validate-auth --auth instance
```
Ensure IAM policies allow access to identity regions and resource search.

## Resource Principals

When running in managed environments like OCI Functions or OKE with service accounts, resource principals can be used:
```
oci-inv validate-auth --auth resource
```

## Security token (session profiles)

If you have a temporary security token profile in `~/.oci/config`:
```
oci-inv validate-auth --auth security_token --profile MY_SESSION
```

## IAM scope for inventory + enrichment + cost

Discovery uses Resource Search, and enrichment uses per-service `get` calls. Cost reporting uses the Usage API and Budgets API. To minimize `enrichStatus=ERROR`, the calling principal must have read/inspect access to the services present in scope.

### Option A: Broad read-only (lowest friction)
```
allow group <group-name> to read all-resources in tenancy
allow group <group-name> to read usage-reports in tenancy
allow group <group-name> to read budgets in tenancy
```

### Option B: Least-privilege baseline (recommended if you manage IAM closely)
```
# Resource Search (discovery)
allow group <group-name> to inspect resources in tenancy

# Identity (users/groups/policies/compartments/tags)
allow group <group-name> to read users in tenancy
allow group <group-name> to read groups in tenancy
allow group <group-name> to read policies in tenancy
allow group <group-name> to read compartments in tenancy
allow group <group-name> to read tag-namespaces in tenancy
allow group <group-name> to read tag-defaults in tenancy

# Core workload/services (common enrichment targets)
allow group <group-name> to read virtual-network-family in tenancy
allow group <group-name> to read instance-family in tenancy
allow group <group-name> to read volume-family in tenancy
allow group <group-name> to read load-balancers in tenancy
allow group <group-name> to read objectstorage-family in tenancy
allow group <group-name> to read functions-family in tenancy
allow group <group-name> to read devops-family in tenancy
allow group <group-name> to read dns in tenancy
allow group <group-name> to read logging-family in tenancy
allow group <group-name> to read loganalytics-family in tenancy
allow group <group-name> to read cloud-guard-family in tenancy
allow group <group-name> to read vaults in tenancy
allow group <group-name> to read keys in tenancy
allow group <group-name> to read secret-family in tenancy
allow group <group-name> to read database-family in tenancy
allow group <group-name> to read osmh-family in tenancy
allow group <group-name> to read resource-manager-family in tenancy
allow group <group-name> to read service-connector-hub-family in tenancy
allow group <group-name> to read streams in tenancy
allow group <group-name> to read bastion in tenancy
allow group <group-name> to read waf-family in tenancy

# Cost + budgets
allow group <group-name> to read usage-reports in tenancy
allow group <group-name> to read budgets in tenancy
```

### Validate and refine
- If `report/report.md` shows NotAuthorized enrichment errors, expand read/inspect access for the affected services.
- If NotFound errors dominate, treat them as expected drift (resources deleted) and re-run to confirm.
- If Throttling errors appear, reduce `--workers-enrich` or increase `--client-connection-pool-size`.

## Validation and troubleshooting

Validate your auth:
```
oci-inv validate-auth --auth auto --profile DEFAULT
```

If validation succeeds, you should see a list of subscribed regions. If it fails:
- Ensure your profile is correct and accessible.
- Ensure your dynamic group and policy allow calling identity and resource search APIs.
- For signer-based methods, provide `--tenancy` if required.

Security hygiene:
- Do not print environment variables or secrets.
- Prefer least-privilege IAM policies tailored to the inventory use case.
