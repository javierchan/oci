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
