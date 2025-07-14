frappe.pages['home'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Home',
		single_column: true
	});

	frappe.set_route("ai-accountant"); // redirects to /app/ai-accountant

}