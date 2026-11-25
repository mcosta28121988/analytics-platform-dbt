-- =============================================================================
-- 05_users.sql: users and role assignment
-- Run in: Snowflake worksheet | Role: USERADMIN | Idempotent: yes
-- =============================================================================
-- OLIST_SVC_DEV is a SERVICE user: no password and no interactive login, only
-- key-pair (JWT) authentication. Local tools (the Python loader, dbt dev) use it.
-- Snowflake is phasing out single-factor password logins, and key pairs are
-- also the right pattern for automation.
--
-- The prod service user for GitHub Actions (OLIST_SVC_PROD) is created in
-- Phase 10, with its own key, so dev and prod credentials never overlap.
--
-- BEFORE RUNNING: replace the two placeholders below.
--   <RSA_PUBLIC_KEY_BODY>  contents of olist_svc_dev.pub WITHOUT the
--                          -----BEGIN/END PUBLIC KEY----- lines, on one line
--   <YOUR_SNOWFLAKE_USER>  your own login name (SELECT CURRENT_USER();)
-- =============================================================================

use role useradmin;

create user if not exists olist_svc_dev
    type = service
    default_role = olist_transformer_dev
    default_warehouse = olist_transforming_wh
    comment = 'Olist local dev: Python loader and dbt dev. Key-pair auth only.';

alter user olist_svc_dev set rsa_public_key = '<RSA_PUBLIC_KEY_BODY>';

grant role olist_loader          to user olist_svc_dev;
grant role olist_transformer_dev to user olist_svc_dev;

-- Your own (human) user: develop, load, and check what BI will see.
-- Not prod: only the scheduled pipeline builds prod.
grant role olist_loader          to user <YOUR_SNOWFLAKE_USER>;
grant role olist_transformer_dev to user <YOUR_SNOWFLAKE_USER>;
grant role olist_reporter        to user <YOUR_SNOWFLAKE_USER>;

-- Verify: RSA_PUBLIC_KEY_FP should show a SHA256 fingerprint
-- desc user olist_svc_dev;
