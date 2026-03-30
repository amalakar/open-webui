import logging
import os
from contextvars import ContextVar

from peewee import *
from peewee import InterfaceError as PeeWeeInterfaceError
from peewee import PostgresqlDatabase
from playhouse.db_url import connect, parse
from playhouse.shortcuts import ReconnectMixin

log = logging.getLogger(__name__)

db_state_default = {'closed': None, 'conn': None, 'ctx': None, 'transactions': None}
db_state = ContextVar('db_state', default=db_state_default.copy())


class PeeweeConnectionState(object):
    def __init__(self, **kwargs):
        super().__setattr__('_state', db_state)
        super().__init__(**kwargs)

    def __setattr__(self, name, value):
        self._state.get()[name] = value

    def __getattr__(self, name):
        value = self._state.get()[name]
        return value


class CustomReconnectMixin(ReconnectMixin):
    reconnect_errors = (
        # psycopg2
        (OperationalError, 'termin'),
        (InterfaceError, 'closed'),
        # peewee
        (PeeWeeInterfaceError, 'closed'),
    )


class ReconnectingPostgresqlDatabase(CustomReconnectMixin, PostgresqlDatabase):
    pass


class IAMPostgresqlDatabase(CustomReconnectMixin, PostgresqlDatabase):
    """PostgreSQL database that uses RDS IAM auth tokens instead of static passwords."""

    def _connect(self):
        from open_webui.internal.iam import generate_rds_iam_token

        self.connect_params['password'] = generate_rds_iam_token(
            host=self.connect_params.get('host'),
            port=self.connect_params.get('port', 5432),
            user=self.connect_params.get('user'),
        )
        return super()._connect()


def register_connection(db_url, use_iam_auth=False):
    # Check if using SQLCipher protocol
    if db_url.startswith('sqlite+sqlcipher://'):
        database_password = os.environ.get('DATABASE_PASSWORD')
        if not database_password or database_password.strip() == '':
            raise ValueError('DATABASE_PASSWORD is required when using sqlite+sqlcipher:// URLs')
        from playhouse.sqlcipher_ext import SqlCipherDatabase

        # Parse the database path from SQLCipher URL
        # Convert sqlite+sqlcipher:///path/to/db.sqlite to /path/to/db.sqlite
        db_path = db_url.replace('sqlite+sqlcipher://', '')

        # Use Peewee's native SqlCipherDatabase with encryption
        db = SqlCipherDatabase(db_path, passphrase=database_password)
        db.autoconnect = True
        db.reuse_if_open = True
        log.info('Connected to encrypted SQLite database using SQLCipher')

    else:
        # Standard database connection (existing logic)
        db = connect(db_url, unquote_user=True, unquote_password=True)
        if isinstance(db, PostgresqlDatabase):
            # Enable autoconnect for SQLite databases, managed by Peewee
            db.autoconnect = True
            db.reuse_if_open = True
            log.info('Connected to PostgreSQL database')

            # Get the connection details
            connection = parse(db_url, unquote_user=True, unquote_password=True)

            # Use IAM auth or standard reconnecting database
            db_class = IAMPostgresqlDatabase if use_iam_auth else ReconnectingPostgresqlDatabase
            db = db_class(**connection)
            db.connect(reuse_if_open=True)
        elif isinstance(db, SqliteDatabase):
            # Enable autoconnect for SQLite databases, managed by Peewee
            db.autoconnect = True
            db.reuse_if_open = True
            log.info('Connected to SQLite database')
        else:
            raise ValueError('Unsupported database connection')
    return db
