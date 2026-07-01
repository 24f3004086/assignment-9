from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uuid
import time
import base64

app = FastAPI(title="Orders API")

# ----------------------------------------------------
# CORS
# ----------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 42
RATE_LIMIT = 18
WINDOW = 10

# Fixed catalog
catalog = [
    {"id": i, "item": f"Item {i}"}
    for i in range(1, TOTAL_ORDERS + 1)
]

# Memory stores
idempotency_store = {}
rate_limit_store = {}


# ----------------------------------------------------
# Cursor helpers
# ----------------------------------------------------
def encode_cursor(index: int) -> str:
    return base64.b64encode(str(index).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        return int(base64.b64decode(cursor).decode())
    except Exception:
        return 0


# ----------------------------------------------------
# Rate limiter
# ----------------------------------------------------
def check_rate_limit(client_id: str):
    now = time.time()

    bucket = rate_limit_store.setdefault(client_id, [])

    # Remove timestamps older than WINDOW seconds
    bucket[:] = [t for t in bucket if now - t < WINDOW]

    if len(bucket) >= RATE_LIMIT:
        retry_after = max(1, int(WINDOW - (now - bucket[0])))

        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(retry_after)
            },
        )

    bucket.append(now)


# ----------------------------------------------------
# Root
# ----------------------------------------------------
@app.get("/")
def root():
    return {"message": "Orders API is running"}


# ----------------------------------------------------
# POST /orders
# ----------------------------------------------------
@app.post("/orders", status_code=201)
def create_order(
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key"
    ),
    x_client_id: str = Header(
        default="anonymous",
        alias="X-Client-Id"
    ),
):
    check_rate_limit(x_client_id)

    if idempotency_key is None:
        idempotency_key = str(uuid.uuid4())

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4())
    }

    idempotency_store[idempotency_key] = order

    return order


# ----------------------------------------------------
# GET /orders
# ----------------------------------------------------
@app.get("/orders")
def get_orders(
    limit: int = 10,
    cursor: str | None = None,
    x_client_id: str = Header(
        default="anonymous",
        alias="X-Client-Id"
    ),
):
    check_rate_limit(x_client_id)

    if limit < 1:
        limit = 1

    start = 0

    if cursor:
        start = decode_cursor(cursor)

    items = catalog[start:start + limit]

    next_index = start + len(items)

    if next_index >= TOTAL_ORDERS:
        next_cursor = None
    else:
        next_cursor = encode_cursor(next_index)

    return {
        "items": items,
        "next_cursor": next_cursor
    }