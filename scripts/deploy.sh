#!/usr/bin/env bash
# deploy.sh -- deploy (or redeploy) the Streamlit app to Snowflake.
#
# Normal usage (redeploy after a git push):
#   scripts/deploy.sh
#
# First-time bootstrap (wire API integration + git repo, then deploy):
#   scripts/deploy.sh --bootstrap
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'oregon-sedemo')
#       --bootstrap         Run the full first-time setup (sections 1+2 of deploy/10)
#                           before the redeploy loop.  Requires ACCOUNTADMIN access.
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

BOOTSTRAP=false

show_help() {
    cat <<EOF
git-sis $VERSION -- deploy

Redeploys SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE from the git repo:
  1. ALTER GIT REPOSITORY ... FETCH        (pull latest commit from GitHub)
  2. CREATE OR REPLACE STREAMLIT ... FROM  (snapshot from git clone)
  3. ALTER STREAMLIT ... ADD LIVE VERSION  (make it live)

With --bootstrap, also creates the API integration, PAT secret reference,
and GIT REPOSITORY object (one-time setup, needs ACCOUNTADMIN).

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
        --bootstrap         Full first-time wiring before the redeploy loop
    -h, --help              Show this help text
        --version           Print version and exit

EXAMPLES
    # Normal redeploy after git push
    git push && scripts/deploy.sh

    # First-time setup (creates integration, git repo, and deploys)
    scripts/deploy.sh --bootstrap
EOF
}

parse_common_args "$@"
set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --bootstrap) BOOTSTRAP=true ;;
        *) die "Unknown argument: $1. Run with --help for usage." ;;
    esac
    shift
done

DB="SNOWFLAKE_LEARNING_DB"
SCHEMA="GIT_SIS"
REPO="$DB.$SCHEMA.APP_REPO"
APP="$DB.$SCHEMA.INGEST_CONSOLE"
WH="COMPUTE_WH"
POOL="SYSTEM_COMPUTE_POOL_CPU"
EAI="PYPI_ACCESS_INTEGRATION"
RUNTIME="SYSTEM\$ST_CONTAINER_RUNTIME_PY3_11"

if [[ "$BOOTSTRAP" == true ]]; then
    info "Bootstrap mode -- creating API integration, git repo ..."
    warn "This requires ACCOUNTADMIN access. You will be prompted if your role lacks it."
    snow sql -c "$CONN" -q "
        USE ROLE ACCOUNTADMIN;
        CREATE API INTEGRATION IF NOT EXISTS git_api_waldekkot
            API_PROVIDER = git_https_api
            API_ALLOWED_PREFIXES = ('https://github.com/waldekkot')
            ALLOWED_AUTHENTICATION_SECRETS = (GIT_SIS_INFRA.SECRETS.GITHUB_PAT)
            ENABLED = TRUE;
        GRANT USAGE ON INTEGRATION git_api_waldekkot TO ROLE SYSADMIN;
        USE ROLE SYSADMIN;
        CREATE GIT REPOSITORY IF NOT EXISTS $REPO
            API_INTEGRATION = git_api_waldekkot
            GIT_CREDENTIALS = GIT_SIS_INFRA.SECRETS.GITHUB_PAT
            ORIGIN = 'https://github.com/waldekkot/git-sis';
    "
    success "Bootstrap complete."
fi

info "Fetching latest commit from GitHub ..."
snow sql -c "$CONN" -q "USE ROLE SYSADMIN; ALTER GIT REPOSITORY $REPO FETCH;"

info "Creating Streamlit app from git on container runtime ..."
snow sql -c "$CONN" -q "
    USE ROLE SYSADMIN;
    CREATE OR REPLACE STREAMLIT $APP
        FROM '@$REPO/branches/main/app/'
        MAIN_FILE = 'streamlit_app.py'
        QUERY_WAREHOUSE = $WH
        RUNTIME_NAME = '$RUNTIME'
        COMPUTE_POOL = $POOL
        EXTERNAL_ACCESS_INTEGRATIONS = ($EAI)
        TITLE = 'Ingestion Ops Console';
    ALTER STREAMLIT $APP ADD LIVE VERSION FROM LAST;
"

success "Deployed: $APP"
info "Run 'scripts/verify.sh' to confirm and get the URL."
