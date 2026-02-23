from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
import httpx
import time

from .database import SessionLocal, engine
from .models import Base, Investment

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="backend/static"), name="static")
templates = Jinja2Templates(directory="backend/templates")

COINS = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "sui": "sui",
    "xrp": "ripple",
}

# -------- CACHE --------
price_cache = {
    "data": {},
    "timestamp": 0
}

usd_cache = {
    "rate": 360,
    "timestamp": 0
}

CACHE_SECONDS = 60


async def get_prices():

    now = time.time()

    if now - price_cache["timestamp"] < CACHE_SECONDS:
        return price_cache["data"]

    try:
        ids = ",".join(COINS.values())
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            data = response.json()

        if isinstance(data, dict):
            price_cache["data"] = data
            price_cache["timestamp"] = now
            return data

        return price_cache["data"]

    except:
        return price_cache["data"]


async def get_usd_huf():

    now = time.time()

    if now - usd_cache["timestamp"] < CACHE_SECONDS:
        return usd_cache["rate"]

    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,huf"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5)
            data = response.json()

        btc = data.get("bitcoin", {})
        btc_usd = btc.get("usd", 0)
        btc_huf = btc.get("huf", 0)

        if btc_usd > 0:
            rate = btc_huf / btc_usd
            usd_cache["rate"] = rate
            usd_cache["timestamp"] = now
            return rate

        return usd_cache["rate"]

    except:
        return usd_cache["rate"]


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):

    db: Session = SessionLocal()
    investments = db.query(Investment).all()

    prices = await get_prices()
    usd_huf_now = await get_usd_huf()

    processed = []

    total_value_usd = 0
    total_profit_usd = 0
    total_profit_huf = 0

    for inv in investments:

        coin_key = inv.asset.lower()

       if coin_key not in COINS:
    current_price = inv.buy_price
else:
    coin_id = COINS[coin_key]
    current_price = prices.get(coin_id, {}).get("usd", inv.buy_price)

        current_value = inv.quantity * current_price
        profit_usd = current_value - inv.invested_amount
        profit_huf = profit_usd * usd_huf_now

        today = datetime.utcnow().date()
        days_held = (today - inv.purchase_date.date()).days

        processed.append({
            "id": inv.id,
            "asset": inv.asset.upper(),
            "buy_price": inv.buy_price,
            "invested": inv.invested_amount,
            "quantity": inv.quantity,
            "current_price": current_price,
            "profit_usd": profit_usd,
            "profit_huf": profit_huf,
            "purchase_date": inv.purchase_date.strftime("%Y-%m-%d"),
            "days_held": days_held,
            "usd_huf_at_purchase": inv.usd_huf_rate_at_purchase
        })

        total_value_usd += current_value
        total_profit_usd += profit_usd
        total_profit_huf += profit_huf

    db.close()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "investments": processed,
        "usd_huf_now": usd_huf_now,
        "total_value_usd": total_value_usd,
        "total_profit_usd": total_profit_usd,
        "total_profit_huf": total_profit_huf,
        "prices": prices
    })


@app.post("/add")
async def add_investment(
    asset: str = Form(...),
    buy_price: float = Form(...),
    invested_amount: float = Form(...),
    purchase_date: str = Form(...)
):

    db: Session = SessionLocal()

    usd_huf_now = await get_usd_huf()
    quantity = invested_amount / buy_price

    investment = Investment(
        asset=asset.lower(),
        buy_price=buy_price,
        invested_amount=invested_amount,
        quantity=quantity,
        purchase_date=datetime.strptime(purchase_date, "%Y-%m-%d"),
        usd_huf_rate_at_purchase=usd_huf_now
    )

    db.add(investment)
    db.commit()
    db.close()

    return RedirectResponse("/", status_code=303)


@app.post("/delete/{investment_id}")
async def delete_investment(investment_id: int):

    db: Session = SessionLocal()

    investment = db.query(Investment).filter(Investment.id == investment_id).first()

    if investment:
        db.delete(investment)
        db.commit()

    db.close()

    return RedirectResponse("/", status_code=303)