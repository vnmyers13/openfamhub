# Graph Report - .  (2026-10-12)

## Corpus Check
- 137 files · ~75,487 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 846 nodes · 1500 edges · 67 communities (45 shown, 22 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 207 edges (avg confidence: 0.75)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Frontend Calendar API & Hooks|Frontend Calendar API & Hooks]]
- [[_COMMUNITY_Core Types, Roles & Models|Core Types, Roles & Models]]
- [[_COMMUNITY_Auth & Session Security|Auth & Session Security]]
- [[_COMMUNITY_User & Auth Schemas|User & Auth Schemas]]
- [[_COMMUNITY_SSRF Guard & iCal Feed|SSRF Guard & iCal Feed]]
- [[_COMMUNITY_Event Bus, Integrations & Realtime|Event Bus, Integrations & Realtime]]
- [[_COMMUNITY_Alembic Migrations|Alembic Migrations]]
- [[_COMMUNITY_App Config, Database & Backup|App Config, Database & Backup]]
- [[_COMMUNITY_Gitea Actions CICD|Gitea Actions CI/CD]]
- [[_COMMUNITY_Phase 2 Regression Tests|Phase 2 Regression Tests]]
- [[_COMMUNITY_Project Docs & Conventions|Project Docs & Conventions]]
- [[_COMMUNITY_Calendar Router Endpoints|Calendar Router Endpoints]]
- [[_COMMUNITY_Phase 1 Regression Tests|Phase 1 Regression Tests]]
- [[_COMMUNITY_Wall Display API Hooks|Wall Display API Hooks]]
- [[_COMMUNITY_Release History v0.13-14|Release History v0.13-14]]
- [[_COMMUNITY_Frontend Dev Dependencies|Frontend Dev Dependencies]]
- [[_COMMUNITY_TypeScript App Config|TypeScript App Config]]
- [[_COMMUNITY_TypeScript Node Config|TypeScript Node Config]]
- [[_COMMUNITY_Pytest Fixtures|Pytest Fixtures]]
- [[_COMMUNITY_Frontend Entry & Assets|Frontend Entry & Assets]]
- [[_COMMUNITY_Frontend Runtime Dependencies|Frontend Runtime Dependencies]]
- [[_COMMUNITY_Edit Permissions & Tests|Edit Permissions & Tests]]
- [[_COMMUNITY_Social Media Icons|Social Media Icons]]
- [[_COMMUNITY_Alembic Env Runtime|Alembic Env Runtime]]
- [[_COMMUNITY_npm Scripts|npm Scripts]]
- [[_COMMUNITY_PWA Maskable Icon|PWA Maskable Icon]]
- [[_COMMUNITY_PWA Brand Refresh Plan|PWA Brand Refresh Plan]]
- [[_COMMUNITY_Favicon Brand Mark|Favicon Brand Mark]]
- [[_COMMUNITY_Wall Kiosk Setup Docs|Wall Kiosk Setup Docs]]
- [[_COMMUNITY_PWA App Identity|PWA App Identity]]
- [[_COMMUNITY_App Icon Branding|App Icon Branding]]
- [[_COMMUNITY_Event Range Parsing & Tests|Event Range Parsing & Tests]]
- [[_COMMUNITY_Backend Architecture Docs|Backend Architecture Docs]]
- [[_COMMUNITY_TypeScript Root Config|TypeScript Root Config]]
- [[_COMMUNITY_Apple Touch Icon|Apple Touch Icon]]
- [[_COMMUNITY_PWA Icon 192|PWA Icon 192]]
- [[_COMMUNITY_Monochrome Brand Icon|Monochrome Brand Icon]]
- [[_COMMUNITY_Releases 0.30 and 0.12|Releases 0.30 and 0.12]]
- [[_COMMUNITY_Development Guide|Development Guide]]
- [[_COMMUNITY_Deployment Stack Docs|Deployment Stack Docs]]
- [[_COMMUNITY_Release v0.10 QA Log|Release v0.10 QA Log]]
- [[_COMMUNITY_User Creation & PIN Login Tests|User Creation & PIN Login Tests]]
- [[_COMMUNITY_Release 0.18|Release 0.18]]
- [[_COMMUNITY_Port Recommendation|Port Recommendation]]
- [[_COMMUNITY_v0.29 Security Gaps|v0.29 Security Gaps]]
- [[_COMMUNITY_Future Enhancements Backlog|Future Enhancements Backlog]]
- [[_COMMUNITY_Background Jobs|Background Jobs]]
- [[_COMMUNITY_Calendar Sync Architecture|Calendar Sync Architecture]]
- [[_COMMUNITY_Archived Planning Docs|Archived Planning Docs]]
- [[_COMMUNITY_Release v0.11|Release v0.11]]
- [[_COMMUNITY_Calendar Create Source|Calendar Create Source]]
- [[_COMMUNITY_Calendar Delete Source|Calendar Delete Source]]
- [[_COMMUNITY_Calendar List Sources|Calendar List Sources]]
- [[_COMMUNITY_Calendar Source Logs|Calendar Source Logs]]
- [[_COMMUNITY_Delete User|Delete User]]
- [[_COMMUNITY_Get User|Get User]]
- [[_COMMUNITY_List Users|List Users]]
- [[_COMMUNITY_Unique Names Tests|Unique Names Tests]]

## God Nodes (most connected - your core abstractions)
1. `apiClient` - 20 edges
2. `User` - 18 edges
3. `useAuthStore` - 18 edges
4. `assert_public_http_url()` - 17 edges
5. `_UserFields` - 17 edges
6. `_h()` - 17 edges
7. `compilerOptions` - 17 edges
8. `compilerOptions` - 16 edges
9. `Deploying OpenFamHub` - 16 edges
10. `CI/CD (Gitea Actions)` - 15 edges

## Surprising Connections (you probably didn't know these)
- `CI Workflow` --references--> `publish()`  [EXTRACTED]
  /Users/vernon/Documents/opencode/OpenFamHub/.gitea/workflows/ci.yml → scripts/deploy.sh
- `CI Workflow` --references--> `server()`  [EXTRACTED]
  /Users/vernon/Documents/opencode/OpenFamHub/.gitea/workflows/ci.yml → scripts/deploy.sh
- `Installable PWA` --semantically_similar_to--> `Workbox Runtime Caching`  [INFERRED] [semantically similar]
  /Users/vernon/Documents/opencode/OpenFamHub/README.md → /Users/vernon/Documents/opencode/OpenFamHub/frontend/vite.config.ts
- `Background Sync Emit Gap` --references--> `EventBus`  [EXTRACTED]
  /Users/vernon/Documents/opencode/OpenFamHub/docs/security-notes.md → backend/app/core/events.py
- `Background Sync Emit Gap` --references--> `add_ical_source()`  [EXTRACTED]
  /Users/vernon/Documents/opencode/OpenFamHub/docs/security-notes.md → backend/app/routers/integrations.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **PWA Asset and Offline Pipeline** — scripts_generate_icons, frontend_vite_config, frontend_index, frontend_package [INFERRED 0.85]
- **CI Publish and Deploy Flow** — workflows_ci, scripts_deploy_publish, scripts_deploy_server [EXTRACTED 1.00]
- **Version and Release Process** — agents, claude, readme, todo [EXTRACTED 1.00]
- **Runtime Stack Services** — docker_compose_local_stack, deploy_compose_runtime_stack, docs_architecture_components [EXTRACTED 0.95]
- **Gitea Actions CI Pipeline** — docs_ci, docs_ci_ci_workflow, docs_ci_gitea_runner, docs_ci_publish_job, docs_ci_deploy_job, docs_ci_test_vm [EXTRACTED 1.00]
- **Registry Deploy Workflow** — docs_deployment, docs_deployment_deploy_sh, docs_deployment_registry_deploy, plans_2026_10_11_gitea_actions_ci_server_subcommand [INFERRED 0.85]
- **Early Release Records** — docs_releases_v0_10_release, docs_releases_v0_11_release, docs_releases_v0_12_release, docs_test_history_qa_log [EXTRACTED 1.00]
- **Release v0.13 Publication Flow** — docs_releases_v0_13_release_v0_13, docs_releases_v0_13_github_release_v0_13, docs_releases_v0_13_docker_hub_api_tags, docs_releases_v0_13_docker_hub_web_tags, docs_releases_v0_13_release_checklist_completed [EXTRACTED 0.75]
- **Release v0.14 Publication Flow** — docs_releases_v0_14_release_v0_14, docs_releases_v0_14_github_release_v0_14, docs_releases_v0_14_docker_hub_api_tags, docs_releases_v0_14_docker_hub_web_tags, docs_releases_v0_14_release_checklist_completed [EXTRACTED 0.75]
- **Release v0.15 Publication Flow** — docs_releases_v0_15_release_v0_15, docs_releases_v0_15_github_release_v0_15, docs_releases_v0_15_docker_hub_api_tags, docs_releases_v0_15_docker_hub_web_tags, docs_releases_v0_15_release_checklist_completed [EXTRACTED 0.75]
- **Every-Hop SSRF Guarding mechanism** — core_url_safety_assert_public_http_url, integrations_ical_feed_fetch_ics_bytes, docs_security_notes_every_hop_ssrf_guarding, tests_test_ssrf [EXTRACTED 1.00]
- **Background sync never emits calendar_updated** — jobs_calendar_sync_sync_source, jobs_calendar_sync_sync_all_due, core_events_eventbus, routers_ws_connectionmanager, docs_security_notes_background_sync_emit_gap [EXTRACTED 1.00]
- **add_ical_source bridges request and feed worlds** — routers_integrations_add_ical_source, integrations_ical_feed_fetch_ics_bytes, jobs_calendar_sync_sync_source, docs_security_notes_cross_community_bridge_add_ical_source [EXTRACTED 1.00]
- **PWA Brand Refresh** — specs_2026_10_11_pwa_brand_refresh_design, plans_2026_10_11_pwa_brand_refresh, specs_2026_10_11_pwa_brand_refresh_design_brand_mark, plans_2026_10_11_pwa_brand_refresh_icon_generator, plans_2026_10_11_pwa_brand_refresh_maskable_icon [INFERRED 0.85]
- **Composite Favicon Mark** — public_favicon_house, public_favicon_heart, public_favicon_window [EXTRACTED 1.00]
- **SVG Symbol Sprite Form** — frontend_public_icons_svg_sprite, frontend_public_icons_svg_bluesky_icon, frontend_public_icons_svg_discord_icon, frontend_public_icons_svg_documentation_icon, frontend_public_icons_svg_github_icon, frontend_public_icons_svg_social_icon, frontend_public_icons_svg_x_icon [EXTRACTED 1.00]
- **Social Media Icon Set** — frontend_public_icons_svg_bluesky_icon, frontend_public_icons_svg_discord_icon, frontend_public_icons_svg_github_icon, frontend_public_icons_svg_social_icon, frontend_public_icons_svg_x_icon, frontend_public_icons_svg_social_media_icons [INFERRED 0.85]
- **PWA Icon Bundle** — icons_icon_512_openfamhub_pwa_icon, icons_icon_512_pwa_manifest [INFERRED 0.95]
- **App Icon Branding Composition** — icons_icon_app_app_icon, icons_icon_app_house_motif, icons_icon_app_heart_motif, icons_icon_app_indigo_gradient [INFERRED 0.85]
- **Maskable Icon Visual Composition** — icons_icon_maskable_maskable_icon, icons_icon_maskable_house_symbol, icons_icon_maskable_indigo_gradient, icons_icon_maskable_heart_motif [EXTRACTED 1.00]
- **PWA Icon Set** — icons_maskable_icon_512_maskable_icon, icons_icon_maskable_maskable_icon, icons_icon_512_app_icon [INFERRED 0.75]
- **Alembic revision chain 001-005** — backend_alembic_versions_5ca65f282ae7_initial_schema_upgrade, backend_alembic_versions_4c6b1ca5fd2c_002_sessions_and_relationships_upgrade, backend_alembic_versions_12c7ab6cf8c5_003_calendar_upgrade, backend_alembic_versions_a1f3c9d2e004_004_wall_devices_upgrade, backend_alembic_versions_b7d2e1f0a005_005_session_auth_method_upgrade [EXTRACTED 1.00]
- **Startup schema migration and scheduler wiring** — backend_app_main_lifespan, backend_app_core_migrate_upgrade_database, backend_app_core_database_base, backend_app_core_database_engine, backend_app_jobs_scheduler_start_scheduler, backend_app_jobs_scheduler_stop_scheduler [INFERRED 0.85]
- **Session-backed authentication stack** — backend_app_models_auth_session, backend_app_core_security_start_session, backend_app_core_security_get_auth, backend_app_core_security_create_access_token, backend_app_core_security_decode_token, backend_app_core_security_login_throttle [INFERRED 0.85]
- **Authentication session lifecycle** — backend_app_routers_auth_setup, backend_app_routers_auth_login, backend_app_routers_auth_pin_login, backend_app_routers_auth_elevate, backend_app_routers_auth_logout, backend_app_core_security_start_session [INFERRED 0.85]
- **Wall display pairing and read-only access** — backend_app_routers_wall_create_device, backend_app_routers_wall_pair, backend_app_routers_wall_get_wall_device, backend_app_routers_wall__hash, backend_app_routers_wall__set_cookie, backend_app_models_wall_device_walldevice [EXTRACTED 1.00]
- **Calendar event to API response mapping** — backend_app_services_calendar_event_to_response, backend_app_services_calendar_get_events_in_range, backend_app_models_calendar_event_calendarevent, backend_app_models_calendar_source_calendarsource, backend_app_schemas_calendar_calendareventresponse [INFERRED 0.85]
- **Admin password-unlock flow** — frontend_src_api_client_apiclient, frontend_src_api_client_onpasswordprompt, frontend_src_api_client_requestpasswordprompt, frontend_src_components_passwordprompt_passwordprompt, frontend_src_components_navshell_navshell [EXTRACTED 1.00]
- **Frontend calendar data layer** — frontend_src_api_calendar, frontend_src_api_wall, frontend_src_api_client_apiclient [INFERRED 0.85]
- **OpenFamHub MVP sprint plan sequence** — docs_archive_planning_sprint_s1, docs_archive_planning_sprint_s2, docs_archive_planning_sprint_s3, docs_archive_planning_sprint_s4, docs_archive_planning_sprint_s5, docs_archive_planning_sprint_s6 [EXTRACTED 1.00]
- **All-day event date handling across views** — frontend_src_lib_dates_eventstart, frontend_src_lib_dates_eventend, frontend_src_lib_dates_eventdaykeys, frontend_src_pages_calendarpage_calendarpage, frontend_src_pages_dashboard_todayseventswidget, frontend_src_wall_wallsevendaystrip_wallsevendaystrip [INFERRED 0.85]
- **Wall display read-only board** — frontend_src_wall_walllayout_walllayout, frontend_src_wall_wallclock_wallclock, frontend_src_wall_wallsevendaystrip_wallsevendaystrip, frontend_src_wall_wallmemberlist_wallmemberlist, frontend_src_wall_wallphotoplaceholder_wallphotoplaceholder, frontend_src_pages_admin_walldisplays_walldisplays [INFERRED 0.85]
- **Authentication and pairing flow** — frontend_src_stores_auth_useauthstore, frontend_src_pages_login_login, frontend_src_pages_setupwizard_setupwizard, frontend_src_wall_walllayout_walllayout, frontend_src_pages_admin_walldisplays_walldisplays [INFERRED 0.75]

## Communities (67 total, 22 thin omitted)

### Community 0 - "Frontend Calendar API & Hooks"
Cohesion: 0.06
Nodes (69): CalendarSource, CreateEventData, SyncLogEntry, useAddIcalSource(), useAddIcalSource, useCalendarEvents(), useCalendarSources(), useCreateEvent() (+61 more)

### Community 1 - "Core Types, Roles & Models"
Cohesion: 0.05
Nodes (67): Base, Role gate. Admin access additionally needs a password session or a recent     el, require_role(), Datetime column that always stores UTC and always returns aware UTC values., UTC datetime contract, UTCDateTime, CalendarEvent, CalendarSource (+59 more)

### Community 2 - "Auth & Session Security"
Cohesion: 0.07
Nodes (48): Auth, clear_login_cookie(), create_access_token(), decode_token(), get_auth(), get_current_user(), LoginThrottle, AsyncSession (+40 more)

### Community 3 - "User & Auth Schemas"
Cohesion: 0.09
Nodes (30): hash_password(), SetupRequest, CreateUserRequest, Fields shared by create and update, with one copy of each rule., SetPinRequest, UpdateUserRequest, _UserFields, avatar() (+22 more)

### Community 4 - "SSRF Guard & iCal Feed"
Cohesion: 0.09
Nodes (19): AsyncBaseTransport, assert_public_http_url(), _is_blocked(), Reject server-side requests to non-public addresses (SSRF guard).  Any code that, Raise ``ValueError`` unless *url* is http(s) and every resolved IP is public., _expand_recurrence(), fetch_and_parse(), fetch_ics_bytes() (+11 more)

### Community 5 - "Event Bus, Integrations & Realtime"
Cohesion: 0.09
Nodes (28): EventBus, Any, add_ical_source(), AsyncSession, User, ConnectionManager, _forward_to_manager(), Any (+20 more)

### Community 6 - "Alembic Migrations"
Cohesion: 0.06
Nodes (22): upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), _alembic_config(), Alembic owns schema at startup, Bring the database schema up to date with Alembic at startup.  Installs from bef (+14 more)

### Community 7 - "App Config, Database & Backup"
Cohesion: 0.07
Nodes (29): APP_VERSION, get_settings(), Settings, engine, get_db(), set_sqlite_pragmas(), daily_backup(), register_backup_job() (+21 more)

### Community 8 - "Gitea Actions CI/CD"
Cohesion: 0.11
Nodes (33): CI/CD (Gitea Actions), backend Job, builtin:checkout, ci.yml Pipeline, deploy Job, Forgejo Container Registry, frontend Job, Gitea Actions (+25 more)

### Community 9 - "Phase 2 Regression Tests"
Cohesion: 0.13
Nodes (11): admin(), _cookie(), _event(), _h(), _member(), Phase 2 (v0.30): sign-in model, sessions, admin password gate, event roles., TestAdminPasswordGate, TestEventRoles (+3 more)

### Community 10 - "Project Docs & Conventions"
Cohesion: 0.17
Nodes (23): Wall Display Paired-Device Cookie, family_id Tenant Scoping, Port, Don't Merge (v0.29 Reference Only), Server-Side Session Revocation (jti), Single API Worker / In-Process Scheduler, UTCDateTime Convention, Workbox Runtime Caching, Installable PWA (+15 more)

### Community 11 - "Calendar Router Endpoints"
Cohesion: 0.15
Nodes (28): _check_can_edit(), create_event(), create_source(), delete_event(), delete_source(), get_event(), list_events(), list_sources() (+20 more)

### Community 12 - "Phase 1 Regression Tests"
Cohesion: 0.13
Nodes (10): admin(), _cookie(), _create_event(), _list(), Regression tests for the Phase 1 review fixes (timezones, ranges, sources, wall), Extract 'name=value' from a Set-Cookie header (the test client is http,     so S, TestRangeOverlap, TestSources (+2 more)

### Community 13 - "Wall Display API Hooks"
Cohesion: 0.14
Nodes (19): CalendarEvent, getWallSession(), pairWall(), useCreateWallDevice(), useRevokeWallDevice(), useWallDevices(), useWallMembers(), WallDevice (+11 more)

### Community 14 - "Release History v0.13-14"
Cohesion: 0.10
Nodes (21): Docker Hub API Tags, Docker Hub Web Tags, Git SHA 80bf7d1, GitHub Release v0.13, Release Checklist Completed, Release v0.13, Test History Reference, Docker Hub API Tags (+13 more)

### Community 15 - "Frontend Dev Dependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, postcss (+12 more)

### Community 16 - "TypeScript App Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+10 more)

### Community 17 - "TypeScript Node Config"
Cohesion: 0.11
Nodes (17): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+9 more)

### Community 18 - "Pytest Fixtures"
Cohesion: 0.15
Nodes (10): app, client(), db_engine(), db_session(), Creates a single async engine for the entire test session., Provides a clean, transactional session for each test function., Ensures the database schema is created before each test., Provides an AsyncClient with the test database session injected via dependency o (+2 more)

### Community 19 - "Frontend Entry & Assets"
Cohesion: 0.18
Nodes (7): name, private, type, version, here, iconsDir, jobs

### Community 20 - "Frontend Runtime Dependencies"
Cohesion: 0.17
Nodes (12): dependencies, axios, clsx, date-fns, react, react-big-calendar, react-dom, react-router-dom (+4 more)

### Community 21 - "Edit Permissions & Tests"
Cohesion: 0.18
Nodes (12): _check_can_edit, delete_event, get_event, _load_event_with_source, update_event, _authorize_change, set_pin, update_user (+4 more)

### Community 22 - "Social Media Icons"
Cohesion: 0.39
Nodes (8): Bluesky Icon, Discord Icon, Documentation Icon, GitHub Icon, Social Icon, Social Media Icons, SVG Icon Sprite, X Icon

### Community 23 - "Alembic Env Runtime"
Cohesion: 0.47
Nodes (4): do_run_migrations(), run_async_migrations(), run_migrations_online(), Connection

### Community 24 - "npm Scripts"
Cohesion: 0.33
Nodes (6): scripts, build, dev, icons, lint, preview

### Community 25 - "PWA Maskable Icon"
Cohesion: 0.40
Nodes (6): App Icon (512x512), Heart Motif, House Symbol, Indigo Gradient Background, Maskable PWA Icon, Maskable App Icon (512x512)

### Community 26 - "PWA Brand Refresh Plan"
Cohesion: 0.53
Nodes (6): PWA Brand Refresh Implementation Plan, generate-icons.mjs, Maskable Icon Variant, PWA Brand Refresh Design, House + Calendar Brand Mark, @resvg/resvg-js Rasterizer

### Community 27 - "Favicon Brand Mark"
Cohesion: 0.53
Nodes (6): Family Hub / Home Identity, Heart Motif at Doorway, House Outline (roof + body), Indigo Brand Stroke #4F46E5, OpenFamHub Favicon, Window Grid Detail

### Community 28 - "Wall Kiosk Setup Docs"
Cohesion: 0.40
Nodes (5): Authentication Architecture, Realtime Wall Updates, Caddy Internal CA Trust, MVP Hardware Test Sign-off Checklist, Raspberry Pi Wall Display Kiosk

### Community 29 - "PWA App Identity"
Cohesion: 0.40
Nodes (5): Family Calendar Application, Mobile App Icon, OpenFamHub PWA Icon, Progressive Web App, PWA Manifest

### Community 30 - "App Icon Branding"
Cohesion: 0.70
Nodes (5): OpenFamHub App Icon, Family Home Branding, Heart Motif, House Motif, Indigo Gradient Background

### Community 31 - "Event Range Parsing & Tests"
Cohesion: 0.40
Nodes (5): create_event, list_events, _parse_dt, test_phase1 TestRangeOverlap, test_phase1 TestTimezones

### Community 32 - "Backend Architecture Docs"
Cohesion: 0.67
Nodes (3): Architecture Components, Data Model, Backend Dependencies

### Community 34 - "Apple Touch Icon"
Cohesion: 1.00
Nodes (3): OpenFamHub App Branding, OpenFamHub Apple Touch Icon (180x180), iOS Home Screen / PWA Icon Asset

### Community 35 - "PWA Icon 192"
Cohesion: 0.67
Nodes (3): OpenFamHub Frontend, Progressive Web App, PWA App Icon (192x192)

### Community 36 - "Monochrome Brand Icon"
Cohesion: 0.67
Nodes (3): Family Icon, House Symbol, Monochrome Home Icon

## Ambiguous Edges - Review These
- `main()` → `get_events_in_range()`  [AMBIGUOUS]
  backend/scripts/fix_event_timezones.py · relation: conceptually_related_to

## Knowledge Gaps
- **210 isolated node(s):** `$schema`, `style`, `rsc`, `tsx`, `css` (+205 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `main()` and `get_events_in_range()`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `get_auth()` connect `Auth & Session Security` to `App Config, Database & Backup`?**
  _High betweenness centrality (0.001) - this node is a cross-community bridge._
- **Why does `Session` connect `Auth & Session Security` to `Core Types, Roles & Models`, `Alembic Migrations`?**
  _High betweenness centrality (0.000) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `User` (e.g. with `Base` and `UTCDateTime`) actually correct?**
  _`User` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Bring the database schema up to date with Alembic at startup.  Installs from bef`, `Counts failed sign-ins per key ("pin:<user_id>", "pw:<name>") with an     escala`, `Create a session row and set the login cookie for it.` to the rest of the system?**
  _244 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Frontend Calendar API & Hooks` be split into smaller, more focused modules?**
  _Cohesion score 0.057967313585291114 - nodes in this community are weakly interconnected._
- **Should `Core Types, Roles & Models` be split into smaller, more focused modules?**
  _Cohesion score 0.052100840336134456 - nodes in this community are weakly interconnected._