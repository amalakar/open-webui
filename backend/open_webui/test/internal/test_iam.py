import pytest
from unittest.mock import patch, MagicMock

from open_webui.internal.iam import generate_rds_iam_token, get_aws_region


def test_port_cast_to_int_from_string(monkeypatch):
    """Peewee's URL parser returns port as a string; generate_db_auth_token expects int."""
    monkeypatch.setenv('AWS_REGION', 'us-west-2')
    mock_client = MagicMock()
    mock_client.generate_db_auth_token.return_value = 'token'

    with patch('open_webui.internal.iam._get_rds_client', return_value=mock_client):
        generate_rds_iam_token(host='db.example.com', port='5432', user='app')

    mock_client.generate_db_auth_token.assert_called_once_with(
        DBHostname='db.example.com',
        Port=5432,
        DBUsername='app',
    )


def test_raises_when_no_region_configured(monkeypatch):
    """Must fail fast if no AWS region is resolvable."""
    monkeypatch.delenv('AWS_REGION', raising=False)
    monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)
    with patch('open_webui.internal.iam.boto3') as mock_boto3:
        mock_boto3.session.Session.return_value.region_name = None
        with pytest.raises(ValueError, match='AWS_REGION'):
            get_aws_region()


def test_raises_when_host_missing():
    with pytest.raises(ValueError, match='DATABASE_HOST'):
        generate_rds_iam_token(host=None, port=5432, user='app')


def test_raises_when_user_missing():
    with pytest.raises(ValueError, match='DATABASE_USER'):
        generate_rds_iam_token(host='db.example.com', port=5432, user=None)
