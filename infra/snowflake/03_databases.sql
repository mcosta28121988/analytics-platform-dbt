-- =============================================================================
-- 03_databases.sql: storage layout per environment
-- Run in: Snowflake worksheet | Role: SYSADMIN | Idempotent: yes
-- =============================================================================
--   OLIST_RAW              source of truth, loaded as delivered. PERMANENT
--     .OLIST               one schema per source system (room for more sources later)
--   OLIST_ANALYTICS        prod, built only by scheduled dbt. PERMANENT
--   OLIST_ANALYTICS_DEV    dev + CI schemas (dbt_<name>, ci_pr_<n>). TRANSIENT
--
-- Why a separate prod database? Permissions become simple and safe: dev and CI
-- roles have no privileges on OLIST_ANALYTICS at all, so a dev or CI run can't
-- overwrite prod by accident.
--
-- Why is dev TRANSIENT? Everything in it can be rebuilt with `dbt build`, so we
-- skip the 7-day Fail-safe storage that permanent tables carry.
-- dbt creates the schemas inside the analytics databases (the transformer roles
-- own what they build).
-- =============================================================================

use role sysadmin;

create database if not exists olist_raw
    comment = 'Olist raw source data, append-only, as delivered';
create schema if not exists olist_raw.olist
    comment = 'Raw tables from the Olist e-commerce source system';

create database if not exists olist_analytics
    comment = 'Olist prod analytics, built only by scheduled dbt runs';

create transient database if not exists olist_analytics_dev
    data_retention_time_in_days = 1
    comment = 'Olist dev and CI dbt schemas; fully rebuildable, so transient';
