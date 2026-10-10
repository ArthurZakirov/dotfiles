# Personal Mac only. Credentials stay in Keychain, outside this repository.
export LANGSMITH_TRACING=true
export LANGSMITH_PROJECT="codex"
bws() {
  local access_token
  access_token="$(security find-generic-password -a {{ .bwsAccount | quote }} -s BWS_ACCESS_TOKEN -w)" || return
  BWS_ACCESS_TOKEN="$access_token" command bws "$@"
}
# A new Mac works before secret provisioning; only load after the entry exists.
if command -v bws >/dev/null 2>&1 && security find-generic-password -a {{ .bwsAccount | quote }} -s BWS_ACCESS_TOKEN >/dev/null 2>&1; then
  if _bws_env="$(bws secret list --output env)"; then
    eval "$_bws_env"
  else
    print -u2 'Bitwarden secrets could not be loaded; check authentication.'
  fi
  unset _bws_env
fi
