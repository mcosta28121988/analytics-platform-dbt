-- =============================================================================
-- 06_resource_monitor.sql: hard credit cap
-- Run in: Snowflake worksheet | Role: ACCOUNTADMIN | Idempotent: yes
-- =============================================================================
-- A resource monitor is the cost guardrail: if anything goes wrong (a runaway
-- query or a misconfigured schedule), the warehouses stop at the quota.
-- 10 credits/month is far more than this project should use (expected
-- 2-3/month for the daily pipeline), so hitting it means something is wrong.
--
-- NOTIFY sends an email only to account admins who have verified their email
-- in Snowsight (Settings > Profile).
-- =============================================================================

use role accountadmin;

create resource monitor if not exists olist_monthly_monitor with
    credit_quota = 10
    frequency = monthly
    start_timestamp = immediately
    triggers
        on 75 percent do notify
        on 90 percent do suspend             -- let running queries finish, then stop
        on 100 percent do suspend_immediate; -- cancel running queries and stop

alter warehouse olist_loading_wh      set resource_monitor = olist_monthly_monitor;
alter warehouse olist_transforming_wh set resource_monitor = olist_monthly_monitor;
alter warehouse olist_reporting_wh    set resource_monitor = olist_monthly_monitor;
