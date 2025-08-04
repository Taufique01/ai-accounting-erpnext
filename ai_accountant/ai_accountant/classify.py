from enum import Enum

class AccountingName(Enum):
    MSB_TRUST = "MSB Trust"
    MSB_PAYROLL = "MSB PAYROLL"
    MSB_OPERATING = "MSB_OPERATING"
    MSB_WORKER_COMPENSATION = "MSB Workers compensation"
    MSB_ARS = "MSB ARS"

def classify_msb_trust(transactions):
    results = []

    for tnx in transactions:
        entries = []
        amount = abs(tnx.amount)
        cp = tnx.counterpartyName  # assumed to be string like "MSB_OPERATING"

        if tnx.amount > 0:  # Incoming money
            if tnx.kind == "internal":
                # Transfer into MSB Trust
                entries.append({
                    "debit_account": AccountingName.MSB_TRUST.value,
                    "credit_account": cp,
                    "amount": amount,
                    "memo": f"Internal transfer received from {cp} into Trust",
                    "confidence": 1.0
                })

                if cp in [AccountingName.MSB_OPERATING.value, AccountingName.MSB_PAYROLL.value]:
                    # Fee revenue reversal or adjustment
                    entries.append({
                        "debit_account": "Revenue – Collection Fee",
                        "credit_account": "Client Funds Payable",
                        "amount": amount,
                        "memo": "Reversing fee revenue, returned to Trust",
                        "confidence": 1.0
                    })

            else:
                # External debtor or third-party inflow
                entries.append({
                    "debit_account": AccountingName.MSB_TRUST.value,
                    "credit_account": "Client Funds Payable",
                    "amount": amount,
                    "memo": "Funds received from debtor into Trust account",
                    "confidence": 1.0
                })

        else:  # Outgoing money
            if tnx.kind == "internal":
                # Trust to internal MSB accounts
                entries.append({
                    "debit_account": cp,
                    "credit_account": AccountingName.MSB_TRUST.value,
                    "amount": amount,
                    "memo": f"Internal transfer from Trust to {cp}",
                    "confidence": 1.0
                })

                if cp in [AccountingName.MSB_OPERATING.value, AccountingName.MSB_PAYROLL.value]:
                    # Recognizing fee
                    entries.append({
                        "debit_account": "Client Funds Payable",
                        "credit_account": "Revenue – Collection Fee",
                        "amount": amount,
                        "memo": "Fee transferred from Trust to Operating",
                        "confidence": 1.0
                    })

            else:
                # Payout to client
                entries.append({
                    "debit_account": "Client Funds Payable",
                    "credit_account": AccountingName.MSB_TRUST.value,
                    "amount": amount,
                    "memo": "Client payout from Trust",
                    "confidence": 1.0
                })

        results.append(entries)

    return results
