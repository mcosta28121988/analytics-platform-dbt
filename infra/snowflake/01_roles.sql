-- =============================================================================
-- 01_roles.sql: functional roles and hierarchy
-- Run in: Snowflake worksheet | Role: USERADMIN | Idempotent: yes
-- =============================================================================
-- One role per *workload*, not per person. People and service users receive
-- roles, so access is reviewed in one place.
--
--   OLIST_LOADER            writes source files into OLIST_RAW
--   OLIST_TRANSFORMER_DEV   dbt dev + CI: reads RAW, builds in OLIST_ANALYTICS_DEV
--   OLIST_TRANSFORMER_PROD  scheduled dbt: reads RAW, builds OLIST_ANALYTICS
--   OLIST_REPORTER          read-only on prod marts (Power BI, later the AI agent)
-- =============================================================================

use role useradmin;

create role if not exists olist_loader
    comment = 'Loads Olist source files into OLIST_RAW (append-only)';
create role if not exists olist_transformer_dev
    comment = 'dbt development and CI: reads OLIST_RAW, builds in OLIST_ANALYTICS_DEV';
create role if not exists olist_transformer_prod
    comment = 'Scheduled dbt production runs: reads OLIST_RAW, builds OLIST_ANALYTICS';
create role if not exists olist_reporter
    comment = 'Read-only access to approved prod marts (Power BI)';

-- Roll every custom role up to SYSADMIN so administrators can manage the
-- objects these roles own. Snowflake recommends this; orphaned roles own
-- objects that no admin can see.
grant role olist_loader           to role sysadmin;
grant role olist_transformer_dev  to role sysadmin;
grant role olist_transformer_prod to role sysadmin;
grant role olist_reporter         to role sysadmin;
