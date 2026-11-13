import httpx
from bs4 import BeautifulSoup

async def fetch_product_price(url: str) -> float | None:
    """
    ასინქრონულად ხსნის მოცემულ URL-ს და ცდილობს ფასის ამოკითხვას.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code != 200:
                return None
            
            # BeautifulSoup-ით HTML-ის დამუშავება
            soup = BeautifulSoup(response.text, "html.parser")
            
            # სამომავლოდ, რეალური საიტისთვის შეგიძლია აქ ჩასვა კონკრეტული სელექტორი, 
            # მაგალითად: price_tag = soup.find("span", class_="price-class")
            # ახლა კი ტესტირებისთვის ვაბრუნებთ სიმულაციურ ფასს
            return 99.99
            
    except Exception as e:
        print(f"სკრაპინგის შეცდომა {url}-სთვის: {e}")
        return None