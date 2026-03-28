#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  OCI Pricing Agent — Environment Setup
#  Reads ~/.oci/config [DEFAULT] and writes .env automatically.
#  No OCI CLI required — just the config file and your .pem key.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
OCI_CONFIG="${OCI_CLI_CONFIG_FILE:-$HOME/.oci/config}"
OCI_PROFILE="${OCI_CLI_PROFILE:-DEFAULT}"
GENAI_CONFIG_FILE="${OCI_PRICING_GENAI_CONFIG:-${OCI_INV_GENAI_CONFIG:-$HOME/.config/oci-inv/genai.yaml}}"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

echo ""
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  OCI Pricing Agent — Environment Setup${RESET}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""

# ── 1. Verify ~/.oci/config exists ────────────────────────────────────────────
if [[ ! -f "$OCI_CONFIG" ]]; then
  echo -e "${RED}✗ OCI config not found at: $OCI_CONFIG${RESET}"
  echo ""
  echo "  Create it manually at ~/.oci/config with this format:"
  echo ""
  echo "    [DEFAULT]"
  echo "    user=ocid1.user.oc1..xxx"
  echo "    tenancy=ocid1.tenancy.oc1..xxx"
  echo "    fingerprint=xx:xx:xx:..."
  echo "    region=us-chicago-1"
  echo "    key_file=~/.oci/oci_api_key.pem"
  echo ""
  exit 1
fi

echo -e "  Reading ${CYAN}$OCI_CONFIG${RESET} [${CYAN}$OCI_PROFILE${RESET}]"
echo ""

# ── 2. Parse the profile (handles spaces around = sign) ──────────────────────
parse_field() {
  local file="$1" profile="$2" key="$3"
  awk -v prof="[$profile]" -v k="$key" '
    /^\[/ { in_section = ($0 == prof); next }
    in_section && $0 ~ "^[[:space:]]*" k "[[:space:]]*=" {
      sub(/^[^=]*=[[:space:]]*/, "")
      gsub(/[[:space:]]*$/, "")
      print; exit
    }
  ' "$file"
}

OCI_USER_VAL=$(parse_field        "$OCI_CONFIG" "$OCI_PROFILE" "user")
OCI_TENANCY_VAL=$(parse_field     "$OCI_CONFIG" "$OCI_PROFILE" "tenancy")
OCI_FINGERPRINT_VAL=$(parse_field "$OCI_CONFIG" "$OCI_PROFILE" "fingerprint")
OCI_REGION_VAL=$(parse_field      "$OCI_CONFIG" "$OCI_PROFILE" "region")
OCI_KEY_FILE_RAW=$(parse_field    "$OCI_CONFIG" "$OCI_PROFILE" "key_file")

# Expand ~ in key_file path
OCI_KEY_FILE_VAL="${OCI_KEY_FILE_RAW/#\~/$HOME}"

# ── 3. Validate required fields ───────────────────────────────────────────────
MISSING=()
[[ -z "$OCI_USER_VAL"        ]] && MISSING+=("user")
[[ -z "$OCI_TENANCY_VAL"     ]] && MISSING+=("tenancy")
[[ -z "$OCI_FINGERPRINT_VAL" ]] && MISSING+=("fingerprint")
[[ -z "$OCI_REGION_VAL"      ]] && MISSING+=("region")
[[ -z "$OCI_KEY_FILE_RAW"    ]] && MISSING+=("key_file")

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo -e "${RED}✗ Missing fields in [$OCI_PROFILE]: ${MISSING[*]}${RESET}"
  exit 1
fi

if [[ ! -f "$OCI_KEY_FILE_VAL" ]]; then
  echo -e "${RED}✗ Private key file not found: $OCI_KEY_FILE_VAL${RESET}"
  exit 1
fi

if grep -q "BEGIN ENCRYPTED PRIVATE KEY" "$OCI_KEY_FILE_VAL"; then
  ALT_KEY_FILE=""
  if [[ "$OCI_KEY_FILE_VAL" == *".pem" ]]; then
    ALT_KEY_FILE="${OCI_KEY_FILE_VAL%.pem}_unencrypted.pem"
  fi
  if [[ -n "$ALT_KEY_FILE" && -f "$ALT_KEY_FILE" ]]; then
    echo -e "  ${YELLOW}⚠ Encrypted private key detected in $OCI_KEY_FILE_VAL${RESET}"
    echo -e "  ${YELLOW}  Using unencrypted key file instead: $ALT_KEY_FILE${RESET}"
    OCI_KEY_FILE_VAL="$ALT_KEY_FILE"
  else
    echo -e "${RED}✗ Encrypted private key detected: $OCI_KEY_FILE_VAL${RESET}"
    echo -e "${RED}  Provide an unencrypted API signing key or create a sibling *_unencrypted.pem file.${RESET}"
    exit 1
  fi
fi

# ── 4. OCI GenAI region resolution ───────────────────────────────────────────
# OCI GenAI is NOT available in all regions.
# If the home region doesn't have GenAI, use us-chicago-1 as the inference
# endpoint while keeping the home region for identity/auth.
#
# Regions with OCI GenAI (as of early 2025):
GENAI_REGIONS=("us-chicago-1" "us-ashburn-1" "eu-frankfurt-1" "ap-osaka-1" "ap-sydney-1" "sa-saopaulo-1")

GENAI_REGION="$OCI_REGION_VAL"

has_genai=false
for r in "${GENAI_REGIONS[@]}"; do
  [[ "$r" == "$OCI_REGION_VAL" ]] && has_genai=true && break
done

if [[ "$has_genai" == false ]]; then
  GENAI_REGION="us-chicago-1"
  echo -e "  ${YELLOW}⚠ Your home region ($OCI_REGION_VAL) does not have OCI GenAI.${RESET}"
  echo -e "  ${YELLOW}  Using inference endpoint: $GENAI_REGION${RESET}"
  echo -e "  ${YELLOW}  Auth still uses your tenancy credentials.${RESET}"
  echo ""
fi

# ── 5. Private key transport for Docker/.env ──────────────────────────────────
OCI_PRIVATE_KEY_INLINE=$(awk '{printf "%s\\n", $0}' "$OCI_KEY_FILE_VAL")
OCI_PRIVATE_KEY_B64=$(base64 < "$OCI_KEY_FILE_VAL" | tr -d '\n')

# ── 6. Preserve COMPARTMENT and MODEL from existing .env ─────────────────────
COMPARTMENT=""
GENAI_MODEL=""
GENAI_COMPARTMENT=""
GENAI_ENDPOINT=""
GENAI_PROFILE_VAL=""

if [[ -f "$ENV_FILE" ]]; then
  COMPARTMENT=$(grep -E '^OCI_COMPARTMENT=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)
  GENAI_MODEL=$(grep  -E '^OCI_GENAI_MODEL='  "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)
  GENAI_COMPARTMENT=$(grep -E '^OCI_GENAI_COMPARTMENT=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)
  GENAI_ENDPOINT=$(grep -E '^OCI_GENAI_ENDPOINT=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)
  GENAI_PROFILE_VAL=$(grep -E '^OCI_GENAI_PROFILE=' "$ENV_FILE" 2>/dev/null | cut -d'=' -f2- | tr -d '"' || true)
fi

[[ -z "$COMPARTMENT" ]] && COMPARTMENT="$OCI_TENANCY_VAL"

parse_yaml_field() {
  local file="$1" key="$2"
  [[ -f "$file" ]] || return 0
  awk -F':' -v k="$key" '
    $0 ~ "^[[:space:]]*" k ":[[:space:]]*" {
      sub(/^[^:]*:[[:space:]]*/, "", $0)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
      gsub(/^["'\'']|["'\'']$/, "", $0)
      print
      exit
    }
  ' "$file"
}

if [[ -f "$GENAI_CONFIG_FILE" ]]; then
  YAML_GENAI_PROFILE=$(parse_yaml_field "$GENAI_CONFIG_FILE" "oci_profile")
  YAML_GENAI_COMPARTMENT=$(parse_yaml_field "$GENAI_CONFIG_FILE" "compartment_id")
  YAML_GENAI_ENDPOINT=$(parse_yaml_field "$GENAI_CONFIG_FILE" "endpoint")
  YAML_GENAI_MODEL=$(parse_yaml_field "$GENAI_CONFIG_FILE" "base_model_id")

  [[ -n "$YAML_GENAI_PROFILE" ]] && GENAI_PROFILE_VAL="$YAML_GENAI_PROFILE"
  [[ -n "$YAML_GENAI_COMPARTMENT" ]] && GENAI_COMPARTMENT="$YAML_GENAI_COMPARTMENT"
  [[ -n "$YAML_GENAI_ENDPOINT" ]] && GENAI_ENDPOINT="$YAML_GENAI_ENDPOINT"
  [[ -n "$YAML_GENAI_MODEL" ]] && GENAI_MODEL="$YAML_GENAI_MODEL"
fi

[[ -z "$GENAI_PROFILE_VAL" ]] && GENAI_PROFILE_VAL="$OCI_PROFILE"
[[ -z "$GENAI_COMPARTMENT" ]] && GENAI_COMPARTMENT="$COMPARTMENT"
[[ -z "$GENAI_ENDPOINT" ]] && GENAI_ENDPOINT="https://inference.generativeai.$GENAI_REGION.oci.oraclecloud.com"

# Pick default model OCID based on resolved GenAI region
if [[ -z "$GENAI_MODEL" ]]; then
  case "$GENAI_REGION" in
    "us-chicago-1")
      GENAI_MODEL="ocid1.generativeaimodel.oc1.us-chicago-1.amaaaaaask7dceyafjcwpf75fmqoismvwlmzjbprdzzljhfcrirozftbrjoq" ;;
    "us-ashburn-1")
      GENAI_MODEL="ocid1.generativeaimodel.oc1.iad.amaaaaaask7dceyafjcwpf75fmqoismvwlmzjbprdzzljhfcrirozftbrjoq" ;;
    "eu-frankfurt-1")
      GENAI_MODEL="ocid1.generativeaimodel.oc1.eu-frankfurt-1.amaaaaaask7dceyafjcwpf75fmqoismvwlmzjbprdzzljhfcrirozftbrjoq" ;;
    *)
      GENAI_MODEL="ocid1.generativeaimodel.oc1.us-chicago-1.amaaaaaask7dceyafjcwpf75fmqoismvwlmzjbprdzzljhfcrirozftbrjoq" ;;
  esac
fi

# ── 7. Write .env ──────────────────────────────────────────────────────────────
cat > "$ENV_FILE" << ENVEOF
# ─────────────────────────────────────────────────────────────────────────────
#  OCI Pricing Agent — Auto-generated by setup-env.sh
#  Source profile : $OCI_CONFIG [$OCI_PROFILE]
#  Generated      : $(date)
#  DO NOT EDIT — re-run setup-env.sh to refresh.
# ─────────────────────────────────────────────────────────────────────────────

# ── OCI Identity (from ~/.oci/config) ─────────────────────────────────────────
OCI_USER=$OCI_USER_VAL
OCI_TENANCY=$OCI_TENANCY_VAL
OCI_FINGERPRINT=$OCI_FINGERPRINT_VAL

# Home region (identity/auth)
OCI_HOME_REGION=$OCI_REGION_VAL

# GenAI inference region (may differ from home region)
OCI_REGION=$GENAI_REGION

# ── Compartment ───────────────────────────────────────────────────────────────
OCI_COMPARTMENT=$COMPARTMENT
OCI_GENAI_COMPARTMENT=$GENAI_COMPARTMENT
OCI_GENAI_ENDPOINT=$GENAI_ENDPOINT
OCI_GENAI_PROFILE=$GENAI_PROFILE_VAL

# ── Private Key ────────────────────────────────────────────────────────────────
# OCI_PRIVATE_KEY is kept for backward compatibility in local runs.
# OCI_PRIVATE_KEY_B64 is Docker-safe and avoids multiline env parsing issues.
OCI_PRIVATE_KEY=$OCI_PRIVATE_KEY_INLINE
OCI_PRIVATE_KEY_B64=$OCI_PRIVATE_KEY_B64
OCI_KEY_FILE=

# ── GenAI Model OCID ──────────────────────────────────────────────────────────
OCI_GENAI_MODEL=$GENAI_MODEL
ENVEOF

# ── 8. Summary ────────────────────────────────────────────────────────────────
echo -e "  ${GREEN}✓ user         ${RESET}$OCI_USER_VAL"
echo -e "  ${GREEN}✓ tenancy      ${RESET}$OCI_TENANCY_VAL"
echo -e "  ${GREEN}✓ fingerprint  ${RESET}$OCI_FINGERPRINT_VAL"
echo -e "  ${GREEN}✓ home region  ${RESET}$OCI_REGION_VAL"
echo -e "  ${GREEN}✓ genai region ${RESET}$GENAI_REGION"
echo -e "  ${GREEN}✓ key file     ${RESET}$OCI_KEY_FILE_VAL ($(wc -c < "$OCI_KEY_FILE_VAL") bytes)"
echo -e "  ${GREEN}✓ private key  ${RESET}inlined into .env"
echo ""
echo -e "  ${YELLOW}OCI_COMPARTMENT ${RESET}: $COMPARTMENT"
echo -e "  ${YELLOW}OCI_GENAI_COMPARTMENT ${RESET}: $GENAI_COMPARTMENT"
echo -e "  ${YELLOW}OCI_GENAI_ENDPOINT ${RESET}: $GENAI_ENDPOINT"
echo -e "  ${YELLOW}OCI_GENAI_PROFILE ${RESET}: $GENAI_PROFILE_VAL"
echo -e "  ${YELLOW}OCI_GENAI_MODEL ${RESET}: $GENAI_MODEL"
echo ""
echo -e "  ${GREEN}✓ .env written${RESET} → $ENV_FILE"
echo ""

# ── 9. Optionally start Docker ────────────────────────────────────────────────
if command -v docker &>/dev/null && [[ -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
  read -rp "  Start the agent now? [y/N] " ANSWER
  if [[ "$ANSWER" =~ ^[Yy]$ ]]; then
    echo ""
    cd "$SCRIPT_DIR"
    docker compose up -d --build
    echo ""
    echo -e "${GREEN}✓ Agent running at http://localhost:8742${RESET}"
    echo ""
  else
    echo -e "  Run when ready: ${CYAN}docker compose up -d --build${RESET}"
    echo ""
  fi
fi
