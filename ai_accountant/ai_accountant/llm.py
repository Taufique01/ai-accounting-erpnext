import frappe
import json
from openai import OpenAI
from datetime import datetime
from ai_accountant.ai_accountant.realtime_utils import notify_progress
from ai_accountant.ai_accountant.llm_helper import get_openai_api_key, log_cost, format_accounts_for_prompt

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
                        "name": {"type": "string"},
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
                    "required": ["name", "entries"]
                }
            }
        },
        "required": ["results"]
    }
}



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



ERROR_PROMPT = "You are provided with:\n" + "1. The current bank transaction,\n" + "2. The previous classification result for this transaction,\n" + "3. The previous general ledger entry error (if available).\n\n" + "Use the company's Chart of Accounts to select the most accurate classification. so that the error goes away"

def classify_transaction(tx_list, status="Pending"):
    """Classify a single transaction using OpenAI"""
    
    start_time = datetime.now()


    accounts_text = format_accounts_for_prompt()

    prompt = [
        {
            "role": "system",
            "content": (
                "You are an expert accountant. Your task is to classify bank transactions into double-entry journal entries. "
                "For each transaction, return the corresponding 'debit_account' and 'credit_account' using the company's Chart of Accounts below. Use the name of the account as 'debit_account' and 'credit_account'"
                "Only use account names from the list.You can also use vendor details if available. If no suitable match is found or you are not confident, return 'Unknown account name' for debit or credit."
            )
        },
        {
            "role": "system",
            "content": f"Company's Chart of Accounts:\n{accounts_text}"
        }
    ]

    model = "gpt-3.5-turbo"    
    if status == "Error":
        prompt.append({
            "role": "system",
            "content": ERROR_PROMPT
        })
        
        model = "gpt-4o"
    
    
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
            model=model,  # You may want to switch to just "gpt-3.5-turbo" or a newer model
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

        end_time = datetime.now() 
        
        duration = end_time - start_time
        
        


        results = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        print(results)
        
        
        log_cost(
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            input=f"Classify the following transactions:\n{json.dumps(tx_list, indent=2)}",
            output=json.dumps(results),
            duration = duration
        )
        
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
    limit = frappe.db.get_single_value('LLMSettings', 'limit')
    batch_size = frappe.db.get_single_value('LLMSettings', 'batch_size')
    
    transactions = frappe.get_all(
        "BankTransaction",
        filters={"status": status},
        fields=["name", "payload", "error_description", "ai_result"],
        limit = limit
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
            
        
        results = classify_transaction(tx_list, status)
        
        tx_map = {tx.name: tx for tx in working_list}

        for result in results:
            
            input_transaction  = tx_map.get(result['name'])
            if not input_transaction:
                print(f"Transaction {result['name']} not found in working_list")
                continue

            if not result:
                doc = frappe.get_doc("BankTransaction", input_transaction.name)
                doc.status = "Error"
                doc.save()
                continue
            
            tx_details = json.loads(input_transaction.payload)
        
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
                
            tx_doc = frappe.get_doc("BankTransaction", input_transaction.name)
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

                doc = frappe.get_doc("BankTransaction", input_transaction.name)
                doc.status = "Processed"
                doc.save()
            
            except Exception as e:
                print(f"Error processing transaction {input_transaction.name}: {str(e)}", "AI Accountant")
                doc = frappe.get_doc("BankTransaction", input_transaction.name)
                doc.error_description = str(e)
                if doc.status == "Error":
                    doc.status = "RetryError"
                else:
                    doc.status = "Error"
                doc.save()
                
            processed += 1




    notify_progress(total_transactions, total_transactions)

    return f"Processed {processed} transactions"

