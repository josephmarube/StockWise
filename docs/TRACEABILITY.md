# Requirements traceability

Maps each SRS requirement to where it is implemented and how it is verified. Test names are in `backend/tests/`. "E2E" means it was checked in the browser end-to-end run (desktop 1360px and mobile 390px).

## Functional requirements

| Req | Implementation | Verification |
|---|---|---|
| FR1.1 Add product | `routers/products.py::create_product`, `ProductForm.jsx` | `test_fr1_1_create_product`, `test_fr1_1_duplicate_sku_rejected`, `test_fr1_1_invalid_fields_rejected` (8 cases), `test_fr1_1_initial_stock_is_audited`; E2E duplicate-SKU message |
| FR1.2 Edit / archive | `update_product`, `archive_product`, `restore_product`, `delete_product` | `test_fr1_2_edit_product`, `test_fr1_2_stock_not_editable_directly`, `test_fr1_2_product_with_history_cannot_be_deleted`, `test_fr1_2_product_without_history_can_be_deleted`, `test_fr1_2_archive_keeps_history_and_hides_from_staff` |
| FR1.4 Product barcodes *(new; add to SRS)* | `ProductBarcode` model, `_check_barcodes_free`, `ProductForm.jsx` | `TestFR1_4Barcodes` (create, uniqueness, validation, edit, search, staff blocked); E2E duplicate-barcode message |
| FR1.3 View catalogue | `list_products` (search, category, low-stock, sort, paging), `Products.jsx` | `test_fr1_3_search_and_filter` |
| FR2.1 Stock in | `services/stock_service.py::record_movement`, `RecordStock.jsx` | `test_fr2_1_stock_in_increases` |
| FR2.2 Stock out + negative rule | `record_movement` (row lock, admin-only override, 409) | `test_fr2_2_stock_out_decreases`, `test_fr2_2_negative_stock_rejected_for_staff_even_with_override`, `test_fr2_2_admin_without_override_rejected`, `test_fr2_2_admin_override_allows_negative_and_is_flagged`, `test_simultaneous_stock_outs_never_oversell` (MySQL); E2E admin override dialog, staff rejection |
| FR2.3 Stock levels within 2 s | Movement response returns new level; dashboard re-fetches on navigation and polls every 10 s for other users' changes | `test_fr2_3_stock_level_visible_immediately`; load test p95 < 120 ms |
| FR2.5 Scan to record *(new; add to SRS)* | `GET /api/products/by-barcode/{code}`, `ProductPicker.jsx` (USB scanner), `BarcodeScanner.jsx` (camera) | `TestFR2_5ScanLookup`; E2E with a simulated camera reading an EAN-13 (about 0.2 s), USB-scanner keystrokes, unknown-barcode flow for admin and staff |
| FR2.4 Movement history | `routers/stock.py::list_movements`, `ProductDetail.jsx` | `test_fr2_4_history_is_chronological` |
| FR3.1 Supplier CRUD / deactivate | `routers/suppliers.py` | `test_fr3_1_create_and_edit`, `test_fr3_1_invalid_email_rejected`, `test_fr3_1_unlinked_supplier_deleted`, `test_fr3_1_linked_supplier_deactivated` |
| FR3.2 Link product to supplier | `set_product_suppliers` | `test_fr3_2_link_multiple_suppliers`, `test_fr3_2_cannot_link_inactive_supplier` |
| FR4.1 Login | `routers/auth.py` | `test_fr4_1_login_issues_signed_jwt`, `test_fr4_1_invalid_credentials_generic_error` |
| FR4.2 Role-based access | `deps.py::require_admin` on admin routes | `test_fr4_2_nfr2_admin_only_enforced_at_api` (9 endpoints), `test_fr4_2_staff_can_view_products_and_record_stock` |
| FR4.3 Business signup *(new)* | `POST /api/auth/signup`, `Signup.jsx` | `TestSignup` (creates business + admin, starts empty, works end to end, duplicate email, validation); E2E signup |
| FR4.4 Invite links *(new)* | `routers/invites.py`, `Join.jsx`, invite dialog in `Users.jsx` | `TestInvites` (full flow, admin role, email lock, single use, revoked, expired, hashed token, staff blocked, other business blocked); E2E: admin creates link, staff joins on a phone |
| FR4.5 User management *(add to SRS: built but not specified)* | `routers/users.py`, `Users.jsx` | `test_demoted_admin_loses_access_immediately`, `test_deactivated_user_cannot_use_token_or_login`, `test_last_admin_cannot_be_demoted` |
| FR4.6 Business settings *(new)* | `routers/business.py`, business card in `Users.jsx` | `TestBusinessSettings`; E2E rename |
| FR8.1 Business data isolation *(new)* | `business_id` on every table; every query filtered in routers and `StockService` | `test_tenancy.py`: another business can't list, open, edit, archive, delete, stock, link, scan, report on or manage users of this business. Mutation-checked: removing any of 8 filters makes tests fail. E2E across three businesses |
| FR8.2 Per-business uniqueness *(new)* | `uq_products_business_sku`, `uq_product_barcodes_business_code`, `uq_categories_business_name` | `TestPerBusinessUniqueness` |
| FR5.1 Threshold alerting | `Product.is_low_stock`, `routers/dashboard.py` | `test_fr5_1_flag_at_threshold`, `test_fr5_1_raising_threshold_flags_product` |
| FR6.1 Stock report | `routers/reports.py::stock_report` | `test_fr6_1_stock_report`, `test_fr6_1_date_range_excludes_outside`, `test_fr6_1_invalid_range` |
| FR6.2 CSV export | `export_stock_csv`, `export_movements_csv` | `test_fr6_2_csv_export`, `test_fr6_2_csv_formula_injection_neutralised`; E2E download |
| FR7.2 Movement source *(new; add to SRS)* | `StockMovement.source`, filters in history, audit log and CSV | `TestFR7_2MovementSource` (default, recorded, invalid rejected, same rules for every source, filters + CSV) |
| FR7.1 Audit log | `StockMovement` (user, timestamp, override flag), `audit_log` | `test_fr7_1_audit_records_user_and_timestamp`, `test_fr7_1_audit_filter_and_csv` |

## Non-functional requirements

| Req | Implementation | Verification |
|---|---|---|
| NFR1 bcrypt + JWT required | `security.py`, `deps.py::get_current_user` | `test_nfr1_protected_endpoints_require_jwt`, `test_nfr1_expired_token_rejected`, `test_nfr1_passwords_stored_as_bcrypt` |
| NFR1b Abuse protection *(new)* | `ratelimit.py`: login 20/5 min, signup 5/hour, invite use 10/hour per IP | `TestRateLimits` |
| NFR2 Server-side RBAC | `require_admin`; role read from DB each request | `test_fr4_2_nfr2_admin_only_enforced_at_api`, `test_demoted_admin_loses_access_immediately`, `test_deactivated_user_cannot_use_token_or_login` |
| NFR3 10 concurrent users, < 1 s | Connection pool (10+10), indexed queries | `scripts/load_test.py`: 10 users, 1,000 requests, p95 83–117 ms, 0 errors |
| NFR4 Stock in/out in ≤ 3 screens | Dashboard → Record stock → saved (2 screens). Also reachable from the product page. | E2E. The 4-of-5 user test needs real participants and is part of the pilot. |
| NFR5 Auditability | Same as FR7.1 | `test_nfr5_every_movement_has_user_and_time` |
| NFR6 Chrome & Edge | Standard React/CSS, no browser-specific APIs | E2E on Chromium (the engine behind both Chrome and Edge) |
| NFR8 Client + server validation | Pydantic schemas + readable 422 handler; form checks in every React form | `test_fr1_1_invalid_fields_rejected`, `test_nfr8_invalid_quantity_rejected`, `test_validation_errors_are_readable`; E2E client errors |
| Maintainability: schema changes | Alembic migrations; v1.0 databases detected and upgraded in place | `test_migrations.py` (MySQL): fresh install matches models, v1.0 database upgrades with data kept, idempotent, reset |
| SRS 3.4 HTTPS / secure transport | Render serves HTTPS; database traffic uses TLS with CA and hostname verification; production refuses a weak `JWT_SECRET` | `test_deploy_config.py` (Aiven URI, TLS contexts, secret check, static serving); manual TLS checks against MySQL (encrypted, refused without TLS, refused with wrong CA, refused on hostname mismatch) |
| NFR9 Layer separation | `frontend/`, `backend/` (routers / services / models), MySQL | Structure |

## Safety and business rules (SRS 5.2, 5.5)

| Rule | Where |
|---|---|
| Destructive actions need confirmation | `Confirm` dialog on archive, delete, deactivate supplier, disable user, negative-stock override |
| Negative stock rejected by default; admin override only | `record_movement`; override flagged in the audit log |
| Movements are never deleted; products with history are archived | No delete endpoint for movements; `delete_product` returns 409 |
| A failed save changes nothing | Transaction rollback (`test_failed_movement_rolls_back`) |
| At least one active admin always exists | `update_user` (`test_last_admin_cannot_be_demoted`) |

## SRS changes needed to match the prototype

The rubric grades the prototype against the SRS, so these changes bring the SRS in line with what is built and tested.

**1. Introduction and scope (sections 1.2–1.3)**
- StockWise is now a **multi-business web platform**: each business (one location) signs up and gets a private workspace. Multi-*branch* (one business, several locations) stays out of scope.
- Move **barcode scanning** into scope. POS/till integration, scan-to-sell, spreadsheet import and wholesale stay out of scope as the Phase 2/3 roadmap.

**2. Overall description (section 2)**
- **Product perspective:** a hosted, multi-tenant web application (one Docker container on Render, MySQL on Aiven, HTTPS). Data is separated per business.
- **User classes:** add **Visitor** (not logged in: can create a business or accept an invite). Admin and Staff are roles *within one business*. The person who creates a business is its first Admin.
- **Constraints:** each email belongs to exactly one business.

**3. New functional requirements**
- **FR1.4 Product barcodes.** An admin can attach one or more barcodes to a product. Within a business, each barcode belongs to one product; a duplicate is rejected, naming the product that has it.
- **FR2.5 Scan to record.** Users can select a product by scanning its barcode with a USB/Bluetooth scanner or a device camera. An unknown barcode shows a message; admins can add a product with that barcode.
- **FR4.3 Business signup.** A visitor can create a business by giving the business name, their name, email and password. They become its admin and are logged in.
- **FR4.4 Invite links.** An admin can create a single-use invite link for a Staff or Admin role, optionally limited to one email, expiring after 1–30 days. The recipient sets their own name and password and joins that business. Admins can see and cancel pending links.
- **FR4.5 User management.** An admin can add users, change their role, reset their password and disable or re-enable accounts. A business always keeps at least one active admin.
- **FR4.6 Business settings.** An admin can rename the business.
- **FR7.2 Movement source.** Each stock movement records how it was entered (typed, scanner or camera). The audit log and its CSV can be filtered by source.
- **FR8.1 Data isolation.** Users can see and change only their own business's data. Records of other businesses are treated as not existing.
- **FR8.2 Per-business uniqueness.** SKUs, barcodes and category names are unique within a business, not across businesses.

**4. Non-functional requirements**
- **NFR1 (security), add:**
  - login, signup and invite acceptance are rate-limited per IP address;
  - invite tokens are random, single-use, expiring and stored only as a hash;
  - the database connection uses TLS with certificate verification.
- **Deployment, add:** the system is reachable at a public HTTPS URL, packaged as a Docker image.

**5. Business rules (section 5.5)**
- "At least one active admin" applies **per business**.
- Deactivating a business locks out all its users.
- Replace "admins may edit historical stock records" with: *movements are never edited or deleted; an admin corrects a mistake by recording a compensating movement with a note.*

**6. System design (Appendix B)**
- **Class diagram:**
  - add `Business` (1 to many with User, Category, Product, Supplier, StockMovement);
  - add `Invite` (Business 1 to many Invite; User creates Invite);
  - add `ProductBarcode` (Product 1 to many);
  - add attribute `StockMovement.source`.
- **Use case diagram:**
  - Visitor: *Create business*, *Join by invite*.
  - Admin: *Invite user*, *Rename business*, *Manage barcodes*.
  - Admin and Staff: *Scan barcode to record stock*.
- **Sequence diagrams:** add *Business signup* and *Accept invite*. In *Record stock*, the product lookup is filtered by business.
- **Deployment diagram:** browser → Render (Docker: FastAPI + React) → Aiven MySQL (TLS).

**7. Existing inconsistencies to fix**
- NFR numbering skips NFR7.
- Section 5.5 refers to a "Section 4.5" that does not exist; FR5.1 is meant.
