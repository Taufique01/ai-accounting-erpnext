frappe.ui.form.on('BankTransaction', {
    refresh(frm) {
        frm.add_custom_button(__('Quick Journal Entry'), function () {
            frappe.model.with_doctype('Journal Entry', () => {
                const je = frappe.model.get_new_doc('Journal Entry');

                // Use values from the BankTransaction form
                const posting_date = frm.doc.transaction_date || frappe.datetime.nowdate();
                const company = frappe.defaults.get_default("Company");
                const companyAbbr = company==="Taufique company (Demo)"? "TCD": "MSBL";
            
                je.posting_date = posting_date;
                je.company = company;
                

                console.log(frm.doc);

                for (let i=0; i<frm.doc.ai_recommended_entries.length; i++){
                    const entry = frm.doc.ai_recommended_entries[i];                    
                    // Use BankTransaction details for journal entry lines
                    const debit_row = frappe.model.add_child(je, 'Journal Entry Account', 'accounts');
                    debit_row.account = entry.debit_account==="Unknown account name"?`Suspense (Receipts) - ${companyAbbr}`: entry.debit_account;
                    debit_row.debit_in_account_currency = entry.amount || 0;
                    
                    const credit_row = frappe.model.add_child(je, 'Journal Entry Account', 'accounts');
                    credit_row.account = entry.credit_account==="Unknown account name"?`Suspense (Payments) - ${companyAbbr}`: entry.credit_account;
                    credit_row.credit_in_account_currency = entry.amount || 0;
                    
                    je.user_remark = entry.memo + "\n" + "transaction name: "+ frm.doc.name;
                }

                sessionStorage.setItem("return_to_transaction", frm.doc.name);

                frappe.set_route('Form', 'Journal Entry', je.name);
            });
        });
    }
});
