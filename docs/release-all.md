# Release all workspace repositories

The workspace `push-all.sh` accompanies `pull-all.sh`. Its tracked implementation
is `scripts/push-all.sh` and `scripts/push_all.py` in CodeCollective. From
CodeCollective, install the workspace entry point with:

```bash
ln -s CodeCollective/scripts/push-all.sh ../push-all.sh
```

From the Organization workspace:

```bash
./push-all.sh --dry-run
./push-all.sh --message 'Release reviewed workspace changes'
```

An optional directory selects another workspace. Initialized submodules are
processed before parents. The script fetches, commits changes, merges upstream
without rewriting history, validates applications, pushes, then deploys changed
applications. Conflicts and failed checks stop execution and retain local commits.
A workspace lock prevents overlapping releases.

PIdP releases separately. OrgPortal chat and organization Workers release before
the shared CodeCollective frontend. Worker production variables are retained.
Pending D1 migrations receive a recovery export before application. MedTech and
LifeTech use their own deployment commands. Repositories without a configured
deployment are pushed only; clean applications are not redeployed.

Use `--skip-deploy` for validation and Git operations only. Use `--deploy-all` to
retry all configured deployments after a failure following a successful push.
Command logs and commit manifests reside in the restricted workspace
`.local-releases` directory. Recovery exports must not be committed and should
be removed within seven days under the service retention policy.
Production verification is read-only and unauthenticated; authenticated fixtures
belong in the local Docker deployment.

CLI verification: `python3 -m unittest discover -s CodeCollective/tests`.
