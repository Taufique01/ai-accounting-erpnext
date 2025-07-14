import frappe
from datetime import datetime
import json

def get_openai_api_key():
    return frappe.conf.get('openai_api_key')


def log_cost(tokens_in, tokens_out, input="", output="", duration=None, model="gpt-3.5-turbo"):
    """Log the OpenAI usage cost"""
    if model.startswith("gpt-3.5"):
        in_rate = 0.0005 / 1000
        out_rate = 0.0015 / 1000
    elif model.startswith("gpt-4o"):
        in_rate = 0.005 / 1000
        out_rate = 0.015 / 1000
    else:
        # fallback for gpt-4-turbo
        in_rate = 0.01 / 1000
        out_rate = 0.03 / 1000
    cost = (tokens_in * in_rate) + (tokens_out * out_rate)
    
    
    current_user = frappe.session.user

    log = frappe.get_doc({
        "doctype": "LlmCostLog",
        "date": datetime.now().date(),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": cost,
        "input": input,
        "output": output,
        "duration": duration,
        "user": current_user,
        "model":model
        
    })
    log.insert()
    return cost


def format_accounts_for_prompt():
    company_name = frappe.db.get_single_value('BankTransactionInfo', 'company_name')

    accounts = frappe.get_all(
        "Account",
        fields=["name", "account_type", "parent_account"],
        filters={"company": company_name, "is_group": 0},
        order_by="name"
    )
    
    lines = []
    for acc in accounts:
        # Example: "Cash - TC (Asset > Current Assets), Type: Cash"
        line = (
            f"name: {acc['name']}, "
            f"account_type: {acc['account_type']}, "
            f"parent_account: {acc['parent_account']}"
        )
        lines.append(line)
    return "\n".join(lines)



def prepare_tx_list_for_prompt(status, working_list):
    tx_list = []
    for tx in working_list:
        parsed = json.loads(tx.payload)
        counterparty = tx.get("counterparty_name", "").strip().upper()
        vendor_doc = frappe.db.get_value(
                "VendorMap",
                {"vendor_name": ["like", counterparty]},
                ["vendor_name", "debit_account", "credit_account"],
                as_dict=True
            )
            
        vendor = ""
        if vendor_doc:
            vendor = f"Vendor: {vendor.vendor_name}. Credit: {vendor.credit_account}. Debit: {vendor.debit_account}"

        if status == "Error":
            temp = {
                    "name":tx.name,
                    "previous_classification_query_result": tx.ai_result,
                    "gl_entry_error": tx.error_description,
                    "transaction": parsed,
                    "vendor": vendor
                }
            tx_list.append(temp)
        else:
            tx_list.append({
                    "name":tx.name,
                    'transaction': parsed,
                    "vendor": vendor
                })
            
    return tx_list

