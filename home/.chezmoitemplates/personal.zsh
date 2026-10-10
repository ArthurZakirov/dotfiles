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
  if _bws_env="$(bws secret list --output env)"; then
    # BWS emits assignments without export; make them visible to child processes.
    if [[ -o allexport ]]; then
      eval "$_bws_env"
    else
      setopt allexport
      eval "$_bws_env"
      unsetopt allexport
    fi
  else
    print -u2 'Bitwarden secrets could not be loaded; check authentication.'
  fi
  unset _bws_env
fi
