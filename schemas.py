"""
Database Schemas for Skincare E-commerce

Each Pydantic model represents a MongoDB collection. The collection name is the lowercase of the class name.

- User -> "user"
- Product -> "product"
- Cart -> "cart"
- Order -> "order"
"""
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password")
    address: Optional[str] = Field(None, description="Address")
    phone: Optional[str] = Field(None, description="Phone number")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in IDR")
    category: str = Field(..., description="Product category")
    image_url: Optional[str] = Field(None, description="Image URL")
    in_stock: bool = Field(True, description="Whether product is in stock")

class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(1, ge=1)

class Cart(BaseModel):
    user_id: str
    items: List[CartItem] = []

class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float

class Order(BaseModel):
    user_id: str
    items: List[OrderItem]
    total: float
    status: str = Field("pending", description="Order status")
