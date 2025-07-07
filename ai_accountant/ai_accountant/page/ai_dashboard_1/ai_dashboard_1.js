frappe.pages['ai-dashboard-1'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Welcome here',
		single_column: true
	});

	page.set_primary_action('Refresh', () => {
		frappe.msgprint("Refreshed!");
	});

	$(wrapper).html(`<div class="p-4">Welcome to AI Dashboard</div>`);
}