# Query warehouse for the Streamlit app and local development.
# Used by: app/snowflake.yml (QUERY_WAREHOUSE), deploy scripts.
resource "snowflake_warehouse" "app_warehouse" {
  name           = var.warehouse_name
  warehouse_size = var.warehouse_size
  comment        = "Query warehouse for the git-sis Streamlit app"

  # Auto-suspend after 1 minute of inactivity (cost optimization)
  auto_suspend = 60
  auto_resume  = true

  # Single-cluster (appropriate for demo/dev)
  max_cluster_count = 1
  min_cluster_count = 1
}
