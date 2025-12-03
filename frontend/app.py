import streamlit as st
import requests
import pandas as pd
import datetime

# 設定 API 網址
API_URL = "http://localhost:8000"

# --- API Helper Functions ---
def api_login(username, password, role):
    payload = {
        "username": username,
        "password": password,
        "role": "player" if role == "玩家 (Player)" else "shop"
    }
    try:
        res = requests.post(f"{API_URL}/login", json=payload)
        if res.status_code == 200:
            return True, res.json()
        return False, res.json().get("detail", "登入失敗")
    except:
        return False, "無法連線後端"

def api_register(role, name, account, password, addr=None, phone=None):
    payload = {
        "role": "player" if role == "玩家 (Player)" else "shop",
        "name": name,
        "account_id": account,
        "password": password,
        "extra_info": addr,
        "phone": phone
    }
    res = requests.post(f"{API_URL}/register", json=payload)
    return res.status_code == 200, res.json().get("detail", "")

def fetch_data(endpoint):
    """通用的 GET 請求函式，回傳 DataFrame"""
    try:
        res = requests.get(f"{API_URL}/{endpoint}")
        if res.status_code == 200:
            return pd.DataFrame(res.json())
    except:
        pass
    return pd.DataFrame()

def send_data(endpoint, payload):
    """通用的 POST 請求函式"""
    try:
        res = requests.post(f"{API_URL}/{endpoint}", json=payload)
        return res.status_code == 200
    except:
        return False

# --- Session Management ---
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

# --- Pages ---
def login_page():
    st.title("TCG ONLINE SHOP")
    tab1, tab2 = st.tabs(["登入", "註冊"])

    with tab1:
        role = st.radio("我是...", ["玩家 (Player)", "店家 (Shop)"], horizontal=True)
        username = st.text_input("帳號")
        password = st.text_input("密碼", type="password")
        if st.button("登入"):
            success, result = api_login(username, password, role)
            if success:
                st.session_state['logged_in'] = True
                st.session_state['user_type'] = result['role']
                st.session_state['user_info'] = result['user']
                st.success("登入成功")
                st.rerun()
            else:
                st.error(result)

    with tab2:
        reg_role = st.selectbox("註冊身分", ["玩家 (Player)", "店家 (Shop)"])
        if reg_role == "玩家 (Player)":
            name = st.text_input("暱稱")
            email = st.text_input("Email")
            pw = st.text_input("設定密碼", type="password")
            if st.button("註冊玩家"):
                success, msg = api_register(reg_role, name, email, pw)
                if success: st.success("註冊成功")
                else: st.error("註冊失敗")
        else:
            name = st.text_input("店名")
            addr = st.text_input("地址")
            phone = st.text_input("電話")
            pw = st.text_input("設定密碼", type="password")
            if st.button("註冊店家"):
                success, msg = api_register(reg_role, name, name, pw, addr, phone)
                if success: st.success("註冊成功")
                else: st.error("註冊失敗")

def player_dashboard():
    user = st.session_state['user_info']
    p_id = user['p_id']
    
    st.sidebar.title(f"玩家: {user['p_name']}")
    menu = st.sidebar.radio("功能", ["我的收藏", "我的牌組", "線上商城", "賽事報名"])
    if st.sidebar.button("登出"): logout()

    if menu == "我的收藏":
        st.header("我的卡片")
        df = fetch_data(f"player/{p_id}/cards")
        st.dataframe(df, use_container_width=True)

        with st.expander("登錄新卡片"):
            # 取得所有卡片列表供選擇
            all_cards = fetch_data("cards")
            if not all_cards.empty:
                card_map = dict(zip(all_cards['c_name'], all_cards['c_id']))
                sel_card = st.selectbox("選擇卡牌", all_cards['c_name'])
                qty = st.number_input("數量", min_value=1, value=1)
                
                if st.button("加入"):
                    payload = {"p_id": p_id, "c_id": card_map[sel_card], "qty": qty}
                    if send_data("player/add_card", payload):
                        st.success("成功！")
                        st.rerun()
                    else:
                        st.error("失敗")

    elif menu == "我的牌組":
        st.header("牌組管理")
        df = fetch_data(f"player/{p_id}/decks")
        st.dataframe(df, use_container_width=True)
        
        new_name = st.text_input("新牌組名稱")
        if st.button("建立"):
            payload = {"p_id": p_id, "d_name": new_name}
            if send_data("player/create_deck", payload):
                st.success("建立成功")
                st.rerun()

    elif menu == "線上商城":
        st.header("瀏覽商城")
        df = fetch_data("market")
        st.dataframe(df)

    elif menu == "賽事報名":
        st.header("賽事列表")
        df = fetch_data("events")
        st.dataframe(df)

def shop_dashboard():
    user = st.session_state['user_info']
    s_id = user['s_id']

    st.sidebar.title(f"店家: {user['s_name']}")
    menu = st.sidebar.radio("管理", ["庫存", "舉辦活動"])
    if st.sidebar.button("登出"): logout()

    if menu == "庫存":
        st.header("庫存管理")
        df = fetch_data(f"shop/{s_id}/products")
        st.dataframe(df)

        st.divider()
        st.subheader("上架商品")
        # 取得所有商品列表
        all_prods = fetch_data("products_list")
        if not all_prods.empty:
            prod_map = dict(zip(all_prods['prod_name'], all_prods['prod_id']))
            sel = st.selectbox("商品", all_prods['prod_name'])
            price = st.number_input("價格", min_value=1)
            qty = st.number_input("數量", min_value=1)
            
            if st.button("上架"):
                payload = {"s_id": s_id, "prod_id": prod_map[sel], "qty": qty, "price": price}
                if send_data("shop/add_product", payload):
                    st.success("上架成功")
                    st.rerun()

    elif menu == "舉辦活動":
        st.header("發布新賽事")
        name = st.text_input("名稱")
        c1, c2 = st.columns(2)
        date = c1.date_input("日期")
        time = c2.time_input("時間", datetime.time(12,0))
        fmt = st.selectbox("賽制", ["標準", "開放"])
        size = st.text_input("人數", "16")
        round_type = st.selectbox("類型", ["瑞士輪", "淘汰賽"])

        if st.button("發布"):
            payload = {
                "e_name": name,
                "e_format": fmt,
                "e_date": str(date),
                "e_time": str(time),
                "e_size": size,
                "e_round": round_type,
                "s_id": s_id
            }
            if send_data("shop/create_event", payload):
                st.success("發布成功")
            else:
                st.error("發布失敗")

if __name__ == "__main__":
    if not st.session_state['logged_in']:
        login_page()
    else:
        if st.session_state['user_type'] == 'player':
            player_dashboard()
        else:
            shop_dashboard()