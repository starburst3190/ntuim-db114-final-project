from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import bcrypt
from . import db

app = FastAPI()

# --- Pydantic Models (定義前端傳來的 JSON 格式) ---
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

class AddCardRequest(BaseModel):
    p_id: int
    c_id: int
    qty: int

class CreateDeckRequest(BaseModel):
    p_id: int
    d_name: str

class AddProductRequest(BaseModel):
    s_id: int
    prod_id: int
    qty: int
    price: int

class CreateEventRequest(BaseModel):
    e_name: str
    e_format: str
    e_date: str # 接收 YYYY-MM-DD 字串
    e_time: str # 接收 HH:MM:SS 字串
    e_size: str
    e_round: str
    s_id: int

# --- Auth Routes ---
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

@app.get("/cards")
def get_all_cards():
    return db.get_all_cards()

@app.post("/player/add_card")
def add_card(data: AddCardRequest):
    if db.upsert_player_card(data.p_id, data.c_id, data.qty):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to add card")

@app.get("/player/{p_id}/decks")
def get_decks(p_id: int):
    return db.get_player_decks(p_id)

@app.post("/player/create_deck")
def create_deck(data: CreateDeckRequest):
    if db.create_deck(data.p_id, data.d_name):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to create deck")

# --- Shop Routes ---
@app.get("/shop/{s_id}/products")
def get_shop_inventory(s_id: int):
    return db.get_shop_inventory(s_id)

@app.get("/products_list")
def get_products_list():
    return db.get_all_products_list()

@app.post("/shop/add_product")
def add_shop_product(data: AddProductRequest):
    if db.upsert_shop_product(data.s_id, data.prod_id, data.qty, data.price):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to add product")

@app.post("/shop/create_event")
def create_event(data: CreateEventRequest):
    if db.create_event(data.e_name, data.e_format, data.e_date, data.e_time, data.e_size, data.e_round, data.s_id):
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Failed to create event")

# --- Public Routes ---
@app.get("/market")
def get_market_items():
    return db.get_all_shop_items()

@app.get("/events")
def get_events():
    return db.get_all_events()