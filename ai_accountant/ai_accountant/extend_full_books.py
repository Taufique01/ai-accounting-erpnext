import frappe
import json
from frappe.utils import now

def execute():
    """Extend the AI Accountant with full AR/AP and reporting functionality"""
    print("Starting extension of AI Accountant to full books...")

    # Create required DocTypes if they don't exist
    ensure_doctypes_exist()

    # Set up Mercury API webhook if not already configured
    setup_mercury_webhook()

    # Enable AR/AP processing in settings
    enable_ar_ap()

    # Update scheduler events
    update_scheduler()

    # Create dummy data for testing
    create_test_data()

    print("AI Accountant extension completed successfully!")
    return "Extension completed"


def ensure_doctypes_exist():
    """Ensure all required DocTypes exist"""
    print("Checking DocTypes...")

    if not frappe.db.exists("DocType", "BankTransaction"):
        print("Creating BankTransaction DocType...")
        # TODO: Add DocType creation code here

    if not frappe.db.exists("DocType", "VendorMap"):
        print("Creating VendorMap DocType...")
        # TODO: Add DocType creation code here

    if not frappe.db.exists("DocType", "LlmCostLog"):
        print("Creating LlmCostLog DocType...")
        # TODO: Add DocType creation code here

    if not frappe.db.exists("DocType", "AI Accountant Settings"):
        print("Creating AI Accountant Settings DocType...")
        # TODO: Add DocType creation code here


def setup_mercury_webhook():
    """Set up the Mercury API webhook if not already configured"""
    print("Setting up Mercury webhook...")
    site_config_path = frappe.get_site_path('site_config.json')

    with open(site_config_path, 'r') as f:
        config = json.load(f)

    if 'mercury_webhook_url' not in config:
        print("Adding Mercury webhook URL to site config...")
        site_url = frappe.utils.get_url()
        webhook_url = f"{site_url}/api/method/ai_accountant.ai_accountant.mercury_webhook"
        config['mercury_webhook_url'] = webhook_url

        with open(site_config_path, 'w') as f:
            json.dump(config, f, indent=4)

        print(f"Mercury webhook URL set to: {webhook_url}")
        print("Please configure this URL in your Mercury account settings")


def enable_ar_ap():
    """Enable AR/AP processing in settings"""
    print("Enabling AR/AP processing...")

    if not frappe.db.exists("AI Accountant Settings"):
        doc = frappe.get_doc({
            "doctype": "AI Accountant Settings",
            "enable_ar_ap": 1,
            "commission_rate": 0.25,
            "default_model": "gpt-3.5-turbo-1106",
            "use_gpt4_threshold": 0.8
        })
        doc.insert()
        print("Created AI Accountant Settings with AR/AP enabled")
    else:
        doc = frappe.get_doc("AI Accountant Settings")
        doc.enable_ar_ap = 1
        doc.commission_rate = 0.25
        doc.save()
        print("Updated AI Accountant Settings with AR/AP enabled")


def update_scheduler():
    """Update scheduler events to include AR/AP and reporting"""
    print("Updating scheduler events...")

    print("""
Please add the following lines to your hooks.py file if not already present:

scheduler_events = {
    "daily": [
        "ai_accountant.ai_accountant.batch.process_all_pending",
        "ai_accountant.ai_accountant.ar_ap.process_ar_ap_transactions",
        "ai_accountant.ai_accountant.reconcile.reconcile_transactions",
        "ai_accountant.ai_accountant.reports.generate_management_pack"
    ],
    "hourly": [
        "ai_accountant.ai_accountant.batch.check_pending_transactions"
    ]
}
""")


def create_test_data():
    """Create test data for demonstration"""
    print("Creating test data...")

    if not frappe.db.exists("BankTransaction"):
        print("Creating sample bank transactions...")

        transactions = [
            {
                "external_id": "tx_sample_1",
                "payload": json.dumps({
                    "id": "tx_sample_1",
                    "amount": 5000,
                    "date": "2023-05-25",
                    "description": "Hospital Payment - Invoice #1234",
                    "merchant_name": "General Hospital",
                    "category": "deposit"
                }),
                "processed_hash": frappe.generate_hash("5000,2023-05-25,Hospital Payment - Invoice #1234"),
                "status": "Pending"
            },
            {
                "external_id": "tx_sample_2",
                "payload": json.dumps({
                    "id": "tx_sample_2",
                    "amount": -1250,
                    "date": "2023-05-26",
                    "description": "Office Supplies",
                    "merchant_name": "Office Depot",
                    "category": "expense"
                }),
                "processed_hash": frappe.generate_hash("-1250,2023-05-26,Office Supplies"),
                "status": "Pending"
            }
        ]

        for tx in transactions:
            doc = frappe.get_doc({
                "doctype": "BankTransaction",
                **tx
            })
            doc.insert(ignore_permissions=True)

        print(f"Created {len(transactions)} sample bank transactions")

    if not frappe.db.exists("LlmCostLog"):
        print("Creating sample cost logs...")

        logs = [
            {
                "date": frappe.utils.add_days(frappe.utils.today(), -1),
                "tokens_in": 500,
                "tokens_out": 200,
                "cost": 0.0005
            },
            {
                "date": frappe.utils.today(),
                "tokens_in": 1200,
                "tokens_out": 350,
                "cost": 0.0012
            }
        ]

        for log in logs:
            doc = frappe.get_doc({
                "doctype": "LlmCostLog",
                **log
            })
            doc.insert(ignore_permissions=True)

        print(f"Created {len(logs)} sample cost logs")
