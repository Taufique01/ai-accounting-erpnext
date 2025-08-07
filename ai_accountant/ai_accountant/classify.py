from enum import Enum
import frappe


class Account:
    MSB_TRUST = "MSB Trust"
    MSB_PAYROLL = "MSB Payroll"
    MSB_OPERATING = "MSB Operating"
    MSB_WORKER_COMPENSATION = "MSB Worker's Compensation"
    MSB_ARS = "MSB ARS Account Account"
    
def accounting_name(ant):
    return f"{ant} - MSBL"

def get_transaction(account_name):
    limit = frappe.db.get_single_value('LLMSettings', 'limit')
    
    tnxs = frappe.get_all(
        "BankTransaction",
        filters={"status": "Pending", "transaction_status": "sent", "our_account_nickname": account_name},
        fields=["name"],
        limit = 500
    )
    
    transactions = [frappe.get_doc("BankTransaction", tx.name) for tx in tnxs]
    return transactions


ACC_NAME_REV_COLLECTION_FEE = "Collection Revenue - MSBL"
ACC_NAME_CLIENT_PAYABLE = "Funds Held in Trust - MSBL"

def classify_msb_trust():
    
    transactions = get_transaction(Account.MSB_TRUST)
    print(transactions)
    results = []

    for tnx in transactions:
        print("tnx")
        entries = []
        amount = abs(tnx.amount)
        cp = tnx.counterparty_nickname  # assumed to be string like "MSB_OPERATING"
       
        if tnx.amount > 0:  # Incoming money
            if tnx.kind == "internalTransfer":
                # Transfer into MSB Trust
                entries.append({
                    "debit_account": accounting_name(Account.MSB_TRUST),
                    "credit_account": accounting_name(cp),
                    "amount": amount,
                    "memo": f"internal transfer received from {cp} into Trust",
                    "confidence": 1.0
                })

                if cp in [Account.MSB_OPERATING, Account.MSB_PAYROLL]:
                    # Fee revenue reversal or adjustment
                    entries.append({
                        "debit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "credit_account": ACC_NAME_CLIENT_PAYABLE,
                        "amount": amount,
                        "memo": "Reversing collection fee revenue, returned to Trust",
                        "confidence": 1.0
                    })

            else:
                # External debtor or third-party inflow
                entries.append({
                    "debit_account": accounting_name(Account.MSB_TRUST),
                    "credit_account": ACC_NAME_CLIENT_PAYABLE,
                    "amount": amount,
                    "memo": f"Funds received from debtor into Trust account from {tnx.counterparty_name}",
                    "confidence": 1.0
                })

        else:  # Outgoing money
            if tnx.kind == "internalTransfer":
                # Trust to internalTransfer MSB accounts
                entries.append({
                    "debit_account": accounting_name(cp),
                    "credit_account": accounting_name(Account.MSB_TRUST),
                    "amount": amount,
                    "memo": f"internal transfer from Trust to {cp}",
                    "confidence": 1.0
                })

                if cp in [Account.MSB_OPERATING, Account.MSB_PAYROLL]:
                    # Recognizing revenue
                    entries.append({
                        "debit_account": ACC_NAME_CLIENT_PAYABLE,
                        "credit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "amount": amount,
                        "memo": "Collection revenue transferred from Trust to Operating",
                        "confidence": 1.0
                    })

            else:
                # Payout to client
                entries.append({
                    "debit_account": ACC_NAME_CLIENT_PAYABLE,
                    "credit_account": accounting_name(Account.MSB_TRUST),
                    "amount": amount,
                    "memo": f"Client payout from Trust to {tnx.counterparty_name}", ## can be refund to payment service
                    "confidence": 1.0
                })

        results.append({"name": tnx.name, "entries":entries})
    
    

    return results, transactions



def classify_msb_operating():
    transactions = get_transaction(Account.MSB_OPERATING)

    results = []
    for tnx in transactions:
        cp = tnx.counterparty_nickname
        entries = []
        
        # if tnx.counterparty_nickname == Account.MSB_TRUST:
        #     continue

        # INFLOW: Money coming into MSB Operating
        if tnx.amount > 0:
            if tnx.kind == "internalTransfer":
                # internalTransfer transfer from other MSB account
                
                entries.append({
                    "debit_account": accounting_name(Account.MSB_OPERATING),
                    "credit_account": accounting_name(cp),
                    "amount": tnx.amount,
                    "memo": f"Internal transfer from {cp} to MSB Operating",
                    "confidence": 1
                })

                # If from Trust or Workers Comp → revenue recognition
                if cp in [
                    Account.MSB_TRUST,
                    Account.MSB_WORKER_COMPENSATION,
                    Account.MSB_ARS
                ]:
                    entries.append({
                        "debit_account": ACC_NAME_CLIENT_PAYABLE,
                        "credit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "amount": tnx.amount,
                        "memo": f"Recognize revenue from internal transfer to MSB Operating",
                        "confidence": 1
                    })

            else:
                # External inflow (e.g., refund, overpayment, etc.)
                entries.append({
                    "debit_account": accounting_name(Account.MSB_OPERATING),
                    "credit_account": ACC_NAME_REV_COLLECTION_FEE,
                    "amount": tnx.amount,
                    "memo": f"External deposit into MSB Operating from {tnx.counterparty_name}",
                    "confidence": 1  # Lower confidence since purpose may vary
                })

        # OUTFLOW: Money leaving MSB Operating
        else:
            if tnx.kind == "internalTransfer":
                # internalTransfer transfer to another MSB account
                entries.append({
                    "debit_account": accounting_name(cp),
                    "credit_account": accounting_name(Account.MSB_OPERATING),
                    "amount": abs(tnx.amount),
                    "memo": f"internal transfer from MSB Operating to {cp}",
                    "confidence": 1
                })

                # If to Trust or Workers Comp → revenue reverse
                if cp in [
                    Account.MSB_TRUST,
                    Account.MSB_WORKER_COMPENSATION,
                    Account.MSB_ARS
                ]:
                    entries.append({
                        "debit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "credit_account": ACC_NAME_CLIENT_PAYABLE,
                        "amount": abs(tnx.amount),
                        "memo": "Recognize revenue from internal transfer from MSB Operating",
                        "confidence": 1
                    })

            else:
                # External outflow (e.g., operating expense, vendor payment)
                entries.append({
                    "debit_account": "Administrative Expenses - MSBL", ## need AI to classify what type of expense## may be asset
                    "credit_account": accounting_name(Account.MSB_OPERATING),
                    "amount": abs(tnx.amount),
                    "memo": "External payment from MSB Operating (e.g., vendor or expense)", ## AI generated
                    "confidence": 0.9
                })

        results.append({"name": tnx.name, "entries":entries})
    return results, transactions


def classify_msb_payroll():
    transactions = get_transaction(Account.MSB_PAYROLL)

    results = []
    for tnx in transactions:
        entries = []
        cp = tnx.counterparty_nickname
        
        # if cp in [Account.MSB_TRUST, Account.MSB_OPERATING]:
        #     continue

        # INFLOW: Money coming into MSB Payroll
        if tnx.amount > 0:
            if tnx.kind == "internalTransfer":
                # internalTransfer transfer from other MSB account
                entries.append({
                    "debit_account": accounting_name(Account.MSB_PAYROLL),
                    "credit_account": accounting_name(cp),
                    "amount": tnx.amount,
                    "memo": f"internal transfer from {cp} to MSB Payroll",
                    "confidence": 1
                })

                # If from Trust or Workers Comp or ARS → revenue recognition
                if cp in [
                    Account.MSB_TRUST,
                    Account.MSB_WORKER_COMPENSATION,
                    Account.MSB_ARS
                ]:
                    entries.append({
                        "debit_account": ACC_NAME_CLIENT_PAYABLE,
                        "credit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "amount": tnx.amount,
                        "memo": "Recognize revenue from internal transfer to MSB Payroll",
                        "confidence": 1
                    })

            else:
                # External inflow (e.g., payroll reimbursements etc.)
                entries.append({
                    "debit_account": accounting_name(Account.MSB_PAYROLL),
                    "credit_account": ACC_NAME_REV_COLLECTION_FEE,
                    "amount": tnx.amount,
                    "memo": f"External deposit into MSB Payroll from {tnx.counterparty_name}",
                    "confidence": 1
                })

        # OUTFLOW: Money leaving MSB Payroll
        else:
            if tnx.kind == "internalTransfer":
                # internalTransfer transfer to another MSB account
                entries.append({
                    "debit_account": accounting_name(cp),
                    "credit_account": accounting_name(Account.MSB_PAYROLL),
                    "amount": abs(tnx.amount),
                    "memo": f"internal transfer from MSB Payroll to {cp}",
                    "confidence": 1
                })

                # If to Trust or Workers Comp or ARS → reverse revenue recognition
                if cp in [
                    Account.MSB_TRUST,
                    Account.MSB_WORKER_COMPENSATION,
                    Account.MSB_ARS
                ]:
                    entries.append({
                        "debit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "credit_account": ACC_NAME_CLIENT_PAYABLE,
                        "amount": abs(tnx.amount),
                        "memo": "Reverse revenue for internal transfer from MSB Payroll",
                        "confidence": 1
                    })

            else:
                # External outflow (e.g., payroll expenses, salary payments)
                entries.append({
                    "debit_account": "Salary - MSBL",  # Consider AI classification for specific payroll expense types
                    "credit_account": accounting_name(Account.MSB_PAYROLL),
                    "amount": abs(tnx.amount),
                    "memo": "External payroll payment from MSB Payroll",
                    "confidence": 1
                })

        results.append({"name": tnx.name, "entries":entries})
    return results, transactions


def classify_msb_ars():
    transactions = get_transaction(Account.MSB_ARS)

    results = []
    for tnx in transactions:
        
        cp = tnx.counterparty_nickname
        # if cp in [Account.MSB_TRUST, Account.MSB_OPERATING, Account.MSB_PAYROLL]:
        #     continue

        entries = []

        # Inflow to MSB ARS
        if tnx.amount > 0:
            if tnx.kind == "internalTransfer":
                # From another internalTransfer MSB account
                entries.append({
                    "debit_account": accounting_name(Account.MSB_ARS),
                    "credit_account": accounting_name(cp),
                    "amount": tnx.amount,
                    "memo": f"Transfer from {cp} to ARS",
                    "confidence": 1
                })

                # If it’s reverse revenue transfer (from MSB Operating or Payroll)
                if cp in [Account.MSB_OPERATING, Account.MSB_PAYROLL]:
                    entries.append({
                        "debit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "credit_account": ACC_NAME_CLIENT_PAYABLE,
                        "amount": tnx.amount,
                        "memo": "Recognize revenue from internal ARS deposit",
                        "confidence": 1
                    })                    
                    

            else:
                # External inflow: deposit from client
                entries.append({
                    "debit_account": accounting_name(Account.MSB_ARS),
                    "credit_account": ACC_NAME_CLIENT_PAYABLE,
                    "amount": tnx.amount,
                    "memo": f"Client funds received in ARS from {tnx.counterparty_name}",
                    "confidence": 1
                })

        # Outflow from MSB ARS
        else:
            if tnx.kind == "internalTransfer":
                # To another MSB account
                entries.append({
                    "debit_account": accounting_name(cp),
                    "credit_account": accounting_name(Account.MSB_ARS),
                    "amount": abs(tnx.amount),
                    "memo": f"Transfer from ARS to {cp}",
                    "confidence": 1
                })

                # If it’s revenue transfer (to Operating or Payroll)
                if cp in [Account.MSB_OPERATING, Account.MSB_PAYROLL]:
                    entries.append({
                        "debit_account": ACC_NAME_CLIENT_PAYABLE,
                        "credit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "amount": abs(tnx.amount),
                        "memo": "Recognize revenue from ARS internal transfer",
                        "confidence": 1
                    })
            else:
                # External payout from ARS
                entries.append({
                    "debit_account": ACC_NAME_CLIENT_PAYABLE,
                    "credit_account": accounting_name(Account.MSB_ARS),
                    "amount": abs(tnx.amount),
                    "memo": "External payout from ARS",
                    "confidence": 1
                })

        results.append({"name": tnx.name, "entries":entries})
    return results, transactions


def classify_msb_workers_comp():
    transactions = get_transaction(Account.MSB_WORKER_COMPENSATION)

    results = []
    for tnx in transactions:
        cp = tnx.counterparty_nickname

        
        # if cp in [Account.MSB_TRUST, Account.MSB_OPERATING, Account.MSB_PAYROLL, Account.MSB_ARS]:
        #     continue

        entries = []

        # Inflow to MSB Workers Compensation
        if tnx.amount > 0:
            if tnx.kind == "internalTransfer":
                # From another MSB account
                entries.append({
                    "debit_account": accounting_name(Account.MSB_WORKER_COMPENSATION),
                    "credit_account": accounting_name(cp),
                    "amount": tnx.amount,
                    "memo": f"Transfer from {cp} to Workers Comp",
                    "confidence": 1
                })

                # If from Operating or Payroll – reverse revenue
                if cp in [Account.MSB_OPERATING, Account.MSB_PAYROLL]:
                    entries.append({
                        "debit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "credit_account": ACC_NAME_CLIENT_PAYABLE,
                        "amount": tnx.amount,
                        "memo": "Recognize revenue from internalTransfer deposit to Workers Comp",
                        "confidence": 1
                    })

            else:
                # External deposit into Workers Comp
                entries.append({
                    "debit_account": accounting_name(Account.MSB_WORKER_COMPENSATION),
                    "credit_account": ACC_NAME_CLIENT_PAYABLE,
                    "amount": tnx.amount,
                    "memo": f"External deposit into Workers Comp from {tnx.counterparty_name}",
                    "confidence": 1
                })

        # Outflow from MSB Workers Compensation
        else:
            if tnx.kind == "internalTransfer":
                # To another MSB account
                entries.append({
                    "debit_account": accounting_name(cp),
                    "credit_account": accounting_name(Account.MSB_WORKER_COMPENSATION),
                    "amount": abs(tnx.amount),
                    "memo": f"Transfer from Workers Comp to {cp}",
                    "confidence": 1
                })

                # If to Operating or Payroll – may be revenue recognition
                if cp in [Account.MSB_OPERATING, Account.MSB_PAYROLL]:
                    entries.append({
                        "debit_account": ACC_NAME_CLIENT_PAYABLE,
                        "credit_account": ACC_NAME_REV_COLLECTION_FEE,
                        "amount": abs(tnx.amount),
                        "memo": "Recognize revenue from Workers Comp internalTransfer transfer",
                        "confidence": 1
                    })

            else:
                # External payout from Workers Comp
                entries.append({
                    "debit_account": ACC_NAME_CLIENT_PAYABLE,
                    "credit_account": accounting_name(Account.MSB_WORKER_COMPENSATION),
                    "amount": abs(tnx.amount),
                    "memo": f"External transfer from Workers Comp to {tnx.counterparty_name}",
                    "confidence": 1
                })

        results.append({"name": tnx.name, "entries":entries})
    return results, transactions



