import frappe
from frappe.utils.background_jobs import enqueue
from ai_accountant.ai_accountant.classify_and_into_journal import classify_batch

def check_pending_transactions():
    """Check if there are enough pending transactions to process"""
    count = frappe.db.count("BankTransaction", filters={"status": "Pending"})
    if count >= 100:
    # Enqueue batch processing
        enqueue(
        classify_batch,
        queue="default",
        job_name="batch_classify",
        timeout=1800,
        # 30 minutes
)


@frappe.whitelist()
def process_all_pending():
    """Process all pending transactions regardless of count"""
    # enqueue(
    # classify_batch,
    # queue="default",
    # job_name="batch_classify_all",
    # timeout=3600,
    # # 1 hour
    # )
    # print("Job enqueued with ID:", job.id)
    # frappe.get_doc("Job", job.id).status
    
    classify_batch()
    return {"status": "success", "message": "All pending transaction processing completed."}


@frappe.whitelist()
def process_all_error():
    """Process all pending transactions regardless of count"""
    # enqueue(
    # classify_batch,
    # queue="default",
    # job_name="process_all_error",
    # timeout=3600,
    # status="Error"
    # )
    
    classify_batch(status="Error")

    return {"status": "success", "message": "All error transactions retry completed."}
