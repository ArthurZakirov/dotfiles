# Personal Mac only. Credentials stay in Keychain, outside this repository.
# CONFIG ENV VARIABLES (PERSONAL MAC ONLY)
# ------------------------------------------------------
export LANGSMITH_TRACING=true
export LANGSMITH_PROJECT="codex"

# API KEYS (PERSONAL MAC ONLY)
# ------------------------------------------------------
bws() {
  local access_token
  access_token="$(security find-generic-password -a {{ .bwsAccount | quote }} -s BWS_ACCESS_TOKEN -w)" || return
  BWS_ACCESS_TOKEN="$access_token" command bws "$@"
}
# A new Mac works before secret provisioning; only load after the entry exists.
if command -v bws >/dev/null 2>&1 && security find-generic-password -a {{ .bwsAccount | quote }} -s BWS_ACCESS_TOKEN >/dev/null 2>&1; then
  if _bws_json="$(bws secret list --output json)"; then
    # Interpret secret values as data, never shell code (including $(...) values).
    # NUL-delimited pairs preserve spaces, quotes, and newlines.
    while IFS= read -r -d '' _bws_key && IFS= read -r -d '' _bws_value; do
      typeset -gx "$_bws_key=$_bws_value"
    done < <(python3 {{ printf "%s/src/bws_env.py" .chezmoi.workingTree | quote }} <<< "$_bws_json")
    unset _bws_key _bws_value
  else
    print -u2 'Bitwarden secrets could not be loaded; check authentication.'
  fi
  unset _bws_json
fi
