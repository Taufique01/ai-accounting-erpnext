frappe.pages['reports'].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'AI Reports',
        single_column: true
    });

    const container = $(`<div class="dashboard-section" style="padding:20px;"></div>`).appendTo(page.body);

    const reportList = ['Cash Flow', 'Balance Sheet', 'Profit and Loss Statement'];

    reportList.forEach(report => {
        frappe.call({
            method: 'ai_accountant.ai_accountant.reports.get_latest_summary',  // create this
            args: { report_name: report },
            callback: function (r) {
                if (r.message) {
                    const { summary_html, file_url } = r.message;

                    container.append(`
                        <div class="card" style="margin-bottom:20px;padding:15px;border:1px solid #ccc;border-radius:8px;">
                            <h3>${report}</h3>
                            ${summary_html}
                            <a href="${file_url}" target="_blank">📥 Download PDF</a>
                        </div>
                    `);
                }
            }
        });
    });
};
