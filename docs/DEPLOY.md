# Deploy

`UnixGram Changelog` is deployed as a separate Dockerized systemd service and does not share state with `unixgram-history-bot`.

## VPS layout

```text
/etc/unixgram-changelog.env
/opt/unixgram-changelog/releases/<git-sha>
/opt/unixgram-changelog/current -> active release
/var/lib/unixgram-changelog/changelog.db
```

## GitHub to VPS flow

1. `main` receives a push.
2. CI runs `ruff`, `mypy`, `pytest`.
3. GitHub Actions uploads the current tree to the VPS release directory.
4. `deploy/deploy.sh <git-sha>` builds `unixgram-changelog:<git-sha>` and retags `unixgram-changelog:local`.
5. systemd restarts `unixgram-changelog`.
6. `deploy/smoke.py` verifies bot token, channel access and SQLite quick check.
7. On failure the script restores the previous image tag and restarts the previous release.

## Required GitHub secrets

- `VPS_HOST`
- `VPS_PORT`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_KNOWN_HOSTS`

The bot token stays on the server in `/etc/unixgram-changelog.env`. Do not copy it to GitHub Secrets unless you need a different release model.
