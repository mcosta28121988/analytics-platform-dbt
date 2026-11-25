-- =============================================================================
-- 99_teardown.sql: remove EVERYTHING this project created
-- Run in: Snowflake worksheet | Role: ACCOUNTADMIN
-- =============================================================================
-- DESTRUCTIVE: drops all Olist databases, including raw data. Only use it to
-- clean up the account or to rehearse a rebuild from scratch (01 -> 06).
-- Statements are commented out on purpose. Uncomment deliberately.
-- =============================================================================

use role accountadmin;

-- drop database if exists olist_analytics_dev;
-- drop database if exists olist_analytics;
-- drop database if exists olist_raw;
-- drop warehouse if exists olist_loading_wh;
-- drop warehouse if exists olist_transforming_wh;
-- drop warehouse if exists olist_reporting_wh;
-- drop resource monitor if exists olist_monthly_monitor;
-- drop user if exists olist_svc_dev;
-- drop role if exists olist_loader;
-- drop role if exists olist_transformer_dev;
-- drop role if exists olist_transformer_prod;
-- drop role if exists olist_reporter;
