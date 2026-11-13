# app/scraper.py
from bs4 import BeautifulSoup
import httpx


async def check_product_price(url: str) -> float | None:
  """ფუნქცია შედის მითითებულ ლინკზე და ცდილობს ფასის ამოკითხვას HTML-დან."""
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  }

  async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
    try:
      response = await client.get(url, follow_redirects=True)
      if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        # ყურადღება: ეს სელექტორი (.product-price) უნდა მოვარგოთ იმ კონკრეტულ
        # საიტს, საიდანაც პროდუქტებს ამატებ (მაგალითად, ზუმერი, ალტა და ა.შ.)
        price_tag = soup.select_one(".product-price")

        if price_tag:
          # ვწმენდთ სიმბოლოებს (ლარის ნიშანი, გამოტოვებები) და ვაქცევთ რიცხვად
          price_text = (
              price_tag.text.replace("₾", "")
              .replace("lari", "")
              .replace("GEL", "")
              .strip()
          )
          # მძიმის წერტილით ჩანაცვლება თუ ათწილადია
          price_text = price_text.replace(",", ".")
          return float(price_text)
    except Exception as e:
      print(f"შეცდომა {url}-ის პარსვისას: {e}")

    return None