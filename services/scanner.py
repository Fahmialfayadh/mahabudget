"""
The Scanner AI Service - Vision Layer (PaddleOCR Implementation)
Uses PaddleOCR (PP-OCRv4) for text extraction and Llama 8B (Accountant) for parsing.
"""

import base64
import httpx
import numpy as np
import cv2
from groq import Groq
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from io import BytesIO
from PIL import Image
from paddleocr import PaddleOCR

from config import settings


# Initialize Groq client
groq_client = Groq(api_key=settings.groq_api_key)

# Initialize PaddleOCR (English/Indonesian support)
# PaddleOCR v3.0+ uses new API without use_angle_cls
# lang='en' covers latin characters used in ID/EN
scanner_engine = PaddleOCR(lang='en')


class ReceiptItem(BaseModel):
    """Single item from receipt."""
    name: str
    quantity: int = 1
    price: int


class ReceiptData(BaseModel):
    """Extracted receipt data."""
    store_name: str = "Unknown Store"
    total_amount: int = 0
    date: Optional[str] = None
    items: list[ReceiptItem] = []
    raw_text: Optional[str] = None


# Updated System Prompt for TEXT processing (not Image)
PARSER_SYSTEM_PROMPT = """Kamu adalah JSON parser untuk data struk belanja.
Tugasmu: Ekstrak data dari TEKS OCR struk dan output sebagai JSON object.

OUTPUT FORMAT (WAJIB):
{
  "store_name": "Nama Toko",
  "total_amount": 12345,
  "date": "2024-01-10",
  "items": [{"name": "Item 1", "quantity": 1, "price": 5000}]
}

EKSTRAK:
- store_name: Nama toko/merchant (biasanya di bagian atas)
- total_amount: Total pembayaran FINAL (INTEGER, tanpa Rp/titik)
- date: Tanggal transaksi (format YYYY-MM-DD)
- items: Daftar item [{name, quantity, price}]

RULES:
- Nominal: Ambil angka saja (10.000 → 10000)
- Quantity: Default 1 jika tidak ada
- JANGAN tulis penjelasan, code, atau teks lain
- OUTPUT HANYA JSON OBJECT, tidak ada yang lain
"""


def extract_text_from_image(image_bytes: bytes) -> str:
    """
    Extract text using PaddleOCR v3.0+ (predict API).
    """
    try:
        print(f"[DEBUG Scanner] Image bytes length: {len(image_bytes)}")
        
        # Convert bytes to numpy array for OpenCV/Paddle
        # 1. Open with PIL to handle formats
        img = Image.open(BytesIO(image_bytes))
        print(f"[DEBUG Scanner] Image size: {img.size}, mode: {img.mode}")
        
        # 2. Convert to RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        # 3. Convert to numpy array
        img_np = np.array(img)
        print(f"[DEBUG Scanner] NumPy array shape: {img_np.shape}")
        
        # 4. PaddleOCR expects BGR for cv2 compatibility
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # 5. Run OCR using new predict() API (PaddleOCR v3.0+)
        print("[DEBUG Scanner] Running PaddleOCR predict...")
        result = scanner_engine.predict(img_np)
        print(f"[DEBUG Scanner] OCR result type: {type(result)}")
        
        full_text = []
        
        # Handle new result format (list of dicts with 'rec_texts' key)
        if result:
            for page_result in result:
                if isinstance(page_result, dict):
                    # New format: dict with 'rec_texts' key
                    rec_texts = page_result.get('rec_texts', [])
                    full_text.extend(rec_texts)
                    print(f"[DEBUG Scanner] Found rec_texts: {rec_texts}")
                elif isinstance(page_result, list):
                    # Old format fallback: list of [coords, (text, conf)]
                    for line in page_result:
                        if isinstance(line, (list, tuple)) and len(line) >= 2:
                            text = line[1][0] if isinstance(line[1], (list, tuple)) else line[1]
                            full_text.append(str(text))
                
        extracted = "\n".join(full_text)
        print(f"[DEBUG Scanner] Extracted text: {extracted[:200] if extracted else 'EMPTY'}")
        return extracted
        
    except Exception as e:
        import traceback
        print(f"PaddleOCR Error: {e}")
        traceback.print_exc()
        return ""


async def parse_text_with_accountant(text: str) -> ReceiptData:
    """
    Use Accountant Model (Llama 3.1) to parse OCR text into JSON.
    """
    print(f"[DEBUG Accountant] Received text length: {len(text)}")
    print(f"[DEBUG Accountant] Text preview: {text[:300] if text else 'EMPTY'}")
    
    if not text.strip():
        print("[DEBUG Accountant] Text is empty, returning default ReceiptData")
        return ReceiptData(raw_text="No text extracted from image.")
        
    try:
        print(f"[DEBUG Accountant] Calling Groq with model: {settings.accountant_model}")
        chat_completion = groq_client.chat.completions.create(
            model=settings.accountant_model,
            messages=[
                {
                    "role": "system",
                    "content": PARSER_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.1,
            max_tokens=600,
            response_format={"type": "json_object"},  # Force JSON output
        )
        
        response_text = chat_completion.choices[0].message.content
        print(f"[DEBUG Accountant] AI Response: {response_text}")
        
        receipt_data = parse_receipt_response(response_text)
        print(f"[DEBUG Accountant] Parsed total_amount: {receipt_data.total_amount}")
        print(f"[DEBUG Accountant] Parsed store_name: {receipt_data.store_name}")
        
        receipt_data.raw_text = text # Store original OCR text
        return receipt_data
        
    except Exception as e:
        import traceback
        print(f"Accountant Parsing Error: {e}")
        traceback.print_exc()
        return ReceiptData(raw_text=text) # Return raw text if parsing fails


async def read_receipt_from_url(image_url: str) -> ReceiptData:
    """
    Read receipt from URL using PaddleOCR pipeline.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            image_bytes = resp.content
            
        # 1. Extract Text
        raw_text = extract_text_from_image(image_bytes)
        
        # 2. Parse with Accountant
        return await parse_text_with_accountant(raw_text)
        
    except Exception as e:
        print(f"Error reading receipt from URL: {e}")
        return ReceiptData(raw_text=f"Error: {str(e)}")


async def read_receipt_from_base64(image_base64: str) -> ReceiptData:
    """
    Read receipt from base64 using PaddleOCR pipeline.
    """
    try:
        # Strip header if present
        if "base64," in image_base64:
            image_base64 = image_base64.split("base64,")[1]
            
        image_bytes = base64.b64decode(image_base64)
        
        # 1. Extract Text
        raw_text = extract_text_from_image(image_bytes)
        
        # 2. Parse with Accountant
        return await parse_text_with_accountant(raw_text)
        
    except Exception as e:
        print(f"Error reading receipt from base64: {e}")
        return ReceiptData(raw_text=f"Error: {str(e)}")


def parse_receipt_response(response_text: str) -> ReceiptData:
    """Parse AI response into ReceiptData object."""
    import json
    import re
    
    print(f"[DEBUG Parser] Attempting to parse: {response_text[:500]}")
    
    try:
        # Method 1: Try direct JSON parse (if response is pure JSON)
        try:
            data = json.loads(response_text.strip())
            print("[DEBUG Parser] Direct JSON parse succeeded")
        except json.JSONDecodeError:
            # Method 2: Find JSON object using bracket matching
            start_idx = response_text.find('{')
            if start_idx == -1:
                print("[DEBUG Parser] No JSON object found")
                return ReceiptData(raw_text=response_text)
            
            # Count brackets to find matching closing brace
            bracket_count = 0
            end_idx = start_idx
            for i, char in enumerate(response_text[start_idx:], start_idx):
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_idx = i + 1
                        break
            
            json_str = response_text[start_idx:end_idx]
            print(f"[DEBUG Parser] Extracted JSON: {json_str[:300]}...")
            data = json.loads(json_str)
        
        # Parse items
        items = []
        for item in data.get("items", []):
            try:
                items.append(ReceiptItem(
                    name=item.get("name", "Unknown"),
                    quantity=int(item.get("quantity", 1)),
                    price=int(item.get("price", 0))
                ))
            except (ValueError, TypeError):
                continue
        
        result = ReceiptData(
            store_name=data.get("store_name", "Unknown Store"),
            total_amount=int(data.get("total_amount", 0)),
            date=data.get("date"),
            items=items,
            raw_text=response_text
        )
        print(f"[DEBUG Parser] Successfully parsed: store={result.store_name}, total={result.total_amount}")
        return result
    except Exception as e:
        print(f"Error parsing receipt response: {e}")
    
    return ReceiptData(raw_text=response_text)


def format_for_confirmation(receipt_data: ReceiptData) -> str:
    """Format receipt data for user confirmation message."""
    formatted_amount = f"Rp {receipt_data.total_amount:,}"
    
    if receipt_data.items:
        items_text = ", ".join([item.name for item in receipt_data.items[:3]])
        if len(receipt_data.items) > 3:
            items_text += f" (+{len(receipt_data.items) - 3} lainnya)"
        return f"Dari struk {receipt_data.store_name}: {items_text}. Total {formatted_amount}. Bener gak?"
    
    if receipt_data.raw_text and receipt_data.total_amount == 0:
         return f"Hmm, aku bisa baca teksnya tapi gak nemu totalnya. Coba cek struknya lagi? (Text: {receipt_data.raw_text[:50]}...)"

    return f"Dari struk {receipt_data.store_name}: Total {formatted_amount}. Bener gak?"


async def compress_image(image_bytes: bytes, max_size_kb: int = 500) -> bytes:
    """Compress image for faster processing."""
    try:
        img = Image.open(BytesIO(image_bytes))
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Resize if too large
        max_dimension = 1024
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Compress
        output = BytesIO()
        quality = 85
        img.save(output, format='JPEG', quality=quality, optimize=True)
        
        # Further compress if still too large
        while output.tell() > max_size_kb * 1024 and quality > 30:
            output = BytesIO()
            quality -= 10
            img.save(output, format='JPEG', quality=quality, optimize=True)
        
        return output.getvalue()
        
    except Exception as e:
        print(f"Error compressing image: {e}")
        return image_bytes


async def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 data URL."""
    compressed = await compress_image(image_bytes)
    base64_data = base64.b64encode(compressed).decode('utf-8')
    return f"data:image/jpeg;base64,{base64_data}"
