import frappe

def boot_session(bootinfo):
    # user = frappe.session.user
    # if frappe.has_role(user, "Sales User"):
    #     bootinfo["home_page"] = "/desk#List/Sales%20Order"
    # elif frappe.has_role(user, "Accounts User"):
    #     bootinfo["home_page"] = "/desk#List/Journal%20Entry"
    # else:
    bootinfo["home_page"] = "ai-dashboard"