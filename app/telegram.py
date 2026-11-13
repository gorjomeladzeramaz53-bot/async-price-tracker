import os
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.future import select
from app.database import AsyncSessionLocal
from app.models import Product
from app.tracker import fetch_product_price

# სერვერის მისამართი (Render-ის ლინკი)
API_URL = "https://async-price-tracker.onrender.com"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        "გამარჯობა! მე ვარ ფასების ტრეკერი ბოტი. 🤖\n\n"
        "გამოიყენე შემდეგი ბრძანებები:\n"
        "/add დასახელება | ლინკი | სასურველი_ფასი\n"
        "/list - შენი პროდუქტების სია\n"
        "/check - ფასების მიმდინარე შემოწმება\n"
        "/delete ID - პროდუქტის წაშლა ID-ით"
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_URL}/products/")
            if response.status_code == 200:
                products = response.json()
                if not products:
                    await update.message.reply_text("📋 შენი პროდუქტების სია ცარიელია.")
                    return
                
                text = "📊 **შენი პროდუქტების სია:**\n\n"
                for p in products:
                    current_p = p.get('current_price')
                    price_text = f"{current_p} ₾" if current_p is not None else "არ არის შემოწმებული"
                    
                    text += f"📦 **ID: {p.get('id')}**\n"
                    text += f"🔹 დასახელება: {p.get('title')}\n"
                    text += f"💰 ფასი: {price_text} (მიზანი: {p.get('target_price')} ₾)\n"
                    text += f"🔗 {p.get('url')}\n"
                    text += "-------------------\n"
                
                await update.message.reply_text(text, parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ სერვერთან დაკავშირების შეცდომა.")
        except Exception as e:
            await update.message.reply_text(f"❌ შეცდომა: {e}")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    try:
        text = " ".join(context.args) if context.args else ""
        if not text or "|" not in text:
            await update.message.reply_text(
                "გთხოვთ მიუთითოთ სწორი ფორმატი:\n"
                "/add დასახელება | ლინკი | სასურველი_ფასი\n\n"
                "მაგალითი: /add მაუსი | https://site.ge/mouse | 50"
            )
            return

        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            await update.message.reply_text("❌ არასწორი ფორმატი. გთხოვთ გამოიყენოთ მილყინები (|).")
            return

        title, url, target_price_str = parts[0], parts[1], parts[2]
        target_price = float(target_price_str)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_URL}/products/",
                json={"title": title, "url": url, "target_price": target_price}
            )
            if response.status_code in [200, 201]:
                await update.message.reply_text(f"✅ პროდუქტი „{title}“ წარმატებით დაემატა!")
            else:
                try:
                    err_detail = response.json().get("detail", "უცნობი შეცდომა")
                except Exception:
                    err_detail = response.text
                await update.message.reply_text(f"❌ შეცდომა: {err_detail}")
    except ValueError:
        await update.message.reply_text("❌ ფასი უნდა იყოს რიცხვითი მნიშვნელობა!")
    except Exception as e:
        await update.message.reply_text(f"❌ შეცდომა: {e}")

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("გთხოვთ მიუთითოთ პროდუქტის ID. მაგალითი: /delete 1")
        return

    product_id = context.args[0]
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(f"{API_URL}/products/{product_id}")
            if response.status_code == 200:
                await update.message.reply_text(f"🗑️ პროდუქტი ID: {product_id} წარმატებით წაიშალა!")
            else:
                await update.message.reply_text("❌ პროდუქტი ამ ID-ით ვერ მოიძებნა.")
        except Exception as e:
            await update.message.reply_text(f"❌ შეცდომა: {e}")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ამოწმებს პროდუქტების ფასებს და აგზავნის პასუხს ტელეგრამში"""
    if not update.message:
        return
        
    chat_id = update.effective_chat.id
    await update.message.reply_text("🔍 ვამოწმებ პროდუქტების ფასებს საიტებზე, გთხოვთ დაიცადოთ...")
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Product))
        products = result.scalars().all()
        
        if not products:
            await update.message.reply_text("📦 შენს სიაში პროდუქტები ჯერ არ არის.")
            return
            
        checked_count = 0
        for product in products:
            if not product.url:
                continue
            
            new_price = await fetch_product_price(product.url)
            if new_price is not None:
                product.current_price = new_price
                checked_count += 1
                await update.message.reply_text(f"📦 {product.title}\n💰 მიმდინარე ფასი: {new_price} ₾")
                
                if product.target_price and new_price <= product.target_price:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=f"🔔 **ფასის ვარდნის ალერტი!**\n\n📦 პროდუქტი: **{product.title}**\n💰 მიმდინარე ფასი: **{new_price}₾** (შენი მიზანი: {product.target_price}₾)\n🔗 [ლინკი პროდუქტზე]({product.url})",
                        parse_mode="Markdown"
                    )
            else:
                await update.message.reply_text(f"❌ {product.title}-ს ფასის ამოკითხვა ვერ მოხერხდა.")
        
        await db.commit()
    
    await update.message.reply_text(f"✅ შემოწმდა და განახლდა {checked_count} პროდუქტი!")

async def send_telegram_alert(chat_id: str, message: str):
    """დამხმარე ფუნქცია შეტყობინებების გამოსაგზავნად"""
    if not TELEGRAM_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})
        except Exception as e:
            print(f"შეტყობინების გაგზავნის შეცდომა: {e}")