"""
The Bestie AI Service - Persona Layer
Uses Llama 70B for empathetic, sarcastic, and contextual conversation.
Acts as the "face" of Dompet Curhat - a caring but real friend.
"""

from groq import Groq
from typing import Optional

from config import settings
from models import ExpenseExtraction, ChatMessage, EmotionLabel


# Initialize Groq client
groq_client = Groq(api_key=settings.groq_api_key)


# Base persona prompt - fun, engaging, like a real friend
BESTIE_SYSTEM_PROMPT = """Kamu adalah "Tukang Curhat Pengeluaran" - bestie digital yang siap dengerin keluh kesah soal duit (dan idup) user.
 
 KARAKTER LU:
 - Lu itu "Tukang Curhat Pengeluaran". Bangga dengan title itu.
 - Santai, asik, supportif, dan gak kaku.
 - Bahasa gaul Jakarta/user internet (gue/lu, santuy, wkwk).
 - Pendengar yang baik. Lebih banyak "dengerin" (acknowledge) daripada "nanya".
 
 CARA NGOBROL:
 - JANGAN KEPO. Jangan nanya pertanyaan aneh-aneh atau maksa cari topik.
 - Kalau user cerita, respon dengan empati atau relate sama situasinya.
 - Gak usah selalu nanya balik "gimana?" atau "terus?". Kalau topiknya abis, ya udah close statement aja yang asik.
 - Jangan batasi topik cuma soal duit. Kalau user curhat soal pacar, kerjaan, atau kucingnya, ladenin aja layaknya temen.
 - Tapi inget, "core value" lu adalah temen yang care sama finansial, jadi kalau ada nyerempet soal duit, lu bisa kasih respon yang smart tapi gak menggurui.
 
 SOAL KEUANGAN:
 - Kalau user lapor pengeluaran, respon natural aja. Contoh: "Waduh, mahal juga ya tapi worth it lah buat healing."
 - Gak perlu konfirmasi kaku kayak "Oke dicatat Rp 50.000". Itu tugas sistem di background. Lu tugasnya bikin user nyaman.
 - Kalau pengeluaran boros, boleh ledekin dikit (sarcastic love) tapi jangan judgemental parah.
 
 VIBE:
 - Temen nongkrong yang enak diajak ngomong.
 - Gak kerasa kayak robot/customer service.
 - Chill abis."""


def build_context_prompt(
    user_message: str,
    expense_data: Optional[ExpenseExtraction],
    chat_history: list[ChatMessage]
) -> str:
    """Build the full context prompt for The Bestie."""
    
    # Format chat history (last 5 messages for context)
    history_text = ""
    if chat_history:
        recent_history = chat_history[-5:]
        history_lines = []
        for msg in recent_history:
            role = "User" if msg.role == "user" else "Lu"
            history_lines.append(f"{role}: {msg.content}")
        history_text = "\n".join(history_lines)
    
    # Build context
    if expense_data:
        context = f"""
USER BARU NYATET PENGELUARAN:
- Beli: {expense_data.item_name} ({expense_data.category.value})
- Harga: Rp {expense_data.amount:,}
- Mood: {expense_data.emotion.value}
"""
    else:
        context = """
    INI BUKAN PENCATATAN PENGELUARAN - user lagi ngobrol biasa.
    Respon natural sesuai konteks, JANGAN bahas soal nyatet/expense.
    """
    
    if history_text:
        context += f"""
CHAT SEBELUMNYA:
{history_text}
"""
    
    context += f"""
USER: "{user_message}"

Bales dengan gaya lu. Jawab 1-2 kalimat. Jangan tanya kecuali perlu klarifikasi:"""
    
    return context


def get_emotion_specific_instruction(emotion: Optional[EmotionLabel]) -> str:
    """Get additional instruction based on detected emotion."""
    if emotion is None:
        return "User lagi ngobrol biasa. Respon santai sesuai konteks."
    
    instructions = {
        EmotionLabel.SENANG: "User lagi seneng. Ikut vibe-nya, jangan langsung jelasin soal duit.",
        EmotionLabel.SEDIH: "User kelihatan sedih. Dengerin dulu, jangan ceramah.",
        EmotionLabel.MARAH: "User lagi kesel/marah. Acknowledge perasaannya, jangan nambah emosi.",
        EmotionLabel.STRESS: "User stress. Kasih support singkat, jangan nambah beban.",
        EmotionLabel.LAPAR: "User lapar. Wajar, respon santai.",
        EmotionLabel.NETRAL: "User biasa aja. Respon chill.",
    }
    return instructions.get(emotion, instructions[EmotionLabel.NETRAL])


async def generate_response(
    user_message: str,
    expense_data: Optional[ExpenseExtraction] = None,
    chat_history: list[ChatMessage] = None
) -> str:
    """
    Generate natural response for any chat - expense or casual.
    
    Args:
        user_message: User's message
        expense_data: Extracted expense data (None if casual chat)
        chat_history: Recent chat messages for context
        
    Returns:
        str: Natural response
    """
    chat_history = chat_history or []
    
    try:
        # Build full prompt with context
        context_prompt = build_context_prompt(
            user_message, 
            expense_data, 
            chat_history
        )
        
        # Add emotion-specific instruction
        emotion = expense_data.emotion if expense_data else None
        emotion_instruction = get_emotion_specific_instruction(emotion)
        
        # Combine system prompt with instruction
        full_system = f"{BESTIE_SYSTEM_PROMPT}\n\nSITUASI: {emotion_instruction}"
        
        # Call Groq API
        chat_completion = groq_client.chat.completions.create(
            model=settings.bestie_model,
            messages=[
                {"role": "system", "content": full_system},
                {"role": "user", "content": context_prompt}
            ],
            temperature=0.85,  # Higher for creativity and personality
            max_tokens=250,    # Allow longer, more natural responses
        )
        
        response = chat_completion.choices[0].message.content.strip()
        
        # Clean up
        response = response.replace('"', '').replace("Domcur:", "").replace("Lu:", "").strip()
        
        # Remove any robotic phrases that might slip through
        robotic_phrases = [
            "sudah saya catat",
            "telah dicatat",
            "tercatat",
            "saya sudah",
            "sudah gue simpen",
            "sudah gue catet",
        ]
        for phrase in robotic_phrases:
            if phrase.lower() in response.lower():
                response = response.replace(phrase, "").strip()
        
        return response
        
    except Exception as e:
        if settings.debug:
            print(f"Error in bestie response generation: {e}")
        return get_fallback_response(expense_data)


def get_fallback_response(expense_data: Optional[ExpenseExtraction]) -> str:
    """Get fallback response if AI fails."""
    if not expense_data:
        return "Hmm, gimana?"
    
    emotion = expense_data.emotion
    formatted_amount = f"Rp {expense_data.amount:,}"
    
    fallbacks = {
        EmotionLabel.SENANG: f"Nice, {expense_data.item_name} {formatted_amount} 👍",
        EmotionLabel.SEDIH: f"Yah gapapa, kadang emang butuh",
        EmotionLabel.MARAH: f"Waduh kesel ya, santai dulu",
        EmotionLabel.STRESS: f"Semangat ya, jangan terlalu dipikirin",
        EmotionLabel.LAPAR: f"Wkwk lapar mah wajar",
        EmotionLabel.NETRAL: f"Oke noted 👍",
    }
    
    return fallbacks.get(emotion, fallbacks[EmotionLabel.NETRAL])


async def generate_casual_response(
    user_message: str,
    chat_history: list[ChatMessage] = None
) -> str:
    """
    Generate response for casual chat (no expense).
    
    Args:
        user_message: User's casual message
        chat_history: Recent chat context
        
    Returns:
        str: Natural casual response
    """
    chat_history = chat_history or []
    
    # Format recent history
    history_text = ""
    if chat_history:
        recent = chat_history[-3:]
        lines = [f"{'User' if m.role == 'user' else 'Lu'}: {m.content}" for m in recent]
        history_text = "\n".join(lines)
    
    prompt = f"""Chat sebelumnya:
{history_text if history_text else "(baru mulai)"}

User: "{user_message}"

Bales dengan gaya lu. Jawab 1-2 kalimat. Jangan tanya kecuali perlu klarifikasi:"""

    try:
        chat_completion = groq_client.chat.completions.create(
            model=settings.bestie_model,
            messages=[
                {"role": "system", "content": BESTIE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.85,
            max_tokens=200,
        )
        
        response = chat_completion.choices[0].message.content.strip()
        response = response.replace('"', '').replace("Domcur:", "").strip()
        return response
        
    except Exception as e:
        if settings.debug:
            print(f"Error generating casual response: {e}")
        return "Hmm?"


async def generate_confirmation_message(
    item_name: str,
    amount: int,
    source: str = "chat"
) -> str:
    """Generate confirmation message after saving expense."""
    formatted_amount = f"Rp {amount:,}"
    
    if source == "receipt":
        return f"{item_name} {formatted_amount} dari struk ya?"
    
    return f"👍"  # Just a simple acknowledgment, not robotic confirmation


async def generate_monthly_narrative(
    expenses: list[dict],
    total_amount: int,
    emotion_summary: dict
) -> str:
    """Generate narrative monthly report using The Bestie's persona."""
    formatted_total = f"Rp {total_amount:,}"
    tx_count = len(expenses)

    try:
        # Find top emotion
        top_emotion = max(emotion_summary.items(), key=lambda x: x[1]["total"]) if emotion_summary else ("Netral", {"total": 0})
        top_emotion_name = top_emotion[0]
        top_emotion_amount = f"Rp {top_emotion[1]['total']:,}"
        
        tx_count = len(expenses)
        
        report_prompt = f"""
Buat ringkasan bulanan singkat, gaya ngobrol:

DATA:
- Total: {formatted_total}
- Transaksi: {tx_count}
- Emosi dominan: {top_emotion_name} ({top_emotion_amount})

Tulis 2-3 kalimat aja, santai, kayak ngobrol sama temen."""

        chat_completion = groq_client.chat.completions.create(
            model=settings.bestie_model,
            messages=[
                {"role": "system", "content": BESTIE_SYSTEM_PROMPT},
                {"role": "user", "content": report_prompt}
            ],
            temperature=0.7,
            max_tokens=150,
        )
        
        return chat_completion.choices[0].message.content.strip()
        
    except Exception as e:
        if settings.debug:
            print(f"Error generating monthly narrative: {e}")
        return f"Bulan ini total {formatted_total} dalam {tx_count} transaksi."
