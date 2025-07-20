frappe.ui.form.on('Journal Entry', {
    after_save(frm) {
        const txn = sessionStorage.getItem("return_to_transaction");
        if (txn) {
            frappe.msgprint("Journal Entry saved. Returning to BankTransaction...");
            sessionStorage.removeItem("return_to_transaction");
            frappe.set_route(`/app/banktransaction/${txn}`);
        }
    }
});
