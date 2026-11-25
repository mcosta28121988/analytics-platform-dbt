-- =============================================================================
-- 07_verify.sql: check the setup (read-only)
-- Run in: Snowflake worksheet | Role: SECURITYADMIN (or ACCOUNTADMIN)
-- =============================================================================

use role securityadmin;

show roles like 'OLIST%';
show warehouses like 'OLIST%';        -- size XSMALL, auto_suspend 60, state SUSPENDED
show databases like 'OLIST%';         -- OLIST_ANALYTICS_DEV kind = TRANSIENT
show grants to role olist_loader;
show grants to role olist_transformer_dev;
show grants to role olist_transformer_prod;
show grants to role olist_reporter;
show grants to user olist_svc_dev;
desc user olist_svc_dev;               -- TYPE = SERVICE, RSA_PUBLIC_KEY_FP set

use role accountadmin;
show resource monitors like 'OLIST%';
