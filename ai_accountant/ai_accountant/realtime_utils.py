import frappe

def notify_progress(processed, total, event_name="transaction_processing_update"):
    frappe.publish_realtime(
                event=event_name,
                message={"completed": total - processed, "total": total, "is_completed": total == processed, "percent": 100 * processed/total},
                # user=tx.owner  # Optional: limit to specific user
            )
