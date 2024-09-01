from sqlalchemy import text, create_engine
from sqlalchemy.engine import Engine
import os
from dotenv import load_dotenv

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
        

def insert_flyer_record(flyer_id, flyer_url, valid_until, table, engine):
    query = text(f"""
                 INSERT INTO {table} 
                 (flyer_id, flyer_url, valid_until)
                 VALUES (:flyer_id, :flyer_url, :valid_until)
                 """) 

    try:
        with engine.connect() as connection:
            connection.execute(query, 
                               {
                                "flyer_id": flyer_id,
                                "flyer_url": flyer_url,
                                "valid_until": valid_until
                                })
            connection.commit()
    except Exception as e:
        print(f"Error adding flyer record to database: {e}")
        

def insert_value_in_column(value, column, table, engine):
    query = text(f"""
                 INSERT INTO {table} 
                 ({column})
                 VALUES (:value)
                 """) 

    try:
        with engine.connect() as connection:
            connection.execute(query, {"value": value})
            connection.commit()
    except Exception as e:
        print(f"Error adding chain_name record to database: {e}")



def insert_product_record(product_infos, table, engine):
    query = text(f"""
                 INSERT INTO {table} 
                 (product_id, product_name, price, url, unit, flyer_id)
                 VALUES (:product_id, :product_name, :price, :url, :unit, :flyer_id)
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
                                "flyer+id": product_infos["flyer_id"]
                                })
            connection.commit()
    except Exception as e:
        print(f"Error adding flyer record to database: {e}")