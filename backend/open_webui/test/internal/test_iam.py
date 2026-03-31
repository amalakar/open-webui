import os
import pytest
from unittest.mock import patch, MagicMock

from open_webui.internal.iam import (
    generate_rds_iam_token,
    get_aws_region,
    _get_rds_client,
)


class TestGetAwsRegion:
    def test_from_aws_region(self, monkeypatch):
        monkeypatch.setenv('AWS_REGION', 'us-west-2')
        monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)
        assert get_aws_region() == 'us-west-2'

    def test_from_aws_default_region(self, monkeypatch):
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.setenv('AWS_DEFAULT_REGION', 'eu-central-1')
        assert get_aws_region() == 'eu-central-1'

    def test_aws_region_takes_precedence(self, monkeypatch):
        monkeypatch.setenv('AWS_REGION', 'us-west-2')
        monkeypatch.setenv('AWS_DEFAULT_REGION', 'eu-central-1')
        assert get_aws_region() == 'us-west-2'

    def test_falls_back_to_boto3_session(self, monkeypatch):
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)
        with patch('open_webui.internal.iam.boto3') as mock_boto3:
            mock_boto3.session.Session.return_value.region_name = 'ap-southeast-1'
            assert get_aws_region() == 'ap-southeast-1'

    def test_raises_when_no_region(self, monkeypatch):
        monkeypatch.delenv('AWS_REGION', raising=False)
        monkeypatch.delenv('AWS_DEFAULT_REGION', raising=False)
        with patch('open_webui.internal.iam.boto3') as mock_boto3:
            mock_boto3.session.Session.return_value.region_name = None
            with pytest.raises(ValueError, match='AWS_REGION'):
                get_aws_region()


class TestGenerateRdsIamToken:
    def test_generates_token(self, monkeypatch):
        monkeypatch.setenv('AWS_REGION', 'us-west-2')
        mock_client = MagicMock()
        mock_client.generate_db_auth_token.return_value = 'mock-iam-token-123'

        with patch('open_webui.internal.iam._get_rds_client', return_value=mock_client):
            token = generate_rds_iam_token(
                host='mydb.cluster-xxx.us-west-2.rds.amazonaws.com',
                port=5432,
                user='openwebui_rw',
            )

        assert token == 'mock-iam-token-123'
        mock_client.generate_db_auth_token.assert_called_once_with(
            DBHostname='mydb.cluster-xxx.us-west-2.rds.amazonaws.com',
            Port=5432,
            DBUsername='openwebui_rw',
        )

    def test_port_cast_to_int(self, monkeypatch):
        """Peewee URL parser may return port as a string."""
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


class TestGetRdsClient:
    def test_caches_client(self, monkeypatch):
        """Client should be reused for the same region."""
        import open_webui.internal.iam as iam_module

        # Reset cache
        iam_module._rds_client = None
        iam_module._rds_client_region = None

        with patch('open_webui.internal.iam.boto3') as mock_boto3:
            client1 = _get_rds_client('us-west-2')
            client2 = _get_rds_client('us-west-2')

            assert client1 is client2
            mock_boto3.client.assert_called_once_with('rds', region_name='us-west-2')

    def test_recreates_on_region_change(self, monkeypatch):
        """Client should be recreated if region changes."""
        import open_webui.internal.iam as iam_module

        iam_module._rds_client = None
        iam_module._rds_client_region = None

        with patch('open_webui.internal.iam.boto3') as mock_boto3:
            client1 = _get_rds_client('us-west-2')
            client2 = _get_rds_client('eu-central-1')

            assert client1 is not client2
            assert mock_boto3.client.call_count == 2
