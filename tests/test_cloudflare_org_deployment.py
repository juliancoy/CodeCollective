from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_org_deployment_applies_migrations_and_checks_a_database_route():
    workflow = (ROOT / ".github/workflows/cloudflare-deploy.yml").read_text()
    deploy_script = (ROOT / "deploy.sh").read_text()

    assert "./deploy.sh --component org --skip-org-migrations" not in workflow
    assert "./deploy.sh --component org" in workflow
    assert 'wrangler d1 migrations apply "$ORG_D1_DATABASE_NAME" --remote' in deploy_script
    assert "/api/network/orgs/public?limit=1" in deploy_script
