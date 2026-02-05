"""
Chat API routes.
Main interaction endpoint for the Dompet Curhat chat interface.
"""

import re
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from typing import Optional

from models import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    ChatMessageCreate,
    ExpenseCreate,
    ExpenseExtraction,
    EmotionLabel,
    ExpenseCategory,
)
from services import (
    supabase_service,
    extract_expense_data,
    validate_extraction,
    generate_response,
    generate_confirmation_message,
    generate_monthly_narrative,
)
from routes.auth import get_current_user


router = APIRouter(prefix="/api/chat", tags=["Chat"])


def is_review_request(message: str) -> bool:
    """Check if user is asking for a review/report of their expenses."""
    review_keywords = [
        r'review',
        r'insight',
        r'laporan',
        r'rangkum',
        r'summary',
        r'pengeluaran.*(bulan|minggu|hari)',
        r'berapa.*(total|habis|keluar)',
        r'statistik',
        r'rekap',
        r'lihat.*(data|pengeluaran)',
    ]
    message_lower = message.lower()
    for pattern in review_keywords:
        if re.search(pattern, message_lower):
            return True
    return False


async def generate_review_response(user_id: int, message: str) -> str:
    """Generate review response based on actual database data."""
    from services.bestie import groq_client, BESTIE_SYSTEM_PROMPT
    from config import settings
    
    now = datetime.now()
    year = now.year
    month = now.month
    
    # Fetch actual expenses from database
    expenses = await supabase_service.get_monthly_expenses(user_id, year, month)
    
    if not expenses:
        return "Belum ada transaksi bulan ini. Yuk mulai catat pengeluaranmu! 💪"
    
    # Calculate real stats
    total_amount = sum(e.get("amount", 0) for e in expenses)
    tx_count = len(expenses)
    
    # Get emotional breakdown
    emotion_summary = {}
    category_summary = {}
    for expense in expenses:
        emotion = expense.get("emotion_label") or "Netral"
        category = expense.get("category") or "Lainnya"
        amount = expense.get("amount") or 0
        
        if emotion in emotion_summary:
            emotion_summary[emotion]["total"] += amount
            emotion_summary[emotion]["count"] += 1
        else:
            emotion_summary[emotion] = {"total": amount, "count": 1}
        
        if category in category_summary:
            category_summary[category] += amount
        else:
            category_summary[category] = amount
    
    # Find top emotion and category
    top_emotion = max(emotion_summary.items(), key=lambda x: x[1]["total"]) if emotion_summary else ("Netral", {"total": 0, "count": 0})
    top_category = max(category_summary.items(), key=lambda x: x[1]) if category_summary else ("Lainnya", 0)
    
    # Build recent transactions list (last 5)
    recent_items = []
    for exp in expenses[:5]:
        item = exp.get("item_name", "Unknown")
        amt = exp.get("amount", 0)
        recent_items.append(f"- {item}: Rp {amt:,}")
    recent_list = "\n".join(recent_items)
    
    # Build prompt with REAL data
    review_prompt = f"""
User minta review pengeluaran bulan ini. GUNAKAN DATA BERIKUT, JANGAN MENGARANG:

DATA AKTUAL BULAN INI ({now.strftime('%B %Y')}):
- Total Pengeluaran: Rp {total_amount:,}
- Jumlah Transaksi: {tx_count}
- Rata-rata per Transaksi: Rp {total_amount // tx_count if tx_count > 0 else 0:,}
- Emosi Paling Banyak Keluar Duit: {top_emotion[0]} (Rp {top_emotion[1]['total']:,} dalam {top_emotion[1]['count']} transaksi)
- Kategori Terbesar: {top_category[0]} (Rp {top_category[1]:,})

TRANSAKSI TERAKHIR:
{recent_list}

BREAKDOWN EMOSI:
{', '.join([f"{k}: Rp {v['total']:,}" for k, v in emotion_summary.items()])}

BREAKDOWN KATEGORI:
{', '.join([f"{k}: Rp {v:,}" for k, v in category_summary.items()])}

Buat ringkasan 2-4 kalimat dengan gaya Domcur (santai, friendly). 
PENTING: Gunakan ANGKA dan NAMA ITEM yang TEPAT dari data di atas. JANGAN MENGARANG.
Sebutkan total yang benar, kategori/emosi yang dominan, dan kasih insight singkat."""

    try:
        chat_completion = groq_client.chat.completions.create(
            model=settings.bestie_model,
            messages=[
                {"role": "system", "content": BESTIE_SYSTEM_PROMPT},
                {"role": "user", "content": review_prompt}
            ],
            temperature=0.5,  # Lower temperature for more factual response
            max_tokens=250,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating review: {e}")
        return f"Bulan ini lu udah spend Rp {total_amount:,} dalam {tx_count} transaksi. Emosi {top_emotion[0]} paling banyak bikin dompet jebol! 💸"


@router.post("", response_model=ChatResponse)
async def process_chat_message(chat_request: ChatRequest, http_request: Request):
    """
    Process user chat message:
    1. Check if it's a review/insight request
    2. Extract MULTIPLE expenses using The Accountant
    3. Save all expenses to database
    4. Generate empathetic response using The Bestie
    5. Save chat messages to history
    
    Uses authenticated user ID from JWT token.
    """
    from services import extract_multiple_expenses
    
    try:
        # Get authenticated user ID
        auth_user = await get_current_user(http_request)
        if not auth_user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        user_id = auth_user.id
        print(f"[DEBUG] Processing chat for user_id: {user_id}")
        
        # Step 1: Save user message to chat history
        user_chat = ChatMessageCreate(
            user_id=user_id,
            role="user",
            content=chat_request.message,
            type="text"
        )
        await supabase_service.save_chat_message(user_chat)
        
        # Step 2: Check if user is asking for a review/report
        if is_review_request(chat_request.message):
            ai_response = await generate_review_response(user_id, chat_request.message)
            
            assistant_chat = ChatMessageCreate(
                user_id=user_id,
                role="assistant",
                content=ai_response,
                type="review"
            )
            await supabase_service.save_chat_message(assistant_chat)
            
            return ChatResponse(
                message=ai_response,
                expense_saved=False,
                expenses_count=0,
                expense_data=None,
                requires_confirmation=False
            )
        
        # Step 3: Get chat history for context
        history_data = await supabase_service.get_chat_history(user_id, limit=10)
        chat_history = []
        for msg in history_data:
            role = msg.get("role", "user")
            if role not in ("user", "assistant"):
                role = "assistant" if role in ("bot", "system") else "user"
            chat_history.append(ChatMessage(
                role=role,
                content=msg.get("content", ""),
                transaction_id=msg.get("transaction_id")
            ))
        
        # Step 4: Extract MULTIPLE expenses using The Accountant
        extractions = await extract_multiple_expenses(chat_request.message)
        
        saved_expenses = []
        expense_data_list = []
        
        # Step 5: Save ALL extracted expenses
        for extraction in extractions:
            if extraction.amount > 0:
                expense_data = ExpenseCreate(
                    user_id=user_id,
                    item_name=extraction.item_name,
                    description=chat_request.message,
                    amount=extraction.amount,
                    category=extraction.category.value,
                    emotion_label=extraction.emotion.value,
                    sentiment_score=extraction.sentiment_score,
                    ai_confidence=extraction.ai_confidence,
                )
                saved = await supabase_service.create_expense(expense_data)
                saved_expenses.append(saved)
                expense_data_list.append({
                    "id": saved.get("id"),  # Include ID for editing
                    "item_name": extraction.item_name,
                    "amount": extraction.amount,
                    "category": extraction.category.value,
                    "emotion": extraction.emotion.value,
                    "sentiment_score": extraction.sentiment_score,
                    "ai_confidence": extraction.ai_confidence,
                })
        
        expenses_count = len(saved_expenses)
        expense_saved = expenses_count > 0
        
        # Step 6: Generate response using The Bestie
        # Pass first extraction for emotion context, or None if no expenses
        first_extraction = extractions[0] if extractions else None
        ai_response = await generate_response(
            user_message=chat_request.message,
            expense_data=first_extraction,
            chat_history=chat_history
        )
        
        # Step 7: Save AI response to chat history
        assistant_chat = ChatMessageCreate(
            user_id=user_id,
            role="assistant",
            content=ai_response,
            type="expense" if expense_saved else "text",
            transaction_id=saved_expenses[0].get("id") if saved_expenses else None
        )
        await supabase_service.save_chat_message(assistant_chat)
        
        return ChatResponse(
            message=ai_response,
            expense_saved=expense_saved,
            expenses_count=expenses_count,
            expense_data=expense_data_list if expense_saved else None,
            requires_confirmation=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[ERROR] Chat processing failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")


@router.get("/history/{user_id}")
async def get_chat_history(user_id: int, request: Request, limit: int = 50):
    """Get chat history for authenticated user only."""
    try:
        # Get authenticated user
        auth_user = await get_current_user(request)
        if not auth_user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Only allow accessing own chat history
        if user_id != auth_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        history = await supabase_service.get_chat_history(auth_user.id, limit=limit)
        return {"messages": history}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")


@router.delete("/clear/{user_id}")
async def clear_chat_history(user_id: int, request: Request):
    """Clear all chat history for authenticated user only."""
    try:
        # Get authenticated user
        auth_user = await get_current_user(request)
        if not auth_user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Only allow clearing own chat history
        if user_id != auth_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await supabase_service.clear_chat_history(auth_user.id)
        return {"success": True, "message": "Chat history cleared"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing chat: {str(e)}")


@router.delete("/{message_id}")
async def delete_chat_message(message_id: int, request: Request):
    """Delete a chat message. TODO: Add ownership verification."""
    try:
        # Get authenticated user
        auth_user = await get_current_user(request)
        if not auth_user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # TODO: Verify message belongs to user before deleting
        success = await supabase_service.delete_chat_message(message_id)
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting message: {str(e)}")
