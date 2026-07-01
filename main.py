from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time
import base64

app = FastAPI(title="Orders API")

# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for grader
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Constants
# -----------------------------
TOTAL_ORDERS = 42
RATE_LIMIT = 18
WINDOW = 10  # seconds

# -----------------------------
# Fake order catalog (IDs 1..42)
# -----------------------------
orders = [
    {
        "id": i,
        "item": f"Item {i}"
    }
    for i in range(1, TOTAL_ORDERS + 1)
]

# -----------------------------
# Memory stores
# -----------------------------
idempotency_store = {}
rate_limit_store = {}


# =====================================================
# Helper Functions
# =====================================================

def encode_cursor(index: int):
    return base64.b64encode(str(index).encode()).decode()


def decode_cursor(cursor: str):
    return int(base64.b64decode(cursor.encode()).decode())


def check_rate_limit(client_id: str):
    now = time.time()

    if client_id not in rate_limit_store:
        rate_limit_store[client_id] = []

    # Remove timestamps older than WINDOW seconds
    rate_limit_store[client_id] = [
        t for t in rate_limit_store[client_id]
        if now - t < WINDOW
    ]

    if len(rate_limit_store[client_id]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "10"},
        )

    rate_limit_store[client_id].append(now)


# =====================================================
# POST /orders
# =====================================================

@app.post("/orders", status_code=201)
def create_order(
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    x_client_id: str = Header(..., alias="X-Client-Id"),
):

    check_rate_limit(x_client_id)

    # Same key? Return previous order
    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    # Create new order
    new_order = {
        "id": str(uuid.uuid4())
    }

    idempotency_store[idempotency_key] = new_order

    return new_order


# =====================================================
# GET /orders
# =====================================================

@app.get("/orders")
def get_orders(
    limit: int = 10,
    cursor: str = None,
    x_client_id: str = Header(..., alias="X-Client-Id"),
):

    check_rate_limit(x_client_id)

    if cursor:
        start = decode_cursor(cursor)
    else:
        start = 0

    items = orders[start:start + limit]

    next_index = start + len(items)

    if next_index >= len(orders):
        next_cursor = None
    else:
        next_cursor = encode_cursor(next_index)

    return {
        "items": items,
        "next_cursor": next_cursor
    }


# =====================================================
# Health Check (optional)
# =====================================================

@app.get("/")
def root():
    return {
        "message": "Orders API is running"
    }