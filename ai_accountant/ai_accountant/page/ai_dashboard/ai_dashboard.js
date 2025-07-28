frappe.pages['ai-dashboard'].on_page_load = function (wrapper) {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'AI Accountant Dashboard',
		single_column: true
	});

	// Manual tab buttons
	const tab_html = `
		<div class="btn-group mb-3" role="group">
			<button class="btn btn-secondary tab-btn" data-tab="status">Transaction Status</button>
			<button class="btn btn-secondary tab-btn" data-tab="ai-accountant">GL Entry Assistant</button>
			<button class="btn btn-secondary tab-btn" data-tab="chat">Chat</button>
			<button class="btn btn-secondary tab-btn" data-tab="cost">Cost Overview</button>
		</div>
		<div id="ai-tab-content"></div>
	`;
	$(page.body).html(tab_html);

	// Handle tab clicks
	page.body.on('click', '.tab-btn', function () {
		
		$('.tab-btn').removeClass('btn-primary').addClass('btn-secondary');
		$(this).removeClass('btn-secondary').addClass('btn-primary');

		const tab = $(this).data('tab');
		if (tab === 'cost') showCostOverview();
		if (tab === 'status') showTransactionStatus();
		if (tab === 'chat') showChatInterface();
		if (tab === 'ai-accountant') showAIAccountantChatInterface();
	});

	// Default tab
	$('.tab-btn[data-tab="status"]').click();

	page.set_primary_action('Refresh', () => {
		const tab = $('.tab-btn.btn-primary').data('tab');
		if (tab === 'cost') showCostOverview();
		else if (tab === 'status') showTransactionStatus();
	});

	page.add_action_item('Sync Transactions', () => {
		frappe.call({
			method: 'ai_accountant.ai_accountant.dashboard.fetch_transaction_data',
			callback: function (r) {
				frappe.hide_progress();
				if (r.message) {
					frappe.msgprint(r.message);
					$('.tab-btn.btn-primary').click();
				}
			}
		});
		
	});

	page.add_action_item('Classify Transactions', () => {
		
		frappe.call({
			method: 'ai_accountant.ai_accountant.batch.process_all_pending',
			callback: function (r) {
				frappe.hide_progress();
				if (r.message) {
					frappe.msgprint(r.message);
					$('.tab-btn.btn-primary').click();
				}
				
			}
		});
	});


	page.add_action_item('Retry Error Transactions', () => {
		
		frappe.call({
			method: 'ai_accountant.ai_accountant.batch.process_all_error',
			callback: function (r) {
				frappe.hide_progress();
				if (r.message) {frappe.msgprint(r.message);
				$('.tab-btn.btn-primary').click();}
			}
		});
	});



};

// === Cost Overview Tab ===
function showCostOverview() {
	$('#ai-tab-content').empty();

	let section = $(`
		<div class="cost-overview-section">
			<h4>OpenAI API Costs</h4>
			<div class="cost-charts row">
				<div class="col-md-6" id="daily-cost-chart"></div>
				<div class="col-md-6" id="monthly-cost-chart"></div>
			</div>
			<div class="cost-stats row">
				<div class="col-md-4" id="token-stats"></div>
				<div class="col-md-4" id="cost-stats"></div>
				<div class="col-md-4" id="model-stats"></div>
			</div>
		</div>
	`).appendTo('#ai-tab-content');

	frappe.call({
		method: 'ai_accountant.ai_accountant.dashboard.get_cost_data',
		callback: function (r) {
			if (r.message) renderCostCharts(r.message);
		}
	});
}

const App = {
	charts: {},
  
	renderChart(id, config) {
	  const el = document.querySelector(`#${id}`);
	  if (!el) return;
  
	  // destroy if already exists
	  if (this.charts[id] && typeof this.charts[id].destroy === "function") {
		this.charts[id].destroy();
		this.charts[id] = null;
		el.innerHTML = "";  // clear SVG and observers
	  }
  
	  this.charts[id] = new frappe.Chart("#" + id, config);
	},
  
	renderCharts(data) {
	  this.renderChart("daily-cost-chart", {
		title: "Daily API Costs",
		data: {
		  labels: data.daily.labels,
		  datasets: [{ name: "Daily Cost", values: data.daily.values }]
		},
		type: 'line',
		height: 250,
		colors: ['#8e44ad'],
		axisOptions: { xIsSeries: true }
	  });
  
	  this.renderChart("monthly-cost-chart", {
		title: "Monthly API Costs",
		data: {
		  labels: data.monthly.labels,
		  datasets: [{ name: "Monthly Cost", values: data.monthly.values }]
		},
		type: 'bar',
		height: 250,
		colors: ['#2980b9']
	  });
	},

	renderStatusChart(data) {
		const id = "status-chart";
		const el = document.querySelector("#" + id);
		if (!el || el.offsetParent === null) {
		  // Element missing or hidden, don't render now
		  console.warn(`#${id} container missing or hidden. Skipping render.`);
		  return;
		}
	
		const labels = Object.keys(data.status_counts);
		const values = Object.values(data.status_counts);
	
		// Destroy existing chart and clear container before recreating
		if (this.charts[id] && typeof this.charts[id].destroy === "function") {
		  this.charts[id].destroy();
		  this.charts[id] = null;
		  el.innerHTML = ""; // Clear old SVG content
		}
	
		// Delay creation to avoid DOM timing issues
		setTimeout(() => {
		  this.charts[id] = new frappe.Chart("#" + id, {
			title: "Transaction Status Distribution",
			data: {
			  labels,
			  datasets: [{ values }]
			},
			type: 'pie',
			height: 250,
			colors: ['#27ae60', '#e74c3c', '#f39c12', '#3498db', '#9b59b6']
		  });
		}, 50);
	  }


  };
  
function renderCostCharts(data) {
	
	App.renderCharts(data);


	$("#token-stats").html(`
		<div class="stat-card">
			<h5>Token Usage (30 days)</h5>
			<div class="stat-value">${data.stats.total_tokens}</div>
			<div class="stat-label">Input: ${data.stats.input_tokens} | Output: ${data.stats.output_tokens}</div>
		</div>
	`);

	$("#cost-stats").html(`
		<div class="stat-card">
			<h5>API Costs</h5>
			<div class="stat-value">$${data.stats.total_cost.toFixed(2)}</div>
			<div class="stat-label">This Month: $${data.stats.month_cost.toFixed(2)}</div>
		</div>
	`);

	$("#model-stats").html(`
		<div class="stat-card">
			<h5>Model Usage</h5>
			<div class="stat-label">GPT-3.5: ${data.stats.model_usage.gpt35 || 0}%</div>
			<div class="stat-label">GPT-4o-mini: ${data.stats.model_usage.gpt4o || 0}%</div>
		</div>
	`);
}

// === Transaction Status Tab ===
function showTransactionStatus() {
	$('#ai-tab-content').empty();

	let section = $(`
		<div class="transaction-status-section">
			<h4>Transaction Processing Status</h4>
			<div class="row">
				<div class="col-md-6" id="status-chart"></div>
				<div class="col-md-6" id="processing-stats"></div>
			</div>
			<div class="row mt-3">
				<div class="col-md-12">
					<h5>Recent Transactions</h5>
					<div id="recent-transactions"></div>
				</div>
			</div>
		</div>
	`).appendTo('#ai-tab-content');

	frappe.call({
		method: 'ai_accountant.ai_accountant.dashboard.get_transaction_stats',
		callback: function (r) {
			if (r.message) renderTransactionStats(r.message);
		}
	});
}


function renderTransactionStats(data) {
	App.renderStatusChart(data);

	$("#processing-stats").html(`
		<div class="stat-card">
			<h5>Processing Statistics</h5>
			<div class="stat-row"><div class="stat-label">Total Transactions:</div><div class="stat-value">${data.total_count}</div></div>
			<div class="stat-row"><div class="stat-label">Processed Today:</div><div class="stat-value">${data.today_count}</div></div>
			<div class="stat-row"><div class="stat-label">Avg Processing Time:</div><div class="stat-value">${data.avg_processing_time} seconds</div></div>
			<div class="stat-row"><div class="stat-label">Pending:</div><div class="stat-value">${data.status_counts.Pending || 0}</div></div>
			<div class="stat-row"><div class="stat-label">Currently processing:</div><div id="processing-progress" class="stat-value"></div></div>

		</div>
	`);

	let table = $(`
		<table class="table table-bordered">
			<thead><tr><th>Date</th><th>Description</th><th>Amount</th><th>Status</th></tr></thead>
			<tbody></tbody>
		</table>
	`);
	data.recent_transactions.forEach(tx => {
		table.find('tbody').append(`
			<tr>
				<td>${tx.date}</td>
				<td>${tx.description}</td>
				<td>${tx.amount}</td>
				<td><span class="status-indicator ${tx.status}">${tx.status}</span></td>
			</tr>
		`);
	});
	$("#recent-transactions").html(table);
}

// === Chat Tab ===
function showChatInterface() {
	$('#ai-tab-content').empty();

	let section = $(`
		<div class="chat-interface">
			<div class="chat-box" id="chat-messages"></div>
			<div class="chat-input mt-3 d-flex">
				<input type="text" id="chat-text" placeholder="Ask a financial question..." class="form-control me-2" />
				<button id="send-btn" class="btn btn-primary">Send</button>
			</div>
		</div>
	`).appendTo('#ai-tab-content');

	$("#chat-messages").append(`
		<div class="chat-message system">
			<div class="message-content">
				Welcome to the AI Financial Assistant! You can ask:
				<ul>
					<li>What's our current cash position?</li>
					<li>How are our accounts receivable trending?</li>
					<li>What were our top expenses last month?</li>
					<li>Can you forecast our cash flow for next month?</li>
				</ul>
			</div>
		</div>
	`);



	$("#send-btn").click(sendChatMessage);
	$("#chat-text").keypress(function (e) {
		if (e.which === 13) sendChatMessage();
	});
}


function sendChatMessage() {
	let message = $("#chat-text").val().trim();
	if (!message) return;

	$("#chat-messages").append(`
		<div class="chat-message user"><div class="message-content">${frappe.utils.escape_html(message)}</div></div>
	`);
	$("#chat-text").val('');

	let loadingId = 'loading-' + Date.now();
	$("#chat-messages").append(`
		<div class="chat-message system" id="${loadingId}">
			<div class="message-content">
				<div class="typing-indicator"><span></span><span></span><span></span></div>
			</div>
		</div>
	`);
	$("#chat-messages").scrollTop($("#chat-messages")[0].scrollHeight);

	frappe.call({
		method: 'ai_accountant.ai_accountant.chat.ai_chat',
		args: { question: message },
		callback: function (r) {
			console.log("chat response",  r.message);
			$(`#${loadingId}`).remove();
			if (r.message && r.message.success) {
				$("#chat-messages").append(`
					<div class="chat-message system">
						<div class="message-content">${frappe.utils.escape_html(r.message.answer)}</div>
					</div>
				`);
			} else {
				$("#chat-messages").append(`
					<div class="chat-message system error">
						<div class="message-content">Sorry, I encountered an error.</div>
					</div>
				`);
			}
			$("#chat-messages").scrollTop($("#chat-messages")[0].scrollHeight);
		}
	});
}



function showAIAccountantChatInterface() {
	$('#ai-tab-content').empty();

	let section = $(`
		<div class="chat-interface">
			<div class="chat-box" id="ai-accountant-chat-messages"></div>
			<div class="chat-input mt-3 d-flex">
				<textarea id="ai-accountant-chat-text" placeholder="Ask a financial question..." class="form-control me-2"> </textarea>
				<button id="ai-accountant-send-btn" class="btn btn-primary">Send</button>
			</div>
		</div>
	`).appendTo('#ai-tab-content');

	$("#ai-accountant-chat-messages").append(`
		<div class="chat-message system">
			<div class="message-content">
				Welcome to the AI Accountant Assistant!
				<ul>
					<li>Tell me what you want to add in General Ledger for you?</li>
				</ul>
			</div>
		</div>
	`);

	$("#ai-accountant-send-btn").click(sendAIAccountantChatMessage);
	$("#ai-accountant-chat-text").keypress(function (e) {
		// if (e.which === 13) sendAIAccountantChatMessage();
	});
}


function sendAIAccountantChatMessage() {
	let message = $("#ai-accountant-chat-text").val().trim();
	if (!message) return;


	const input_lines = message
	.split('\n')           // Split by newlines
	.map(line => line.trim()) // Remove extra spaces
	.filter(line => line); // Remove empty lines

	$("#ai-accountant-chat-messages").append(`
		<div class="chat-message user"><div class="message-content">${frappe.utils.escape_html(message)}</div></div>
	`);
	$("#ai-accountant-chat-text").val('');

	let loadingId = 'loading-' + Date.now();
	$("#ai-accountant-chat-messages").append(`
		<div class="chat-message system" id="${loadingId}">
			<div class="message-content">
				<div class="typing-indicator"><span></span><span></span><span></span></div>
			</div>
		</div>
	`);

	$("#ai-accountant-chat-messages").scrollTop($("#ai-accountant-chat-messages")[0].scrollHeight);

	frappe.call({
		method: 'ai_accountant.ai_accountant.journal_entry_assistant_llm.journal_entry_assistant',
		args: { query: input_lines },
		callback: function (r) {
			console.log("chat response",  r.message);
			$(`#${loadingId}`).remove();
			if (r.message) {
				$("#ai-accountant-chat-messages").append(`
					<div class="chat-message system">
						<div class="message-content">
						Added GL Entry: ${r.message.success} <br>
						Failed to add GL entry: ${r.message.failed} <br>
						${r.message.error_responses.map(value=>value)}</div>
					</div>
				`);
			} else {
				$("#ai-accountant-chat-messages").append(`
					<div class="chat-message system error">
						<div class="message-content">Sorry, I encountered an error.</div>
					</div>
				`);
			}
			$("#ai-accountant-hat-messages").scrollTop($("#ai-accountant-chat-messages")[0].scrollHeight);
		}
	});
}




frappe.realtime.on("transaction_processing_update", function(data) {
	frappe.show_progress("Processing Transactions", parseFloat(data.percent), 100, "Processing .....");

    console.log("Transaction processed", data);
    // Update DOM, refresh data, or show a notification
    $("#processing-progress").html(data.completed);
});


frappe.realtime.on("transaction_sync_update", function(data) {
	frappe.show_progress("Syncing Transactions", parseFloat(data.percent), 100, "Please wait");

    console.log("Transaction updated", data);
});