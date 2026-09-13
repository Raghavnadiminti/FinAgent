import os

from .postgres import PostgresDatabase
from .mongodb import MongoDatabase


class DatabaseFactory:

    @staticmethod
    def create(database_type: str):

        database_type = database_type.lower()

        if database_type == "postgres":

            return PostgresDatabase(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv(
                    "POSTGRES_DATABASE",
                    "accounting"
                ),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", "1234")
            )

        elif database_type == "mongodb":

            return MongoDatabase(
                uri=os.getenv(
                    "MONGODB_URI",
                    "mongodb://localhost:27017"
                ),
                database=os.getenv(
                    "MONGODB_DATABASE",
                    "ai_accountant"
                )
            )

        else:
            raise ValueError(
                f"Unsupported database: {database_type}"
            )