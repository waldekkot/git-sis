"""Shared fixtures for unit tests (no Snowflake connection required)."""
import pytest
from snowflake.snowpark import Session


@pytest.fixture(scope="module")
def local_session():
    """Snowpark session in local-testing mode -- no Snowflake, no credentials."""
    sess = Session.builder.config("local_testing", True).create()
    yield sess
    sess.close()
