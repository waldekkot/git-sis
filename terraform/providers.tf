terraform {
  required_version = ">= 1.9"

  required_providers {
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 1.0"
    }
  }

  # Recommended: configure remote state backend.
  # Uncomment and configure ONE of the following:
  #
  # AWS S3:
  # backend "s3" {
  #   bucket = "my-tf-state"
  #   key    = "git-sis/terraform.tfstate"
  #   region = "us-east-1"
  # }
  #
  # Terraform Cloud / HCP Terraform:
  # cloud {
  #   organization = "my-org"
  #   workspaces {
  #     name = "git-sis"
  #   }
  # }
  #
  # Local (development only, do NOT commit .tfstate):
  # (default when no backend is configured)
}

provider "snowflake" {
  # Authentication: uses environment variables by default.
  # Set these before running terraform plan/apply:
  #   SNOWFLAKE_ACCOUNT   e.g. sfseeurope-wkot_demo1
  #   SNOWFLAKE_USER      e.g. your Snowflake username
  #   SNOWFLAKE_PASSWORD  OR use key-pair: SNOWFLAKE_PRIVATE_KEY_PATH
  #
  # For CI: use SNOWFLAKE_PRIVATE_KEY (key-pair auth) or
  #         SNOWFLAKE_AUTHENTICATOR=EXTERNALBROWSER for local dev.
  #
  # See: https://registry.terraform.io/providers/Snowflake-Labs/snowflake/latest/docs
  account = var.snowflake_account
  role    = var.snowflake_role
}
