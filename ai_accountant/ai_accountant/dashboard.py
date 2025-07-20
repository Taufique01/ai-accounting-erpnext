import frappe
import json
from datetime import datetime
import frappe
import json
import requests # type: ignore
from urllib.parse import quote


def get_mercury_account_ids():
    api_token = frappe.conf.get("mercury_api_key")
    url = "https://api.mercury.com/api/v1/accounts"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {api_token}"
    }

    try:
        response = requests.get(url, headers=headers)
        
        response.raise_for_status()  # Raise exception for HTTP errors
        data = response.json()

        account_ids = [account["id"] for account in data.get("accounts", [])]
        return account_ids

    except requests.exceptions.RequestException as e:
        print(f"HTTP Request failed: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []


@frappe.whitelist()
def fetch_transaction_data():
    # Get Mercury API token from site config
    
    frappe.publish_realtime(event="transaction_sync_update", message={
        "is_completed": False,
        "percent": 0,
        "message": "Fetching accounts."
    })
    
    token = frappe.conf.get("mercury_api_key")
    if not token:
        frappe.throw("Missing Mercury API key in site config")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    

    account_ids = get_mercury_account_ids()
    
    if not account_ids:
         return {"status": "success", "message": "No accounts to fetch transactions."}
    
    frappe.publish_realtime(event="transaction_sync_update", message={
        "is_completed": False,
        "percent": 10,
        "message": "Accounts fetched."
    })
    
    total_transactions = 0
    progress = 1
    last_fetched_time = frappe.db.get_single_value('BankTransactionInfo', 'last_fetched_time')
    frappe.db.set_value("BankTransactionInfo", None, "last_fetched_time", datetime.now())

    last_fetched_time_formatted = quote(last_fetched_time.isoformat()+ "Z")
    
    for id in account_ids:
        
        url = f"https://api.mercury.com/api/v1/account/{id}/transactions?limit=100&offset=0&order=desc&start={last_fetched_time_formatted}"

        # Call the Mercury API
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            frappe.throw(f"Mercury API error: {e}")

        # Process each transaction
        for tx in data.get("transactions", []):
            
            if frappe.db.exists("BankTransaction", {"external_id": tx["id"]}):
                continue

            # Generate a hash for deduplication
            tx_hash = frappe.generate_hash(
                f"{tx.get('amount')}{tx.get('createdAt')}{tx.get('counterpartyName')}{tx.get('note') or ''}"
            )
            
            # Create a new BankTransaction with only the required fields
            doc = frappe.get_doc({
                "doctype": "BankTransaction",
            })
            
            doc.external_id = tx["id"]
            doc.payload = json.dumps(tx)
            doc.processed_hash = tx_hash
            doc.status = "Pending"
            
            doc.amount = tx.get("amount", 0.0)
            doc.transaction_date =  datetime.fromisoformat(tx.get("createdAt").rstrip('Z'))
            doc.transaction_status = tx.get("status")
            doc.bank_description = tx.get("bankDescription")
            doc.counterparty_name = tx.get("counterpartyName")
            doc.kind = tx.get("kind")
            doc.dashboard_link = tx.get("dashboardLink")
            
            doc.insert()
            
            total_transactions = total_transactions + 1
        
        progress = progress + 1
        
        frappe.publish_realtime(event="transaction_sync_update", message={
            "is_completed": False,
            "percent": 10 + 90*progress/len(account_ids),
            "message": "Fetching transactions..."
        })
            
    response_meg = str(total_transactions) + " Transactions synced from " + str(len(account_ids)) + " accounts."
    
    frappe.publish_realtime(event="transaction_sync_update", message={
        "is_completed": True,
        "percent": 100,
        "message": "Transactions Fetched"
    })
            
    return {"status": "success", "message": response_meg}


@frappe.whitelist()
def get_cost_data():

    """Get cost data for the AI Accountant dashboard."""

    # Calculate date 30 days ago
    thirty_days_ago = frappe.utils.add_days(frappe.utils.today(), -30)

    # Daily costs for the last 30 days (sum cost grouped by date)
    daily_costs = frappe.db.sql("""
        SELECT
            DATE(date) as date,
            SUM(cost) as daily_cost
        FROM `tabLlmCostLog`
        WHERE date >= %s
        GROUP BY DATE(date)
        ORDER BY DATE(date)
    """, (thirty_days_ago,), as_dict=True)

    # Format daily data for chart labels and values
    daily_labels = [frappe.utils.formatdate(entry.date, "MM-dd") for entry in daily_costs]
    daily_values = [entry.daily_cost for entry in daily_costs]

    # Monthly costs (sum cost grouped by year and month)
    monthly_costs = frappe.db.sql("""
        SELECT
            YEAR(date) as year,
            MONTH(date) as month,
            SUM(cost) as monthly_cost
        FROM `tabLlmCostLog`
        GROUP BY YEAR(date), MONTH(date)
        ORDER BY YEAR(date), MONTH(date)
    """, as_dict=True)

    # Format monthly labels and values
    monthly_labels = [datetime(entry.year, entry.month, 1).strftime("%b %Y") for entry in monthly_costs]
    monthly_values = [entry.monthly_cost for entry in monthly_costs]

    # Overall token and cost statistics
    total_tokens = frappe.db.sql("""
        SELECT
            SUM(tokens_in) as input_tokens,
            SUM(tokens_out) as output_tokens,
            SUM(tokens_in + tokens_out) as total_tokens,
            SUM(cost) as total_cost
        FROM `tabLlmCostLog`
    """, as_dict=True)[0]

    # This month's cost
    now = datetime.now()
    month_cost = frappe.db.sql("""
        SELECT SUM(cost) as cost
        FROM `tabLlmCostLog`
        WHERE MONTH(date) = %s AND YEAR(date) = %s
    """, (now.month, now.year), as_dict=True)[0].cost or 0

    # Model usage breakdown (percentage usage for tokens_in <= 4000 and > 4000)
    # Assuming tokens_in <= 4000 => GPT-3.5, tokens_in > 4000 => GPT-4o-mini
    total_count = frappe.db.count("LlmCostLog")
    gpt35_count = frappe.db.count("LlmCostLog", filters={"model": "gpt-3.5-turbo"})
    gpt4o_count = frappe.db.count("LlmCostLog", filters={"model": "gpt-4o"})

    model_usage = {
        "gpt35": (gpt35_count / total_count * 100) if total_count else 0,
        "gpt4o": (gpt4o_count / total_count * 100) if total_count else 0,
    }

    return {
        "daily": {
            "labels": daily_labels,
            "values": daily_values
        },
        "monthly": {
            "labels": monthly_labels,
            "values": monthly_values
        },
        "stats": {
            "input_tokens": total_tokens.input_tokens or 0,
            "output_tokens": total_tokens.output_tokens or 0,
            "total_tokens": total_tokens.total_tokens or 0,
            "total_cost": total_tokens.total_cost or 0,
            "month_cost": month_cost,
            "model_usage": {
                "gpt35": round(model_usage["gpt35"], 1),
                "gpt4o": round(model_usage["gpt4o"], 1)
            }
        }
    }


@frappe.whitelist()
def get_transaction_stats():
    """Get transaction statistics for the dashboard."""

    # Count transactions by status
    status_counts = frappe.db.sql("""
        SELECT
            status,
            COUNT(*) as count
        FROM `tabBankTransaction`
        GROUP BY status
    """, as_dict=True)

    status_dict = {status.status: status.count for status in status_counts}

    # Total transactions
    total_count = frappe.db.count("BankTransaction")

    # Transactions modified today (since midnight)
    today = frappe.utils.now_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = frappe.db.count("BankTransaction", {"modified": [">=", today]})

    # Placeholder average processing time in days (replace with real logic if available)
    avg_time = 3.5

    # Recent 10 transactions
    recent_txs = frappe.get_all(
        "BankTransaction",
        fields=["name", "payload", "status", "modified"],
        order_by="modified desc",
        limit=10
    )

    # Format recent transactions for frontend
    formatted_txs = []
    for tx in recent_txs:
        try:
            payload = json.loads(tx.payload)
        except Exception:
            payload = {}

        formatted_txs.append({
            "date": frappe.utils.format_datetime(payload.get("date") or tx.modified),
            "description": (payload.get("description") or "")[:50],
            "amount": payload.get("amount") or 0,
            "status": tx.status
        })
        
   
    return {
        "status_counts": status_dict,
        "total_count": total_count,
        "today_count": today_count,
        "avg_processing_time": avg_time,
        "recent_transactions": formatted_txs,
        
    }
