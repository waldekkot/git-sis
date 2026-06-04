variable "snowflake_account" {
  description = "Snowflake account identifier (no .snowflakecomputing.com suffix)"
  type        = string
  default     = "sfseeurope-wkot_demo1"
}

variable "snowflake_role" {
  description = "Snowflake role used to apply Terraform changes (requires SYSADMIN or equivalent)"
  type        = string
  default     = "SYSADMIN"
}

variable "environment" {
  description = "Target environment name: dev, ci, prod"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "ci", "prod"], var.environment)
    error_message = "environment must be one of: dev, ci, prod"
  }
}

variable "database_name" {
  description = "Name of the database managed by this Terraform workspace"
  type        = string
  default     = "SNOWFLAKE_LEARNING_DB"
}

variable "warehouse_name" {
  description = "Name of the query warehouse used by the Streamlit app"
  type        = string
  default     = "COMPUTE_WH"
}

variable "warehouse_size" {
  description = "Warehouse size (X-Small, Small, Medium, ...)"
  type        = string
  default     = "X-Small"
}

variable "github_repo_url" {
  description = "GitHub repository URL for the Snowflake Git integration"
  type        = string
  default     = "https://github.com/waldekkot/git-sis"
}

variable "github_api_prefix" {
  description = "GitHub API prefix for the Snowflake API integration (owner path)"
  type        = string
  default     = "https://github.com/waldekkot"
}
