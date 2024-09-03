from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

def get_sql_engine_from_env() -> Engine:
    """
    Create a SQLAlchemy engine using environment variables.

    Returns:
        Engine: SQLAlchemy engine connected to the database.
    """
    username = os.getenv("DATABASE_USERNAME")
    password = os.getenv("DATABASE_PASSWORD")
    host = os.getenv("DATABASE_HOST")
    db = os.getenv("DATABASE_NAME")
    port = os.getenv("DATABASE_PORT", "5432")

    return create_engine(f"postgresql://{username}:{password}@{host}:{port}/{db}")


def insert_store_chain_record(chain_name, table, engine):
    query = text(f"""
                 INSERT INTO {table} 
                 (chain_name)
                 VALUES (:chain_name)
                 """) 

    try:
        with engine.connect() as connection:
            connection.execute(query, {"chain_name": chain_name})
            connection.commit()
    except Exception as e:
        print(f"Error adding chain_name record to database: {e}")
        

def insert_flyer_record(flyer_id, flyer_url, valid_until, store_chain, table, engine):
    query = text(f"""
                 INSERT INTO {table} 
                 (flyer_id, flyer_url, valid_until, store_chain)
                 VALUES (:flyer_id, :flyer_url, :valid_until, :store_chain)
                 """) 

    try:
        with engine.connect() as connection:
            connection.execute(query, 
                               {
                                "flyer_id": flyer_id,
                                "flyer_url": flyer_url,
                                "valid_until": valid_until,
                                "store_chain": store_chain
                                })
            connection.commit()
    except Exception as e:
        print(f"Error adding flyer record to database: {e}")
        

def insert_product_record(product_infos, table, engine):
    query = text(f"""
                 INSERT INTO {table} 
                 (product_id, product_name, price, url, unit, flyer_id, image_url)
                 VALUES (:product_id, :product_name, :price, :url, :unit, :flyer_id, :image_url)
                 """) 

    try:
        with engine.connect() as connection:
            connection.execute(query, 
                               {
                                "product_id": product_infos["product_id"],
                                "product_name": product_infos["product_name"],
                                "price": product_infos["price"],
                                "url": product_infos["url"],
                                "unit": product_infos["unit"],
                                "flyer_id": product_infos["flyer_id"],
                                "image_url": product_infos["product_image_url"]
                                })
            connection.commit()
    except Exception as e:
        print(f"Error adding flyer record to database: {e}")


def flyer_exists(flyer_id, table, engine):
    query = text(f"""
                 SELECT flyer_id 
                 FROM {table}
                 WHERE flyer_id = :flyer_id
                 """) 
    try:
        with engine.connect() as connection:
            result = connection.execute(query, {"flyer_id": flyer_id})
            flyer = result.fetchone()
            return flyer is not None
    except Exception as e:
        print(f"Error checking if flyer exists: {e}")
        return False


def delete_old_flyers_and_products(product_table, flyer_table, engine):
    eastern_timezone = pytz.timezone('America/Toronto')
    today = datetime.now(eastern_timezone).date()
    
    # Step 1: Retrieve all flyer_ids that have a valid_until date in the past
    select_query = text(f"""
        SELECT flyer_id 
        FROM {flyer_table} 
        WHERE valid_until < :today
    """)
    
    try:
        with engine.connect() as connection:
            old_flyers = connection.execute(select_query, {"today": today}).fetchall()
            old_flyer_ids = [row[0] for row in old_flyers]

            if not old_flyer_ids:
                print("No old flyers found.")
                return

            # Step 2: Delete products associated with old flyers
            delete_products_query = text(f"""
                DELETE FROM {product_table}
                WHERE flyer_id = ANY(:old_flyer_ids)
            """)
            connection.execute(delete_products_query, {"old_flyer_ids": old_flyer_ids})

            # Step 3: Delete old flyers
            delete_flyers_query = text(f"""
                DELETE FROM {flyer_table}
                WHERE flyer_id = ANY(:old_flyer_ids)
            """)
            connection.execute(delete_flyers_query, {"old_flyer_ids": old_flyer_ids})

            connection.commit()
            print(f"Deleted {len(old_flyer_ids)} old flyers and associated products.")

    except Exception as e:
        print(f"Error deleting old flyers and products: {e}")


def get_unretrieved_flyers(table, engine):
    query = text(f"""
                 SELECT flyer_id, flyer_url 
                 FROM {table}
                 WHERE retrieved = 'false'
                 """) 
    try:
        with engine.connect() as connection:
            result = connection.execute(query)
            flyers = result.fetchall()
            return flyers
    except Exception as e:
        print(f"Error getting unretrieved flyers: {e}")
        return None


def set_flyer_retrieved_to_true(flyer_id, table, engine):
    query = text(f"""
                 UPDATE {table} 
                 SET retrieved = 'true'
                 WHERE flyer_id = :flyer_id
                 """)
    try:
        with engine.connect() as connection:
            result = connection.execute(query, {"flyer_id": flyer_id})
            if result.rowcount == 0:
                print(f"No rows updated for flyer_id: {flyer_id}")
    except Exception as e:
        print(f"Error setting flyer retrieved value to true: {e}")
        