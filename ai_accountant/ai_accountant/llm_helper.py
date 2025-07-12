import frappe
from datetime import datetime

def get_openai_api_key():
    return frappe.conf.get('openai_api_key')


def log_cost(tokens_in, tokens_out, input="", output="", duration=None, model="gpt-3.5-turbo-1106",):
    """Log the OpenAI usage cost"""
    if model.startswith("gpt-3.5"):
        in_rate = 0.0000005
        out_rate = 0.0000015
    elif model.startswith("gpt-4o-mini"):
        in_rate = 0.000001
        out_rate = 0.000003
    else:
        in_rate = 0.000003
        out_rate = 0.000006

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
        "user": current_user
        
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
