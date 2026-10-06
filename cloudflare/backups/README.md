# Daily ecosystem backups

The installed user timer runs at 03:15 America/New_York (up to five minutes of jitter), catches up missed runs when the user's systemd manager starts, and invokes `scripts/backup-ecosystem.py`. It requires this machine to be running and a valid Wrangler session. It is not an always-on cloud scheduler.

Each run exports the production `org` D1 database, restores the SQL into a disposable SQLite database, runs `integrity_check`, checks the organization/event/support/ledger tables, and packages the public ecosystem JSON plus CodeCollective event archives. It also discovers running organization-worker Docker deployments and uses SQLite's online backup API inside each container to take consistent local database copies. Temporary restore databases are deleted after completion. Archives and manifests are private (umask 077), with an SHA-256 digest and row counts. Uploaded bundles are downloaded again and hash-checked before recording success. Bundles are retained locally and uploaded to the private `codecollective-ecosystem-backups` R2 bucket; no public route is configured. Retention is indefinite until explicitly changed.

D1 export temporarily blocks database queries; the scheduled run is placed overnight. An export failure, restore failure, local snapshot failure or upload failure makes the service fail. `~/.local/share/codecollective-backups/latest-success.json` records the last complete upload. Failed uploads leave the local archive for recovery. Signed export-download links are withheld from service output.

Inspect:

```sh
systemctl --user list-timers codecollective-ecosystem-backup.timer
journalctl --user -u codecollective-ecosystem-backup.service
cat ~/.local/share/codecollective-backups/latest-success.json
```

Restore into a disposable SQLite database first; never run the SQL against production without an explicit restore request. D1 Time Travel is an additional managed recovery mechanism, separate from these exports.
