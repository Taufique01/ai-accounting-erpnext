import frappe
import json
from openai import OpenAI
from datetime import datetime, date
from ai_accountant.ai_accountant.realtime_utils import notify_progress

# Define OpenAI function calling schema
journal_schema = {
    "name": "post_journal",
    "parameters": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "number"},
                        "entries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "debit_account": {"type": "string"},
                                    "credit_account": {"type": "string"},
                                    "amount": {"type": "number"},
                                    "memo": {"type": "string"},
                                    "confidence": {"type": "number"}
                                },
                                "required": ["debit_account", "credit_account", "amount", "memo", "confidence"]
                            }
                        }
                    },
                    "required": ["index", "entries"]
                }
            }
        },
        "required": ["results"]
    }
}


def get_openai_api_key():
    return frappe.conf.get('openai_api_key')


def log_cost(tokens_in, tokens_out, model="gpt-3.5-turbo-1106"):
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

    log = frappe.get_doc({
        "doctype": "LlmCostLog",
        "date": datetime.now().date(),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost": cost
    })
    log.insert()
    return cost


def check_vendor_map(vendor_name):
    if not vendor_name:
        return None
    vendor_hash = frappe.generate_hash(vendor_name)
    return frappe.db.get_value("VendorMap", {"vendor_hash": vendor_hash}, "gl_account")


def update_vendor_map(vendor_name, gl_account):
    if not vendor_name or not gl_account:
        return
    vendor_hash = frappe.generate_hash(vendor_name)
    existing = frappe.db.exists("VendorMap", {"vendor_hash": vendor_hash})
    if existing:
        doc = frappe.get_doc("VendorMap", existing)
        doc.gl_account = gl_account
        doc.save()
    else:
        doc = frappe.get_doc({
            "doctype": "VendorMap",
            "vendor_hash": vendor_hash,
            "gl_account": gl_account
        })
        doc.insert()

def format_accounts_for_prompt():
    company_name = frappe.db.get_single_value('BankTransactionInfo', 'company_name')

    accounts = frappe.get_all(
        "Account",
        fields=["name", "account_type", "parent_account", "company"],
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


ERROR_PROMPT = "You are provided with:\n" + "1. The current bank transaction,\n" + "2. The previous classification result for this transaction,\n" + "3. The previous general ledger entry error (if available).\n\n" + "Use the company's Chart of Accounts to select the most accurate classification. so that the error goes away"

def classify_transaction(tx_list, status="Pending"):
    """Classify a single transaction using OpenAI"""

    accounts_text = format_accounts_for_prompt()

    prompt = [
        {
            "role": "system",
            "content": "You are an expert accountant. Classify bank transactions into journal entries by matching transaction details with the company's Chart of Accounts below. If you can't classify or tell the account name, tell that Unknown account name",
        },
        {
            "role": "system",
            "content": f"Company's Chart of Accounts:\n{accounts_text}"
        },
        {
            "role": "system",
            "content": "Return 'index' as array index of the transactions at the same order and length, user sent to you. starting from 0 so that user can backtrack bank transactions from the index. Do not return extra entries. The number of entry should be equal to the number of bank transactions."
        }
    ]
    
    
    if status == "Error":
        prompt.append({
            "role": "system",
            "content": ERROR_PROMPT
        })
    
    
    prompt.append(        {
            "role": "user",
            "content": f"Classify the following transactions:\n{json.dumps(tx_list, indent=2)}"
    })


    api_key = get_openai_api_key()
    if not api_key:
        frappe.throw("OpenAI API key not configured")

    client = OpenAI(
        # base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # You may want to switch to just "gpt-3.5-turbo" or a newer model
            tools=[
                {
                    "type": "function",
                    "function": journal_schema  # your function schema goes here
                }
            ],
            tool_choice={"type": "function", "function": {"name": "post_journal"}},
            messages=prompt,
            max_tokens=1000
        )


        log_cost(
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens
        )

        results = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        
        # for result in results:

        #     # Retry with GPT-4o-mini if confidence is low
        #     if any(entry.get("confidence", 1.0) < 0.8 for entry in result.get("entries", [])):
        #         response = client.chat.completions.create(
        #             model="gpt-4o",
        #             functions=[journal_schema],
        #             function_call={"name": "post_journal"},
        #             messages=prompt,
        #             max_tokens=1800
        #         )

        #         log_cost(
        #             tokens_in=response.usage.prompt_tokens,
        #             tokens_out=response.usage.completion_tokens,
        #             model="gpt-4o"
        #         )

        #         result = json.loads(response.choices[0].message.function_call.arguments)

        #     # Save to vendor map
        #     for entry in result.get("entries", []):
        #         if merchant:
        #             account = entry.get("debit_account") if amount > 0 else entry.get("credit_account")
        #             if account != "Bank Account":
        #                 update_vendor_map(merchant, account)

        return results["results"]

    except Exception as e:
        print(f"OpenAI API Error: {str(e)}", "AI Accountant")
        return None




def classify_batch(status="Pending"):
    """Process a batch of pending transactions"""
    print("I am in classifying batch")
    transactions = frappe.get_all(
        "BankTransaction",
        filters={"status": status},
        fields=["name", "payload", "error_description", "ai_result"],
    )
    
    batch_size = 10
    
    if not transactions:
        return "No pending transactions found"

    processed = 0
    total_transactions = len(transactions)
    
    for i in range(0, total_transactions, batch_size):
        notify_progress(processed, total_transactions)

        tx_list = []
        
        working_list = transactions[i:i+batch_size]
        
        for tx in working_list:
            parsed = json.loads(tx.payload)
            
            if status == "Error":
                temp = {
                    'previous_classification_query_result': tx.ai_result,
                    'gl_entry_error': tx.error_description,
                    'transaction': parsed
                }
                tx_list.append(temp)
            else:
                tx_list.append(parsed)
            
        
        results = classify_transaction(tx_list, status)
        
        
        for result in results:
            result_of_the_tx  = working_list[result['index']]

            if not result:
                doc = frappe.get_doc("BankTransaction", result_of_the_tx.name)
                doc.status = "Error"
                doc.save()
                continue
            
            tx_details = json.loads(result_of_the_tx.payload)
        
            created_at_str = tx_details.get("createdAt")  # '2025-05-24T06:24:30.945859Z'

            # Remove the trailing Z and parse datetime
            created_at_str = created_at_str.rstrip('Z')
            dt = datetime.fromisoformat(created_at_str)

            # Extract date only in YYYY-MM-DD format
            posting_date = dt.date().isoformat()  # '2025-05-24'
            
            beautify_results = ""
            for entry in result.get("entries", []):
                print(entry)
                memo = "Memo: " + (entry.get("memo", "") or "") +"\n"
                debit = "Debit: " + entry.get("debit_account") + " -- " + str(entry.get("amount")) + "\n"
                credit = "Credit: " + entry.get("credit_account") + " -- " + str(entry.get("amount")) + "\n"
                
                beautify_results = memo + debit + credit + "\n"
                
            tx_doc = frappe.get_doc("BankTransaction", result_of_the_tx.name)
            tx_doc.ai_result = beautify_results
            tx_doc.save()
            
            
            try:
                for entry in result.get("entries", []):
                    je = frappe.get_doc({
                        "doctype": "Journal Entry",
                        "posting_date": posting_date,
                        "user_remark": entry.get("memo", ""),
                        "accounts": [
                            {
                                "account": entry.get("debit_account"),
                                "debit_in_account_currency": entry.get("amount"),
                                "credit_in_account_currency": 0
                            },
                            {
                                "account": entry.get("credit_account"),
                                "debit_in_account_currency": 0,
                                "credit_in_account_currency": entry.get("amount")
                            }
                        ]
                    })
                    je.insert()
                    je.submit()

                doc = frappe.get_doc("BankTransaction", result_of_the_tx.name)
                doc.status = "Processed"
                doc.save()
            
            except Exception as e:
                print(f"Error processing transaction {result_of_the_tx.name}: {str(e)}", "AI Accountant")
                doc = frappe.get_doc("BankTransaction", result_of_the_tx.name)
                doc.error_description = str(e)
                if doc.status == "Error":
                    doc.status = "RetryError"
                else:
                    doc.status = "Error"
                doc.save()
                
            processed += 1




    notify_progress(total_transactions, total_transactions)

    return f"Processed {processed} transactions"

