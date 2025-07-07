import frappe
import json
from frappe.utils import flt

def process_ar_ap_transactions():
    """Process bank transactions for AR/AP automation"""
    transactions = frappe.get_all(
        "BankTransaction",
        filters={"status": "Processed"},
        fields=["name", "payload"]
    )

    ar_count = 0
    ap_count = 0

    for tx in transactions:
        payload = json.loads(tx["payload"])
        amount = flt(payload.get("amount", 0))

        # Check if it's a hospital deposit (AR)
        if payload.get("category") == "deposit" and "Hospital" in payload.get("merchant_name", ""):
            create_sales_invoice(payload)
            ar_count += 1

        # Check if it's a payment to vendor (AP)
        elif amount < 0:
            vendor = frappe.db.get_value("Supplier", {"supplier_name": payload.get("merchant_name")})
            if vendor:
                create_purchase_invoice(payload, vendor)
                ap_count += 1

    return f"Processed {ar_count} AR transactions and {ap_count} AP transactions"

def create_sales_invoice(tx_data):
    """Create a Sales Invoice from a bank transaction"""
    customer_name = tx_data.get("merchant_name")
    customer = frappe.db.get_value("Customer", {"customer_name": customer_name})

    if not customer:
        customer_doc = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name,
            "customer_type": "Company",
            "customer_group": frappe.db.get_single_value("Selling Settings", "customer_group"),
            "territory": frappe.db.get_single_value("Selling Settings", "territory")
        })
        customer_doc.insert(ignore_permissions=True)
        customer = customer_doc.name

    amount = flt(tx_data.get("amount", 0))
    if amount <= 0:
        return None

    item_code = "COLLECTION_FEE"
    if not frappe.db.exists("Item", item_code):
        item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": "Collection Fee",
            "item_group": "Services",
            "is_stock_item": 0,
            "include_item_in_manufacturing": 0,
            "stock_uom": "Nos"
        })
        item_doc.insert(ignore_permissions=True)

    fee_rate = amount * 0.25

    invoice = frappe.get_doc({
        "doctype": "Sales Invoice",
        "customer": customer,
        "posting_date": tx_data.get("date"),
        "due_date": tx_data.get("date"),
        "items": [{
            "item_code": item_code,
            "qty": 1,
            "rate": fee_rate
        }]
    })
    invoice.insert(ignore_permissions=True)
    invoice.submit()

    payment = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Receive",
        "mode_of_payment": "Bank Transfer",
        "party_type": "Customer",
        "party": customer,
        "paid_amount": fee_rate,
        "received_amount": fee_rate,
        "reference_no": tx_data.get("id"),
        "reference_date": tx_data.get("date"),
        "posting_date": tx_data.get("date"),
        "paid_to": "Bank Account",
        "references": [{
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "allocated_amount": fee_rate
        }]
    })
    payment.insert(ignore_permissions=True)
    payment.submit()

    frappe.db.set_value("BankTransaction", {"external_id": tx_data.get("id")}, "status", "AR Processed")
    return invoice.name

def create_purchase_invoice(tx_data, supplier):
    """Create a Purchase Invoice from a bank transaction"""
    amount = abs(flt(tx_data.get("amount", 0)))
    if amount <= 0:
        return None

    item_code = "SUPPLIER_EXPENSE"
    if not frappe.db.exists("Item", item_code):
        item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": "Supplier Expense",
            "item_group": "Services",
            "is_stock_item": 0,
            "include_item_in_manufacturing": 0,
            "stock_uom": "Nos"
        })
        item_doc.insert(ignore_permissions=True)

    invoice = frappe.get_doc({
        "doctype": "Purchase Invoice",
        "supplier": supplier,
        "posting_date": tx_data.get("date"),
        "due_date": tx_data.get("date"),
        "items": [{
            "item_code": item_code,
            "qty": 1,
            "rate": amount
        }]
    })
    invoice.insert(ignore_permissions=True)
    invoice.submit()

    payment = frappe.get_doc({
        "doctype": "Payment Entry",
        "payment_type": "Pay",
        "mode_of_payment": "Bank Transfer",
        "party_type": "Supplier",
        "party": supplier,
        "paid_amount": amount,
        "received_amount": amount,
        "reference_no": tx_data.get("id"),
        "reference_date": tx_data.get("date"),
        "posting_date": tx_data.get("date"),
        "paid_from": "Bank Account",
        "references": [{
            "reference_doctype": "Purchase Invoice",
            "reference_name": invoice.name,
            "allocated_amount": amount
        }]
    })
    payment.insert(ignore_permissions=True)
    payment.submit()

    frappe.db.set_value("BankTransaction", {"external_id": tx_data.get("id")}, "status", "AP Processed")
    return invoice.name
