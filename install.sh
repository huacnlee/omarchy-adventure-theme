#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
destination=${XDG_CONFIG_HOME:-${HOME}/.config}/omarchy/themes
themes=(adventure adventure-time)

usage() {
  echo "Usage: ./install.sh [--destination DIR]"
}

while (($#)); do
  case "$1" in
    --destination)
      if (($# < 2)); then
        echo "Error: --destination requires a directory." >&2
        exit 2
      fi
      destination=$2
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p -- "$destination"
for theme in "${themes[@]}"; do
  rm -rf -- "$destination/$theme"
  cp -R -- "$repo_dir/$theme" "$destination/$theme"
  echo "Installed $theme"
done

echo "Choose a variant with: omarchy theme set adventure"
echo "Or:                    omarchy theme set adventure-time"
