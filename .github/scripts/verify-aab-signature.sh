#!/usr/bin/env bash
# Verify that a release AAB is signed, that the signature is valid, and that it was signed with the configured
# upload key. Used by .github/workflows/build-aab.yml.
#
# Inputs (environment):
#   AAB                        path to the bundle
#   ANDROID_KEYSTORE_FILE      upload keystore (.jks)
#   ANDROID_KEYSTORE_PASSWORD  keystore password — read by keytool via -storepass:env, never on a command line
#   ANDROID_KEY_ALIAS          alias of the upload key
#
# Deliberately pipeline-free: with `set -o pipefail`, `echo "$x" | grep -q …` or `keytool … | grep -m1 …` can fail
# with SIGPIPE ("Broken pipe") when grep exits early, although the text was found. Outputs are captured into
# variables and examined with bash pattern matching and here-string read loops.
set -euo pipefail

fail() { echo "::error::$*"; exit 1; }

: "${AAB:?AAB is not set}"
: "${ANDROID_KEYSTORE_FILE:?ANDROID_KEYSTORE_FILE is not set}"
: "${ANDROID_KEY_ALIAS:?ANDROID_KEY_ALIAS is not set}"
: "${ANDROID_KEYSTORE_PASSWORD:?ANDROID_KEYSTORE_PASSWORD is not set}"
[ -s "$AAB" ] || fail "AAB not found at $AAB"
[ -s "$ANDROID_KEYSTORE_FILE" ] || fail "Upload keystore not found at $ANDROID_KEYSTORE_FILE"

# First "SHA256:" fingerprint in the text, upper-cased with whitespace removed; empty if there is none.
first_sha256() {
  local line fp=""
  while IFS= read -r line; do
    case "$line" in
      *SHA256:*)
        fp="${line#*SHA256:}"
        fp="${fp//[[:space:]]/}"
        break
        ;;
    esac
  done <<< "$1"
  printf '%s' "${fp^^}"
}

# 1. Signed, and the signature verifies. jarsigner exits non-zero for some warnings, so its status alone is not used.
VERIFY_OUT="$(jarsigner -verify "$AAB" 2>&1)" || true
VERIFY_LC="${VERIFY_OUT,,}"
if [[ "$VERIFY_LC" == *"jar is unsigned"* ]] || [[ "$VERIFY_LC" == *"no manifest"* ]]; then
  fail "The AAB is unsigned."
fi
if [[ $'\n'"$VERIFY_OUT"$'\n' != *$'\n'"jar verified."$'\n'* ]]; then
  echo "jarsigner output (first lines):"
  n=0
  while IFS= read -r line && [ $n -lt 20 ]; do echo "  $line"; n=$((n + 1)); done <<< "$VERIFY_OUT"
  fail "jarsigner could not verify the AAB signature."
fi
echo "jarsigner: jar verified."
if [[ "$VERIFY_LC" == *"self-signed"* || "$VERIFY_LC" == *"pkix"* || "$VERIFY_LC" == *"certificate chain"* ]]; then
  echo "Note: self-signed / certificate-chain warnings are expected for an upload key; the fingerprint check below decides."
fi

# 2. SHA-256 of the certificate that signed the AAB.
AAB_CERT_OUT="$(keytool -printcert -jarfile "$AAB" 2>&1)" || fail "keytool could not read the AAB's signing certificate."
AAB_SHA="$(first_sha256 "$AAB_CERT_OUT")"

# 3. SHA-256 of the configured upload key's certificate (password from the environment, not the command line).
KS_OUT="$(keytool -list -v -keystore "$ANDROID_KEYSTORE_FILE" -alias "$ANDROID_KEY_ALIAS" \
  -storepass:env ANDROID_KEYSTORE_PASSWORD 2>&1)" \
  || fail "Could not read the upload certificate from the keystore (wrong alias or password?)."
KS_SHA="$(first_sha256 "$KS_OUT")"

[ -n "$AAB_SHA" ] || fail "Could not read the signing certificate fingerprint from the AAB."
[ -n "$KS_SHA" ] || fail "Could not read the upload certificate fingerprint from the keystore."

echo "AAB signing certificate SHA-256:     $AAB_SHA"
echo "Upload keystore certificate SHA-256: $KS_SHA"
[ "$AAB_SHA" = "$KS_SHA" ] || fail "AAB is not signed with the configured upload key (fingerprints differ)."
echo "Fingerprints match: the AAB is signed with the upload key."

if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  {
    echo "### AAB signature verified"
    echo "- Certificate SHA-256: \`$AAB_SHA\`"
    echo "- Register this as the upload key fingerprint in Play Console if asked."
  } >> "$GITHUB_STEP_SUMMARY"
fi
