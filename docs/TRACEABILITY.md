# Requirements traceability

Maps each SRS requirement to where it is implemented and how it is verified. Test names are in `backend/tests/`. "E2E" means it was checked in the browser end-to-end run (desktop 1360px and mobile 390px).

## Functional requirements

| Req | Implementation | Verification |
|---|---|---|
| FR1.1 Add product | `routers/products.py::create_product`, `ProductForm.jsx` | `test_fr1_1_create_product`, `test_fr1_1_duplicate_sku_rejected`, `test_fr1_1_invalid_fields_rejected` (8 cases), `test_fr1_1_initial_stock_is_audited`; E2E duplicate-SKU message |
| FR1.2 Edit / archive | `update_product`, `archive_product`, `restore_product`, `delete_product` | `test_fr1_2_edit_product`, `test_fr1_2_stock_not_editable_directly`, `test_fr1_2_product_with_history_cannot_be_deleted`, `test_fr1_2_product_without_history_can_be_deleted`, `test_fr1_2_archive_keeps_history_and_hides_from_staff` |
| FR1.3 View catalogue | `list_products` (search, category, low-stock, sort, paging), `Products.jsx` | `test_fr1_3_search_and_filter` |
| FR2.1 Stock in | `services/stock_service.py::record_movement`, `RecordStock.jsx` | `test_fr2_1_stock_in_increases` |
| FR2.2 Stock out + negative rule | `record_movement` (row lock, admin-only override, 409) | `test_fr2_2_stock_out_decreases`, `test_fr2_2_negative_stock_rejected_for_staff_even_with_override`, `test_fr2_2_admin_without_override_rejected`, `test_fr2_2_admin_override_allows_negative_and_is_flagged`, `test_simultaneous_stock_outs_never_oversell` (MySQL); E2E admin override dialog, staff rejection |
| FR2.3 Stock levels within 2 s | Movement response returns new level; dashboard re-fetches on navigation and polls every 10 s for other users' changes | `test_fr2_3_stock_level_visible_immediately`; load test p95 < 120 ms |
| FR2.4 Movement history | `routers/stock.py::list_movements`, `ProductDetail.jsx` | `test_fr2_4_history_is_chronological` |
| FR3.1 Supplier CRUD / deactivate | `routers/suppliers.py` | `test_fr3_1_create_and_edit`, `test_fr3_1_invalid_email_rejected`, `test_fr3_1_unlinked_supplier_deleted`, `test_fr3_1_linked_supplier_deactivated` |
| FR3.2 Link product to supplier | `set_product_suppliers` | `test_fr3_2_link_multiple_suppliers`, `test_fr3_2_cannot_link_inactive_supplier` |
| FR4.1 Login | `routers/auth.py` | `test_fr4_1_login_issues_signed_jwt`, `test_fr4_1_invalid_credentials_generic_error` |
| FR4.2 Role-based access | `deps.py::require_admin` on admin routes | `test_fr4_2_nfr2_admin_only_enforced_at_api` (9 endpoints), `test_fr4_2_staff_can_view_products_and_record_stock` |
| FR5.1 Threshold alerting | `Product.is_low_stock`, `routers/dashboard.py` | `test_fr5_1_flag_at_threshold`, `test_fr5_1_raising_threshold_flags_product` |
| FR6.1 Stock report | `routers/reports.py::stock_report` | `test_fr6_1_stock_report`, `test_fr6_1_date_range_excludes_outside`, `test_fr6_1_invalid_range` |
| FR6.2 CSV export | `export_stock_csv`, `export_movements_csv` | `test_fr6_2_csv_export`, `test_fr6_2_csv_formula_injection_neutralised`; E2E download |
| FR7.1 Audit log | `StockMovement` (user, timestamp, override flag), `audit_log` | `test_fr7_1_audit_records_user_and_timestamp`, `test_fr7_1_audit_filter_and_csv` |

## Non-functional requirements

| Req | Implementation | Verification |
|---|---|---|
| NFR1 bcrypt + JWT required | `security.py`, `deps.py::get_current_user` | `test_nfr1_protected_endpoints_require_jwt`, `test_nfr1_expired_token_rejected`, `test_nfr1_passwords_stored_as_bcrypt` |
| NFR2 Server-side RBAC | `require_admin`; role read from DB each request | `test_fr4_2_nfr2_admin_only_enforced_at_api`, `test_demoted_admin_loses_access_immediately`, `test_deactivated_user_cannot_use_token_or_login` |
| NFR3 10 concurrent users, < 1 s | Connection pool (10+10), indexed queries | `scripts/load_test.py`: 10 users, 1,000 requests, p95 83–117 ms, 0 errors |
| NFR4 Stock in/out in ≤ 3 screens | Dashboard → Record stock → saved (2 screens). Also reachable from the product page. | E2E. The 4-of-5 user test needs real participants and is part of the pilot. |
| NFR5 Auditability | Same as FR7.1 | `test_nfr5_every_movement_has_user_and_time` |
| NFR6 Chrome & Edge | Standard React/CSS, no browser-specific APIs | E2E on Chromium (the engine behind both Chrome and Edge) |
| NFR8 Client + server validation | Pydantic schemas + readable 422 handler; form checks in every React form | `test_fr1_1_invalid_fields_rejected`, `test_nfr8_invalid_quantity_rejected`, `test_validation_errors_are_readable`; E2E client errors |
| NFR9 Layer separation | `frontend/`, `backend/` (routers / services / models), MySQL | Structure |

## Safety and business rules (SRS 5.2, 5.5)

| Rule | Where |
|---|---|
| Destructive actions need confirmation | `Confirm` dialog on archive, delete, deactivate supplier, disable user, negative-stock override |
| Negative stock rejected by default; admin override only | `record_movement`; override flagged in the audit log |
| Movements are never deleted; products with history are archived | No delete endpoint for movements; `delete_product` returns 409 |
| A failed save changes nothing | Transaction rollback (`test_failed_movement_rolls_back`) |
| At least one active admin always exists | `update_user` (`test_last_admin_cannot_be_demoted`) |

## Notes for the next SRS revision

- **Section 5.5** says admins may "edit historical stock records". The class diagram (B.1) and FR7.1 treat movements as immutable. The build follows the diagram: an admin corrects a mistake by recording a compensating movement with a note, so the audit trail stays complete. Consider rewording 5.5 to match.
- **NFR numbering** skips NFR7.
- **Section 5.5, last bullet** refers to "Section 4.5", which does not exist (FR5.1 is meant).
