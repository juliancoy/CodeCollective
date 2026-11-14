
## 2026-11-09 — WhatsApp invite replacement

- Command: `git diff --check` — PASS.
- Command: `git grep -n -I -e JFlI9aRvNaGCTU2lOFXpOt -e J5P9iAcOyFKEw7k8zVx1X7` — PASS: three replacement links in two files; no old invite remains in tracked files.
- SHA-256 `js/reusableComponents.js`: `88ae4d1fb73b8da6b0c073ab7734739b4bf619e43c24fee1cb6ddae5ad709eed`.
- SHA-256 `personnel/juliancoy.html`: `1c8daf5f323dc1f2ddb26146f45b96a21eefa84d036ed22645205a67882d0ad7`.
- Static checks only; invite acceptance was not tested in WhatsApp.

## 2026-11-09 — Production publication

- Source base: `ce92f1d5445f14a250c0a3bbda76da2f12bfa8e0` plus invite changes fingerprinted above; r8-rowhome `52a73c2314d7ddbbafad698aafa46d6f072c7d12`.
- Command: `./cloudflare/scripts/build_cloudflare_site.sh` — PASS.
- Command: `npx wrangler deploy --dry-run` (Wrangler 4.120.1) — PASS.
- Built asset invite assertions — PASS: replacement present, old invite absent in both files.
- SHA-256 `cloudflare/worker.js`: `296f1baff71b4f67bb827774828ebda89f29a3f42cacc96cf29f805d9a521ab9`.
- SHA-256 `wrangler.toml`: `e30316cc74315a9bbbd752405c35279744d03b3f02a68f101cd750f56930ac97`.
- SHA-256 `.cloudflare/site/js/reusableComponents.js`: `88ae4d1fb73b8da6b0c073ab7734739b4bf619e43c24fee1cb6ddae5ad709eed`.
- SHA-256 `.cloudflare/site/personnel/juliancoy.html`: `f299d36e668e44df4ef30d1847e1900876ebcc60be6356d6476589794e5fe5e8`.
- Command: `npx wrangler deploy` — PASS; production version `382c46b1-27e7-4e51-9d88-340e5ec19ea4`.
- Initial Python urllib live check — HTTP 403 from client request; repeated using curl, which succeeded.
- Live verification: Python subprocess invoking `curl --fail --silent --show-error --location --max-time 30 URL`, asserting replacement present and old invite absent in shared JS and profile — PASS:

  - PASS GET https://codecollective.us/ (HTTP 200)
  - PASS GET https://codecollective-site.jcloiacon.workers.dev/ (HTTP 200)
  - PASS GET https://orgportal.cc/ (HTTP 200)
  - PASS GET https://orgportal.cc/assets/index-Jvzt11DA.js (HTTP 200)
  - PASS GET https://codecollective.us/js/reusableComponents.js?v=88ae4d1fb73b8da6 (HTTP 200)
  - PASS new invite present; old invite absent in js/reusableComponents.js?v=88ae4d1fb73b8da6
  - PASS GET https://codecollective.us/personnel/juliancoy.html (HTTP 200)
  - PASS new invite present; old invite absent in personnel/juliancoy.html
