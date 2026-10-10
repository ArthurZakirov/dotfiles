#!/bin/bash
# Common assertions shared by shell unit and integration tests.
fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  [[ "$1" == *"$2"* ]] || fail "expected message to contain '$2', got '$1'"
}

assert_file_exists() {
  [[ -f "$1" ]] || fail "expected file: $1"
}

assert_directory_exists() {
  [[ -d "$1" ]] || fail "expected directory: $1"
}

assert_file_contains() {
  grep -Fq -- "$2" "$1" || fail "expected '$1' to contain '$2'"
}

assert_file_excludes() {
  if grep -Fq -- "$2" "$1"; then
    fail "expected '$1' to exclude '$2'"
  fi
}
