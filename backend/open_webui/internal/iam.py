"""AWS RDS IAM authentication helpers.

When DATABASE_AUTH=iam, both the Peewee migration layer and the SQLAlchemy
runtime use this module to generate short-lived IAM auth tokens instead of
static passwords.  Tokens are valid for 15 minutes; callers generate a fresh
one on each new database connection so pool recycling is seamless.

The process must run with an IAM role / instance profile that has
``rds-db:connect`` permission for the target DB user, and ``sslmode=require``
should be set on the connection since RDS IAM auth mandates TLS.
"""

import logging
import os

import boto3

log = logging.getLogger(__name__)


def generate_rds_iam_token(
    host: str,
    port: int = 5432,
    user: str = 'openwebui_rw',
) -> str:
    """Generate a short-lived RDS IAM authentication token."""
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if not region:
        region = boto3.session.Session().region_name

    if not region:
        raise ValueError(
            'AWS_REGION or AWS_DEFAULT_REGION must be set for RDS IAM auth'
        )

    client = boto3.client('rds', region_name=region)
    token = client.generate_db_auth_token(
        DBHostname=host,
        Port=port,
        DBUsername=user,
    )
    log.debug('Generated RDS IAM auth token for %s@%s:%s', user, host, port)
    return token
