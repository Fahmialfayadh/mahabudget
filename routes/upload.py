"""
Upload API routes.
Receipt image upload and processing.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import base64

from models import ExpenseCreate, ChatMessageCreate
from services import (
    supabase_service,
    read_receipt_from_base64,
    format_for_confirmation,
    compress_image,
    image_to_base64,
)


router = APIRouter(prefix="/api/upload", tags=["Upload"])


# Store pending receipt confirmations (in production, use Redis or DB)
pending_receipts = {}


@router.post("/receipt")
async def upload_receipt(
    file: UploadFile = File(...),
    user_id: int = Form(...)
):
    """
    Upload receipt image and get AI reading.
    Returns extracted data for user confirmation.
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read and compress image
        image_bytes = await file.read()
        compressed_bytes = await compress_image(image_bytes)
        
        # Convert to base64 for AI processing
        base64_image = await image_to_base64(compressed_bytes)
        
        # Read receipt using The Scanner
        receipt_data = await read_receipt_from_base64(base64_image)
        
        if receipt_data.total_amount == 0:
            return {
                "success": False,
                "message": "Maaf, gue ga bisa baca struknya dengan jelas. Coba foto ulang ya!",
                "receipt_data": None
            }
        
        # Upload to Supabase storage
        receipt_url = await supabase_service.upload_receipt(
            compressed_bytes,
            file.filename or "receipt.jpg",
            user_id
        )
        
        # Create expense immediately (Auto-save)
        expense_data = ExpenseCreate(
            user_id=user_id,
            item_name=receipt_data.store_name,
            description=f"Receipt from {receipt_data.store_name}",
            amount=receipt_data.total_amount,
            category="Belanja", # Default category
            emotion_label="Netral", # Default emotion
            sentiment_score=0.0,
            ai_confidence=0.8,
            receipt_url=receipt_url,
            date=None # Use current time
            # is_regret will be None/False by default
        )
        
        saved_expense = await supabase_service.create_expense(expense_data)
        
        # Format message
        formatted_amount = f"Rp {receipt_data.total_amount:,}"
        confirmation_msg = f"✅ Siap! Struk {receipt_data.store_name} sebesar {formatted_amount} udah gue simpen."
        
        # Save to chat history
        chat_msg = ChatMessageCreate(
            user_id=user_id,
            role="assistant",
            content=confirmation_msg,
            type="receipt",
            transaction_id=saved_expense.get("id")
        )
        await supabase_service.save_chat_message(chat_msg)
        
        return {
            "success": True,
            "message": confirmation_msg,
            "receipt_data": saved_expense # Return full saved object
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[DEBUG Upload] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing receipt: {str(e)}")


@router.post("/confirm")
async def confirm_receipt(
    confirmation_id: str = Form(...),
    confirmed: bool = Form(default=True),
    corrected_amount: Optional[int] = Form(default=None),
    corrected_store: Optional[str] = Form(default=None)
):
    """
    Confirm receipt data and save as expense.
    Allows user to correct AI readings before saving.
    """
    try:
        if confirmation_id not in pending_receipts:
            raise HTTPException(status_code=404, detail="Confirmation not found or expired")
        
        pending = pending_receipts.pop(confirmation_id)
        
        if not confirmed:
            return {"success": False, "message": "Receipt discarded"}
        
        receipt_data = pending["receipt_data"]
        
        # Apply corrections if provided
        amount = corrected_amount or receipt_data["total_amount"]
        store_name = corrected_store or receipt_data["store_name"]
        
        # Create expense from receipt
        expense_data = ExpenseCreate(
            user_id=pending["user_id"],
            item_name=f"Belanja di {store_name}",
            description=f"From receipt: {store_name}",
            amount=amount,
            category="Belanja",
            emotion_label="Netral",
            sentiment_score=0.0,
            ai_confidence=0.7,
            receipt_url=pending["receipt_url"]
        )
        
        saved_expense = await supabase_service.create_expense(expense_data)
        
        # Update chat with confirmation
        formatted_amount = f"Rp {amount:,}"
        chat_msg = ChatMessageCreate(
            user_id=pending["user_id"],
            role="assistant",
            content=f"✅ Siap! {store_name} {formatted_amount} udah gue simpen.",
            type="confirmation",
            transaction_id=saved_expense.get("id")
        )
        await supabase_service.save_chat_message(chat_msg)
        
        return {
            "success": True,
            "message": f"Expense saved: {store_name} {formatted_amount}",
            "expense": saved_expense
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error confirming receipt: {str(e)}")
