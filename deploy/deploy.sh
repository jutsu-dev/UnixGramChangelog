#!/usr/bin/env bash
set -euo pipefail

exec 9>/run/lock/unixgram-changelog-deploy.lock
flock -w 900 9

service_name="unixgram-changelog"
app_root="/opt/unixgram-changelog"
releases_dir="$app_root/releases"
current_link="$app_root/current"
env_file="/etc/unixgram-changelog.env"
data_dir="/var/lib/unixgram-changelog"
rollback_dir="/var/backups/unixgram-changelog"
release_id="${1:?release id is required}"
release_path="$releases_dir/$release_id"
timestamp="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$releases_dir" "$rollback_dir"
install -d -m 0755 -o 10001 -g 10001 "$data_dir"

if [[ ! -f "$env_file" ]]; then
  echo "missing env file: $env_file" >&2
  exit 1
fi

env_owner="$(stat -c '%u' "$env_file")"
env_mode="$(stat -c '%a' "$env_file")"
if [[ "$env_owner" != "0" ]]; then
  echo "env file must be owned by root: $env_file" >&2
  exit 1
fi
if [[ "$env_mode" != "600" && "$env_mode" != "400" ]]; then
  echo "env file must use 600 or 400 permissions: $env_file" >&2
  exit 1
fi

if [[ ! -d "$release_path" ]]; then
  echo "missing release directory: $release_path" >&2
  exit 1
fi

previous_release=""
if [[ -L "$current_link" ]]; then
  previous_release="$(readlink -f "$current_link")"
fi

previous_image_id=""
if docker image inspect unixgram-changelog:local >/dev/null 2>&1; then
  previous_image_id="$(docker image inspect unixgram-changelog:local --format '{{.Id}}')"
  docker tag "$previous_image_id" "unixgram-changelog:rollback-$timestamp"
fi

if compgen -G "$data_dir/changelog.db*" >/dev/null; then
  cp -a "$data_dir"/changelog.db* "$rollback_dir"/
fi

rollback() {
  if [[ -n "$previous_image_id" ]]; then
    docker tag "$previous_image_id" unixgram-changelog:local
  fi
  if [[ -n "$previous_release" && -d "$previous_release" ]]; then
    ln -sfn "$previous_release" "$current_link"
  fi
  systemctl restart "$service_name" || true
}

trap rollback ERR

ln -sfn "$release_path" "$current_link"
docker build -t "unixgram-changelog:$release_id" -t unixgram-changelog:local "$release_path"
install -m 0644 "$release_path/deploy/systemd/$service_name.service" "/etc/systemd/system/$service_name.service"
systemctl daemon-reload
systemctl enable "$service_name" >/dev/null
systemctl restart "$service_name"
sleep 5
systemctl is-active --quiet "$service_name"
docker run --rm --env-file "$env_file" -v "$data_dir:/app/data" unixgram-changelog:local python /app/deploy/smoke.py

trap - ERR
echo "release_ok=$release_id"
