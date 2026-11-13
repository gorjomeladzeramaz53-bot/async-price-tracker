from datetime import datetime
from typing import List
from contextlib import asynccontextmanager
import asyncio
import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import ApplicationBuilder, CommandHandler

from app.database import get_db, AsyncSessionLocal, engine, Base
from app import models, schemas
from app.tracker import fetch_product_price
from app.telegram import send_telegram_alert, start_command, list_command, add_command, delete_command, check_command

def should_send_alert(product: models.Product, new_price: float) -> bool:
    if not product.target_price or new_price > product.target_price:
        return False
    if product.last_alert_price is None or new_price < product.last_alert_price:
        return True
    return False

async def check_all_products_background():
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(models.Product))
            products = result.scalars().all()
            
            for product in products:
                new_price = await fetch_product_price(product.url)
                if new_price is not None:
                    product.current_price = new_price
                    product.last_checked = datetime.utcnow()
                    
                    history_entry = models.PriceHistory(
                        product_id=product.id,
                        price=new_price
                    )
                    db.add(history_entry)
                    
                    if should_send_alert(product, new_price):
                        await send_telegram_alert(
                            product_title=product.title,
                            current_price=new_price,
                            target_price=product.target_price,
                            url=product.url
                        )
                        product.last_alert_price = new_price
            
            await db.commit()
            print("ფონური შემოწმება წარმატებით დასრულდა.")
        except Exception as e:
            print(f"შეცდომა ფონური შემოწმებისას: {e}")

async def start_telegram_bot():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        print("შეცდომა: TELEGRAM_TOKEN ვერ მოიძებნა!")
        return
    
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(CommandHandler("check", check_command))
    
    print("🤖 Telegram ბოტი ავტომატურად გააქტიურდა FastAPI-სთან ერთად...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all_products_background, "interval", minutes=1)
    scheduler.start()
    print("ფონური სქედულერი და მონაცემთა ბაზა წარმატებით გააქტიურდა!")
    
    # ვუშვებთ ტელეგრამის ბოტს ფონურ თასქად
    bot_task = asyncio.create_task(start_telegram_bot())
    
    yield
    
    scheduler.shutdown()
    try:
        bot_task.cancel()
    except Exception:
        pass

app = FastAPI(title="Async Price Tracker API", lifespan=lifespan)

# ვებ-ინტერფეისის (static ფოლდერის) მიბმა
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=FileResponse)
async def read_index():
    return "static/index.html"


@app.post("/products/", response_model=schemas.ProductResponse)
async def create_product(product: schemas.ProductCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(models.Product).where(models.Product.url == product.url))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="პროდუქტი ამ URL-ით უკვე დამატებულია")
    
    db_product = models.Product(
        title=product.title,
        url=product.url,
        target_price=getattr(product, "target_price", 0.0)
    )
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product


@app.get("/products/", response_model=List[schemas.ProductResponse])
async def get_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Product))
    return result.scalars().all()


@app.delete("/products/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Product).where(models.Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი ვერ მოიძებნა")
    
    await db.delete(product)
    await db.commit()
    return {"message": "პროდუქტი წარმატებით წაიშალა"}


@app.post("/products/{product_id}/check")
async def check_product_price(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Product).where(models.Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="პროდუქტი ვერ მოიძებნა")
    
    new_price = await fetch_product_price(product.url)
    if new_price is None:
        raise HTTPException(status_code=400, detail="ვებ-გვერდიდან ფასის ამოკითხვა ვერ მოხერხდა")
    
    product.current_price = new_price
    product.last_checked = datetime.utcnow()
    
    history_entry = models.PriceHistory(
        product_id=product.id,
        price=new_price
    )
    db.add(history_entry)
    
    alert_message = None
    if should_send_alert(product, new_price):
        alert_message = f"ყურადღება! ფასი დაეცა! ({new_price} <= {product.target_price})"
        await send_telegram_alert(
            product_title=product.title,
            current_price=new_price,
            target_price=product.target_price,
            url=product.url
        )
        product.last_alert_price = new_price
        
    await db.commit()
    await db.refresh(product)
    
    return {
        "product_id": product.id,
        "title": product.title,
        "current_price": new_price,
        "target_price": product.target_price,
        "alert": alert_message,
        "last_checked": product.last_checked
    }


@app.get("/products/{product_id}/history", response_model=List[schemas.PriceHistoryResponse])
async def get_product_history(product_id: int, db: AsyncSession = Depends(get_db)):
    product_result = await db.execute(select(models.Product).where(models.Product.id == product_id))
    if not product_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="პროდუქტი ვერ მოიძებნა")
    
    result = await db.execute(
        select(models.PriceHistory)
        .where(models.PriceHistory.product_id == product_id)
        .order_by(models.PriceHistory.timestamp.desc())
    )
    return result.scalars().all()