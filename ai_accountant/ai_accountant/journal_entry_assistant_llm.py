import frappe
import json
from openai import OpenAI
from datetime import datetime
from ai_accountant.ai_accountant.llm_helper import get_openai_api_key, log_cost, format_accounts_for_prompt


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
                        "transaction_no": {"type": "number"},
                        "extracted_transactions_input":{"type": "string"},

                        "entries": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    
                                    "debit_account": {"type": "string"},
                                    "credit_account": {"type": "string"},
                                    "amount": {"type": "number"},
                                    "memo": {"type": "string"},
                                    "confidence": {"type": "number"},
                                },
                                "required": ["debit_account", "credit_account", "amount", "memo", "confidence",]
                            }
                        }
                    },
                    "required": ["index", "entries",  "extracted_transactions_input"]
                }
            }
        },
        "required": ["results"]
    }
}


def classify_transaction(text_list):
    """Classify multiple natural language transaction texts using OpenAI"""
    
    start_time = datetime.now()


    accounts_text = format_accounts_for_prompt()
    print(accounts_text)
    prompt = [
        {
            "role": "system",
            "content": "You are an expert accountant. Find out how many transactions has been made form user input. And classify each transaction into debit and credit journal entries using the company's Chart of Accounts. For unknown accounts, use 'Unknown account name'. And return journal entries for each transactions."
        },
        {
            "role": "system",
            "content": f"Company's Chart of Accounts:\n{accounts_text}"
        },
        {
            "role": "user",
            "content": f"Classify the following transactions:\n{json.dumps(text_list, indent=2)}"
        }
    ]

    api_key = get_openai_api_key()
    if not api_key:
        frappe.throw("OpenAI API key not configured")

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            tools=[{
                "type": "function",
                "function": journal_schema
            }],
            tool_choice={"type": "function", "function": {"name": "post_journal"}},
            messages=prompt,
            max_tokens=2000
        )
        
        
        results = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        
        end_time = datetime.now() 
        
        duration = end_time - start_time

        log_cost(
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            input=f"Classify the following transactions:\n{json.dumps(text_list, indent=2)}",
            output=json.dumps(results),
            duration = duration
        )
        
        return results["results"]

    except Exception as e:
        frappe.log_error(str(e), "AI Classification Error")
        return []


def process_text_batch(text_list, posting_date=None):
    """
    Process a batch of plain text transactions and create Journal Entries.
    Example input: ["Paid rent for July...", "Bought laptop for..."]
    """
    results = classify_transaction(text_list)
    
    print(results)
    error_responses = []
    success = 0
    failed = 0
    for result in results:
       
        entries = result.get("entries", [])

        # Parse date or use today's
        posting = datetime.now().isoformat()
        
        is_failed = False

        for entry in entries:
            try:
                je = frappe.get_doc({
                    "doctype": "Journal Entry",
                    "posting_date": posting,
                    "user_remark": entry.get("memo", ""),
                    "accounts": [
                        {
                            "account": entry["debit_account"],
                            "debit_in_account_currency": entry["amount"],
                            "credit_in_account_currency": 0
                        },
                        {
                            "account": entry["credit_account"],
                            "debit_in_account_currency": 0,
                            "credit_in_account_currency": entry["amount"]
                        }
                    ]
                })
                je.insert()
                je.submit()

            except Exception as e:
                is_failed = True
                error_description = result['extracted_transactions_input'] + '\n' + str(e) + '\n'
                error_responses.append(error_description)
                frappe.log_error(f"Error creating journal entry: {str(e)}", "AI Accountant")
        if is_failed:
            failed = failed + 1
        else:
            success = success + 1
            
    return {"success": success, "failed":failed, "error_responses": error_responses, "is_success": True}


@frappe.whitelist()
def journal_entry_assistant(query):
    
    
    result = process_text_batch(query)
    
    
    return result
    