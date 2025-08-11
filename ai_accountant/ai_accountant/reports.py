import frappe
import json
from frappe.utils.pdf import get_pdf
from frappe.utils import today, add_days
from frappe.email.doctype.email_template.email_template import get_email_template
from ai_accountant.ai_accountant.llm_helper import get_openai_api_key, log_cost
from frappe.desk.query_report import run
from openai import OpenAI
from datetime import datetime

# Define the schema for report formatting
summary_schema = {
    "name": "format_financials",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Executive summary of the financial report"
            },
            "key_metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "value": {"type": "string"},
                        "change": {"type": "string"},
                        "insight": {"type": "string"}
                    },
                    "required": ["label", "value", "change", "insight"]
                }
            },
            "recommendations": {
                "type": "array",
                "items": {"type": "string"},
                "description": "recommendation how to improve the metrics"

            }
        },
        "required": ["summary", "key_metrics", "recommendations"]

        
    }
}



def get_openai_api_key():
    # Your way of fetching the OpenAI API key (from Site Config or Env)
    return frappe.conf.get("openai_api_key") or ""

def run_builtin_report(report_name, filters):
    result = run(report_name, filters)
    return result["result"]

def run_report(report_name):
    
    filters = {
        "company": frappe.defaults.get_user_default("Company"),
        "report_date": today(),
        "party": [],
        "ageing_based_on": "Due Date",
        "calculate_ageing_with": "Report Date",
        "range": "30, 60, 90, 120",
        "customer_group": [],
        "period_start_date":  add_days(today(), -300),
        "period_end_date":  today(),
        "periodicity": "Monthly"
    }
    try:
        result = run_builtin_report(report_name, filters)
        return result
    except Exception as e:
        print(str(e))
        return None


def summarize_report(report_data, report_name):
    """Use OpenAI to summarize the report data"""
    api_key = get_openai_api_key()
    if not api_key:
        frappe.throw("OpenAI API key not found in configuration")
    client = OpenAI(
        # base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    prompt = [
        {"role": "system", "content": f"You are an expert CPA. Generate a formal {report_name}. Return in clean html format"},
        {"role": "user", "content": json.dumps(report_data)}
    ]

    try:
        start_time = datetime.now() 

        response = client.chat.completions.create(
            model="gpt-4o",
            
            tools=[
                {
                    "type": "function",
                    "function": summary_schema  # your function schema goes here
                }
            ],
            tool_choice={"type": "function", "function": {"name": "format_financials"}},
            messages=prompt
        )

        end_time = datetime.now() 

        result = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        
        
        duration = end_time - start_time

        log_cost(
            tokens_in=response.usage.prompt_tokens,
            tokens_out=response.usage.completion_tokens,
            input=json.dumps(prompt),
            output=json.dumps(result),
            duration = duration,
            model="gpt-4o"
        )

        return result

    except Exception as e:
        print(f"OpenAI API Error: {str(e)}", "AI Accountant")
        return None

def generate_pdf_from_summary(summary, report_name):
    """Generate a PDF from the summary data"""
    html_content = f"""
        <head>
        <style>
            body {{
                background-color: white !important;
                color: black;
                font-family: Arial, sans-serif;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            th, td {{
                border: 1px solid #000;
                padding: 8px;
                text-align: left;
            }}
            h1, h2 {{
                color: #333;
            }}
        </style>
        </head>

    <body><h1>{report_name} - Executive Summary</h1>
    <p>{summary.get('summary', '')}</p>
    <h2>Key Metrics</h2>
    <table border="1" cellpadding="5" cellspacing="0">
        <tr>
            <th>Metric</th>
            <th>Value</th>
            <th>Change</th>
            <th>Insight</th>
        </tr>
    """
    for metric in summary.get('key_metrics', []):
        html_content += f"""
        <tr>
            <td>{metric.get('label', '')}</td>
            <td>{metric.get('value', '')}</td>
            <td>{metric.get('change', '')}</td>
            <td>{metric.get('insight', '')}</td>
        </tr>
        """
    html_content += "</table><h2>Recommendations</h2><ul>"

    for rec in summary.get('recommendations', []):
        html_content += f"<li>{rec}</li>"
    html_content += "</ul></body>"

    pdf_data = get_pdf(html_content)
    file_name = f"{report_name.replace(' ', '_')}_{today()}.pdf"

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "content": pdf_data,
        "is_private": 1
    })
    file_doc.insert()
    return file_doc

def email_report(file_doc, recipient_list, subject=None):
    """Email the report to specified recipients"""
    if not subject:
        subject = f"Financial Report - {today()}"

    template_name = "Financial Report"
    template_values = {
        "report_date": today(),
        "company": frappe.defaults.get_user_default("Company")
    }

    try:
        message = get_email_template(template_name, template_values)
    except:
        message = "Please find attached the latest financial report."

    frappe.sendmail(
        recipients=recipient_list,
        subject=subject,
        message=message,
        attachments=[{
            "fname": file_doc.file_name,
            "fcontent": file_doc.get_content()
        }]
    )
    return "Email sent successfully"

def generate_cashflow_report():
    """Generate and email Cash Flow report"""
    report_data = run_report("Cash Flow Statement")
    if not report_data:
        return "Failed to generate Cash Flow report"

    summary = summarize_report(report_data, "Cash Flow Statement")
    if not summary:
        return "Failed to summarize Cash Flow report"

    file_doc = generate_pdf_from_summary(summary, "Cash Flow Statement")

    owner_email = frappe.db.get_value("User", {"role": "System Manager"}, "email")
    if owner_email:
        email_report(file_doc, [owner_email], "Cash Flow Report")
    return "Cash Flow report generated and emailed"

def generate_balance_sheet():
    """Generate and email Balance Sheet report"""
    report_data = run_report("Balance Sheet")
    if not report_data:
        return "Failed to generate Balance Sheet report"

    summary = summarize_report(report_data, "Balance Sheet")
    if not summary:
        return "Failed to summarize Balance Sheet report"

    file_doc = generate_pdf_from_summary(summary, "Balance Sheet")

    owner_email = frappe.db.get_value("User", {"role": "System Manager"}, "email")
    if owner_email:
        email_report(file_doc, [owner_email], "Balance Sheet Report")
    return "Balance Sheet report generated and emailed"

def generate_pl_statement():
    """Generate and email Profit and Loss Statement"""
    report_data = run_report("Profit and Loss Statement")
    if not report_data:
        return "Failed to generate P&L report"

    summary = summarize_report(report_data, "Profit and Loss Statement")
    if not summary:
        return "Failed to summarize P&L report"

    file_doc = generate_pdf_from_summary(summary, "Profit and Loss Statement")

    owner_email = frappe.db.get_value("User", {"role": "System Manager"}, "email")
    if owner_email:
        email_report(file_doc, [owner_email], "P&L Report")
    return "P&L report generated and emailed"

def generate_management_pack():
    """Generate all reports and combine into a management pack"""
    cf_result = generate_cashflow_report()
    bs_result = generate_balance_sheet()
    pl_result = generate_pl_statement()
    return f"Management pack generation: {cf_result}, {bs_result}, {pl_result}"



@frappe.whitelist()
def get_latest_summary(report_name):
    report_data = run_report(report_name)
    if not report_data:
        return {"summary_html": "<p>Unable to generate report.</p>", "file_url": ""}

    summary = summarize_report(report_data, report_name)
    if not summary:
        return {"summary_html": "<p>Unable to summarize report.</p>", "file_url": ""}

    file_doc = generate_pdf_from_summary(summary, report_name)

    # Build HTML summary block
    metrics_html = "<table style='width:100%;border-collapse:collapse' border='1'><tr><th>Metric</th><th>Value</th><th>Change</th><th>Insight</th></tr>"
    for metric in summary.get("key_metrics", []):
        metrics_html += f"<tr><td>{metric.get('label')}</td><td>{metric.get('value')}</td><td>{metric.get('change')}</td><td>{metric.get('insight')}</td></tr>"
    metrics_html += "</table>"

    rec_html = "<ul>" + "".join(f"<li>{r}</li>" for r in summary.get("recommendations", [])) + "</ul>"

    summary_html = f"""
        <p>{summary.get('summary')}</p>
        <h4>Key Metrics</h4>
        {metrics_html}
        <h4>Recommendations</h4>
        {rec_html}
    """
    # return report_data

    return {
        "summary_html": summary_html,
        "file_url": file_doc.file_url
    }