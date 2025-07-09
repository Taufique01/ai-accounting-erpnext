import frappe
from frappe.utils import flt, today, get_datetime

def reconcile_transactions():
    """Match bank transactions with payment entries"""

    # Get unreconciled payment entries
    payment_entries = frappe.get_all(
        "Payment Entry",
        filters={
            "docstatus": 1,
            "clearance_date": ["is", "not set"]
        },
        fields=[
            "name", "payment_type", "paid_amount", "received_amount",
            "reference_no", "reference_date", "party", "party_type", "posting_date"
        ]
    )

    # Get processed bank transactions
    bank_transactions = frappe.get_all(
        "BankTransaction",
        filters={"status": "Processed"},
        fields=["name", "payload"]
    )

    # Convert bank transactions to a structured format
    bank_data = []
    for tx in bank_transactions:
        payload = frappe.parse_json(tx.payload)
        bank_data.append({
            "name": tx.name,
            "amount": flt(payload.get("amount")),
            "date": payload.get("date"),
            "description": payload.get("description"),
            "merchant": payload.get("merchant_name"),
            "external_id": payload.get("id")
        })

    reconciled_count = 0

    for payment in payment_entries:
        amount = payment.paid_amount if payment.payment_type == "Pay" else payment.received_amount

        # Filter matching transactions
        matches = []
        for tx in bank_data:
            if payment.payment_type == "Pay" and tx["amount"] < 0 and abs(tx["amount"]) == flt(amount):
                matches.append(tx)
            elif payment.payment_type == "Receive" and tx["amount"] > 0 and flt(tx["amount"]) == flt(amount):
                matches.append(tx)

        # Refine matches by party name if multiple
        if len(matches) > 1:
            better_matches = [tx for tx in matches if payment.party.lower() in (tx["merchant"] or "").lower()]
            if better_matches:
                matches = better_matches

        # Refine by date proximity if still multiple
        if len(matches) > 1:
            matches.sort(key=lambda tx: abs((get_datetime(tx["date"]) - get_datetime(payment.posting_date)).days))

        if matches:
            match = matches[0]

            # Update payment entry
            payment_doc = frappe.get_doc("Payment Entry", payment.name)
            payment_doc.clearance_date = today()
            payment_doc.save()

            # Update bank transaction status
            frappe.db.et_value("BankTransaction", match["name"], "status", "Reconciled")

            reconciled_count += 1

            # Remove matched transaction
            bank_data.remove(match)

    return f"Reconciled {reconciled_count} transactions"
