import frappe
import json
from openai import OpenAI
from datetime import datetime
from ai_accountant.ai_accountant.realtime_utils import notify_progress
from ai_accountant.ai_accountant.llm_helper import get_openai_api_key, log_cost, format_accounts_for_prompt, prepare_tx_list_for_prompt

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
                "Midwest service bureau, LLC is a Technology-Enhanced Debt Recovery with Human Touch company.\n"
                "You are an expert accountant of the company. Your task is to classify bank transactions into double-entry journal entries.\n"
                "For each bank transaction, return the corresponding 'debit_account' and 'credit_account' using the company's Chart of Accounts below. Use the name of the account as 'debit_account' and 'credit_account'\n"
                "Money received is usually: Debit = Bank, Credit = Income\n"
                "Money sent is usually: Debit = Expense or Asset, Credit = Bank.\n"
                "For internal transfers between bank accounts, use the source account as the credit, and the destination account as the debit. No income or expense is involved.\n"
                "❌ Do not use accrual-based accounts like 'Accounts Receivable', 'Accounts Payable', 'Customer Advances', 'Loans', 'Employee Advances', 'Inventory', or 'Prepaid Expenses'\n"
                "Only classify payments with Bank, Income, or Expense accounts from the company's chart of accounts\n"
                "You can also use vendor details if available. If no suitable account match is found, then use appropriate Suspense account \n"
            )
        },
        {
            "role": "system",
            "content": f"Company's Chart of Accounts:\n{accounts_text}"
        }
    ]

    model = "gpt-4o"   
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
            model=model,  # You may want to switch to just "gpt-3.5-turbo" or a newer model
            tools=[
                {
                    "type": "function",
                    "function": journal_schema  # your function schema goes here
                }
            ],
            tool_choice={"type": "function", "function": {"name": "post_journal"}},
            messages=prompt
        )

        end_time = datetime.now() 
        
        duration = end_time - start_time
        
        


        results = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        
        
        log_cost(
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            input=f"Classify the following transactions:\n{json.dumps(tx_list, indent=2)}",
            output=json.dumps(results),
            duration = duration,
            model=model
        )
        
        return results["results"]

    except Exception as e:
        print(f"OpenAI API Error: {str(e)}", "AI Accountant")
        return None


def save_ai_classification_result(result, input_transaction):
    tx_doc = frappe.get_doc("BankTransaction", input_transaction.name)
    for entry in result.get("entries", []):
       
        memo = entry.get("memo", "")
        debit =  entry.get("debit_account")
        credit =  entry.get("credit_account")
        amount = entry.get("amount")
        confidence = entry.get("confidence", 0)
        tx_doc.set("ai_recommended_entries", [])
   
        tx_doc.append("ai_recommended_entries", {
            "debit_account": debit,
            "credit_account": credit,
            "memo": memo,
            "amount": amount,
            "confidence": confidence
        })
        
    tx_doc.save()

def get_party_info(account, counterparty):
    account_type = frappe.db.get_value("Account", account, "account_type")
    if account_type in ["Receivable", "Payable"]:
        return frappe.db.get_value(
            "VendorMap",
            {"vendor_name": ["like", f"%{counterparty}%"]},
            ["party", "party_type"],
            as_dict=True
        )
    return None


def save_journal_entry(result, tx_created_at_str, kind):
    
    # Step 1: Clean the Zulu time indicator
    tx_created_at_str = tx_created_at_str.rstrip('Z')

    # Step 2: Parse the reference date (original transaction date)
    reference_date = datetime.fromisoformat(tx_created_at_str).date().isoformat()  # e.g. '2025-05-24'

    # Step 3: Create a new posting date with current datetime
    posting_date = datetime.now().date().isoformat()  # e.g. '2025-08-01'

    tx_name = result.get("name") 
        
    for entry in result.get("entries", []):
        
        
        debit_account = entry.get("debit_account")
        credit_account = entry.get("credit_account")
        amount = entry.get("amount")
        memo = entry.get("memo", "")
        counterparty = entry.get("counterparty", "")
        confidence = entry.get("confidence")

        if confidence < .75:
            raise ValueError(f"Classification confidence is very less {confidence}")
        

            
        # Get party info for debit and credit accounts
        party_for_debit = get_party_info(debit_account, counterparty)
        party_for_credit = get_party_info(credit_account, counterparty)
        
        # Prepare debit line
        debit_line = {
            "account": debit_account,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0
        }
        if party_for_debit:
            debit_line.update(party_for_debit)

        # Prepare credit line
        credit_line = {
            "account": credit_account,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": amount
        }
        if party_for_credit:
            credit_line.update(party_for_credit)

        # Create Journal Entry
        je = frappe.get_doc({
            "doctype": "Journal Entry",
            "posting_date": posting_date,
            "user_remark": memo,
            "cheque_no": tx_name,
            "cheque_date": reference_date,
            "accounts": [debit_line, credit_line]
        })
        je.insert()
        je.submit()


def classify_batch(status="Pending"):
    """Process a batch of pending transactions"""
    print("I am in classifying batch")
    limit = frappe.db.get_single_value('LLMSettings', 'limit')
    batch_size = frappe.db.get_single_value('LLMSettings', 'batch_size')
    
    tnxs = frappe.get_all(
        "BankTransaction",
        filters={"status": status, "transaction_status": "sent"},
        fields=["name"],
        limit = limit
    )
    
    
    
    
    
    transactions = [frappe.get_doc("BankTransaction", tx.name) for tx in tnxs]

    
    if not transactions:
        return "No pending transactions found"

    processed = 0
    total_transactions = len(transactions)
    
    for i in range(0, total_transactions, batch_size):
        notify_progress(processed, total_transactions)
        
        working_list = transactions[i:i+batch_size]
        
        
        
        tx_list = prepare_tx_list_for_prompt(status, working_list)
            
        results = classify_transaction(tx_list, status)
        
        tx_map = {tx.name: tx for tx in working_list}

        try:
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
                

                    save_ai_classification_result(result, input_transaction)
                    
                    kind = input_transaction.kind

                    created_at_str = tx_details.get("createdAt")  # '2025-05-24T06:24:30.945859Z'

                    try:
                        save_journal_entry(result, created_at_str, kind)
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
        except Exception as e:
                processed += 1
                print(f"Error processing AI result : {str(e)}", "AI Accountant")




    notify_progress(total_transactions, total_transactions)

    return f"Processed {processed} transactions"

