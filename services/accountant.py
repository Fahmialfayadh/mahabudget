"""
The Accountant AI Service - Data Extraction Layer
Uses Llama 8B for fast, accurate expense data extraction from informal text.
Supports extracting MULTIPLE expenses from a single message.
"""

import json
import re
from groq import Groq
from typing import Optional, Tuple, List

from config import settings
from models import ExpenseExtraction, EmotionLabel, ExpenseCategory


# Initialize Groq client
groq_client = Groq(api_key=settings.groq_api_key)


def has_expense_pattern(message: str) -> bool:
    """
    Check if message likely contains an expense to record.
    Returns False for casual chat, greetings, reactions, etc.
    """
    message_lower = message.lower().strip()
    
    # Skip very short messages (likely reactions)
    if len(message_lower) < 5:
        return False
    
    # Skip common casual chat patterns
    casual_patterns = [
        r'^(hai|halo|hi|hey|yo)\b',          # Greetings
        r'^(oke|ok|siap|mantap|nice|wkwk|haha|lol|wkwkwk)\b',  # Reactions
        r'^(makasih|thanks|thx|terima kasih)',  # Thanks
        r'^(iya|yoi|yup|yes|ya|bener|betul)',   # Affirmations
        r'^(ga|gak|nggak|tidak|no|nope)',       # Negations
        r'^(kenyang|puas|enak|mantul|mantep)',  # Satisfaction without amount
        r'^(mahal|murah)\s*(bgt|banget|amat)?$', # Just price comments without detail
        r'^gimana|bagaimana|apa kabar',          # Questions
        r'^(sedih|seneng|senang|kesel|marah)\s*(bgt|banget)?$',  # Just emotions
        r'mana ada',                             # Questioning
    ]
    
    for pattern in casual_patterns:
        if re.search(pattern, message_lower):
            # But if it contains money indicators, still process it
            if has_money_indicator(message_lower):
                return True
            return False
    
    # Check if message has money/expense indicators
    return has_money_indicator(message_lower)


def has_money_indicator(message: str) -> bool:
    """Check if message contains money/expense related patterns."""
    money_patterns = [
        r'\d+\s*[kr]',           # 50k, 12r
        r'\d+\s*rb',             # 50rb
        r'\d+\s*ribu',           # 50ribu
        r'\d+\s*jt',             # 2jt
        r'\d+\s*juta',           # 2juta
        r'\d{4,}',               # 50000 (4+ digit numbers)
        r'(beli|bayar|abis|habis|keluar|spend)',  # Transaction verbs
        r'(harga|biaya|ongkir|ongkos)',           # Cost words
    ]
    
    for pattern in money_patterns:
        if re.search(pattern, message.lower()):
            return True
    return False


def count_expense_indicators(message: str) -> int:
    """Count how many separate expenses might be in the message."""
    message_lower = message.lower()
    
    # Count money patterns
    money_count = len(re.findall(r'\d+\s*(k|rb|ribu|jt|juta)\b', message_lower))
    money_count += len(re.findall(r'\d{4,}', message_lower))
    
    # Also count transaction separators
    separators = len(re.findall(r'(,|sama|dan|plus|terus|abis itu|trus|\+)', message_lower))
    
    return max(money_count, 1)


def detect_emotion_from_text(message: str) -> Tuple[EmotionLabel, float]:
    """
    Detect emotion from Indonesian slang/informal text.
    Returns (emotion, sentiment_score)
    """
    message_lower = message.lower()
    
    # Anger indicators (Indonesian slang)
    anger_words = ['anjing', 'anjir', 'bangsat', 'babi', 'kesel', 'kesal', 
                   'emosi', 'bete', 'bt', 'marah', 'goblok', 'tolol', 'kampret',
                   'sialan', 'sial', 'nyebelin', 'sebel', 'jengkel']
    
    # Sadness indicators
    sad_words = ['sedih', 'nyesel', 'menyesal', 'kecewa', 'galau', 'nangis',
                 'sakit hati', 'patah hati', 'gagal', 'rugi', 'boros']
    
    # Happy indicators
    happy_words = ['seneng', 'senang', 'happy', 'yey', 'yeay', 'hore', 'asik',
                   'mantap', 'mantul', 'keren', 'seru', 'bagus', 'puas', 'worth']
    
    # Stress indicators
    stress_words = ['stress', 'stres', 'capek', 'cape', 'lelah', 'pusing',
                    'mumet', 'ribet', 'deadline', 'lembur', 'overtime', 'sibuk']
    
    # Hunger indicators
    hunger_words = ['lapar', 'laper', 'hungry', 'pengen makan', 'kelaparan']
    
    for word in anger_words:
        if word in message_lower:
            return EmotionLabel.MARAH, -0.6
    
    for word in sad_words:
        if word in message_lower:
            return EmotionLabel.SEDIH, -0.5
    
    for word in stress_words:
        if word in message_lower:
            return EmotionLabel.STRESS, -0.4
    
    for word in happy_words:
        if word in message_lower:
            return EmotionLabel.SENANG, 0.7
    
    for word in hunger_words:
        if word in message_lower:
            return EmotionLabel.LAPAR, 0.1
    
    return EmotionLabel.NETRAL, 0.0


# System prompt for MULTIPLE expense extraction
ACCOUNTANT_SYSTEM_PROMPT = """Kamu adalah akuntan digital yang mengekstrak data transaksi dari curhat pengguna Indonesia.
Tugasmu: Baca teks informal, ekstrak SEMUA transaksi dalam format JSON ARRAY.

PENTING: User bisa lapor BANYAK pengeluaran dalam 1 pesan. Ekstrak SEMUA transaksi yang ada.

RULES:
1. Nominal:
   - "25rb" atau "25k" = 25000 (Dua puluh lima ribu)
   - "250rb" atau "250k" = 250000 (Dua ratus lima puluh ribu)
   - "2.5jt" = 2500000 (Dua setengah juta)
   - HATI-HATI dengan jumlah nol. "25rb" BUKAN 250000.
2. Kategori: Makanan & Minuman, Transport, Fashion, Hiburan, Belanja, Tagihan, Lainnya
3. Emosi: Marah, Sedih, Senang, Lapar, Stress, Netral (berdasarkan keseluruhan mood pesan)
4. Kata kasar (anjing, anjir, bangsat) = Marah
5. OUTPUT HARUS JSON ARRAY, BUKAN OBJECT TUNGGAL

CONTOH:

Input: "hari ini beli kopi 25k, makan siang 35k"
Output: [{"item_name":"Kopi","amount":25000,"category":"Makanan & Minuman","emotion":"Netral","sentiment_score":0.0,"ai_confidence":0.95},{"item_name":"Makan Siang","amount":35000,"category":"Makanan & Minuman","emotion":"Netral","sentiment_score":0.0,"ai_confidence":0.95}]

Input: "beli ayam 12k anjing mahal bgt"
Output: [{"item_name":"Ayam","amount":12000,"category":"Makanan & Minuman","emotion":"Marah","sentiment_score":-0.6,"ai_confidence":0.92}]

JANGAN tambahkan teks apapun selain JSON ARRAY."""


def normalize_amount_string(text: str) -> str:
    """Pre-process text to normalize amount patterns."""
    text = text.lower()
    
    # Helper to handle decimal multiplication safely
    def replace_million_decimal(match):
        whole = int(match.group(1))
        decimal_str = match.group(2)
        # Pad or truncate decimal part to handle correct multiplier
        # 2.5 -> 500000, 2.05 -> 050000
        multiplier = 1000000
        val = whole * multiplier
        
        if decimal_str:
            decimal_val = float(f"0.{decimal_str}")
            val += int(decimal_val * multiplier)
            
        return str(int(val))

    patterns = [
        # Normalisasi 'k' atau 'rb' -> 25k -> 25000
        (r'(\d+)\s*k\b', lambda m: str(int(m.group(1)) * 1000)),
        (r'(\d+)\s*rb\b', lambda m: str(int(m.group(1)) * 1000)),
        (r'(\d+)\s*ribu\b', lambda m: str(int(m.group(1)) * 1000)),
        
        # Normalisasi 'jt' dengan desimal -> 2.5jt -> 2500000
        (r'(\d+)[.,](\d+)\s*jt\b', replace_million_decimal),
        (r'(\d+)[.,](\d+)\s*juta\b', replace_million_decimal),
        
        # Normalisasi 'jt' bulat -> 2jt -> 2000000
        (r'(\d+)\s*jt\b', lambda m: str(int(m.group(1)) * 1000000)),
        (r'(\d+)\s*juta\b', lambda m: str(int(m.group(1)) * 1000000)),
    ]
    
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def extract_amount_fallback(text: str) -> Optional[int]:
    """Fallback function to extract amount from text."""
    # First define multipliers
    multipliers = {
        'k': 1000,
        'rb': 1000,
        'ribu': 1000,
        'jt': 1000000,
        'juta': 1000000
    }
    
    text = text.lower()
    
    # Try direct matches with suffix
    # 25k, 25rb, 25000
    for suffix, multiplier in multipliers.items():
        # Match integer with suffix
        pattern = r'(\d+)\s*' + suffix + r'\b'
        match = re.search(pattern, text)
        if match:
            return int(match.group(1)) * multiplier
            
    # Match decimal millions (2.5jt)
    match = re.search(r'(\d+)[.,](\d+)\s*(jt|juta)\b', text)
    if match:
        val = float(f"{match.group(1)}.{match.group(2)}")
        return int(val * 1000000)
        
    # Match large plain numbers (>= 1000)
    match = re.search(r'(\d{4,})', text)
    if match:
        return int(match.group(1))
        
    return None


def parse_ai_response(response_text: str) -> List[dict]:
    """Parse AI response and extract JSON array of expenses."""
    response_text = response_text.strip()
    
    # Try to find JSON array in the response
    array_match = re.search(r'\[[\s\S]*\]', response_text)
    if array_match:
        try:
            result = json.loads(array_match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    
    # Try to find single JSON object and wrap in array
    obj_match = re.search(r'\{[^}]+\}', response_text, re.DOTALL)
    if obj_match:
        try:
            result = json.loads(obj_match.group())
            if isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass
    
    return []


def map_category(category_str: str) -> ExpenseCategory:
    """Map extracted category string to enum."""
    category_map = {
        "makanan & minuman": ExpenseCategory.MAKANAN_MINUMAN,
        "makanan": ExpenseCategory.MAKANAN_MINUMAN,
        "minuman": ExpenseCategory.MAKANAN_MINUMAN,
        "food": ExpenseCategory.MAKANAN_MINUMAN,
        "transport": ExpenseCategory.TRANSPORT,
        "transportasi": ExpenseCategory.TRANSPORT,
        "fashion": ExpenseCategory.FASHION,
        "pakaian": ExpenseCategory.FASHION,
        "hiburan": ExpenseCategory.HIBURAN,
        "entertainment": ExpenseCategory.HIBURAN,
        "belanja": ExpenseCategory.BELANJA,
        "shopping": ExpenseCategory.BELANJA,
        "tagihan": ExpenseCategory.TAGIHAN,
        "bill": ExpenseCategory.TAGIHAN,
        "lainnya": ExpenseCategory.LAINNYA,
        "other": ExpenseCategory.LAINNYA,
    }
    return category_map.get(category_str.lower(), ExpenseCategory.LAINNYA)


def map_emotion(emotion_str: str) -> EmotionLabel:
    """Map extracted emotion string to enum."""
    emotion_map = {
        "marah": EmotionLabel.MARAH,
        "angry": EmotionLabel.MARAH,
        "kesel": EmotionLabel.MARAH,
        "sedih": EmotionLabel.SEDIH,
        "sad": EmotionLabel.SEDIH,
        "nyesel": EmotionLabel.SEDIH,
        "senang": EmotionLabel.SENANG,
        "happy": EmotionLabel.SENANG,
        "bahagia": EmotionLabel.SENANG,
        "lapar": EmotionLabel.LAPAR,
        "hungry": EmotionLabel.LAPAR,
        "stress": EmotionLabel.STRESS,
        "stressed": EmotionLabel.STRESS,
        "capek": EmotionLabel.STRESS,
        "netral": EmotionLabel.NETRAL,
        "neutral": EmotionLabel.NETRAL,
        "biasa": EmotionLabel.NETRAL,
    }
    return emotion_map.get(emotion_str.lower(), EmotionLabel.NETRAL)


async def extract_multiple_expenses(user_message: str) -> List[ExpenseExtraction]:
    """
    Extract MULTIPLE expenses from a single message.
    Returns empty list if no expenses detected.
    
    Args:
        user_message: User's informal message that may contain multiple expenses
        
    Returns:
        List[ExpenseExtraction]: List of extracted expenses (can be empty)
    """
    # First check if this looks like an expense at all
    if not has_expense_pattern(user_message):
        return []
        
    # PRE-PROCESS: Normalize amounts to help LLM
    # "25rb" -> "25000", "2.5jt" -> "2500000"
    normalized_message = normalize_amount_string(user_message)
    
    try:
        # Call Groq API for multi-expense extraction
        chat_completion = groq_client.chat.completions.create(
            model=settings.accountant_model,
            messages=[
                {"role": "system", "content": ACCOUNTANT_SYSTEM_PROMPT},
                {"role": "user", "content": normalized_message} # Send normalized text
            ],
            temperature=0.1,
            max_tokens=600,
        )
        
        response_text = chat_completion.choices[0].message.content
        parsed_items = parse_ai_response(response_text)
        
        if not parsed_items:
            # Try fallback if AI failed
            fallback_amt = extract_amount_fallback(user_message)
            if fallback_amt:
                return [ExpenseExtraction(
                    item_name="Pengeluaran",
                    amount=fallback_amt,
                    category=ExpenseCategory.LAINNYA,
                    emotion=EmotionLabel.NETRAL,
                    sentiment_score=0.0,
                    ai_confidence=0.4
                )]
            return []
        
        # Detect overall emotion from text (override AI if needed)
        detected_emotion, detected_sentiment = detect_emotion_from_text(user_message)
        
        expenses = []
        for item in parsed_items:
            amount = item.get("amount", 0)
            if not amount:
                continue  # Skip items without amount
            
            # Get AI emotion or use detected
            ai_emotion = map_emotion(item.get("emotion", "Netral"))
            if ai_emotion == EmotionLabel.NETRAL and detected_emotion != EmotionLabel.NETRAL:
                final_emotion = detected_emotion
                final_sentiment = detected_sentiment
            else:
                final_emotion = ai_emotion
                final_sentiment = float(item.get("sentiment_score", 0.0))
            
            expenses.append(ExpenseExtraction(
                item_name=item.get("item_name", "Unknown Item"),
                amount=int(amount),
                category=map_category(item.get("category", "Lainnya")),
                emotion=final_emotion,
                sentiment_score=final_sentiment,
                ai_confidence=float(item.get("ai_confidence", 0.7)),
            ))
        
        return expenses
        
    except Exception as e:
        print(f"Error in multi-expense extraction: {e}")
        
        # Fallback: try to extract at least one amount
        fallback_amount = extract_amount_fallback(user_message)
        if fallback_amount:
            detected_emotion, detected_sentiment = detect_emotion_from_text(user_message)
            return [ExpenseExtraction(
                item_name="Item tidak terdeteksi",
                amount=fallback_amount,
                category=ExpenseCategory.LAINNYA,
                emotion=detected_emotion,
                sentiment_score=detected_sentiment,
                ai_confidence=0.3,
            )]
        
        return []


# Keep backward compatibility - single expense extraction
async def extract_expense_data(user_message: str) -> Optional[ExpenseExtraction]:
    """
    Extract single expense (backward compatible).
    Returns first expense if multiple found, or None if none.
    """
    expenses = await extract_multiple_expenses(user_message)
    return expenses[0] if expenses else None


async def validate_extraction(
    extraction: Optional[ExpenseExtraction], 
    original_message: str
) -> tuple[bool, str]:
    """Validate the extraction result."""
    if extraction is None:
        return False, "No expense detected"
    
    issues = []
    
    if extraction.amount == 0:
        issues.append("nominal tidak terdeteksi")
    
    if extraction.item_name == "Item tidak terdeteksi":
        issues.append("item tidak terdeteksi")
    
    if extraction.ai_confidence < 0.5:
        issues.append("confidence rendah")
    
    if issues:
        return False, f"Perlu konfirmasi: {', '.join(issues)}"
    
    return True, "Extraction validated successfully"
