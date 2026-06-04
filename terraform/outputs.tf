output "database_name" {
  description = "Name of the Snowflake database"
  value       = snowflake_database.learning_db.name
}

output "warehouse_name" {
  description = "Name of the query warehouse"
  value       = snowflake_warehouse.app_warehouse.name
}

output "api_integration_name" {
  description = "Name of the GitHub App API integration"
  value       = snowflake_api_integration.github_app.name
}

output "setup_complete_message" {
  description = "Post-apply instructions"
  value       = <<-EOT
    Terraform apply complete. Next steps:
    1. Run: make setup         (create GIT_SIS schema + tables via DCM or SQL)
    2. Run: make setup-git     (create GIT REPOSITORY object using the API integration)
    3. Authorize GitHub App:   Snowsight → Workspace → Connect Git Repository
    4. Run: make deploy        (deploy the Streamlit app)
  EOT
}
