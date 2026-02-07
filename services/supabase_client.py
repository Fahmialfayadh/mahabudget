"""
Supabase client service for database and storage operations.
Handles all direct interactions with Supabase.
"""

from supabase import create_client, Client
from typing import Optional
from datetime import datetime
import httpx

from config import settings
from models import (
    ExpenseCreate,
    ExpenseResponse,
    ExpenseUpdate,
    ChatMessageCreate,
    ChatMessageResponse,
)


class SupabaseService:
    """Service class for Supabase operations."""
    
    def __init__(self):
        if settings.debug:
            print(f"[DEBUG Supabase] Initializing with URL: {settings.supabase_url}")
        
        # Anon client (for client-side compatible ops/reads)
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        
        # Service client (for backend ops/writes)
        self.service_client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )
        
        # Test connection
        try:
            if settings.debug:
                print("[DEBUG Supabase] Testing Service Client connection...")
            response = self.service_client.table("expenses").select("id").limit(1).execute()
            if settings.debug:
                print("[DEBUG Supabase] Service Client Connection: OK")
        except Exception as e:
            if settings.debug:
                print(f"[ERROR Supabase] Service Client Connection FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    # ==================== EXPENSE OPERATIONS ====================
    
    async def get_user_expenses(
        self, 
        user_id: int, 
        limit: int = 50, 
        offset: int = 0
    ) -> list[dict]:
        """Fetch paginated expenses for a user."""
        response = self.service_client.table("expenses") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("date", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        return response.data
    
    async def get_expense_by_id(self, expense_id: int) -> Optional[dict]:
        """Fetch single expense by ID."""
        response = self.service_client.table("expenses") \
            .select("*") \
            .eq("id", expense_id) \
            .single() \
            .execute()
        return response.data
    
    async def create_expense(self, expense: ExpenseCreate) -> dict:
        """Create a new expense record."""
        data = {
            "user_id": expense.user_id,
            "item_name": expense.item_name,
            "description": expense.description,
            "amount": expense.amount,
            "category": expense.category,
            "emotion_label": expense.emotion_label,
            "sentiment_score": int(expense.sentiment_score * 10),  # Scale and convert to int
            "ai_confidence": expense.ai_confidence,
            "receipt_url": expense.receipt_url,
            "date": expense.date.isoformat() if expense.date else datetime.now().isoformat(),
            "is_regret": expense.is_regret, # New field
        }
        # Use service_client for writes
        response = self.service_client.table("expenses").insert(data).execute()
        return response.data[0] if response.data else {}
    
    async def update_expense(
        self, 
        expense_id: int, 
        update_data: ExpenseUpdate
    ) -> Optional[dict]:
        """Update an existing expense (correction mode)."""
        data = {k: v for k, v in update_data.model_dump().items() if v is not None}
        if not data:
            return None
        
        response = self.service_client.table("expenses") \
            .update(data) \
            .eq("id", expense_id) \
            .execute()
        return response.data[0] if response.data else None
    
    async def delete_expense(self, expense_id: int) -> bool:
        """Delete an expense record."""
        response = self.service_client.table("expenses") \
            .delete() \
            .eq("id", expense_id) \
            .execute()
        return len(response.data) > 0
    
    async def get_monthly_expenses(
        self, 
        user_id: int, 
        year: int, 
        month: int
    ) -> list[dict]:
        """Get all expenses for a specific month."""
        start_date = f"{year}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"
        
        response = self.service_client.table("expenses") \
            .select("*") \
            .eq("user_id", user_id) \
            .gte("date", start_date) \
            .lt("date", end_date) \
            .order("date", desc=True) \
            .execute()
        return response.data
    
    async def get_emotional_summary(self, user_id: int) -> list[dict]:
        """Get expense summary grouped by emotion."""
        # Fetch all expenses and aggregate in Python
        response = self.service_client.table("expenses") \
            .select("emotion_label, amount") \
            .eq("user_id", user_id) \
            .execute()
        
        # Aggregate by emotion
        emotion_totals = {}
        for expense in response.data:
            emotion = expense.get("emotion_label") or "Netral"
            amount = expense.get("amount") or 0
            if emotion in emotion_totals:
                emotion_totals[emotion]["total"] += amount
                emotion_totals[emotion]["count"] += 1
            else:
                emotion_totals[emotion] = {"total": amount, "count": 1}
        
        return [
            {"emotion": k, "total": v["total"], "count": v["count"]}
            for k, v in emotion_totals.items()
        ]

    # ==================== REGRET AUDIT OPERATIONS ====================

    async def get_audit_candidates(self, user_id: int) -> list[dict]:
        """
        Get expenses eligible for regret audit.
        Criteria:
        1. Emosi: Sedih, Marah, Stress
        2. Date: Older than 48 hours
        3. is_regret: NULL (Not yet audited)
        """
        try:
            # Calculate 48h ago timestamp
            # Note: Ideally do this filtering in SQL, but for now we filter in Python
            # to handle complex date logic easier with existing Setup
            response = self.service_client.table("expenses") \
                .select("*") \
                .eq("user_id", user_id) \
                .in_("emotion_label", ["Sedih", "Marah", "Stress"]) \
                .is_("is_regret", "null") \
                .order("date", desc=True) \
                .limit(20) \
                .execute()
            
            candidates = []
            now = datetime.now()
            for expense in response.data:
                # Parse date (ISO 8601)
                exp_date_str = expense.get("date")
                if not exp_date_str:
                    continue
                # Handle potentially varying ISO formats (with/without Z)
                try:
                    exp_date_str = exp_date_str.replace("Z", "")
                    exp_date = datetime.fromisoformat(exp_date_str)
                    
                    # Check age > 48 hours
                    age = now - exp_date
                    if age.total_seconds() > 48 * 3600:
                        candidates.append(expense)
                except Exception as e:
                    if settings.debug:
                        print(f"Error parsing date {exp_date_str}: {e}")
                    continue
                    
            return candidates
        except Exception as e:
            if settings.debug:
                print(f"Error fetching audit candidates: {e}")
            return []

    async def get_regret_stats(self, user_id: int) -> dict:
        """Get summary of 'Dana Terbuang' (is_regret=True)."""
        try:
            response = self.service_client.table("expenses") \
                .select("amount") \
                .eq("user_id", user_id) \
                .eq("is_regret", True) \
                .execute()
            
            total_regret = sum(e.get("amount", 0) for e in response.data)
            count_regret = len(response.data)
            
            return {
                "total_wasted": total_regret,
                "count": count_regret
            }
        except Exception as e:
            return {"total_wasted": 0, "count": 0}
    
    # ==================== CHAT OPERATIONS ====================
    
    async def get_chat_history(
        self, 
        user_id: int, 
        limit: int = 20
    ) -> list[dict]:
        """Fetch recent chat history for context."""
        response = self.service_client.table("chat_history") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("date", desc=True) \
            .limit(limit) \
            .execute()
        
        messages = list(reversed(response.data))
        
        # Collect transaction IDs
        tx_ids = [m["transaction_id"] for m in messages if m.get("transaction_id")]
        
        if tx_ids:
            try:
                # Fetch all related expenses
                exp_response = self.service_client.table("expenses") \
                    .select("*") \
                    .in_("id", tx_ids) \
                    .execute()
                
                # Map by ID
                expense_map = {e["id"]: e for e in exp_response.data}
                
                # Enrich messages
                for msg in messages:
                    if msg.get("transaction_id") and msg["transaction_id"] in expense_map:
                        msg["expense_data"] = expense_map[msg["transaction_id"]]
            except Exception as e:
                if settings.debug:
                    print(f"[ERROR] Failed to fetch enriched expenses: {e}")
        
        return messages
    
    async def save_chat_message(self, message: ChatMessageCreate) -> dict:
        """Save a chat message to history."""
        data = {
            "user_id": message.user_id,
            "role": message.role,
            "content": message.content,
            "type": message.type,
            "transaction_id": message.transaction_id,
            "date": datetime.now().isoformat(),
        }
        # Use service_client to bypass RLS/Auth issues
        response = self.service_client.table("chat_history").insert(data).execute()
        return response.data[0] if response.data else {}
    
    async def delete_chat_message(self, message_id: int) -> bool:
        """Delete a chat message."""
        response = self.service_client.table("chat_history") \
            .delete() \
            .eq("id", message_id) \
            .execute()
        return len(response.data) > 0
    
    async def clear_chat_history(self, user_id: int) -> bool:
        """Clear all chat history for a user (restart chat)."""
        response = self.service_client.table("chat_history") \
            .delete() \
            .eq("user_id", user_id) \
            .execute()
        return True
    
    # ==================== USER OPERATIONS ====================
    
    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """Fetch user by username."""
        response = self.service_client.table("users") \
            .select("*") \
            .eq("username", username) \
            .single() \
            .execute()
        return response.data
    
    async def create_user(self, username: str, password_hash: str) -> dict:
        """Create a new user."""
        data = {"username": username, "password": password_hash}
        response = self.service_client.table("users").insert(data).execute()
        return response.data[0] if response.data else {}
    
    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Fetch user by ID."""
        response = self.service_client.table("users") \
            .select("id, username") \
            .eq("id", user_id) \
            .single() \
            .execute()
        return response.data
    
    # ==================== STORAGE OPERATIONS ====================
    
    async def upload_receipt(
        self, 
        file_bytes: bytes, 
        filename: str, 
        user_id: int
    ) -> str:
        """Upload receipt image to storage bucket."""
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_path = f"{user_id}/{timestamp}_{filename}"
        
        # Upload to storage
        self.service_client.storage.from_(settings.receipt_bucket).upload(
            storage_path,
            file_bytes,
            {"content-type": "image/jpeg"}
        )
        
        # Get public URL
        public_url = self.service_client.storage.from_(settings.receipt_bucket) \
            .get_public_url(storage_path)
        
        return public_url

    # ==================== DASHBOARD & ANALYTICS ====================

    async def get_dashboard_aggregates(self, user_id: int) -> dict:
        """Fetch aggregated data for dashboard widgets."""
        try:
            # 1. Get recent expenses (last 30 days roughly) to calculate trends
            response = self.service_client.table("expenses") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("date", desc=True) \
                .limit(500) \
                .execute()
            
            expenses = response.data
            now = datetime.now()
            
            # --- Top Categories ---
            category_totals = {}
            for e in expenses:
                cat = e.get("category") or "Lainnya"
                amt = e.get("amount", 0)
                category_totals[cat] = category_totals.get(cat, 0) + amt
                
            top_categories = sorted(
                [{"name": k, "total": v} for k, v in category_totals.items()],
                key=lambda x: x["total"], 
                reverse=True
            )[:5]
            
            # --- Forecast (Simple Rule: Avg on this weekday) ---
            today_weekday = now.weekday() # 0=Mon, 6=Sun
            weekday_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            
            same_day_expenses = []
            for e in expenses:
                try:
                    d_str = e["date"].replace("Z", "")
                    d = datetime.fromisoformat(d_str)
                    if d.weekday() == today_weekday:
                        same_day_expenses.append(e)
                except:
                    continue
                    
            if same_day_expenses:
                total_same_day = sum(x["amount"] for x in same_day_expenses)
                # Group by actual dates to get daily average, not transaction average
                unique_dates = len(set(x["date"][:10] for x in same_day_expenses))
                avg_forecast = total_same_day / max(1, unique_dates)
            else:
                avg_forecast = 0
                
            forecast_msg = f"Rata-rata pengeluaranmu di hari {weekday_names[today_weekday]} adalah Rp {avg_forecast:,.0f}."
            if avg_forecast == 0:
                forecast_msg = "Belum cukup data untuk prediksi hari ini."

            return {
                "top_categories": top_categories,
                "forecast": {
                     "amount": int(avg_forecast),
                     "message": forecast_msg
                }
            }
        except Exception as e:
            if settings.debug:
                print(f"Error aggregates: {e}")
            return {"top_categories": [], "forecast": {"amount": 0, "message": "Error calculating forecast"}}

    # ==================== SAVINGS GOALS ====================

    async def get_savings_goals(self, user_id: int) -> list[dict]:
        """Get savings goals with real-time expense tracking based on period."""
        try:
            from datetime import datetime, timedelta
            
            # Get all savings goals
            goals_response = self.service_client.table("savings_goals").select("*").eq("user_id", user_id).order("created_at").execute()
            goals = goals_response.data
            
            if not goals:
                return []
            
            # For each goal, calculate spending based on its period
            for goal in goals:
                period_type = goal.get("period_type", "this_month")
                now = datetime.now()
                
                # Determine date range based on period type
                if period_type == "this_week":
                    start_date = now - timedelta(days=7)
                elif period_type == "custom":
                    # Use stored custom dates
                    start_date = datetime.fromisoformat(goal.get("period_start", now.isoformat())) if goal.get("period_start") else now.replace(day=1)
                    end_date = datetime.fromisoformat(goal.get("period_end", now.isoformat())) if goal.get("period_end") else now
                else:  # this_month (default)
                    start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
                # For non-custom periods, end date is now
                if period_type != "custom":
                    end_date = now
                
                # Query expenses for this period
                expenses_query = self.service_client.table("expenses").select("category, amount").eq("user_id", user_id).gte("date", start_date.isoformat())
                
                # Add end date filter for custom range
                if period_type == "custom":
                    expenses_query = expenses_query.lte("date", end_date.isoformat())
                
                expenses_response = expenses_query.execute()
                expenses = expenses_response.data
                
                # Aggregate expenses by category
                category_totals = {}
                for expense in expenses:
                    category = expense.get("category", "")
                    amount = expense.get("amount", 0)
                    category_totals[category] = category_totals.get(category, 0) + amount
                
                # Match goal name with categories
                goal_name = goal.get("name", "").lower()
                matched_amount = 0
                
                for category, total in category_totals.items():
                    category_lower = category.lower()
                    # Match if goal name is in category or vice versa
                    if goal_name in category_lower or category_lower in goal_name:
                        matched_amount += total
                
                # Update current_amount with real-time data
                goal["current_amount"] = matched_amount
            
            return goals
            
        except Exception as e:
            if settings.debug:
                print(f"Error in get_savings_goals: {e}")
            return []

    async def create_savings_goal(self, user_id: int, name: str, target: int) -> dict:
        data = {
            "user_id": user_id,
            "name": name,
            "target_amount": target,
            "current_amount": 0
        }
        res = self.service_client.table("savings_goals").insert(data).execute()
        return res.data[0] if res.data else {}
        
    async def update_savings_goal(self, goal_id: int, **kwargs) -> dict:
        """Update savings goal with any provided fields."""
        res = self.service_client.table("savings_goals").update(kwargs).eq("id", goal_id).execute()
        return res.data[0] if res.data else {}

    async def delete_savings_goal(self, goal_id: int) -> bool:
        res = self.service_client.table("savings_goals").delete().eq("id", goal_id).execute()
        return len(res.data) > 0


# Singleton instance
supabase_service = SupabaseService()
