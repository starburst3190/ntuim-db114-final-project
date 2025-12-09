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
                SELECT c."c_id", c."c_name" AS "卡牌名稱", c."c_rarity" AS "稀有度", phc."qty" AS "擁有量"
                FROM "PLAYER_HAS_CARD" phc
                JOIN "CARD" c ON phc."c_id" = c."c_id"
                WHERE phc."p_id" = %s
            """, (p_id,))
            return cur.fetchall()

def get_all_card_names_and_ids():
    """登錄卡牌功能用，回傳 ID、名稱和稀有度。"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "c_id", "c_name", "c_rarity" FROM "CARD"')
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
    
def delete_player_card(p_id, c_id, qty):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT "qty" FROM "PLAYER_HAS_CARD" WHERE "p_id"=%s AND "c_id"=%s', (p_id, c_id))
                original = cur.fetchone()['qty']
                if original - qty <= 0:
                    cur.execute('DELETE FROM "PLAYER_HAS_CARD" WHERE "p_id"=%s AND "c_id"=%s', (p_id, c_id))
                else:
                    cur.execute('UPDATE "PLAYER_HAS_CARD" SET "qty" = "qty" - %s WHERE "p_id"=%s AND "c_id"=%s', (qty, p_id, c_id))
        return True
    except Exception as e:
        print(e)
        return False

def get_player_decks(p_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d."d_id", d."d_name" AS "牌組名稱"
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

def remove_deck(p_id, d_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM "PLAYER_BUILDS_DECK" WHERE "p_id"=%s AND "d_id"=%s', (p_id, d_id))
        return True
    except Exception as e:
        print(e)
        return False

# --- 新增：牌組組成功能 ---
def get_deck_composition(d_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c."c_name" AS "卡牌名稱", dcoc."qty" AS "組成數量"
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
        
def join_event(p_id, e_id, d_id):
    SIZE_MAPPING = {
        "POD": 8, "LOCAL": 16, "REGIONAL": 32, "MAJOR": 64
    }
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT e_size FROM "EVENT" WHERE e_id = %s', (e_id,))
                event_row = cur.fetchone()
                if not event_row:
                    return {"success": False, "message": "賽事不存在"}
                
                e_size_str = event_row[0]
                limit_qty = SIZE_MAPPING.get(e_size_str)

                # 2-2. 計算目前已報名人數
                cur.execute("""
                    SELECT COUNT(*) FROM "PLAYER_PARTICIPATES_EVENT_WITH_DECK"
                    WHERE e_id = %s
                """, (e_id,))
                current_qty = cur.fetchone()[0]

                # 2-3. 比對 (如果 目前 >= 上限，就炸掉)
                if current_qty >= limit_qty:
                    return {"success": False, "message": f"報名失敗：人數已滿 ({current_qty}/{limit_qty})"}

                cur.execute("""
                    INSERT INTO "PLAYER_PARTICIPATES_EVENT_WITH_DECK" ("p_id", "e_id", "d_id") VALUES (%s, %s, %s)
                """, (p_id, e_id, d_id))
        return True
    except Exception as e:
        print(e)
        return False
        
def get_player_participations_detailed(p_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            sql = """
                SELECT 
                    pped."p_id",
                    pped."e_id",
                    pped."d_id",
                    e."e_name",
                    e."e_date",
                    e."e_format",
                    e."e_time",
                    s."s_name",
                    d."d_name"
                FROM "PLAYER_PARTICIPATES_EVENT_WITH_DECK" AS pped
                JOIN "EVENT" AS e ON pped.e_id = e.e_id
                JOIN "SHOP" AS s ON E.org_shop_id = s.s_id
                JOIN "DECK" AS d ON pped.d_id = d.d_id
                WHERE pped.p_id = %s
            """
            cur.execute(sql, (p_id,))
            return cur.fetchall()
        
def buy_product(p_id, s_id, prod_id, buy_qty):
    """
    [購買交易]
    1. 扣除商店架上庫存
    2. 建立銷售紀錄 (SALES + SALES_DETAIL)
    3. (若是卡片) 將商品加入玩家庫存
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT "qty", "price" FROM "SHOP_SELLS_PRODUCT" 
                    WHERE "s_id"=%s AND "prod_id"=%s 
                    FOR UPDATE
                """, (s_id, prod_id))
                row = cur.fetchone()
                
                if not row:
                    return {"success": False, "message": "商品已下架"}
                
                current_qty = row['qty'] if isinstance(row, dict) else row[0]
                price = row['price'] if isinstance(row, dict) else row[1]
                
                if current_qty < buy_qty:
                    return {"success": False, "message": f"庫存不足 (剩餘: {current_qty})"}

                cur.execute("""
                    UPDATE "SHOP_SELLS_PRODUCT" 
                    SET "qty" = "qty" - %s 
                    WHERE "s_id"=%s AND "prod_id"=%s
                """, (buy_qty, s_id, prod_id))

                import datetime
                now = datetime.datetime.now()
                cur.execute("""
                    INSERT INTO "SALES" ("datetime", "p_id", "s_id") 
                    VALUES (%s, %s, %s) 
                    RETURNING "sales_id"
                """, (now, p_id, s_id))
                
                sales_row = cur.fetchone()
                sales_id = sales_row['sales_id'] if isinstance(sales_row, dict) else sales_row[0]

                cur.execute("""
                    INSERT INTO "SALES_DETAIL" ("sales_id", "prod_id", "qty") 
                    VALUES (%s, %s, %s)
                """, (sales_id, prod_id, buy_qty))

                cur.execute('SELECT "c_id" FROM "PRODUCT" WHERE "prod_id"=%s', (prod_id,))
                prod_row = cur.fetchone()
                target_c_id = prod_row['c_id'] if isinstance(prod_row, dict) else prod_row[0]

                if target_c_id:
                    cur.execute('SELECT 1 FROM "PLAYER_HAS_CARD" WHERE "p_id"=%s AND "c_id"=%s', (p_id, target_c_id))
                    if cur.fetchone():
                        cur.execute("""
                            UPDATE "PLAYER_HAS_CARD" 
                            SET "qty" = "qty" + %s 
                            WHERE "p_id"=%s AND "c_id"=%s
                        """, (buy_qty, p_id, target_c_id))
                    else:
                        cur.execute("""
                            INSERT INTO "PLAYER_HAS_CARD" ("p_id", "c_id", "qty") 
                            VALUES (%s, %s, %s)
                        """, (p_id, target_c_id, buy_qty))

                return {"success": True, "message": f"訂單成立！請支付 ${price * buy_qty} 給店家"}

    except Exception as e:
        print(f"Buy Error: {e}")
        return {"success": False, "message": f"交易失敗: {str(e)}"}

# --- Shop Features ---
def get_shop_inventory(s_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p."prod_id", p."prod_name", p."prod_type", sp."qty", sp."price"
                FROM "SHOP_SELLS_PRODUCT" sp
                JOIN "PRODUCT" p ON sp."prod_id" = p."prod_id"
                WHERE sp."s_id" = %s
                ORDER BY p."prod_id"
            """, (s_id,))
            return cur.fetchall()

def get_shop_storage(s_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p."prod_id", p."prod_name", p."prod_type", st."qty"
                FROM "SHOP_STORES_PRODUCT" st
                JOIN "PRODUCT" p ON st."prod_id" = p."prod_id"
                WHERE st."s_id" = %s AND st."qty" > 0
                ORDER BY p."prod_id"
            """, (s_id,))
            return cur.fetchall()

def get_all_products_list():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "prod_id", "prod_name", "prod_type" FROM "PRODUCT"')
            return cur.fetchall()
        
def restock_shop_product(s_id, prod_id, qty):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 檢查倉庫是否已有此商品
                cur.execute('SELECT 1 FROM "SHOP_STORES_PRODUCT" WHERE "s_id"=%s AND "prod_id"=%s', (s_id, prod_id))
                if cur.fetchone():
                    cur.execute("""
                        UPDATE "SHOP_STORES_PRODUCT" 
                        SET "qty" = "qty" + %s 
                        WHERE "s_id"=%s AND "prod_id"=%s
                    """, (qty, s_id, prod_id))
                else:
                    cur.execute("""
                        INSERT INTO "SHOP_STORES_PRODUCT" ("s_id", "prod_id", "qty") 
                        VALUES (%s, %s, %s)
                    """, (s_id, prod_id, qty))
        return True
    except Exception as e:
        print(f"Restock Error: {e}")
        return False

def move_product_to_shelf(s_id, prod_id, move_qty, price):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # 1. 檢查倉庫庫存是否足夠
                cur.execute('SELECT "qty" FROM "SHOP_STORES_PRODUCT" WHERE "s_id"=%s AND "prod_id"=%s', (s_id, prod_id))
                row = cur.fetchone()
                
                if not row:
                    return {"success": False, "message": "倉庫中沒有此商品"}
                
                current_storage_qty = row['qty']
                if current_storage_qty < move_qty:
                    return {"success": False, "message": f"庫存不足 (目前: {current_storage_qty}, 欲上架: {move_qty})"}

                # 2. 扣除倉庫數量
                # 這裡我們保留紀錄但數量變少，若為0也可以選擇刪除，這邊選擇保留並設為剩餘量
                cur.execute("""
                    UPDATE "SHOP_STORES_PRODUCT" 
                    SET "qty" = "qty" - %s 
                    WHERE "s_id"=%s AND "prod_id"=%s
                """, (move_qty, s_id, prod_id))

                # 3. 新增或更新架上商品 (SHOP_SELLS_PRODUCT)
                cur.execute('SELECT 1 FROM "SHOP_SELLS_PRODUCT" WHERE "s_id"=%s AND "prod_id"=%s', (s_id, prod_id))
                if cur.fetchone():
                    # 若架上已有，增加數量並更新價格
                    cur.execute("""
                        UPDATE "SHOP_SELLS_PRODUCT" 
                        SET "qty" = "qty" + %s, "price" = %s 
                        WHERE "s_id"=%s AND "prod_id"=%s
                    """, (move_qty, price, s_id, prod_id))
                else:
                    # 若架上沒有，新增
                    cur.execute("""
                        INSERT INTO "SHOP_SELLS_PRODUCT" ("s_id", "prod_id", "qty", "price") 
                        VALUES (%s, %s, %s, %s)
                    """, (s_id, prod_id, move_qty, price))
                return {"success": True, "message": "上架成功"}
    except Exception as e:
        print(f"Move to Shelf Error: {type(e).__name__}: {str(e)}")
        return {"success": False, "message": f"系統錯誤: {type(e).__name__}: {str(e)}"}

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

def get_sales_detail(s_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    sa."sales_id",
                    sa."datetime",
                    sa."p_id",
                    pl."p_name",
                    sd."prod_id",
                    pr."prod_name",
                    pr."prod_type",
                    sd."qty"
                FROM "SALES_DETAIL" sd
                JOIN "SALES" sa ON sd."sales_id" = sa."sales_id"
                JOIN "PLAYER" pl ON sa."p_id" = pl."p_id"
                JOIN "PRODUCT" pr ON sd."prod_id" = pr."prod_id"
                WHERE sa."s_id" = %s
                ORDER BY sa."datetime" DESC
            """, (s_id,))
            return cur.fetchall()

# --- Common Features ---
def get_all_events():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e."e_id", e."e_name", e."e_date", e."e_time", e."e_size", e."e_format", e."e_roundtype", s."s_name", COUNT(p."p_id") as current_participants
                FROM "EVENT" AS e
                JOIN "SHOP" AS s ON e."org_shop_id" = s."s_id"
                LEFT JOIN "PLAYER_PARTICIPATES_EVENT_WITH_DECK" AS p ON e."e_id" = p."e_id"
                GROUP BY e."e_id", s."s_name"
            """)
            return cur.fetchall()
        
def get_market_listings():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    sp."s_id", 
                    s."s_name", 
                    sp."prod_id", 
                    p."prod_name", 
                    p."prod_type", 
                    sp."price", 
                    sp."qty",
                    p."c_id"
                FROM "SHOP_SELLS_PRODUCT" sp
                JOIN "PRODUCT" p ON sp."prod_id" = p."prod_id"
                JOIN "SHOP" s ON sp."s_id" = s."s_id"
                WHERE sp."qty" > 0
                ORDER BY sp."price" ASC
            """)
            return cur.fetchall()