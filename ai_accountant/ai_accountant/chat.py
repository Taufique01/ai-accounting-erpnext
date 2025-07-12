import frappe
import json
from datetime import datetime
from openai import OpenAI
from frappe.utils import today, add_days
from ai_accountant.ai_accountant.llm_helper import get_openai_api_key, log_cost

@frappe.whitelist()
def ai_chat(question):
    """Chat interface for financial queries"""
    api_key = get_openai_api_key()
    if not api_key:
        return {"error": "OpenAI API key not found in configuration"}

    client = OpenAI(
        # base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Get company financial context
    context = get_financial_context()

    # Prepare the messages for OpenAI
    prompt = [
        {
            "role": "system",
            "content": f"""You are an AI financial assistant for a company.
Use the following financial context to answer questions:
{context}
If you need to run calculations or forecasts, explain the methodology.
Provide specific numbers and insights from the data."""
        },
        {"role": "user", "content": question}
    ]

    # Call OpenAI
    try:
        start_time = datetime.now() 

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=prompt,
            temperature=0.2  # Lower temperature for financial accuracy
        )
        
        end_time = datetime.now() 
        
        duration = end_time - start_time
        

        # Log the cost
        log_cost(
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            input=json.dumps(prompt),
            output=response.choices[0].message.content,
            duration=duration,
            model="gpt-3.5-turbo"
        )

        return {
            "answer": response.choices[0].message.content,
            "success": True
        }

    except Exception as e:
        frappe.log_error(f"OpenAI API Error: {str(e)}", "AI Accountant")
        return {
            "error": str(e),
            "success": False
        }

def get_financial_context():
    """Get relevant financial information for context"""
    company = frappe.defaults.get_user_default("Company")
    from_date = add_days(today(), -30)
    to_date = today()

    # Get cash flow summary
    cf_data = frappe.db.sql("""
        SELECT 
            SUM(debit) AS total_debits, 
            SUM(credit) AS total_credits 
        FROM `tabGL Entry` 
        WHERE posting_date BETWEEN %s AND %s 
          AND company = %s
    """, (from_date, to_date, company), as_dict=True)

    # Get top 5 expenses
    top_expenses = frappe.db.sql("""
        SELECT gle.account, SUM(gle.debit) AS amount 
        FROM `tabGL Entry` gle
        JOIN `tabAccount` acc ON gle.account = acc.name
        WHERE gle.posting_date BETWEEN %s AND %s 
        AND gle.company = %s 
        AND gle.debit > 0 
        AND acc.account_type = 'Expense'
        GROUP BY gle.account 
        ORDER BY amount DESC 
        LIMIT 5
    """, (from_date, to_date, company), as_dict=True)


    # Get AR aging
    ar_aging = frappe.db.sql("""
        SELECT 
            SUM(outstanding_amount) AS total_outstanding,
            SUM(IF(DATEDIFF(CURDATE(), due_date) <= 30, outstanding_amount, 0)) AS within_30,
            SUM(IF(DATEDIFF(CURDATE(), due_date) BETWEEN 31 AND 60, outstanding_amount, 0)) AS within_60,
            SUM(IF(DATEDIFF(CURDATE(), due_date) > 60, outstanding_amount, 0)) AS over_60
        FROM `tabSales Invoice`
        WHERE docstatus = 1 AND outstanding_amount > 0 AND company = %s
    """, (company,), as_dict=True)
    
    try:
        net_cash_flow = (cf_data[0].total_credits - cf_data[0].total_debits)
    except Exception as e:
        net_cash_flow = 0

    # Format context
    context = f"""
Financial Summary for {company}:

Cash Flow (Last 30 Days):
- Total Inflows: {cf_data[0].total_credits or 0 if cf_data else 0}
- Total Outflows: {cf_data[0].total_debits or 0 if cf_data else 0}
- Net Cash Flow: {net_cash_flow}

Top Expenses:
"""
    for expense in top_expenses:
        context += f"- {expense.account}: {expense.amount}\n"

    context += f"""
Accounts Receivable Aging:
- Total Outstanding: {ar_aging[0].total_outstanding if ar_aging else 0}
- 0-30 Days: {ar_aging[0].within_30 if ar_aging else 0}
- 31-60 Days: {ar_aging[0].within_60 if ar_aging else 0}
- Over 60 Days: {ar_aging[0].over_60 if ar_aging else 0}
"""
    return context
