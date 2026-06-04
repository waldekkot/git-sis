# Database managed by Terraform.
# Note: Once imported, avoid creating the database manually — use terraform apply.
resource "snowflake_database" "learning_db" {
  name    = var.database_name
  comment = "Development/learning database for git-sis demo app and tutorials"
}
