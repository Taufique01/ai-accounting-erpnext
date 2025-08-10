import frappe
import json
from openai import OpenAI
from datetime import datetime
from ai_accountant.ai_accountant.realtime_utils import notify_progress
from ai_accountant.ai_accountant.llm_helper import get_openai_api_key, log_cost, format_accounts_for_prompt, prepare_tx_list_for_prompt
from ai_accountant.ai_accountant.classify import classify_msb_trust, classify_msb_operating, classify_msb_payroll, classify_msb_ars, classify_msb_workers_comp
from ai_accountant.ai_accountant.ai_classify import classify_transaction


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
        return frappe.db.get_value(
            "VendorMap",
            {"vendor_name": ["like", f"%{counterparty}%"]},
            ["party", "party_type"],
            as_dict=True
        )

def save_journal_entry(result, tx_created_at_str):
    
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

        if confidence < .70:
            raise ValueError(f"Classification confidence is very less {confidence}")
        

            
        # Get party info for debit and credit accounts
        # party_for_debit = get_party_info(debit_account, counterparty)
        # party_for_credit = get_party_info(credit_account, counterparty)
        
        # Prepare debit line
        debit_line = {
            "account": debit_account,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0
        }
        # if party_for_debit:
        #     debit_line.update(party_for_debit)

        # Prepare credit line
        credit_line = {
            "account": credit_account,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": amount
        }
        # if party_for_credit:
        #     credit_line.update(party_for_credit)

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


def merge_ai_classifications(unclassified_expenses, ai_classifications):
    """
    Merge AI classifications into unclassified expenses.

    Args:
        unclassified_expenses (list): List of dicts, each with keys 'name' and 'entries'.
        ai_classifications (list): List of dicts, each with keys 'name' and 'entries',
                                   where entries contain 'debit_account', 'memo', 'confidence'.

    Returns:
        list: Merged list with AI classifications applied to unclassified expenses.
    """
    ai_lookup = {item["name"]: item for item in ai_classifications}

    merged_list = []
    for expense in unclassified_expenses:
        name = expense.get("transaction").name
        entries = expense.get("entries", [])
        if name in ai_lookup:
            ai_entry = ai_lookup[name]["entries"][0]  # assuming 1 entry per transaction here
            updated_entries = []
            for entry in entries:
                updated_entries.append({
                     # keep all original fields
                    "credit_account": entry.get("credit_account"),
                    "amount": entry.get("amount") ,
                    "debit_account": ai_entry.get("debit_account"),
                    "memo": ai_entry.get("memo", entry.get("memo")),
                    "confidence": ai_entry.get("confidence")
                })
            merged_list.append({"name": name, "entries": updated_entries})
        else:
            # No AI classification found, keep original
            merged_list.append(expense)
    return merged_list

def extract_all_transactions(expense_list):
    """
    Extract and combine all 'entries' from a list of dicts with keys 'transaction' and 'entries'.

    Args:
        expense_list (list): List of dicts, each with 'transaction' and 'entries' keys.

    Returns:
        list: A flat list containing all entries from all expense items.
    """
    results = []
    for item in expense_list:
        results.append(item.get("transaction"))
    return results


def classify_batch(status="Pending"):
    """Process a batch of pending transactions"""
    print("I am in classifying batch")

    processed = 0
    total_transactions = 500
    
    notify_progress(processed, total_transactions)
    
    # tx_list = prepare_tx_list_for_prompt(status, working_list)
    # results = classify_transaction(tx_list, status)
    
    # results, transactions = classify_msb_trust()
    # print(results, transactions)
    # tx_map = {tx.name: tx for tx in transactions}
    # trust_processed = save_results_in_gl_entry(results, tx_map)
    # notify_progress(trust_processed, total_transactions)

    # results, transactions = classify_msb_ars()
    # tx_map = {tx.name: tx for tx in transactions}
    # save_results_in_gl_entry(results, tx_map)
    

    # results, transactions = classify_msb_workers_comp()
    # tx_map = {tx.name: tx for tx in transactions}
    # save_results_in_gl_entry(results, tx_map)
    
    
    classify_msb_operating_transactions(total_transactions)

    # results, transactions = classify_msb_payroll()
    # tx_map = {tx.name: tx for tx in transactions}
    # payroll_processed = save_results_in_gl_entry(results, tx_map)
    # notify_progress(0+0+payroll_processed, total_transactions)



    notify_progress(total_transactions, total_transactions)

    return f"Processed {processed} transactions"

def classify_msb_operating_transactions(total_transactions):
    results, transactions, unclassified_expenses, unclassified_revenues = classify_msb_operating()
    tx_map = {tx.name: tx for tx in transactions}
    operating_processed = save_results_in_gl_entry(results, tx_map)
    notify_progress(0+operating_processed, total_transactions)
    
    
    # print("unclassified\n", unclassified_expenses)
    tx = extract_all_transactions(unclassified_expenses)
    tx_list = prepare_tx_list_for_prompt("Pending", tx)
    
    ai_classifications = classify_transaction(tx_list)
    
    expense_ai_result = merge_ai_classifications(unclassified_expenses, ai_classifications)
    # print("after merged", expense_ai_result)
    tx_map = {u_e["transaction"].name: u_e["transaction"] for u_e in unclassified_expenses}
    save_results_in_gl_entry(expense_ai_result, tx_map)
    
    # process unclassified revenues
    
    tx_unclassified_revenues = extract_all_transactions(unclassified_revenues)
    revenue_tx_list_for_ai = prepare_tx_list_for_prompt("Pending", tx_unclassified_revenues)
    ai_classified_for_revenues = classify_transaction(revenue_tx_list_for_ai)
    tx_map = {u_e["transaction"].name: u_e["transaction"] for u_e in unclassified_revenues}
    save_results_in_gl_entry(ai_classified_for_revenues, tx_map)

    

def save_results_in_gl_entry(results, tx_map):
    processed = 0
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
                    

                created_at_str = tx_details.get("createdAt")  # '2025-05-24T06:24:30.945859Z'

                try:
                    print("____________", result)
                    save_journal_entry(result, created_at_str)
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
            frappe.msgprint(f"Error processing AI result : {str(e)}", "AI Accountant")

    return processed

