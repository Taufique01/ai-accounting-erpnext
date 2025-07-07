app_name = "ai_accountant"
app_title = "Ai Accountant"
app_publisher = "s"
app_description = "des"
app_email = "s@mail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "ai_accountant",
		"logo": "/assets/ai_accountant/logo.png",
		"title": "Ai Accountant",
		"route": "/app/ai-dashboard",
		# "has_permission": "ai_accountant.api.permission.has_app_permission"
	}
]



# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/ai_accountant/css/ai_dashboard.css"
# app_include_js = "/assets/ai_accountant/js/ai_dashboard.js"

# include js, css files in header of web template
# web_include_css = "/assets/ai_accountant/css/ai_dashboard.css"
# web_include_js = "/assets/ai_accountant/js/ai_dashboard.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ai_accountant/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ai_accountant/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ai_accountant.utils.jinja_methods",
# 	"filters": "ai_accountant.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ai_accountant.install.before_install"
# after_install = "ai_accountant.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ai_accountant.uninstall.before_uninstall"
# after_uninstall = "ai_accountant.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ai_accountant.utils.before_app_install"
# after_app_install = "ai_accountant.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ai_accountant.utils.before_app_uninstall"
# after_app_uninstall = "ai_accountant.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ai_accountant.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"ai_accountant.tasks.all"
# 	],
# 	"daily": [
# 		"ai_accountant.tasks.daily"
# 	],
# 	"hourly": [
# 		"ai_accountant.tasks.hourly"
# 	],
# 	"weekly": [
# 		"ai_accountant.tasks.weekly"
# 	],
# 	"monthly": [
# 		"ai_accountant.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "ai_accountant.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ai_accountant.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ai_accountant.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ai_accountant.utils.before_request"]
# after_request = ["ai_accountant.utils.after_request"]

# Job Events
# ----------
# before_job = ["ai_accountant.utils.before_job"]
# after_job = ["ai_accountant.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ai_accountant.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }


scheduler_events = {
	"daily": [
	"ai_accountant.ai_accountant.batch.process_all_pending",
	"ai_accountant.ai_accountant.reconcile.reconcile_transactions",
	"ai_accountant.ai_accountant.reports.generate_management_pack"
	]
}


api_routes = [
	# {
	# "endpoint": "ai_accountant.ai_accountant.mercury.webhook_mercury",
	# "methods": ["POST"]
	# },
	{
	"endpoint": "ai_accountant.ai_accountant.chat.ai_chat",
	"methods": ["POST"]
	}
]

doctype_list = ["AI Accountant Settings"]

website_route_rules = [
    {"from_route": "/ai-dashboard", "to_route": "ai_dashboard"},
    { "from_route": "/app/home", "to_route": "ai_dashboard"}
]

fixtures = ["Page"]

