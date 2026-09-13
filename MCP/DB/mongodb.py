from pymongo import MongoClient
from .interface import DatabaseInterface


class MongoDatabase(DatabaseInterface):

    def __init__(
        self,
        uri: str,
        database: str
    ):
        self.uri = uri
        self.database_name = database

        self.client = None
        self.database = None

    def connect(self):

        self.client = MongoClient(self.uri)

        self.database = self.client[self.database_name]

    def query(
        self,
        collection: str,
        filter: dict | None = None,
        projection: dict | None = None
    ):

        if self.database is None:
            raise RuntimeError("Database is not connected")

        filter = filter or {}

        cursor = self.database[collection].find(
            filter,
            projection
        )

        return list(cursor)

    def close(self):

        if self.client:
            self.client.close()

            self.client = None
            self.database = None  

