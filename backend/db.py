import os
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "DBMS_final_project"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

# --- 效能優化：建立連線池 (Connection Pool) ---
# 程式啟動時建立 1 到 20 條連線備用，不用每次都重新登入資料庫
try:
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        cursor_factory=RealDictCursor, # 讓查詢結果直接變字典
        **DB_CONFIG
    )
    print("Database connection pool created successfully")
except Exception as e:
    print(f"Error creating connection pool: {e}")
    connection_pool = None

@contextmanager
def get_db_connection():
    """
    這是一個 Context Manager。
    使用方式: 
    with get_db_connection() as conn:
        ...
    它會自動從池子拿連線，用完自動放回去 (putconn)，
    就算發生錯誤也會確保連線被歸還，不會造成連線洩漏。
    """
    if connection_pool is None:
        raise Exception("Connection pool is not initialized")
    
    conn = connection_pool.getconn()
    try:
        yield conn
        conn.commit() # 預設自動 Commit，避免資料沒存進去
    except Exception as e:
        conn.rollback() # 出錯就回滾
        raise e
    finally:
        connection_pool.putconn(conn) # 歸還連線

# --- User / Auth ---
def get_player_by_email(email):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "PLAYER" WHERE "email" = %s', (email,))
            return cur.fetchone()

def get_shop_by_name(name):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "SHOP" WHERE "s_name" = %s', (name,))
            return cur.fetchone()

def create_player(name, email, hashed_pw):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO "PLAYER" ("p_name", "email", "password") VALUES (%s, %s, %s)', (name, email, hashed_pw))
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def create_shop(name, addr, phone, hashed_pw):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO "SHOP" ("s_name", "s_addr", "s_phone", "password") VALUES (%s, %s, %s, %s)', (name, addr, phone, hashed_pw))
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

# --- Player Features ---
def get_player_cards(p_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c."c_name", c."c_rarity", phc."qty"
                FROM "PLAYER_HAS_CARD" phc
                JOIN "CARD" c ON phc."c_id" = c."c_id"
                WHERE phc."p_id" = %s
            """, (p_id,))
            return cur.fetchall()

def get_all_cards():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "c_id", "c_name" FROM "CARD"')
            return cur.fetchall()

def upsert_player_card(p_id, c_id, qty):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM "PLAYER_HAS_CARD" WHERE "p_id"=%s AND "c_id"=%s', (p_id, c_id))
                if cur.fetchone():
                    cur.execute('UPDATE "PLAYER_HAS_CARD" SET "qty" = "qty" + %s WHERE "p_id"=%s AND "c_id"=%s', (qty, p_id, c_id))
                else:
                    cur.execute('INSERT INTO "PLAYER_HAS_CARD" ("p_id", "c_id", "qty") VALUES (%s, %s, %s)', (p_id, c_id, qty))
        return True
    except Exception as e:
        print(e)
        return False

def get_player_decks(p_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d."d_id", d."d_name"
                FROM "DECK" d 
                JOIN "PLAYER_BUILDS_DECK" pbd ON d."d_id" = pbd."d_id" 
                WHERE pbd."p_id" = %s
            """, (p_id,))
            return cur.fetchall()

def create_deck(p_id, d_name):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO "DECK" ("d_name") VALUES (%s) RETURNING "d_id"', (d_name,))
                new_d_id = cur.fetchone()['d_id']
                cur.execute('INSERT INTO "PLAYER_BUILDS_DECK" ("p_id", "d_id") VALUES (%s, %s)', (p_id, new_d_id))
        return True
    except Exception as e:
        print(e)
        return False

# --- Shop Features ---
def get_shop_inventory(s_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p."prod_name", sp."qty", sp."price"
                FROM "SHOP_SELLS_PRODUCT" sp
                JOIN "PRODUCT" p ON sp."prod_id" = p."prod_id"
                WHERE sp."s_id" = %s
            """, (s_id,))
            return cur.fetchall()

def get_all_products_list():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "prod_id", "prod_name" FROM "PRODUCT"')
            return cur.fetchall()

def upsert_shop_product(s_id, prod_id, qty, price):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM "SHOP_SELLS_PRODUCT" WHERE "s_id"=%s AND "prod_id"=%s', (s_id, prod_id))
                if cur.fetchone():
                    cur.execute('UPDATE "SHOP_SELLS_PRODUCT" SET "qty"=%s, "price"=%s WHERE "s_id"=%s AND "prod_id"=%s', (qty, price, s_id, prod_id))
                else:
                    cur.execute('INSERT INTO "SHOP_SELLS_PRODUCT" ("s_id", "prod_id", "qty", "price") VALUES (%s, %s, %s, %s)', (s_id, prod_id, qty, price))
        return True
    except Exception as e:
        print(e)
        return False

def create_event(e_name, e_format, e_date, e_time, e_size, e_round, s_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO "EVENT" ("e_name", "e_format", "e_date", "e_time", "e_size", "e_roundtype", "org_shop_id")
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (e_name, e_format, e_date, e_time, e_size, e_round, s_id))
        return True
    except Exception as e:
        print(e)
        return False

# --- Common Features ---
def get_all_events():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "EVENT"')
            return cur.fetchall()

def get_all_shop_items():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s."s_name", p."prod_name", sp."price", sp."qty"
                FROM "SHOP_SELLS_PRODUCT" sp
                JOIN "SHOP" s ON sp."s_id" = s."s_id"
                JOIN "PRODUCT" p ON sp."prod_id" = p."prod_id"
            """)
            return cur.fetchall()