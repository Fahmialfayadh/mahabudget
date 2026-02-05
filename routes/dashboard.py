from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel

from services.supabase_client import supabase_service
from routes.auth import require_auth
from models import UserInsightResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


# ==================== PYDANTIC MODELS ====================

class SavingsGoalCreate(BaseModel):
    name: str
    target_amount: int

class SavingsGoalUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[int] = None
    current_amount: Optional[int] = None
    period_type: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None


# ==================== ENDPOINTS ====================

@router.get("/stats")
async def get_dashboard_stats(user: UserInsightResponse = Depends(require_auth)):
    """Get aggregated stats for dashboard widgets."""
    try:
        # Fetch stats from service
        data = await supabase_service.get_dashboard_aggregates(user.id)
        return {"success": True, "data": data}
    except Exception as e:
        print(f"Error fetching dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/savings")
async def get_savings(user: UserInsightResponse = Depends(require_auth)):
    """Get list of savings goals."""
    try:
        data = await supabase_service.get_savings_goals(user.id)
        return {"success": True, "data": data}
    except Exception as e:
        print(f"Error fetching savings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/savings")
async def create_savings(
    payload: SavingsGoalCreate,
    user: UserInsightResponse = Depends(require_auth)
):
    """Create a new savings goal."""
    try:
        data = await supabase_service.create_savings_goal(
            user_id=user.id,
            name=payload.name,
            target=payload.target_amount
        )
        if not data:
            raise HTTPException(status_code=500, detail="Failed to create savings goal")
            
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating savings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/savings/{goal_id}")
async def update_savings(
    goal_id: int,
    payload: SavingsGoalUpdate,
    user: UserInsightResponse = Depends(require_auth)
):
    """Update a savings goal (amount, or period settings)."""
    try:
        # Build update dict with only provided fields
        update_data = {}
        if payload.name is not None:
            update_data["name"] = payload.name
        if payload.target_amount is not None:
            update_data["target_amount"] = payload.target_amount
        if payload.current_amount is not None:
            update_data["current_amount"] = payload.current_amount
        if payload.period_type is not None:
            update_data["period_type"] = payload.period_type
        if payload.period_start is not None:
            update_data["period_start"] = payload.period_start
        if payload.period_end is not None:
            update_data["period_end"] = payload.period_end
        
        data = await supabase_service.update_savings_goal(
            goal_id=goal_id,
            **update_data
        )
        if not data:
            raise HTTPException(status_code=404, detail="Savings goal not found or update failed")
            
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating savings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/savings/{goal_id}")
async def delete_savings(
    goal_id: int,
    user: UserInsightResponse = Depends(require_auth)
):
    """Delete a savings goal."""
    try:
        success = await supabase_service.delete_savings_goal(goal_id)
        if not success:
            raise HTTPException(status_code=404, detail="Savings goal not found")
            
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting savings: {e}")
        raise HTTPException(status_code=500, detail=str(e))
