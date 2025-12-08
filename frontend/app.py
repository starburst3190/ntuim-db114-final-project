import streamlit as st
import requests
import pandas as pd
import datetime
import time
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
        user_label = "帳號 (Email)" if role == "玩家 (Player)" else "帳號 (店名)"
        username = st.text_input(user_label, key="login_username")
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

            # --- 區域 1: 建立新牌組 (摺疊起來，節省空間) ---
            with st.expander("建立新牌組", expanded=False):
                c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
                new_name = c1.text_input("輸入新牌組名稱", placeholder="例如：噴火龍快攻")
                if c2.button("建立", width="stretch"):
                    if new_name:
                        payload = {"p_id": p_id, "d_name": new_name}
                        if send_data("player/create_deck", payload):
                            st.success(f"牌組「{new_name}」建立成功！")
                            st.rerun()
                    else:
                        st.error("牌組名稱不能為空")

            st.divider()

            # --- 區域 2: 選擇要管理的牌組 (主控台) ---
            df_decks = fetch_data(f"player/{p_id}/decks")
            
            if df_decks.empty:
                st.info("目前沒有牌組，請先在上方建立一個吧！")
            else:
                # 製作選單： 讓玩家選一個牌組，後續所有操作都針對這個牌組
                deck_options = dict(zip(df_decks['牌組名稱'], df_decks['d_id']))
                deck_names = list(deck_options.keys())
                
                # 使用 selectbox 成為頁面的「狀態選擇器」
                selected_deck_name = st.selectbox("選擇要管理的牌組", deck_names)
                selected_d_id = deck_options[selected_deck_name]

                # --- 區域 3: 針對選定牌組的功能區 (Tabs) ---
                tab1, tab2, tab3 = st.tabs(["內容編輯", "缺卡檢測", "刪除牌組"])

                # === Tab 1: 編輯牌組內容 (核心功能) ===
                with tab1:
                    col_list, col_edit = st.columns([1.5, 1])
                    
                    with col_list:
                        st.caption(f"「{selected_deck_name}」目前的組成")
                        current_comp = fetch_data(f"deck/{selected_d_id}/composition")
                        if not current_comp.empty:
                            st.dataframe(current_comp, width="stretch", height=400)
                        else:
                            st.info("這副牌組還是空的")

                    with col_edit:
                        st.caption("新增 / 修改卡片")
                        all_cards_list = fetch_data("cards")
                        
                        if not all_cards_list.empty:
                            all_cards_list['display_label'] = all_cards_list['c_name'] + " [" + all_cards_list['c_rarity'] + "]"
                            card_map = dict(zip(all_cards_list['display_label'], all_cards_list['c_id']))
                            
                            sel_card_label = st.selectbox("搜尋並選擇卡牌", all_cards_list['display_label'])
                            
                            qty_edit = st.number_input("數量 (設為 0 移除)", min_value=0, value=1)
                            
                            if st.button("更新牌組", type="primary", width="stretch"):
                                payload = {
                                    "d_id": selected_d_id, 
                                    "c_id": card_map[sel_card_label], 
                                    "qty": qty_edit
                                }
                                if send_data("deck/add_card", payload):
                                    action = "移除" if qty_edit == 0 else "更新"
                                    st.toast(f"已{action}：{sel_card_label}", icon="✅")
                                    time.sleep(0.5) # 稍微停頓讓 toast 顯示
                                    st.rerun()

                # === Tab 2: 缺卡檢測 (分析功能) ===
                with tab2:
                    st.markdown(f"### 正在檢查：{selected_deck_name}")
                    if st.button("開始比對庫存"):
                        with st.spinner("正在掃描您的卡片庫存..."):
                            # 直接使用選定的 ID，不用再選一次
                            missing_df = fetch_data(f"player/{p_id}/decks/{selected_d_id}/missing_cards")
                            
                            if missing_df.empty:
                                st.balloons()
                                st.success("太棒了！您擁有組成這副牌組的所有卡片。")
                            else:
                                st.warning(f"這副牌組還缺少 {len(missing_df)} 種卡片：")
                                # 顯示缺卡列表
                                st.dataframe(
                                    missing_df, 
                                    width="stretch",
                                    column_config={
                                        "c_name": "卡片名稱",
                                        "missing_qty": "缺少數量"
                                    }
                                )

                # === Tab 3: 刪除功能 ===
                with tab3:
                    st.write(f"您確定要刪除整個牌組 **{selected_deck_name}** 嗎？此動作無法復原。")
                    
                    # 加上確認機制，避免誤觸
                    if st.button(f"永久刪除 {selected_deck_name}", type="primary"):
                        payload = {"p_id": p_id, "d_id": selected_d_id}
                        if send_data("player/remove_deck", payload):
                            st.success(f"牌組 {selected_deck_name} 已刪除")
                            st.rerun()

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
            st.header("賽事報名中心")

            size_mapping = {
                "POD": 8,
                "LOCAL": 16,
                "REGIONAL": 32,
                "MAJOR": 64
            }
            name_mapping = {
                "POD": "桌邊賽", "LOCAL": "例行賽", "REGIONAL": "區域賽", "MAJOR": "旗艦賽"
            }

            # 1. 取得賽事列表
            df_events = fetch_data("events")
            
            # 2. 取得玩家自己的牌組 (報名必備)
            df_my_decks = fetch_data(f"player/{p_id}/decks")

            # 3. 取得玩家已報名的賽事
            my_participations = fetch_data(f"player/{p_id}/events")
    
            if not my_participations.empty and "e_id" in my_participations.columns:
                joined_event_ids = set(my_participations["e_id"].tolist())
            else:
                joined_event_ids = set()

            # --- 顯示已報名賽事區塊 ---
            if not my_participations.empty:
                st.subheader("已報名的賽事")
                st.dataframe(
                    my_participations,
                    width="stretch",
                    column_config={
                        # 隱藏不需要給玩家看的 ID 欄位
                        "e_id": None,
                        "d_id": None,
                        "p_id": None,
                        "e_name": "活動名稱",
                        "e_date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
                        "e_time": st.column_config.TimeColumn("時間", format="HH:mm"),
                        "s_name": "舉辦店家",
                        "d_name": "使用牌組",
                        "e_format": "賽制"
                    },
                    hide_index=True
                )
                st.divider()

            # --- 顯示所有賽事列表 ---
            if not df_events.empty:
                st.subheader("近期賽事")

                df_events["size_limit"] = df_events["e_size"].map(size_mapping).astype(int)
                df_events["size_display"] = df_events["e_size"].map(name_mapping)
                df_events["occupancy_rate"] = df_events.apply(
                    lambda row: (row["current_participants"] / row["size_limit"] * 100) if row["size_limit"] > 0 else 0,
                    axis=1
                )
                df_events["status_text"] = (
                    df_events["size_display"] + " (" + 
                    df_events["current_participants"].astype(str) + "/" + 
                    df_events["size_limit"].astype(str) + ")"
                )
                
                # 設定表格顯示格式
                st.dataframe(
                    df_events,
                    width="stretch",
                    column_config={
                        "e_id": None,
                        "e_name": "活動名稱",
                        "e_date": st.column_config.DateColumn("日期", format="YYYY-MM-DD"),
                        "e_time": st.column_config.TimeColumn("時間", format="HH:mm"),
                        "e_format": "賽制",
                        "e_roundtype": "賽制輪次",
                        "s_name": "舉辦店家",
                        "status_text": "賽事規模 (目前/上限)",
                        "occupancy_rate": st.column_config.ProgressColumn(
                            "報名狀況",
                            help="目前人數 / 規模上限",
                            format="%.0f%%",
                            min_value=0,
                            max_value=100,
                        ),
                        "e_size": None,
                        "current_participants": None,
                        "size_limit": None,
                        "size_display": None
                    },
                    hide_index=True
                )

                st.divider()

                # --- 報名操作區 ---
                st.subheader("立即報名")

                if df_my_decks.empty:
                    st.warning("您目前沒有任何牌組，無法參加比賽。請先至「我的牌組」建立一副牌組。")
                else:
                    available_events = df_events[~df_events['e_id'].isin(joined_event_ids)]
                    
                    if available_events.empty:
                        st.info("您已報名了所有可參加的賽事，或是目前沒有賽事。")
                    else:
                        # 步驟 A: 選擇賽事
                        # 製作選單：顯示名稱 + 日期 + 時間 以防同名
                        available_events['display_label'] = available_events['e_name'] + " (" + available_events['e_date'].astype(str) + " " + pd.to_datetime(available_events['e_time']).dt.strftime('%H:%M') + ")"
                        event_map = dict(zip(available_events['display_label'], available_events['e_id']))
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            sel_event_label = st.selectbox("選擇要參加的活動", available_events['display_label'])
                            target_e_id = event_map[sel_event_label]

                        # 步驟 B: 選擇使用的牌組
                        with c2:
                            # 製作牌組選單
                            deck_map = dict(zip(df_my_decks['牌組名稱'], df_my_decks['d_id']))
                            sel_deck_name = st.selectbox("選擇使用的牌組", list(deck_map.keys()))
                            target_d_id = deck_map[sel_deck_name]
                            
                            # 這裡可以做一個簡單的檢查，例如檢查牌組是否合法(張數是否足夠)，這邊先跳過

                        # 步驟 C: 送出報名
                        if st.button("確認報名", type="primary", use_container_width=True):
                            # 根據 Schema: PK 是 (p_id, e_id, d_id)，所以 Payload 要包含這三個
                            payload = {
                                "p_id": p_id,
                                "e_id": target_e_id,
                                "d_id": target_d_id
                            }
                            
                            # 呼叫後端 API
                            if send_data("player/join_event", payload):
                                st.success(f"成功報名「{sel_event_label}」！使用牌組：「{sel_deck_name}」")
                                time.sleep(1)
                                st.rerun() # 重新整理以更新人數
                            else:
                                st.error("報名失敗。可能是名額已滿，或是您已經報名過此賽事。")

            else:
                st.info("目前沒有可用的賽事。")

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
            size_options = ["POD", "LOCAL", "REGIONAL", "MAJOR"]
            size_labels = {
                "POD": "POD (8人)",
                "LOCAL": "LOCAL (16人)",
                "REGIONAL": "REGIONAL (32人)",
                "MAJOR": "MAJOR (64人)"
            }

            name = st.text_input("名稱")
            c1, c2 = st.columns(2)
            date = c1.date_input("日期")
            time = c2.time_input("時間", datetime.time(12,0))
            fmt = st.selectbox("賽制", ["標準", "開放"])
            size = st.selectbox(
                "規模", 
                options=size_options, 
                format_func=lambda x: size_labels[x]
            )
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