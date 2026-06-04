# Snowflake GitHub App API integration for git-connected Streamlit apps.
# Used by: deploy/10_git_and_streamlit.sql, make setup-git
#
# This integration enables:
#   - Snowsight Workspace git-sync (no PAT — uses GitHub App OAuth2)
#   - CREATE/ALTER GIT REPOSITORY with Snowflake-managed credentials
#   - make deploy-git / make deploy-sql (pull-based deploys)
#
# After terraform apply, authorize the GitHub App once in Snowsight:
#   Snowsight → Projects → any Workspace → Files tab → Connect Git Repository
#
resource "snowflake_api_integration" "github_app" {
  name                 = "GIT_API_WALDEKKOT"
  api_provider         = "git_https_api"
  api_allowed_prefixes = [var.github_api_prefix]
  comment              = "GitHub App OAuth2 integration for git-sis repo"
  enabled              = true

  # api_user_authentication block not needed for SNOWFLAKE_GITHUB_APP;
  # the Snowflake GitHub App handles authentication automatically.
  # Note: The Snowflake provider may require this field — see provider docs.
}

# Grant SYSADMIN-managed roles usage on the API integration
resource "snowflake_grant_privileges_to_role" "github_api_to_sysadmin" {
  privileges  = ["USAGE"]
  role_name   = "SYSADMIN"

  on_account_object {
    object_type = "INTEGRATION"
    object_name = snowflake_api_integration.github_app.name
  }
}
