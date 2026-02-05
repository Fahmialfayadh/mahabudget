"""
Report API routes.
Analytics, insights, and AI-generated narratives.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime

from services import supabase_service, generate_monthly_narrative
from routes.auth import get_current_user


router = APIRouter(prefix="/api/report", tags=["Report"])


async def get_user_id_from_request(request: Request) -> int:
    """Get user ID from authenticated session."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user.id


@router.get("/monthly")
async def get_monthly_report(
    request: Request,
    user_id: int = None,  # Keep for backwards compatibility but will be overridden
    year: int = Query(default=None),
    month: int = Query(default=None, ge=1, le=12)
):
    """
    Get AI-generated monthly narrative report.
    Includes spending summary and emotional insights.
    Uses authenticated user ID from JWT token.
    """
    try:
        # Get authenticated user ID
        auth_user_id = await get_user_id_from_request(request)
        
        # Default to current month
        now = datetime.now()
        year = year or now.year
        month = month or now.month
        
        # Get monthly expenses
        expenses = await supabase_service.get_monthly_expenses(auth_user_id, year, month)
        
        if not expenses:
            return {
                "success": True,
                "month": f"{year}-{month:02d}",
                "message": "Belum ada transaksi bulan ini. Yuk mulai catat pengeluaranmu!",
                "stats": {
                    "total": 0,
                    "count": 0,
                    "average": 0
                },
                "narrative": None
            }
        
        # Calculate stats
        total_amount = sum(e.get("amount", 0) for e in expenses)
        tx_count = len(expenses)
        avg_amount = total_amount // tx_count if tx_count > 0 else 0
        
        # Get emotional breakdown
        emotion_summary = {}
        for expense in expenses:
            emotion = expense.get("emotion_label") or "Netral"
            amount = expense.get("amount") or 0
            if emotion in emotion_summary:
                emotion_summary[emotion]["total"] += amount
                emotion_summary[emotion]["count"] += 1
            else:
                emotion_summary[emotion] = {"total": amount, "count": 1}
        
        # Generate narrative using The Bestie
        narrative = await generate_monthly_narrative(
            expenses=expenses,
            total_amount=total_amount,
            emotion_summary=emotion_summary
        )
        
        return {
            "success": True,
            "month": f"{year}-{month:02d}",
            "stats": {
                "total": total_amount,
                "count": tx_count,
                "average": avg_amount
            },
            "emotion_breakdown": emotion_summary,
            "narrative": narrative
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@router.get("/emotional")
async def get_emotional_summary(request: Request, user_id: int = None):
    """
    Get emotional spending breakdown.
    Shows which emotions lead to most spending.
    Uses authenticated user ID from JWT token.
    """
    try:
        # Get authenticated user ID
        auth_user_id = await get_user_id_from_request(request)
        
        summary = await supabase_service.get_emotional_summary(auth_user_id)
        
        # Calculate percentages
        total = sum(item["total"] for item in summary)
        for item in summary:
            item["percentage"] = round((item["total"] / total * 100), 1) if total > 0 else 0
        
        # Sort by total (descending)
        summary.sort(key=lambda x: x["total"], reverse=True)
        
        return {
            "success": True,
            "emotional_spending": summary,
            "total_tracked": total,
            "insight": generate_emotional_insight(summary) if summary else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching emotional summary: {str(e)}")


@router.get("/stats")
async def get_basic_stats(
    request: Request,
    user_id: int = None,  # Keep for backwards compatibility but will be overridden
    year: int = Query(default=None),
    month: int = Query(default=None, ge=1, le=12)
):
    """
    Get basic spending statistics.
    Uses authenticated user ID from JWT token.
    """
    try:
        # Get authenticated user ID
        auth_user_id = await get_user_id_from_request(request)
        
        now = datetime.now()
        year = year or now.year
        month = month or now.month
        
        expenses = await supabase_service.get_monthly_expenses(auth_user_id, year, month)
        
        if not expenses:
            return {
                "success": True,
                "month": f"{year}-{month:02d}",
                "total": 0,
                "count": 0,
                "average": 0,
                "highest": None,
                "categories": {}
            }
        
        # Calculate stats
        amounts = [e.get("amount", 0) for e in expenses]
        total = sum(amounts)
        count = len(expenses)
        average = total // count if count > 0 else 0
        highest = max(expenses, key=lambda x: x.get("amount", 0))
        
        # Category breakdown
        categories = {}
        for expense in expenses:
            cat = expense.get("category") or "Lainnya"
            amt = expense.get("amount") or 0
            if cat in categories:
                categories[cat] += amt
            else:
                categories[cat] = amt
        
        return {
            "success": True,
            "month": f"{year}-{month:02d}",
            "total": total,
            "count": count,
            "average": average,
            "highest": {
                "item": highest.get("item_name"),
                "amount": highest.get("amount"),
                "date": highest.get("date")
            },
            "categories": categories
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")


def generate_emotional_insight(summary: list) -> str:
    """Generate simple insight from emotional spending data."""
    if not summary:
        return None
    
    top = summary[0]
    emotion = top["emotion"]
    percentage = top["percentage"]
    
    insights = {
        "Stress": f"Wah, {percentage}% pengeluaran lu karena stress. Coba cari aktivitas stress relief yang lebih murah ya!",
        "Sedih": f"Hmm, {percentage}% keluar pas lagi sedih. Curhat sama temen kadang lebih healing lho daripada belanja.",
        "Senang": f"Nice! {percentage}% pengeluaran lu pas lagi senang. Boleh lah treat yourself, asal terkontrol~",
        "Marah": f"Hmm, {percentage}% keluar pas lagi kesel. Deep breath dulu sebelum checkout next time!",
        "Lapar": f"Wkwk {percentage}% buat makan. Wajar sih, siapa yang tahan sama lapar 😂",
        "Netral": f"{percentage}% pengeluaran lu terencana dengan baik. Mantap!",
    }
    
    return insights.get(emotion, f"Emosi {emotion} mendominasi {percentage}% pengeluaran lu.")


# ==================== REGRET AUDIT & INSIGHTS ====================

@router.get("/audit")
async def get_audit_data(request: Request):
    """
    Get candidates for Regret Audit and total wasted stats.
    """
    try:
        auth_user_id = await get_user_id_from_request(request)
        
        candidates = await supabase_service.get_audit_candidates(auth_user_id)
        stats = await supabase_service.get_regret_stats(auth_user_id)
        
        return {
            "success": True,
            "candidates": candidates,
            "stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching audit data: {str(e)}")


@router.post("/audit/{expense_id}")
async def set_regret_status(
    expense_id: int, 
    is_regret: bool = Query(..., description="True if regret, False if worth it"),
    request: Request = None
):
    """
    Mark an expense as Regret (Dana Terbuang) or Worth It.
    """
    try:
        # Use helper from expense route or re-implement simple auth here
        # Since I cannot import from expense route easily without circular, I just use auth service
        if request:
             auth_user_id = await get_user_id_from_request(request)
        else:
             # Fallback or strict check
             auth_user = await get_current_user(request)
             if not auth_user:
                 raise HTTPException(status_code=401, detail="Not authenticated")
             auth_user_id = auth_user.id

        # Verify ownership
        expense = await supabase_service.get_expense_by_id(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        if expense.get("user_id") != auth_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Update
        from models import ExpenseUpdate
        update_data = ExpenseUpdate(is_regret=is_regret)
        updated = await supabase_service.update_expense(expense_id, update_data)
        
        return {"success": True, "expense": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating regret status: {str(e)}")


@router.get("/scatter")
async def get_scatter_data(
    request: Request,
    limit: int = 100
):
    """
    Get data for Mood vs Value scatter plot.
    """
    try:
        auth_user_id = await get_user_id_from_request(request)
        
        # Get recent expenses
        expenses = await supabase_service.get_user_expenses(auth_user_id, limit=limit)
        
        # Map emotions to X-axis score
        emotion_map = {
            "Marah": -2,
            "Mukanya Merah": -2, # Variasi
            "Stress": -1.5,
            "Sedih": -1, 
            "Lapar": -0.5,
            "Netral": 0,
            "Senang": 2,
            "Bahagia": 2.5
        }
        
        data_points = []
        for e in expenses:
            emotion = e.get("emotion_label", "Netral")
            x_val = emotion_map.get(emotion, 0)
            
            # Use sentiment score if specific emotion not mapped, or average it
            if x_val == 0 and e.get("sentiment_score"):
                # Sentiment usually -1 to 1. Map to -2 to 2 range roughly
                x_val = float(e.get("sentiment_score")) * 2
                
            data_points.append({
                "x": x_val, # Mood
                "y": e.get("amount", 0), # Value
                "item": e.get("item_name"),
                "emotion": emotion,
                "date": e.get("date")
            })
            
        return {
            "success": True,
            "data": data_points
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching scatter data: {str(e)}")

