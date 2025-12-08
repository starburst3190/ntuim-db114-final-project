import streamlit as st
import requests
import pandas as pd
import datetime
from streamlit_option_menu import option_menu

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
    try:
        res = requests.post(f"{API_URL}/register", json=payload)
        return res.status_code == 200, res.json().get("detail", "")
    except:
        return False, "連線錯誤"

# --- 效能優化：使用 st.cache_data ---
@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(endpoint, params=None):
    """
    快取版本的 GET 請求，現在支援查詢參數。
    """
    try:
        res = requests.get(f"{API_URL}/{endpoint}", params=params, timeout=5)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
        # 如果 API 返回 404/500 等，回傳空 DataFrame 避免程式崩潰
        print(f"API Error for {endpoint}: {res.status_code}")
    except Exception as e:
        print(f"Fetch error: {e}")
    return pd.DataFrame()

def send_data(endpoint, payload):
    """
    POST 請求。
    """
    try:
        res = requests.post(f"{API_URL}/{endpoint}", json=payload)
        if res.status_code == 200:
            fetch_data.clear() # 成功寫入後，清除所有快取
            return True
        else:
            st.error(f"操作失敗: {res.json().get('detail', '後端錯誤')}")
    except Exception as e:
        st.error(f"連線錯誤: {e}")
        pass
    return False

# --- Session Management (不變) ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_type' not in st.session_state:
    st.session_state['user_type'] = None
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = {}

def logout():
    st.session_state.clear()
    st.rerun()

# --- Pages (Login/Register 不變) ---
def login_page():
    st.title("TCG ONLINE SHOP")
    tab1, tab2 = st.tabs(["登入", "註冊"])

    with tab1:
        role = st.radio("我是...", ["玩家 (Player)", "店家 (Shop)"], horizontal=True, key="login_role")
        username = st.text_input("帳號", key="login_username")
        password = st.text_input("密碼", type="password", key="login_password")
        
        if st.button("登入", key="btn_login"):
            with st.spinner("登入中..."):
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
        reg_role = st.selectbox("註冊身分", ["玩家 (Player)", "店家 (Shop)"], key="reg_role_select")
        
        if reg_role == "玩家 (Player)":
            name = st.text_input("暱稱", key="reg_p_name")
            email = st.text_input("Email", key="reg_p_email")
            pw = st.text_input("密碼", type="password", key="reg_p_pw")
            if st.button("註冊玩家", key="btn_reg_player"):
                success, msg = api_register(reg_role, name, email, pw)
                if success: st.success("註冊成功")
                else: st.error("註冊失敗")
        else:
            name = st.text_input("店名", key="reg_s_name")
            addr = st.text_input("地址", key="reg_s_addr")
            phone = st.text_input("電話", key="reg_s_phone")
            pw = st.text_input("密碼", type="password", key="reg_s_pw")
            if st.button("註冊店家", key="btn_reg_shop"):
                success, msg = api_register(reg_role, name, name, pw, addr, phone)
                if success: st.success("註冊成功")
                else: st.error("註冊失敗")

def player_dashboard():
    user = st.session_state['user_info']
    p_id = user['p_id']
    
    with st.sidebar:
        st.title(f"歡迎回來，{user['p_name']}")
        
        # --- 修改：新增「卡牌查詢」選單 ---
        menu = option_menu(
            menu_title=None,
            options=["我的收藏", "我的牌組", "卡牌查詢", "線上商城", "賽事報名"],
            icons=["box-seam", "layers", "search", "shop", "trophy"],
            default_index=0,
        )
        
        if st.button("登出"): logout()

    with st.spinner(f"正在載入 {menu}..."):
        
        # --- 我的收藏 ---
        if menu == "我的收藏":
            st.header("我的卡片")
            df = fetch_data(f"player/{p_id}/cards")
            if not df.empty:
                st.dataframe(df, width="stretch", column_config={"c_id": None})
            else:
                st.info("您沒有登錄的卡片，請點擊下方「登錄新卡片」設定收藏")

            with st.expander("登錄新卡片"):
                all_cards = fetch_data("cards")
                
                if not all_cards.empty:
                    # 步驟 A: 建立一個不重複的顯示名稱 (格式: 名稱 [稀有度])
                    all_cards['display_label'] = all_cards['c_name'] + " [" + all_cards['c_rarity'] + "]"
                    
                    # 步驟 B: 建立 顯示名稱 -> ID 的對照表
                    # 這樣就算名稱重複，加上稀有度後就會是不同的 Key
                    card_map = dict(zip(all_cards['display_label'], all_cards['c_id']))
                    
                    # 步驟 C: 讓玩家選擇這個「組合後的名稱」
                    sel_label = st.selectbox("選擇卡牌", all_cards['display_label'])
                    
                    qty = st.number_input("數量", min_value=1, value=1)
                    
                    if st.button("加入"):
                        # 步驟 D: 透過選單的 label 查回正確的 c_id
                        target_c_id = card_map[sel_label]
                        
                        payload = {"p_id": p_id, "c_id": target_c_id, "qty": qty}
                        
                        if send_data("player/add_card", payload):
                            st.success(f"成功加入 {sel_label}！")
                            st.rerun()
                        else:
                            st.error("失敗")
            if not df.empty:
                with st.expander("刪除卡片"):
                    df['inv_label'] = (
                        df['卡牌名稱'] + 
                        " [" + df['稀有度'] + "] " +
                        "(擁有量: " + df['擁有量'].astype(str) + ")"
                    )
                    
                    # 建立 對應表: Label -> (Card ID, 目前數量)
                    # 這樣我們稍後才能知道這張卡最多能刪幾張
                    inv_map = {
                        row['inv_label']: {'c_id': row['c_id'], 'max_qty': row['擁有量']} 
                        for index, row in df.iterrows()
                    }
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        sel_card_del = st.selectbox("選擇要減少的卡牌", list(inv_map.keys()), key="del_select")
                    
                    # 取得該卡片目前的庫存上限，防止玩家刪除超過持有的數量
                    current_owned = inv_map[sel_card_del]['max_qty']
                    target_c_id = inv_map[sel_card_del]['c_id']

                    with col2:
                        # 設定 max_value 等於持有數，這樣玩家最多只能選到全部刪除
                        qty_del = st.number_input("減少數量", min_value=1, max_value=current_owned, value=1, key="del_qty")
                    
                    # 顯示提示文字
                    if qty_del == current_owned:
                        st.warning(f"注意：將會從收藏中完全移除此卡片！")
                    
                    if st.button("確認減少 / 刪除"):
                        payload = {"p_id": p_id, "c_id": target_c_id, "qty": qty_del}
                        
                        if send_data("player/remove_card", payload):
                            st.success(f"已移除 {qty_del} 張卡片")
                            st.rerun()

        # --- 我的牌組 ---
        elif menu == "我的牌組":
            st.header("牌組管理")
            df_decks = fetch_data(f"player/{p_id}/decks")
            if not df_decks.empty:
                st.dataframe(
                    df_decks, 
                    width="stretch",
                    column_config={
                        "d_id": None
                    }
                )
            
            st.subheader("建立新牌組")
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            new_name = c1.text_input("牌組名稱", placeholder="輸入牌組名稱")
            if c2.button("建立", width="stretch"):
                if new_name:
                    payload = {"p_id": p_id, "d_name": new_name}
                    if send_data("player/create_deck", payload):
                        st.success("建立成功")
                        st.rerun()
                else:
                    st.error("牌組名稱為空")

            if not df_decks.empty:
                deck_options = dict(zip(df_decks['牌組名稱'], df_decks['d_id']))
                deck_names = list(deck_options.keys())
                
                with st.expander("編輯牌組內容"):
                    sel_deck_name_edit = st.selectbox("選擇要編輯的牌組", deck_names, key="edit_deck_select")
                    
                    sel_d_id_edit = deck_options[sel_deck_name_edit] if sel_deck_name_edit else None

                    if sel_d_id_edit:
                        current_comp = fetch_data(f"deck/{sel_d_id_edit}/composition")
                        if not current_comp.empty:
                            st.caption(f"目前 {sel_deck_name_edit} 的組成:")
                            st.dataframe(current_comp, width="stretch")

                        st.divider()
                        st.subheader("新增/修改卡片數量 (設為 0 刪除)")
                        all_cards_list = fetch_data("cards")
                        if not all_cards_list.empty:
                            card_map = dict(zip(all_cards_list['c_name'], all_cards_list['c_id']))
                            card_names = all_cards_list['c_name'].tolist()
                            
                            col1, col2 = st.columns([3, 1])
                            sel_card_edit = col1.selectbox("選擇卡牌", card_names)
                            qty_edit = col2.number_input("數量", min_value=0, value=1, key="deck_qty")
                            
                            if st.button(f"更新 {sel_deck_name_edit}", key="btn_update_deck"):
                                payload = {
                                    "d_id": sel_d_id_edit, 
                                    "c_id": card_map[sel_card_edit], 
                                    "qty": qty_edit
                                }
                                if send_data("deck/add_card", payload):
                                    st.success(f"成功更新牌組：{sel_card_edit} x {qty_edit}")
                                    st.rerun()
                
                # --- 核心新增：缺卡查詢 ---
                with st.expander("檢視缺少的卡牌"):
                    sel_deck_name_missing = st.selectbox("選擇牌組進行缺卡檢查", deck_names, key="missing_deck_select")
                    sel_d_id_missing = deck_options[sel_deck_name_missing] if sel_deck_name_missing else None
                    
                    if sel_d_id_missing and st.button(f"檢查 {sel_deck_name_missing} 缺少的卡牌"):
                        with st.spinner("正在比對你的收藏與牌組需求..."):
                            # Call the new API endpoint
                            missing_df = fetch_data(f"player/{p_id}/decks/{sel_d_id_missing}/missing_cards")
                            if missing_df.empty:
                                st.success(f"{sel_deck_name_missing}：恭喜！卡牌已齊全。")
                            else:
                                st.warning(f"{sel_deck_name_missing} 缺少以下卡牌：")
                                st.dataframe(missing_df, width="stretch")
            else:
                st.info("您尚未建立任何牌組。請先建立牌組！")

# --- 修改後的卡牌查詢頁面 (app.py) ---
        elif menu == "卡牌查詢":
            st.header("卡牌篩選與查詢")
            
            st.subheader("篩選條件")
            col1, col2, col3, col4 = st.columns(4)
            
            search_name = col1.text_input("卡牌名稱關鍵字", placeholder="例如：Pikachu")
            
            type_options = [
                "", "Pokemon", "Trainer", "Energy"
            ]

            rarity_options = [
                "",
                "Common", "Uncommon", "Rare", "Double Rare",
                "Illustration Rare", "Special Illustration Rare", "Ultra Rare"
            ]

            pokemon_type_options = [
                "",
                "Grass", "Fire", "Water", "Lightning", "Psychic",
                "Fighting", "Darkness", "Metal", "Dragon", "Colorless"
            ]

            all_pokemon_types = [t for t in pokemon_type_options if t != ""]

            search_type = col2.selectbox("類型", type_options, index=0)
            
            search_rarity = col3.selectbox("稀有度", rarity_options, index=0)

            pokemon_type = col4.selectbox("寶可夢屬性", pokemon_type_options, index=0, disabled=(search_type != "Pokemon"))
            
            params = {}
            if search_name: params['name'] = search_name
            if search_rarity: params['rarity'] = search_rarity
            if search_type == "Pokemon":
                if pokemon_type:
                    params['card_type'] = pokemon_type
                else:
                    params['card_type'] = all_pokemon_types
            elif search_type:
                params['card_type'] = search_type

            if st.button("執行查詢", type="primary"):
                with st.spinner("查詢中..."):
                    df_results = fetch_data("cards", params=params)
                    
                    if df_results.empty:
                        st.info("查無符合條件的卡牌。")
                    else:
                        st.success(f"找到 {len(df_results)} 張符合條件的卡牌:")
                        st.dataframe(df_results, width="stretch")

        elif menu == "線上商城":
            st.header("瀏覽商城")
            df = fetch_data("market")
            if not df.empty:
                st.dataframe(df, width="stretch")
            else:
                st.info("查無商品")

        elif menu == "賽事報名":
            st.header("賽事列表")
            df = fetch_data("events")
            if not df.empty:
                st.dataframe(df, width="stretch")
            else:
                st.info("查無賽事")

def shop_dashboard():
    user = st.session_state['user_info']
    s_id = user['s_id']

    with st.sidebar:
        st.title(f"歡迎回來，{user['s_name']}")
        
        menu = option_menu(
            menu_title=None,
            options=["庫存", "舉辦活動"],
            icons=["boxes", "calendar-plus"],
            default_index=0,
        )
        
        if st.button("登出"): logout()

    with st.spinner(f"正在載入 {menu}..."):
        if menu == "庫存":
            st.header("庫存管理")
            df = fetch_data(f"shop/{s_id}/products")
            st.dataframe(df, width="stretch")

            st.divider()
            st.subheader("上架商品")
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