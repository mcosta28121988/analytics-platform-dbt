-- =============================================================================
-- 02_warehouses.sql: compute, one XS warehouse per workload
-- Run in: Snowflake worksheet | Role: SYSADMIN | Idempotent: yes
-- =============================================================================
-- Why three warehouses instead of one?
--   * They cost nothing while suspended; you pay only for running seconds.
--   * Cost is attributed per workload (loading vs transforming vs BI).
--   * A heavy dashboard can't slow down the pipeline, and vice versa.
--
-- Cost controls on every warehouse:
--   XSMALL                         1 credit/hour, the smallest size
--   AUTO_SUSPEND = 60              stop after 60 s idle (billing has a 60 s minimum)
--   AUTO_RESUME = TRUE             start automatically when a query arrives
--   INITIALLY_SUSPENDED = TRUE     don't start just because it was created
--   STATEMENT_TIMEOUT_IN_SECONDS   kill runaway queries
-- =============================================================================

use role sysadmin;

create warehouse if not exists olist_loading_wh with
    warehouse_size = 'XSMALL'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true
    statement_timeout_in_seconds = 900
    comment = 'Olist: COPY INTO raw tables';

create warehouse if not exists olist_transforming_wh with
    warehouse_size = 'XSMALL'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true
    statement_timeout_in_seconds = 1800
    comment = 'Olist: dbt builds (dev, CI, prod)';

create warehouse if not exists olist_reporting_wh with
    warehouse_size = 'XSMALL'
    auto_suspend = 60
    auto_resume = true
    initially_suspended = true
    statement_timeout_in_seconds = 300
    comment = 'Olist: Power BI and ad-hoc read-only queries';
