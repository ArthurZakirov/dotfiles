#!/bin/bash
# Snapshot destination-side managed files before an apply can replace them.
# Never follow a managed symlink into a different tree.

snapshot_existing_managed() {
  local config="$1" source="$2" working_tree="$3" destination="$4"
  local scratch backup_root backup_dir target relative copied=0
  scratch="$(mktemp -d)" || return 1
  # The outer chezmoi apply holds its own state lock. A nested status or
  # managed invocation must use a separate scratch state to avoid deadlock.
  local -a cli=(chezmoi --config "$config" --source "$source"
    --working-tree "$working_tree" --destination "$destination"
    --persistent-state "$scratch/state")
  if ! "${cli[@]}" status --exclude scripts > "$scratch/status"; then
    rm -rf "$scratch"
    echo 'Pre-apply backup: unable to assess current managed state.' >&2
    return 1
  fi
  if [[ ! -s "$scratch/status" ]]; then
    rm -rf "$scratch"
    return 0
  fi
  if ! "${cli[@]}" managed --include files,symlinks --path-style absolute \
       --nul-path-separator > "$scratch/paths"; then
    rm -rf "$scratch"
    echo 'Pre-apply backup: unable to enumerate managed files.' >&2
    return 1
  fi

  umask 077
  backup_root="$destination/Library/Application Support/dotfiles/backups"
  while IFS= read -r -d '' target; do
    case "$target" in
      "$destination"/*) relative="${target#"$destination"/}" ;;
      *) printf 'Pre-apply backup: target outside destination: %s\n' "$target" >&2
         rm -rf "$scratch"; return 1 ;;
    esac
    if [[ -f "$target" || -L "$target" ]]; then
      if [[ -z "${backup_dir:-}" ]]; then
        mkdir -p "$backup_root"
        backup_dir="$(mktemp -d "$backup_root/apply.XXXXXXXX")" || return 1
        cp "$scratch/status" "$backup_dir/chezmoi-status.txt"
      fi
      mkdir -p "$backup_dir/files/$(dirname "$relative")"
      if ! cp -pP "$target" "$backup_dir/files/$relative"; then
        printf 'Pre-apply backup failed; stopping before managed files change: %s\n' "$target" >&2
        rm -rf "$scratch"
        return 1
      fi
      copied=$((copied + 1))
    fi
  done < "$scratch/paths"
  rm -rf "$scratch"
  if ((copied > 0)); then
    printf 'Pre-apply backup: saved %d existing managed entries at %s\n' "$copied" "$backup_dir"
  fi
}
