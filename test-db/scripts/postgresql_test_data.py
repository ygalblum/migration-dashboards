""" Module for test table and data creation """
import json
import os

import psycopg2


class TestDBInitializer():  # pylint:disable=R0903
    """ DB initializer """
    def __init__(self) -> None:
        self._db_params = {
            'host': os.getenv("POSTGRESQL_HOST", "localhost"),
            'port': os.getenv("POSTGRESQL_PORT", '5432'),
            'user': os.getenv("POSTGRESQL_USER"),
            'password': os.getenv("POSTGRESQL_PASSWORD"),
            'dbname': os.getenv("POSTGRESQL_DATABASE"),

        }
        self._conn = None
        self._cursor = None

    def _connect(self):
        self._conn = psycopg2.connect(**self._db_params)
        self._cursor = self._conn.cursor()
        print("Database connection opened.")

    def _disconnect(self):
        self._cursor.close()
        self._conn.close()
        print("Database connection closed.")

    def _create_table(self):
        create_table_query = """
        CREATE TABLE IF NOT EXISTS my_table (
            id SERIAL PRIMARY KEY,
            data JSONB
        );
        """
        self._cursor.execute(create_table_query)
        self._conn.commit()
        print("Table created successfully.")

    def _insert_test_data(self):
        # Step 2: Insert JSON data into the table
        insert_query = """
        INSERT INTO my_table (data)
        VALUES (%s)
        RETURNING id;
        """
        json_data = json.dumps({"name": "John", "age": 30, "city": "New York"})

        self._cursor.execute(insert_query, (json_data,))
        inserted_id = self._cursor.fetchone()[0]
        self._conn.commit()
        print(f"Inserted JSON data with ID: {inserted_id}")

    def run(self):
        """ Run the initializer """
        self._connect()
        self._create_table()
        self._insert_test_data()
        self._disconnect()


if __name__ == "__main__":
    try:
        TestDBInitializer().run()
    except Exception as e:  # pylint:disable=W0718
        print(f"An error occurred: {e}")
