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
try:
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=20,
        cursor_factory=RealDictCursor, 
        **DB_CONFIG
    )
    print("Database connection pool created successfully")
except Exception as e:
    print(f"Error creating connection pool: {e}")
    connection_pool = None

@contextmanager
def get_db_connection():
    if connection_pool is None:
        raise Exception("Connection pool is not initialized")
    
    conn = connection_pool.getconn()
    try:
        yield conn
        conn.commit() 
    except Exception as e:
        conn.rollback() 
        raise e
    finally:
        connection_pool.putconn(conn) 

# --- User / Auth (不變) ---
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

def get_all_card_names_and_ids():
    """為了登錄卡牌功能，只回傳 ID 和名稱。"""
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

# --- 新增：牌組組成功能 ---
def get_deck_composition(d_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c."c_name", dcoc."qty"
                FROM "DECK_CONSISTS_OF_CARD" dcoc
                JOIN "CARD" c ON dcoc."c_id" = c."c_id"
                WHERE dcoc."d_id" = %s
            """, (d_id,))
            return cur.fetchall()

def upsert_deck_card(d_id, c_id, qty):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 檢查是否已存在，並更新數量
                cur.execute('SELECT 1 FROM "DECK_CONSISTS_OF_CARD" WHERE "d_id"=%s AND "c_id"=%s', (d_id, c_id))
                if cur.fetchone():
                    if qty > 0:
                        cur.execute('UPDATE "DECK_CONSISTS_OF_CARD" SET "qty"=%s WHERE "d_id"=%s AND "c_id"=%s', (qty, d_id, c_id))
                    else:
                        # 數量為 0 時刪除
                        cur.execute('DELETE FROM "DECK_CONSISTS_OF_CARD" WHERE "d_id"=%s AND "c_id"=%s', (d_id, c_id))
                elif qty > 0:
                    # 不存在且數量大於 0 時插入
                    cur.execute('INSERT INTO "DECK_CONSISTS_OF_CARD" ("d_id", "c_id", "qty") VALUES (%s, %s, %s)', (d_id, c_id, qty))
        return True
    except Exception as e:
        print(e)
        return False

# --- 核心新增：缺卡計算邏輯 ---
def get_missing_cards_for_deck(p_id, d_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                -- DCOC: Deck Consists Of Card (牌組需求)
                -- PHC: Player Has Card (玩家擁有)
                SELECT
                    c."c_name" AS "卡牌名稱",
                    dco."qty" AS "牌組需求量",
                    COALESCE(phc."qty", 0) AS "玩家擁有量",
                    (dco."qty" - COALESCE(phc."qty", 0)) AS "缺少數量"
                FROM "DECK_CONSISTS_OF_CARD" dco
                JOIN "CARD" c ON dco."c_id" = c."c_id"
                -- LEFT JOIN 確保即使玩家沒擁有，也能看到牌組需求
                LEFT JOIN "PLAYER_HAS_CARD" phc 
                    ON dco."c_id" = phc."c_id" AND phc."p_id" = %s
                WHERE dco."d_id" = %s
                  -- 只顯示「缺少數量」大於 0 的記錄
                  AND (dco."qty" - COALESCE(phc."qty", 0)) > 0
                ORDER BY "缺少數量" DESC;
            """, (p_id, d_id))
            return cur.fetchall()

# --- 核心新增：卡牌篩選查詢 ---
def filter_cards(c_name=None, c_type=None, c_rarity=None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    c."c_name" AS "卡牌名稱", 
                    c."c_type" AS "類型", 
                    c."c_rarity" AS "稀有度", 
                    s."series_name" AS "所屬系列"
                FROM "CARD" c
                LEFT JOIN "SERIES" s ON c."series_id" = s."series_id"
                WHERE 1=1
            """
            params = []
            
            # 動態建立 WHERE 條件
            if c_name:
                query += " AND c.\"c_name\" ILIKE %s" # ILIKE 實現大小寫不敏感搜尋
                params.append(f'%{c_name}%')
            if c_type:
                query += " AND c.\"c_type\" IN %s"
                params.append(tuple(c_type))
            if c_rarity:
                query += " AND c.\"c_rarity\" = %s"
                params.append(c_rarity)
            
            query += " ORDER BY c.\"c_name\""
            
            cur.execute(query, tuple(params))
            return cur.fetchall()

# --- Shop Features (不變) ---
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

# --- Common Features (不變) ---
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