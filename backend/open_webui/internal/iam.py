"""AWS RDS IAM authentication helpers.

When DATABASE_AUTH=aws_iam, both the Peewee migration layer and the SQLAlchemy
runtime use this module to generate short-lived IAM auth tokens instead of
static passwords.  Tokens are valid for 15 minutes; callers generate a fresh
one on each new database connection so pool recycling is seamless.

The process must run with an IAM role / instance profile that has
``rds-db:connect`` permission for the target DB user.  RDS IAM auth mandates
TLS, so the startup validation in ``env.py`` ensures ``sslmode`` is set.
"""

import logging
import os

import boto3

log = logging.getLogger(__name__)

_rds_client = None
_rds_client_region = None


def _get_rds_client(region: str):
    """Return a cached boto3 RDS client, recreating only if the region changes."""
    global _rds_client, _rds_client_region
    if _rds_client is None or _rds_client_region != region:
        _rds_client = boto3.client('rds', region_name=region)
        _rds_client_region = region
    return _rds_client


def get_aws_region() -> str:
    """Resolve the AWS region from environment or boto3 session."""
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if not region:
        region = boto3.session.Session().region_name
    if not region:
        raise ValueError(
            'AWS_REGION or AWS_DEFAULT_REGION must be set for RDS IAM auth'
        )
    return region


def generate_rds_iam_token(
    host: str,
    port: int = 5432,
    user: str = 'openwebui_rw',
) -> str:
    """Generate a short-lived RDS IAM authentication token."""
    region = get_aws_region()
    client = _get_rds_client(region)
    token = client.generate_db_auth_token(
        DBHostname=host,
        Port=int(port),
        DBUsername=user,
    )
    log.debug('Generated RDS IAM auth token for %s@%s:%s', user, host, port)
    return token
