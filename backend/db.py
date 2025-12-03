import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "DBMS_final_project"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "password"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None

# --- User / Auth ---
def get_player_by_email(email):
    conn = get_db_connection()
    if not conn: return None
    with conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "PLAYER" WHERE "email" = %s', (email,))
            return cur.fetchone()

def get_shop_by_name(name):
    conn = get_db_connection()
    if not conn: return None
    with conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "SHOP" WHERE "s_name" = %s', (name,))
            return cur.fetchone()

def create_player(name, email, hashed_pw):
    conn = get_db_connection()
    if not conn: return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO "PLAYER" ("p_name", "email", "password") VALUES (%s, %s, %s)', (name, email, hashed_pw))
        return True
    except Exception as e:
        print(e)
        return False

def create_shop(name, addr, phone, hashed_pw):
    conn = get_db_connection()
    if not conn: return False
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO "SHOP" ("s_name", "s_addr", "s_phone", "password") VALUES (%s, %s, %s, %s)', (name, addr, phone, hashed_pw))
        return True
    except Exception as e:
        print(e)
        return False

# --- Player Features ---
def get_player_cards(p_id):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c."c_name", c."c_rarity", phc."qty"
                FROM "PLAYER_HAS_CARD" phc
                JOIN "CARD" c ON phc."c_id" = c."c_id"
                WHERE phc."p_id" = %s
            """, (p_id,))
            return cur.fetchall()

def get_all_cards():
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "c_id", "c_name" FROM "CARD"')
            return cur.fetchall()

def upsert_player_card(p_id, c_id, qty):
    """新增或更新玩家擁有的卡片"""
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                # 先檢查有沒有
                cur.execute('SELECT * FROM "PLAYER_HAS_CARD" WHERE "p_id"=%s AND "c_id"=%s', (p_id, c_id))
                exist = cur.fetchone()
                if exist:
                    cur.execute('UPDATE "PLAYER_HAS_CARD" SET "qty" = "qty" + %s WHERE "p_id"=%s AND "c_id"=%s', (qty, p_id, c_id))
                else:
                    cur.execute('INSERT INTO "PLAYER_HAS_CARD" ("p_id", "c_id", "qty") VALUES (%s, %s, %s)', (p_id, c_id, qty))
        return True
    except Exception as e:
        print(e)
        return False

def get_player_decks(p_id):
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d."d_id", d."d_name"
                FROM "DECK" d 
                JOIN "PLAYER_BUILDS_DECK" pbd ON d."d_id" = pbd."d_id" 
                WHERE pbd."p_id" = %s
            """, (p_id,))
            return cur.fetchall()

def create_deck(p_id, d_name):
    conn = get_db_connection()
    try:
        with conn:
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
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p."prod_name", sp."qty", sp."price"
                FROM "SHOP_SELLS_PRODUCT" sp
                JOIN "PRODUCT" p ON sp."prod_id" = p."prod_id"
                WHERE sp."s_id" = %s
            """, (s_id,))
            return cur.fetchall()

def get_all_products_list():
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "prod_id", "prod_name" FROM "PRODUCT"')
            return cur.fetchall()

def upsert_shop_product(s_id, prod_id, qty, price):
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM "SHOP_SELLS_PRODUCT" WHERE "s_id"=%s AND "prod_id"=%s', (s_id, prod_id))
                if cur.fetchone():
                    cur.execute('UPDATE "SHOP_SELLS_PRODUCT" SET "qty"=%s, "price"=%s WHERE "s_id"=%s AND "prod_id"=%s', (qty, price, s_id, prod_id))
                else:
                    cur.execute('INSERT INTO "SHOP_SELLS_PRODUCT" ("s_id", "prod_id", "qty", "price") VALUES (%s, %s, %s, %s)', (s_id, prod_id, qty, price))
        return True
    except Exception as e:
        print(e)
        return False

def create_event(e_name, e_format, e_date, e_time, e_size, e_round, s_id):
    conn = get_db_connection()
    try:
        with conn:
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
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM "EVENT"')
            return cur.fetchall()

def get_all_shop_items():
    conn = get_db_connection()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s."s_name", p."prod_name", sp."price", sp."qty"
                FROM "SHOP_SELLS_PRODUCT" sp
                JOIN "SHOP" s ON sp."s_id" = s."s_id"
                JOIN "PRODUCT" p ON sp."prod_id" = p."prod_id"
            """)
            return cur.fetchall()