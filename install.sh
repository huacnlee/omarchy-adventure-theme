#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
destination=${XDG_CONFIG_HOME:-${HOME}/.config}/omarchy/themes
theme_files=(
  backgrounds
  btop.theme
  chromium.theme
  colors.toml
  ghostty.conf
  hyprland.lua
  icons.theme
  preview.png
  preview-unlock.png
  shell.bar.toml
  shell.hyprland.toml
  unlock.png
  zed.json
)

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
rm -rf -- "$destination/adventure"
mkdir -p -- "$destination/adventure"
for file in "${theme_files[@]}"; do
  cp -R -- "$repo_dir/$file" "$destination/adventure/$file"
done
echo "Installed adventure"

if command -v omarchy >/dev/null 2>&1; then
  omarchy theme set adventure
  echo "Applied adventure"
else
  echo "Omarchy is not installed. Activate later with: omarchy theme set adventure"
fi
