# CodeCollective Agenda view

Imported from https://github.com/Jayharwani/codecollective-calendar-redesign at commit ce4786f0f64f69ee8dbb441599122497985da3ab.

The complete application is maintained here and served at `/calendar-next/`. It reads the same public city feeds as the existing calendars. The view selector links Calendar, Cards, Simple, and Agenda and preserves the city. Agenda retains its own month grid, maps, filters, subscription tools, and event details.

From the CodeCollective root, run `./scripts/build_calendar_next.sh` to install dependencies when needed, typecheck, build, and copy generated assets into `calendar-next/`. That generated directory is ignored by Git. The canonical Cloudflare site build invokes this script and excludes the application source from published assets.

Run `npm --prefix calendar-next-app test` for unit tests. Run `npm --prefix calendar-next-app run test:e2e` for the upstream browser suite, which uses its original root mount with snapshot data.

Integration changes: default Vite base `/calendar-next/`, city-aware calendar view navigation, and login links pointing to the current OrgPortal host.
