import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from passlib.context import CryptContext

from database import db, create_document, get_documents
from schemas import User as UserSchema, Product as ProductSchema, Cart, CartItem, Order, OrderItem

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Skincare E-commerce API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helpers
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ProductCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    image_url: Optional[str] = None

class AddToCart(BaseModel):
    user_id: str
    product_id: str
    quantity: int = 1

class CheckoutRequest(BaseModel):
    user_id: str

# Health
@app.get("/")
def read_root():
    return {"message": "Skincare E-commerce Backend running"}

@app.get("/test")
def test_database():
    try:
        collections = db.list_collection_names() if db else []
        return {"backend": "ok", "db": "ok" if db else "not_configured", "collections": collections}
    except Exception as e:
        return {"backend": "ok", "db": f"error: {str(e)[:80]}"}

# Auth (simple sessionless - return user id)
@app.post("/api/auth/register")
def register(user: UserCreate):
    # check existing
    existing = db["user"].find_one({"email": user.email}) if db else None
    if existing:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar")
    password_hash = pwd_context.hash(user.password)
    user_doc = UserSchema(name=user.name, email=user.email, password_hash=password_hash)
    user_id = create_document("user", user_doc)
    return {"user_id": user_id, "name": user.name, "email": user.email}

@app.post("/api/auth/login")
def login(creds: UserLogin):
    doc = db["user"].find_one({"email": creds.email}) if db else None
    if not doc:
        raise HTTPException(status_code=401, detail="Email atau password salah")
    if not pwd_context.verify(creds.password, doc.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email atau password salah")
    return {"user_id": str(doc.get("_id")), "name": doc.get("name"), "email": doc.get("email")}

# Products
@app.post("/api/products")
def create_product(p: ProductCreate):
    prod = ProductSchema(**p.model_dump())
    prod_id = create_document("product", prod)
    return {"product_id": prod_id}

@app.get("/api/products")
def list_products():
    docs = get_documents("product")
    for d in docs:
        d["id"] = str(d["_id"]) ; d.pop("_id", None)
    return docs

# Cart
@app.post("/api/cart/add")
def add_to_cart(payload: AddToCart):
    uid = payload.user_id
    pid = payload.product_id
    qty = max(1, payload.quantity)
    # ensure product exists
    prod = db["product"].find_one({"_id": ObjectId(pid)}) if db else None
    if not prod:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan")
    cart = db["cart"].find_one({"user_id": uid}) if db else None
    if not cart:
        cart_doc = {"user_id": uid, "items": [{"product_id": pid, "quantity": qty}]}
        create_document("cart", cart_doc)
    else:
        # update or push
        items = cart.get("items", [])
        found = False
        for it in items:
            if it["product_id"] == pid:
                it["quantity"] += qty
                found = True
                break
        if not found:
            items.append({"product_id": pid, "quantity": qty})
        db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": items}})
    return {"status": "ok"}

@app.get("/api/cart/{user_id}")
def get_cart(user_id: str):
    cart = db["cart"].find_one({"user_id": user_id}) if db else None
    if not cart:
        return {"items": [], "total": 0}
    items = []
    total = 0.0
    for it in cart.get("items", []):
        prod = db["product"].find_one({"_id": ObjectId(it["product_id"])}) if db else None
        if not prod:
            continue
        price = float(prod.get("price", 0))
        subtotal = price * int(it.get("quantity", 1))
        total += subtotal
        items.append({
            "product_id": str(prod["_id"]),
            "title": prod.get("title"),
            "image_url": prod.get("image_url"),
            "price": price,
            "quantity": it.get("quantity", 1),
            "subtotal": subtotal
        })
    return {"items": items, "total": total}

# Checkout -> create order and clear cart
@app.post("/api/checkout")
def checkout(req: CheckoutRequest):
    cart = db["cart"].find_one({"user_id": req.user_id}) if db else None
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Keranjang kosong")
    order_items: List[OrderItem] = []
    total = 0.0
    for it in cart.get("items", []):
        prod = db["product"].find_one({"_id": ObjectId(it["product_id"])}) if db else None
        if not prod:
            continue
        price = float(prod.get("price", 0))
        qty = int(it.get("quantity", 1))
        total += price * qty
        order_items.append(OrderItem(product_id=str(prod["_id"]), quantity=qty, price=price))
    order = Order(user_id=req.user_id, items=order_items, total=total)
    order_id = create_document("order", order)
    db["cart"].update_one({"_id": cart["_id"]}, {"$set": {"items": []}})
    return {"order_id": order_id, "total": total, "status": "created"}

# Simple Chatbot route (rule-based)
class ChatRequest(BaseModel):
    question: str

@app.post("/api/chat")
def chat(req: ChatRequest):
    q = req.question.lower()
    if any(k in q for k in ["jerawat", "acne", "beruntusan"]):
        answer = "Untuk masalah jerawat, gunakan pembersih lembut, toner BHA, dan pelembap non-comedogenic. Tambahkan serum dengan niacinamide."
    elif any(k in q for k in ["kusam", "dull", "pencerah"]):
        answer = "Kulit kusam? Coba exfoliasi AHA 2-3x/minggu dan serum vitamin C pagi hari, selalu gunakan sunscreen."
    elif any(k in q for k in ["kering", "dry", "dehidrasi"]):
        answer = "Kulit kering? Gunakan cleanser lembut, hydrating toner, serum hyaluronic acid, dan pelembap occlusive."
    elif any(k in q for k in ["berminyak", "oily", "minyak"]):
        answer = "Kulit berminyak? Pilih gel moisturizer, hindari cleanser terlalu keras, dan gunakan niacinamide + zinc."
    else:
        answer = "Ceritakan masalah kulit Anda (jerawat, kusam, kering, berminyak) dan saya akan bantu rekomendasi rutinitas."
    return {"answer": answer}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
