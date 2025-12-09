from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import bcrypt
# 注意：為了正確運行，你需要確保 db.py 可以在這個 main.py 檔案中被正確引入
# 如果你是放在同一個資料夾，並且直接執行 main.py，可能需要修改 .db 為 db
from . import db # 假設是這樣引入

app = FastAPI()

# --- Pydantic Models ---
class LoginRequest(BaseModel):
    username: str
    password: str
    role: str

class RegisterRequest(BaseModel):
    role: str
    name: str 
    account_id: str 
    password: str
    extra_info: Optional[str] = None
    phone: Optional[str] = None

class AlterCardRequest(BaseModel):
    p_id: int
    c_id: int
    qty: int

class CreateDeckRequest(BaseModel):
    p_id: int
    d_name: str

class RemoveDeckRequest(BaseModel):
    p_id: int
    d_id: int

class JoinEventRequest(BaseModel):
    p_id: int
    e_id: int
    d_id: int

class BuyProductRequest(BaseModel):
    p_id: int
    s_id: int
    prod_id: int
    qty: int

class ListProductRequest(BaseModel):
    s_id: int
    prod_id: int
    qty: int
    price: int

class RestockRequest(BaseModel):
    s_id: int
    prod_id: int
    qty: int

class CreateEventRequest(BaseModel):
    e_name: str
    e_format: str
    e_date: str 
    e_time: str 
    e_size: str
    e_round: str
    s_id: int
    
# --- 核心新增：用於新增/編輯牌組卡片 ---
class UpsertDeckCardRequest(BaseModel):
    d_id: int
    c_id: int
    qty: int # 數量設為 0 時會被刪除

# --- Auth Routes (不變) ---
@app.post("/login")
def login(data: LoginRequest):
    user = None
    if data.role == "player":
        user = db.get_player_by_email(data.username)
    else:
        user = db.get_shop_by_name(data.username)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if bcrypt.checkpw(data.password.encode('utf-8'), user['password'].encode('utf-8')):
        del user['password']
        return {"status": "success", "user": user, "role": "player" if data.role == "player" else "shop"}
    else:
        raise HTTPException(status_code=401, detail="Wrong password")

@app.post("/register")
def register(data: RegisterRequest):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(data.password.encode('utf-8'), salt).decode('utf-8')
    
    success = False
    if data.role == "player":
        if db.get_player_by_email(data.account_id):
            raise HTTPException(status_code=400, detail="Email taken")
        success = db.create_player(data.name, data.account_id, hashed)
    else:
        if db.get_shop_by_name(data.account_id):
            raise HTTPException(status_code=400, detail="Shop name taken")
        success = db.create_shop(data.account_id, data.extra_info, data.phone, hashed)
    
    if success:
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="DB Error")

# --- Player Routes ---
@app.get("/player/{p_id}/cards")
def get_cards(p_id: int):
    return db.get_player_cards(p_id)

# --- 修改：cards 接口現在支援篩選，如果沒有參數，則回傳用於新增卡牌的列表 ---
@app.get("/cards")
def get_all_cards(
    name: Optional[str] = Query(None, description="卡牌名稱關鍵字"),
    card_type: Optional[List[str]] = Query(None, description="卡牌類型"),
    rarity: Optional[str] = Query(None, description="稀有度")
):
    # 如果有任何篩選參數，則呼叫 filter_cards
    if name or card_type or rarity:
        return db.filter_cards(name, card_type, rarity)
    
    # 否則回傳精簡列表（供前端的 SelectBox 使用）
    return db.get_all_card_names_and_ids()

@app.post("/player/add_card")
def add_card(data: AlterCardRequest):
    if db.upsert_player_card(data.p_id, data.c_id, data.qty):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to add card")

@app.post("/player/remove_card")
def remove_card(data: AlterCardRequest):
    if db.delete_player_card(data.p_id, data.c_id, data.qty):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to delete card")

@app.get("/player/{p_id}/decks")
def get_decks(p_id: int):
    return db.get_player_decks(p_id)

@app.post("/player/create_deck")
def create_deck(data: CreateDeckRequest):
    if db.create_deck(data.p_id, data.d_name):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to create deck")

@app.post("/player/remove_deck")
def remove_deck(data: RemoveDeckRequest):
    if db.remove_deck(data.p_id, data.d_id):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to remove deck")

@app.get("/player/{p_id}/events")
def get_player_events(p_id: int):
    return db.get_player_participations_detailed(p_id)

@app.post("/player/join_event")
def join_event(data: JoinEventRequest):
    result = db.join_event(data.p_id, data.e_id, data.d_id)
    if result is True:
        return {"status": "success"}
    elif isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    raise HTTPException(status_code=500, detail="Failed to join event")

# --- 新增：取得牌組組成 ---
@app.get("/deck/{d_id}/composition")
def get_deck_composition(d_id: int):
    return db.get_deck_composition(d_id)

# --- 新增：新增卡片到牌組 ---
@app.post("/deck/add_card")
def add_card_to_deck(data: UpsertDeckCardRequest):
    if db.upsert_deck_card(data.d_id, data.c_id, data.qty):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to update deck card")

# --- 核心新增：查詢缺卡 ---
@app.get("/player/{p_id}/decks/{d_id}/missing_cards")
def get_missing_deck_cards(p_id: int, d_id: int):
    return db.get_missing_cards_for_deck(p_id, d_id)

# --- Shop Routes (不變) ---
@app.get("/shop/{s_id}/products")
def get_shop_inventory(s_id: int):
    return db.get_shop_inventory(s_id)

@app.get("/shop/{s_id}/storage")
def get_shop_storage(s_id: int):
    return db.get_shop_storage(s_id)

@app.get("/products_list")
def get_products_list():
    return db.get_all_products_list()

@app.post("/shop/restock")
def restock_shop_product(data: RestockRequest):
    result = db.restock_shop_product(data.s_id, data.prod_id, data.qty)
    if result is True:
        return {"status": "success"}
    raise HTTPException(status_code=400, detail="Failed to restock shop product")

@app.post("/shop/list_product")
def list_shop_product(data: ListProductRequest):
    result = db.move_product_to_shelf(data.s_id, data.prod_id, data.qty, data.price)
    if result["success"]:
        return {"status": "success", "message": result["message"]}
    raise HTTPException(status_code=400, detail=result["message"])

@app.post("/shop/create_event")
def create_event(data: CreateEventRequest):
    if db.create_event(data.e_name, data.e_format, data.e_date, data.e_time, data.e_size, data.e_round, data.s_id):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to create event")

# --- Public Routes ---
@app.get("/market")
def get_market_listings():
    return db.get_market_listings()

@app.post("/market/buy")
def buy_product(data: BuyProductRequest):
    result = db.buy_product(data.p_id, data.s_id, data.prod_id, data.qty)
    
    if result["success"]:
        return {"status": "success", "message": result["message"]}
    
    raise HTTPException(status_code=400, detail=result["message"])

@app.get("/events")
def get_events():
    return db.get_all_events()