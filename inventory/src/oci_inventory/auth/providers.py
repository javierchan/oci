from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Union

from ..util.errors import OCIClientError, map_oci_error

try:
    import oci  # type: ignore
except Exception as e:  # pragma: no cover - import error surfaced at runtime/CI
    oci = None  # type: ignore


ConfigDict = Dict[str, Any]


@dataclass(frozen=True)
class AuthContext:
    """
    Holds resolved authentication context to construct OCI SDK clients.
    Exactly one of (config_dict, signer) is required (SDK accepts either).
    tenancy_ocid can be inferred from config_dict for config-file auth.
    """

    method: str  # auto|config|instance|resource|security_token (resolved final)
    config_dict: Optional[ConfigDict]
    signer: Optional[Any]
    profile: Optional[str]
    tenancy_ocid: Optional[str]


class AuthError(RuntimeError):
    pass


def _require_oci() -> None:
    if oci is None:
        raise AuthError(
            "oci Python SDK not installed. Install dependencies and try again: pip install ."
        )


def _detect_region() -> Optional[str]:
    """
    Try to detect current region from environment (used by IMDS/RP flows when available).
    """
    return os.getenv("OCI_REGION") or os.getenv("OCI_CLI_REGION")


def resolve_auth(method: str, profile: Optional[str], tenancy_ocid: Optional[str]) -> AuthContext:
    """
    Resolve auth according to requested method.
    - auto: resource principals -> instance principals -> config
    - config: ~/.oci/config (profile required if multiple)
    - instance: Instance Principals
    - resource: Resource Principals
    - security_token: session profile in ~/.oci/config (handled like config)
    """
    _require_oci()
    method = (method or "auto").lower()

    # Helpers to build contexts
    def ctx_from_config() -> AuthContext:
        try:
            cfg = oci.config.from_file(profile_name=profile)  # type: ignore[attr-defined]
        except Exception as e:
            mapped = map_oci_error(e, "OCI SDK error while loading config profile")
            if mapped:
                raise mapped from e
            raise AuthError(f"Failed to load OCI config profile: {e}") from e
        ten = tenancy_ocid or cfg.get("tenancy")
        return AuthContext(method="config", config_dict=cfg, signer=None, profile=profile, tenancy_ocid=ten)

    def ctx_from_ip() -> AuthContext:
        try:
            signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()  # type: ignore[attr-defined]
        except Exception as e:
            mapped = map_oci_error(e, "OCI SDK error while resolving instance principals")
            if mapped:
                raise mapped from e
            raise AuthError(f"Failed to resolve instance principals: {e}") from e
        # For signer-based clients, pass {"region": "..."} per-client on creation
        return AuthContext(method="instance", config_dict=None, signer=signer, profile=None, tenancy_ocid=tenancy_ocid)

    def ctx_from_rp() -> AuthContext:
        try:
            signer = oci.auth.signers.get_resource_principals_signer()  # type: ignore[attr-defined]
        except Exception as e:
            mapped = map_oci_error(e, "OCI SDK error while resolving resource principals")
            if mapped:
                raise mapped from e
            raise AuthError(f"Failed to resolve resource principals: {e}") from e
        return AuthContext(method="resource", config_dict=None, signer=signer, profile=None, tenancy_ocid=tenancy_ocid)

    if method == "config" or method == "security_token":
        return ctx_from_config()
    if method == "instance":
        return ctx_from_ip()
    if method == "resource":
        return ctx_from_rp()
    if method != "auto":
        raise AuthError(f"Unsupported auth method: {method}")

    # auto resolution order: RP -> IP -> config
    # RP
    try:
        return ctx_from_rp()
    except Exception:
        pass
    # IP
    try:
        return ctx_from_ip()
    except Exception:
        pass
    # Config
    try:
        return ctx_from_config()
    except OCIClientError:
        raise
    except Exception as e:
        raise AuthError(
            "Failed to resolve auth in 'auto' mode. Tried resource principals, instance principals, then config.\n"
            f"Last error: {e}"
        ) from e


def get_tenancy_ocid(ctx: AuthContext) -> Optional[str]:
    """
    Return tenancy OCID if known. For config-file auth, it is read from config.
    For signer-based auth, caller may need to provide it via CLI flag or config file.
    """
    if ctx.tenancy_ocid:
        return ctx.tenancy_ocid
    if ctx.config_dict:
        return ctx.config_dict.get("tenancy")  # type: ignore[return-value]
    return None


def make_client(client_cls: Any, ctx: AuthContext, region: Optional[str] = None) -> Any:
    """
    Construct an OCI SDK client of type client_cls using the provided AuthContext.
    When using signer-based auth, a minimal config dict with region must be provided.
    Optionally sets the client's base region.
    """
    _require_oci()
    retry = getattr(oci.retry, "DEFAULT_RETRY_STRATEGY", None)  # type: ignore[attr-defined]
    kwargs: Dict[str, Any] = {}
    if retry is not None:
        kwargs["retry_strategy"] = retry

    if ctx.config_dict is not None:
        cfg = dict(ctx.config_dict)
        if region:
            cfg["region"] = region
        client = client_cls(cfg, **kwargs)
    elif ctx.signer is not None:
        cfg = {"region": region or _detect_region() or "us-ashburn-1"}
        client = client_cls(cfg, signer=ctx.signer, **kwargs)
    else:  # pragma: no cover - defensive
        raise AuthError("Invalid AuthContext: neither config_dict nor signer present")

    # Some clients expose set_region; set if region provided
    if region and hasattr(client, "base_client") and hasattr(client.base_client, "set_region"):
        try:
            client.base_client.set_region(region)
        except Exception:
            # not fatal; SDK usually respects config['region']
            pass
    return client
