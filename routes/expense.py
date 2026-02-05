"""
Expense API routes.
CRUD operations for expense management and correction mode.
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import Optional

from models import ExpenseResponse, ExpenseUpdate, ExpenseCreate, ExpenseManualCreate
from services import supabase_service
from routes.auth import get_current_user


router = APIRouter(prefix="/api/expenses", tags=["Expenses"])


async def get_user_id_from_request(request: Request) -> int:
    """Get user ID from authenticated session."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user.id


@router.get("")
async def list_expenses(
    request: Request,
    user_id: Optional[int] = None,  # Keep for backwards compatibility but will be overridden
    limit: int = Query(default=50, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    year: Optional[int] = Query(default=None, ge=2000, le=2100),
    month: Optional[int] = Query(default=None, ge=1, le=12)
):
    """
    List user's expenses with pagination.
    Uses authenticated user ID, not query parameter.
    """
    try:
        # Get authenticated user ID
        auth_user_id = await get_user_id_from_request(request)
        
        if year and month:
            expenses = await supabase_service.get_monthly_expenses(
                user_id=auth_user_id,
                year=year,
                month=month
            )
        else:
            expenses = await supabase_service.get_user_expenses(
                user_id=auth_user_id,
                limit=limit,
                offset=offset
            )
        return {"expenses": expenses, "count": len(expenses)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching expenses: {str(e)}")


@router.get("/{expense_id}")
async def get_expense(expense_id: int, request: Request):
    """
    Get single expense by ID.
    Only returns expense if it belongs to authenticated user.
    """
    try:
        auth_user_id = await get_user_id_from_request(request)
        
        expense = await supabase_service.get_expense_by_id(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        # Verify ownership
        if expense.get("user_id") != auth_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return expense
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching expense: {str(e)}")


@router.put("/{expense_id}")
async def update_expense(expense_id: int, update_data: ExpenseUpdate, request: Request):
    """
    Update/correct an expense (correction mode).
    Only allows updating expenses belonging to authenticated user.
    """
    try:
        auth_user_id = await get_user_id_from_request(request)
        
        # Verify ownership first
        expense = await supabase_service.get_expense_by_id(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        if expense.get("user_id") != auth_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        updated = await supabase_service.update_expense(expense_id, update_data)
        if not updated:
            raise HTTPException(status_code=404, detail="Nothing to update")
        return {"success": True, "expense": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating expense: {str(e)}")


@router.delete("/{expense_id}")
async def delete_expense(expense_id: int, request: Request):
    """
    Delete an expense.
    Only allows deleting expenses belonging to authenticated user.
    """
    try:
        auth_user_id = await get_user_id_from_request(request)
        
        # Verify ownership first
        expense = await supabase_service.get_expense_by_id(expense_id)
        if not expense:
            raise HTTPException(status_code=404, detail="Expense not found")
        if expense.get("user_id") != auth_user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await supabase_service.delete_expense(expense_id)
        if not success:
            raise HTTPException(status_code=404, detail="Expense not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting expense: {str(e)}")


@router.post("/manual")
async def create_manual_expense(expense_data: ExpenseManualCreate, request: Request):
    """
    Create a new expense manually without AI extraction.
    """
    try:
        auth_user_id = await get_user_id_from_request(request)
        
        # Prepare Create model
        full_expense = ExpenseCreate(
            user_id=auth_user_id,
            item_name=expense_data.item_name,
            amount=expense_data.amount,
            category=expense_data.category,
            emotion_label=expense_data.emotion_label,
            date=expense_data.date, # Pass date if provided
            is_regret=expense_data.is_regret,
            sentiment_score=0.0, # Default/Recalculate if needed
            ai_confidence=1.0 # Manual input = 100% confidence
        )
        
        created = await supabase_service.create_expense(full_expense)
        return {"success": True, "expense": created}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating expense: {str(e)}")

