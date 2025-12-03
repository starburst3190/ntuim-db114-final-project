import streamlit as st
import psycopg2
import pandas as pd
import bcrypt  # 記得先 pip install bcrypt
import datetime

# ---------------------------------------------------------
# 1. 資料庫連線設定
# ---------------------------------------------------------
DB_CONFIG = {
    "dbname": "DBMS_final_project",
    "user": "postgres",
    "password": "fuck",  # ⚠️ 你的密碼
    "host": "localhost",
    "port": "5433"
}

# ---------------------------------------------------------
# 2. 資料庫功能函數 & 密碼處理
# ---------------------------------------------------------
def get_connection():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        st.error(f"無法連接資料庫: {e}")
        return None

def run_query(query, params=None):
    conn = get_connection()
    if conn:
        try:
            df = pd.read_sql(query, conn, params=params)
            conn.close()
            return df
        except Exception as e:
            st.error(f"查詢錯誤: {e}")
            conn.close()
            return pd.DataFrame()
    return pd.DataFrame()

def run_command(command, params=None):
    conn = get_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(command, params)
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            st.error(f"執行錯誤: {e}")
            conn.close()
            return False
    return False

# --- 新增：密碼雜湊函數 ---
def hash_password(password):
    """將明碼轉為 Hash"""
    # bcrypt 需要 bytes 格式，所以要 encode
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8') # 存入資料庫時轉回字串

def check_password(password, hashed_password):
    """比對明碼與資料庫中的 Hash 是否相符"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

# ---------------------------------------------------------
# 3. Session State 初始化
# ---------------------------------------------------------
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_type' not in st.session_state:
    st.session_state['user_type'] = None
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = {}

def logout():
    st.session_state['logged_in'] = False
    st.session_state['user_type'] = None
    st.session_state['user_info'] = {}
    st.rerun()

# ---------------------------------------------------------
# 4. 介面邏輯：登入/註冊頁面 (已更新 Hash 邏輯)
# ---------------------------------------------------------
def login_page():
    st.title("🔐 TCG ONLINE SHOP - 安全登入系統")
    
    tab1, tab2 = st.tabs(["登入 (Login)", "註冊 (Register)"])

    # --- 登入區塊 (邏輯已修改) ---
    with tab1:
        st.subheader("請選擇身分登入")
        role = st.radio("我是...", ["玩家 (Player)", "店家 (Shop)"], horizontal=True)
        
        username_input = st.text_input("帳號 (玩家請輸入Email / 店家請輸入店名)")
        password_input = st.text_input("密碼", type="password")
        
        if st.button("登入"):
            if not username_input or not password_input:
                st.warning("請輸入帳號密碼")
            else:
                if role == "玩家 (Player)":
                    # 1. 先只用 Email 查出該使用者 (不查密碼)
                    sql = 'SELECT * FROM "PLAYER" WHERE "email" = %s'
                    df = run_query(sql, (username_input,))
                    
                    if not df.empty:
                        # 2. 取出資料庫裡的 Hash 密碼
                        stored_hash = df.iloc[0]['password']
                        # 3. 用 bcrypt 比對
                        if check_password(password_input, stored_hash):
                            st.session_state['logged_in'] = True
                            st.session_state['user_type'] = 'player'
                            st.session_state['user_info'] = df.iloc[0].to_dict()
                            st.success("登入成功！")
                            st.rerun()
                        else:
                            st.error("帳號或密碼錯誤")
                    else:
                        st.error("找不到此帳號")
                        
                else: # 店家登入
                    # 1. 先用店名查
                    sql = 'SELECT * FROM "SHOP" WHERE "s_name" = %s'
                    df = run_query(sql, (username_input,))
                    
                    if not df.empty:
                        # 2. 取出 Hash 密碼並比對
                        stored_hash = df.iloc[0]['password']
                        if check_password(password_input, stored_hash):
                            st.session_state['logged_in'] = True
                            st.session_state['user_type'] = 'shop'
                            st.session_state['user_info'] = df.iloc[0].to_dict()
                            st.success("登入成功！")
                            st.rerun()
                        else:
                            st.error("帳號或密碼錯誤")
                    else:
                        st.error("找不到此店家")

    # --- 註冊區塊 (邏輯已修改) ---
    with tab2:
        st.subheader("註冊新帳號")
        reg_role = st.selectbox("註冊身分", ["玩家 (Player)", "店家 (Shop)"])
        
        if reg_role == "玩家 (Player)":
            new_name = st.text_input("玩家暱稱")
            new_email = st.text_input("Email (作為帳號)")
            new_pw = st.text_input("設定密碼", type="password")
            
            if st.button("註冊玩家"):
                if new_email and new_pw:
                    check = run_query('SELECT * FROM "PLAYER" WHERE "email" = %s', (new_email,))
                    if check.empty:
                        # ⚠️ 這裡改為：先 Hash 再存入
                        hashed_pw = hash_password(new_pw)
                        
                        run_command('INSERT INTO "PLAYER" ("p_name", "email", "password") VALUES (%s, %s, %s)', 
                                    (new_name, new_email, hashed_pw))
                        st.success("註冊成功！密碼已加密儲存。請切換至登入分頁。")
                    else:
                        st.error("該 Email 已被註冊。")
                else:
                    st.warning("請填寫所有欄位。")
                    
        else: # 註冊店家
            s_name = st.text_input("店家名稱 (作為帳號)")
            s_addr = st.text_input("地址")
            s_phone = st.text_input("電話")
            s_pw = st.text_input("設定密碼", type="password")
            
            if st.button("註冊店家"):
                if s_name and s_pw:
                    check = run_query('SELECT * FROM "SHOP" WHERE "s_name" = %s', (s_name,))
                    if check.empty:
                        # ⚠️ 這裡改為：先 Hash 再存入
                        hashed_pw = hash_password(s_pw)
                        
                        run_command('INSERT INTO "SHOP" ("s_name", "s_addr", "s_phone", "password") VALUES (%s, %s, %s, %s)', 
                                    (s_name, s_addr, s_phone, hashed_pw))
                        st.success("店家註冊成功！密碼已加密儲存。")
                    else:
                        st.error("該店家名稱已被註冊。")
                else:
                    st.warning("請填寫所有欄位。")

# ---------------------------------------------------------
# 5. 介面邏輯：玩家專用介面 (已修正 d_id 重複問題)
# ---------------------------------------------------------
def player_dashboard():
    user = st.session_state['user_info']
    st.sidebar.title(f"{user['p_name']}")
    menu = st.sidebar.radio("功能選單", ["首頁", "我的收藏", "我的牌組", "線上商城", "賽事報名"])
    
    if st.sidebar.button("登出"):
        logout()

    if menu == "首頁":
        st.title(f"歡迎回來，{user['p_name']}！")
        st.info("這裡是玩家專屬介面，您可以管理收藏或報名比賽。")
        
    elif menu == "我的收藏":
        st.header("我的卡片收藏")
        my_cards = run_query("""
            SELECT c."c_name", c."c_rarity", phc."qty"
            FROM "PLAYER_HAS_CARD" phc
            JOIN "CARD" c ON phc."c_id" = c."c_id"
            WHERE phc."p_id" = %s
        """, (user['p_id'],))
        st.dataframe(my_cards, use_container_width=True)
        
        with st.expander("登錄新獲得的卡片"):
            all_cards = run_query('SELECT "c_id", "c_name" FROM "CARD"')
            if not all_cards.empty:
                card_map = dict(zip(all_cards['c_name'], all_cards['c_id']))
                sel_card = st.selectbox("選擇卡牌", all_cards['c_name'])
                qty = st.number_input("數量", min_value=1, value=1)
                if st.button("加入收藏"):
                    c_id = card_map[sel_card]
                    exist = run_query('SELECT * FROM "PLAYER_HAS_CARD" WHERE "p_id"=%s AND "c_id"=%s', (user['p_id'], c_id))
                    if exist.empty:
                        run_command('INSERT INTO "PLAYER_HAS_CARD" ("p_id", "c_id", "qty") VALUES (%s, %s, %s)', (user['p_id'], c_id, qty))
                    else:
                        run_command('UPDATE "PLAYER_HAS_CARD" SET "qty" = "qty" + %s WHERE "p_id"=%s AND "c_id"=%s', (qty, user['p_id'], c_id))
                    st.success("已更新收藏！")
                    st.rerun()

    elif menu == "我的牌組":
        st.header("牌組管理")
        # ✅ 修正後的 SQL
        decks = run_query("""
            SELECT d."d_id", d."d_name"
            FROM "DECK" d 
            JOIN "PLAYER_BUILDS_DECK" pbd ON d."d_id" = pbd."d_id" 
            WHERE pbd."p_id" = %s
        """, (user['p_id'],))
        st.dataframe(decks, use_container_width=True)
        
        new_deck_name = st.text_input("建立新牌組名稱")
        if st.button("建立牌組"):
            run_command('INSERT INTO "DECK" ("d_name") VALUES (%s)', (new_deck_name,))
            new_id_df = run_query('SELECT "d_id" FROM "DECK" ORDER BY "d_id" DESC LIMIT 1')
            new_d_id = new_id_df.iloc[0,0]
            run_command('INSERT INTO "PLAYER_BUILDS_DECK" ("p_id", "d_id") VALUES (%s, %s)', (user['p_id'], int(new_d_id)))
            st.success(f"牌組 {new_deck_name} 建立成功！")
            st.rerun()

    elif menu == "線上商城":
        st.header("瀏覽商城")
        shop_items = run_query("""
            SELECT s."s_name" as 賣家, p."prod_name", sp."price", sp."qty"
            FROM "SHOP_SELLS_PRODUCT" sp
            JOIN "SHOP" s ON sp."s_id" = s."s_id"
            JOIN "PRODUCT" p ON sp."prod_id" = p."prod_id"
        """)
        st.dataframe(shop_items)

    elif menu == "賽事報名":
        st.header("🏆 報名比賽")
        events = run_query('SELECT * FROM "EVENT"')
        st.dataframe(events)

# ---------------------------------------------------------
# 6. 介面邏輯：店家專用介面
# ---------------------------------------------------------
def shop_dashboard():
    user = st.session_state['user_info']
    st.sidebar.title(f"店家：{user['s_name']}")
    menu = st.sidebar.radio("後台管理", ["概況", "庫存與上架", "舉辦活動"])
    
    if st.sidebar.button("登出"):
        logout()

    if menu == "概況":
        st.title("店家管理後台")
        st.write(f"店家地址：{user['s_addr']}")
        st.write(f"聯絡電話：{user['s_phone']}")

    elif menu == "庫存與上架":
        st.header("📦 商品上架管理")
        my_products = run_query("""
            SELECT p."prod_name", sp."qty", sp."price"
            FROM "SHOP_SELLS_PRODUCT" sp
            JOIN "PRODUCT" p ON sp."prod_id" = p."prod_id"
            WHERE sp."s_id" = %s
        """, (user['s_id'],))
        st.dataframe(my_products)
        
        st.divider()
        st.subheader("上架新商品")
        all_prods = run_query('SELECT "prod_id", "prod_name" FROM "PRODUCT"')
        if not all_prods.empty:
            prod_map = dict(zip(all_prods['prod_name'], all_prods['prod_id']))
            c1, c2, c3 = st.columns(3)
            with c1:
                sel_prod = st.selectbox("選擇商品", all_prods['prod_name'])
            with c2:
                price = st.number_input("設定價格", min_value=1)
            with c3:
                qty = st.number_input("上架數量", min_value=1)
                
            if st.button("確認上架"):
                pid = prod_map[sel_prod]
                exist = run_query('SELECT * FROM "SHOP_SELLS_PRODUCT" WHERE "s_id"=%s AND "prod_id"=%s', (user['s_id'], pid))
                if exist.empty:
                    run_command('INSERT INTO "SHOP_SELLS_PRODUCT" ("s_id", "prod_id", "qty", "price") VALUES (%s, %s, %s, %s)', (user['s_id'], pid, qty, price))
                else:
                    run_command('UPDATE "SHOP_SELLS_PRODUCT" SET "qty"=%s, "price"=%s WHERE "s_id"=%s AND "prod_id"=%s', (qty, price, user['s_id'], pid))
                st.success("上架成功！")
                st.rerun()

    elif menu == "舉辦活動":
        st.header("舉辦新賽事")
        e_name = st.text_input("活動名稱")
        
        # 修改：版面配置增加時間輸入
        c1, c2, c3 = st.columns(3)
        with c1:
            e_date = st.date_input("活動日期")
        with c2:
            # 新增：時間選擇器 (預設 12:00)
            e_time = st.time_input("活動開始時間", datetime.time(12, 00))
        with c3:
            e_format = st.selectbox("賽制格式", ["標準", "開放"])
            
        c4, c5 = st.columns(2)
        with c4:
            e_size = st.text_input("人數上限", value="16")
        with c5:
            e_round = st.selectbox("比賽進行方式", ["瑞士輪", "淘汰賽"])
            
        if st.button("發布活動"):
            # 修改：INSERT 指令加入 e_time
            run_command("""
                INSERT INTO "EVENT" ("e_name", "e_format", "e_date", "e_time", "e_size", "e_roundtype", "org_shop_id")
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (e_name, e_format, e_date, e_time, e_size, e_round, user['s_id']))
            st.success("活動已發布！")

# ---------------------------------------------------------
# 7. 主程式進入點
# ---------------------------------------------------------
if __name__ == "__main__":
    if not st.session_state['logged_in']:
        login_page()
    else:
        if st.session_state['user_type'] == 'player':
            player_dashboard()
        elif st.session_state['user_type'] == 'shop':
            shop_dashboard()