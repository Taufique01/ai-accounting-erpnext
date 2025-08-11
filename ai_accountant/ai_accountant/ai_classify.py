from datetime import datetime
import json
from ai_accountant.ai_accountant.llm_helper import format_accounts_for_prompt, get_openai_api_key, log_cost
import frappe
from openai import OpenAI


expense_journal_schema = {
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
                                    "memo": {"type": "string"},
                                    "confidence": {"type": "number"}
                                },
                                "required": ["debit_account", "memo", "confidence"]
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


income_journal_schema = {
    "name": "post_journal_income",
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
                                    "credit_account": {"type": "string"},
                                    "memo": {"type": "string"},
                                    "confidence": {"type": "number"}
                                },
                                "required": ["credit_account", "memo", "confidence"]
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



# -------------------------
# Generic OpenAI Function
# -------------------------
def call_openai_with_schema(tx_list, prompt_messages, schema_function, schema_function_name, model="gpt-4o"):
    """
    Sends a classification request to OpenAI with a given prompt and schema.
    Returns parsed tool_call results.
    """
    start_time = datetime.now()

    api_key = get_openai_api_key()
    if not api_key:
        frappe.throw("OpenAI API key not configured")

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            tools=[{
                "type": "function",
                "function": schema_function
            }],
            tool_choice={"type": "function", "function": {"name": schema_function_name}},
            messages=prompt_messages
        )

        end_time = datetime.now()
        duration = end_time - start_time

        results = json.loads(
            response.choices[0].message.tool_calls[0].function.arguments
        )

        # Optional logging
        log_cost(
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            input=json.dumps(tx_list, indent=2),
            output=json.dumps(results),
            duration=duration,
            model=model
        )

        return results

    except Exception as e:
        print(f"OpenAI API Error: {str(e)}", "AI Accountant")
        return None


# -------------------------
# Accounting-specific Function
# -------------------------
def classify_expense_transactions_in_expense_account(tx_list, account_name):
    """
    Classifies bank transactions into double-entry journal entries.
    Uses company's chart of accounts and journal schema.
    """
    if account_name=="Payroll":
        accounts_text = "'Salary - MSBL', 'Insurance - MSBL'"
    else:
        accounts_text = format_accounts_for_prompt(["expense"])
    base_prompt = [
        {
            "role": "system",
            "content": (
                "You are an expert accountant for Midwest Service Bureau, LLC, a Technology-Enhanced Debt Recovery with Human Touch company.\n"
                "Your job is to classify **expense transactions** coming from the company's Operating bank account.\n"
                "Follow these rules:\n"
                "1. Classify the debit account type of each expense using the provided expense accounts list.\n"
                "2. Use available transaction details and other provided information to classify.\n"
                "3. If you cannot determine the exact category, select the most relevant default expense account.\n"
                "4. Only use accounts from the expense accounts list below.\n"
                "5. Return memo as actual memo we write in accounting journal entry.\n"
            )
        },
        {
           "role": "system",   "content": f"Expense Accounts:\n{accounts_text}"
        },
    ]
    
    # if status == "Error":
    #     base_prompt.append({
    #         "role": "system",
    #         "content":" ERROR_PROMPT"
    #     })

    base_prompt.append({
        "role": "user",
        "content": f"Classify the following transactions:\n{json.dumps(tx_list, indent=2)}"
    })

    results = call_openai_with_schema(
        tx_list=tx_list,
        prompt_messages=base_prompt,
        schema_function=expense_journal_schema,
        schema_function_name="post_journal",
        model="gpt-4o"
    )
    
    if results:
        return results.get("results", [])
    return None


def classify_revenue_transactions_in_expense_account(tx_list):
    """
    Classifies bank transactions into double-entry journal entries.
    Uses company's chart of accounts and journal schema.
    """
    accounts_text = format_accounts_for_prompt(["income"])
    base_prompt = [
        {
            "role": "system",
            "content": (
                "You are an expert accountant for Midwest Service Bureau, LLC, a Technology-Enhanced Debt Recovery with Human Touch company.\n"
                "Your job is to classify the incoming transactions in company's Operating account.\n"
                "Follow these rules:\n"
                "1. Classify the credit account type of each revenue transaction using the provided revenue accounts list.\n"
                "2. Use available transaction details and other provided information to classify transactions.\n"
                "3. If you cannot determine the exact category, select the most relevant default revenue account.\n"
                "4. Only use accounts from the revenue accounts list below.\n"
                "5. Return memo as the actual memo we write in accounting journal entries.\n"
                "6. For each transaction, indicate it is a revenue transaction and specify the credit account.\n"
            )
        },
        {
            "role": "system",
            "content": f"Revenue Accounts:\n{accounts_text}"
        },
    ]

    # if status == "Error":
    #     base_prompt.append({
    #         "role": "system",
    #         "content":" ERROR_PROMPT"
    #     })

    base_prompt.append({
        "role": "user",
        "content": f"Classify the following transactions:\n{json.dumps(tx_list, indent=2)}"
    })

    results = call_openai_with_schema(
        tx_list=tx_list,
        prompt_messages=base_prompt,
        schema_function=income_journal_schema,
        schema_function_name="post_journal_income",
        model="gpt-4o"
    )
    
    if results:
        return results.get("results", [])
    return None
