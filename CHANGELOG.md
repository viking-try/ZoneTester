# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.2.0] - 2026-08-22

### Added
- **Collapsible Sidebar**:
  - Added a toggle button in the top navigation bar and global keyboard shortcut (`Ctrl+B` / `Cmd+B`).
  - Added smooth CSS transitions between expanded (`216px`) and icon-only compact mode (`60px`).
  - Added SVG navigation icons with hover tooltip flyouts (`[data-tooltip]`) in collapsed mode.
  - Added `localStorage` persistence for sidebar collapse preference across browser sessions.
  - Added compact brand logo badge (`ZG.`) when sidebar is collapsed.
- **Deep Interactivity & Drill-Downs Across UI**:
  - **Domains (`/#/domains`)**:
    - Clickable domain names that open a comprehensive **Domain Detail Modal** showing DNSSEC status, total record counts, last scan timestamps, creation dates, and instant "View Records" / "Scan Zone Now" actions.
    - Clickable hosted zone pills that update the global active zone filter.
    - Clickable record count badges linking directly to filtered domain records (`/#/records?search=<domain>`).
    - Color-coded DNSSEC status badges (`signed`, `unsigned`, `bogus`, `unknown`).
  - **Executive Dashboard (`/#/dashboard`)**:
    - Interactive clickable KPI tiles with hover lift elevation that navigate to filtered records (Total, Scannable, Up, Down, PQC-ready, Weak cipher, Cleanup candidates, Expiring certs).
    - Clickable grade distribution bar rows (A+, A, B, C, F, T) that filter records by selected grade.
    - Hoverable trend chart data points showing snapshot date, up count, and total record metrics.
  - **Records (`/#/records`)**:
    - URL query parameter synchronization on route entry (`?search=`, `?grade=`, `?state=`, `?protocol=`, `?pqc=`, `?weak_cipher=`, `?hsts_missing=`, `?cleanup=`).
    - Added Quick Filter preset chips ("All Records", "Critical (F/T)", "Down Hosts", "Weak Ciphers", "Missing HSTS", "PQC Ready", "Cleanup Candidates").
    - Enhanced Record Detail modal with one-click **Copy** buttons next to Hostname, DNS Value, and Negotiated Cipher.
    - Clickable hosted zone column pills to filter by zone.
  - **Risk View (`/#/risk`)**:
    - Clickable Issue table rows navigating to filtered records or cleanup candidates.
    - Clickable Asset table cells (Zone, Total, Cleanup, Down, Weak Cipher, F/T grade) linking to corresponding filtered record views.
  - **Cleanup Candidates (`/#/cleanup`)**:
    - Clickable rows opening the complete **Record Detail Modal** to inspect cleanup confidence scores, reasons, and certificates before acknowledging.
    - Clickable hosted zone column pills.
  - **Scan Queue (`/#/scan-queue`)**:
    - Clickable KPI tiles (`queued`, `running`, `done`, `error`) to filter jobs table by state.
    - Clickable job rows opening a **Job Detail Modal** with JSON payload and error traceback inspection.
- **Executive-Grade Reporting Suite (`/#/reports`)**:
  - Multi-tab reporting center:
    - **Tab 1: Report Generator & Viewer**: Interactive scope and template selectors, real-time unreported change counters, live embedded HTML preview, one-click **Print / Save PDF** (with custom `@media print` optimization), **Download HTML**, **Download CSV**, and **Copy Markdown Summary**.
    - **Tab 2: Scheduled Distributions**: Schedule management table with status badges (Active/Paused), template pills, cadence, recipient tags, **Send Now** queue trigger, **Edit Schedule** modal, **Pause/Resume** toggle, and **Delete Schedule** with confirmation.
    - **Tab 3: Templates & Policy**: Visual catalog explaining all report definitions, target audiences, and recommended cadences.
- **Client API & Styles**:
  - Added `apiDelete(path)` helper to `app/web/js/api.js`.
  - Added print stylesheet `@media print` in `app/web/css/base.css` to enable clean PDF export of reports and dashboards.

### Changed
- Refactored client hash router in `app/web/js/app.js` to parse URL query strings and pass `queryParams` into page modules.
- Refactored `buildFilterBar` in `app/web/js/components/filters.js` to support `initialValues` pre-population from URL search params.
- Enhanced backend `app/api/routers/records.py` filter query builder to support `domain_id` parameter.

---

## [0.1.0] - 2026-08-22

### Added
- Initial release of Zoneguard.
- DNS zone ingestion (BIND, CSV, Route 53 JSON, S3 sync).
- Cryptographic scanning engine supporting TLS 1.0–1.3, cipher enumeration, and Post-Quantum Cryptography (ML-KEM).
- Attack surface management, dangling CNAME detection, and stale ACM validation cleanup.
- Three-grade scoring model (A+ to F/T).
- Celery job pipeline with stuck-job self-healing.
- FastAPI backend with session authentication, RBAC, and audit logging.
- Vanilla modern ES-module Single Page Application.
