import psycopg2
from typing import Optional

from .interface import DatabaseInterface


class PostgresDB(DatabaseInterface):

    _instance: Optional["PostgresDB"] = None

    def __new__(cls, *args, **kwargs):

        if cls._instance is None:
            cls._instance = super().__new__(cls)

        return cls._instance

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str
    ):

        # Prevent initialization multiple times
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password

        self.connection = None

        self._initialized = True

    def connect(self):

        if self.connection is not None:
            return

        self.connection = psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password
        )

    def query(self, query: str, params=None):

        if self.connection is None:
            self.connect()

        cursor = self.connection.cursor()

        try:

            cursor.execute(query, params)

            if cursor.description:

                columns = [
                    column[0]
                    for column in cursor.description
                ]

                rows = cursor.fetchall()

                return [
                    dict(zip(columns, row))
                    for row in rows
                ]

            self.connection.commit()

            return {
                "success": True,
                "rows_affected": cursor.rowcount
            }

        except Exception:

            self.connection.rollback()
            raise

        finally:

            cursor.close()

    def close(self):

        if self.connection:

            self.connection.close()
            self.connection = None