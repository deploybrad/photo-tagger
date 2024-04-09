import logging
import os
import sys

import psycopg2
from dotenv import find_dotenv, load_dotenv
from psycopg2 import sql

LOG_FILENAME = "../client_delete.log"
# Initialize logging
def setup_logging(debug=False):
    handlers = [logging.FileHandler(LOG_FILENAME), logging.StreamHandler(sys.stdout)]
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)s [%(filename)s-%(funcName)s:%(lineno)d] %(message)s",
        handlers=handlers,
    )

def main():
    load_dotenv(find_dotenv())
    # Retrieve environment variables
    DB_NAME = os.getenv("POSTGRES_DB")
    DB_USER = os.getenv("POSTGRES_USER")
    DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    DB_HOST = os.getenv("POSTGRES_HOST")
    DB_PORT = os.getenv("POSTGRES_PORT")

    try:
        # Connect to the PostgreSQL database
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT
        )

        # Create a cursor object
        cur = conn.cursor()
        cur.close()
        # SQL statement for creating table
        image_metadata_table = sql.SQL("""
        CREATE TABLE if not exists image_metadata (
            id SERIAL PRIMARY KEY,
            original_path VARCHAR(255) UNIQUE,
            processed_path VARCHAR(255),
            face_coordinates VARCHAR(255),
            aspect_ratio FLOAT4,
            processed_scale FLOAT4,
            landmarks JSONB,  -- Using JSONB for structured data handling
            exif_data JSONB,
            tags JSONB
        );
        """)


        cur = conn.cursor()
   
        # cur.execute("DROP TABLE image_metadata")
        cur.execute(image_metadata_table)
        conn.commit()
        cur.close()
        
        return True
    except psycopg2.DatabaseError as e:
        logging.error(f"An error occurred: {e}")
        return False
    finally:
        # Close the connection to avoid leaking resources
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    main()