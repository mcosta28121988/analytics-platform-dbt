-- =============================================================================
-- 04_grants.sql: least-privilege access per role
-- Run in: Snowflake worksheet | Role: SECURITYADMIN | Idempotent: yes
-- =============================================================================

use role securityadmin;

-- ---- Compute ---------------------------------------------------------------
grant usage on warehouse olist_loading_wh      to role olist_loader;
grant usage on warehouse olist_transforming_wh to role olist_transformer_dev;
grant usage on warehouse olist_transforming_wh to role olist_transformer_prod;
grant usage on warehouse olist_reporting_wh    to role olist_reporter;

-- ---- Loader: creates and owns raw tables, stages and file formats -----------
grant usage on database olist_raw to role olist_loader;
grant usage, create table, create stage, create file format
    on schema olist_raw.olist to role olist_loader;

-- ---- Transformers: read-only on raw ---------------------------------------
-- FUTURE grants cover tables the loader creates later, so no re-granting is
-- needed after each new source table.
grant usage on database olist_raw         to role olist_transformer_dev;
grant usage on schema   olist_raw.olist   to role olist_transformer_dev;
grant select on all tables    in schema olist_raw.olist to role olist_transformer_dev;
grant select on future tables in schema olist_raw.olist to role olist_transformer_dev;

grant usage on database olist_raw         to role olist_transformer_prod;
grant usage on schema   olist_raw.olist   to role olist_transformer_prod;
grant select on all tables    in schema olist_raw.olist to role olist_transformer_prod;
grant select on future tables in schema olist_raw.olist to role olist_transformer_prod;

-- ---- Transformers: build in their own environment only ---------------------
grant usage, create schema on database olist_analytics_dev to role olist_transformer_dev;
grant usage, create schema on database olist_analytics     to role olist_transformer_prod;

-- ---- Reporter: can *see* prod schemas; table access comes from dbt ----------
-- SELECT on individual marts is granted by dbt's `grants` config (Phase 7),
-- so only models we explicitly approve are readable. Staging and intermediate
-- models stay invisible to BI and to the future AI agent.
grant usage on database olist_analytics to role olist_reporter;
grant usage on future schemas in database olist_analytics to role olist_reporter;
