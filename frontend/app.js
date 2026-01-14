/**
 * LinkedIn Sales Robot - Frontend Application
 */

class LinkedInSalesRobot {
    constructor() {
        this.ws = null;
        this.isRunning = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }
    
    init() {
        this.bindElements();
        this.bindEvents();
        this.connectWebSocket();
        this.updateCharCount();
    }
    
    bindElements() {
        // Form elements
        this.jobTitlesInput = document.getElementById('jobTitles');
        this.postedWithinSelect = document.getElementById('postedWithin');
        this.maxConnectionsInput = document.getElementById('maxConnections');
        this.delaySecondsInput = document.getElementById('delaySeconds');
        this.messageTemplateInput = document.getElementById('messageTemplate');
        this.crmStageIdInput = document.getElementById('crmStageId');
        this.crmApiKeyInput = document.getElementById('crmApiKey');
        
        // Buttons
        this.startBtn = document.getElementById('startBtn');
        this.stopBtn = document.getElementById('stopBtn');
        this.clearLogBtn = document.getElementById('clearLogBtn');
        
        // Status elements
        this.statusBadge = document.getElementById('statusBadge');
        this.connectionsSent = document.getElementById('connectionsSent');
        this.connectionsFailed = document.getElementById('connectionsFailed');
        this.leadsCreated = document.getElementById('leadsCreated');
        this.currentAction = document.getElementById('currentAction');
        this.activityIndicator = document.getElementById('activityIndicator');
        this.currentExecutive = document.getElementById('currentExecutive');
        this.logContainer = document.getElementById('logContainer');
        this.charCount = document.getElementById('charCount');
        
        // Placeholder pills
        this.placeholderPills = document.querySelectorAll('.pill[data-placeholder]');
    }
    
    bindEvents() {
        this.startBtn.addEventListener('click', () => this.startBot());
        this.stopBtn.addEventListener('click', () => this.stopBot());
        this.clearLogBtn.addEventListener('click', () => this.clearLog());
        
        this.messageTemplateInput.addEventListener('input', () => this.updateCharCount());
        
        // Placeholder pill clicks
        this.placeholderPills.forEach(pill => {
            pill.addEventListener('click', () => {
                const placeholder = pill.dataset.placeholder;
                this.insertPlaceholder(placeholder);
            });
        });
    }
    
    connectWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.addLogEntry('Connected to server', 'success');
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.scheduleReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };
        
        // Send ping every 30 seconds to keep connection alive
        setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connectWebSocket(), delay);
        } else {
            this.addLogEntry('Connection lost. Please refresh the page.', 'error');
        }
    }
    
    handleMessage(message) {
        if (message.type === 'status') {
            this.updateStatus(message.data);
        }
    }
    
    updateStatus(status) {
        // Update running state
        this.isRunning = status.is_running;
        this.updateButtons();
        
        // Update status badge
        this.statusBadge.classList.toggle('running', status.is_running);
        this.statusBadge.querySelector('.status-text').textContent = 
            status.is_running ? 'Running' : 'Idle';
        
        // Update stats
        this.connectionsSent.textContent = status.connections_sent;
        this.connectionsFailed.textContent = status.connections_failed;
        this.leadsCreated.textContent = status.leads_created;
        
        // Update current action
        this.currentAction.textContent = status.current_action;
        this.activityIndicator.classList.toggle('active', status.is_running);
        
        // Update current executive
        if (status.current_executive) {
            this.currentExecutive.classList.add('visible');
            this.currentExecutive.innerHTML = `
                <div class="exec-name">${status.current_executive.name}</div>
                <div class="exec-title">${status.current_executive.title}</div>
                <div class="exec-company">${status.current_executive.company}</div>
            `;
        } else {
            this.currentExecutive.classList.remove('visible');
        }
        
        // Update log
        if (status.log_messages && status.log_messages.length > 0) {
            this.updateLog(status.log_messages);
        }
    }
    
    updateLog(messages) {
        // Get last message and add if new
        const lastMessage = messages[messages.length - 1];
        const existingEntries = this.logContainer.querySelectorAll('.log-entry');
        
        // Check if this message already exists
        const lastEntry = existingEntries[existingEntries.length - 1];
        if (lastEntry && lastEntry.dataset.message === lastMessage) {
            return;
        }
        
        // Parse timestamp and message
        const match = lastMessage.match(/\[(\d{2}:\d{2}:\d{2})\] (.+)/);
        if (match) {
            const [, time, text] = match;
            let type = 'info';
            if (text.includes('✅')) type = 'success';
            else if (text.includes('❌')) type = 'error';
            else if (text.includes('⚠️')) type = 'warning';
            
            const entry = document.createElement('div');
            entry.className = `log-entry ${type}`;
            entry.dataset.message = lastMessage;
            entry.innerHTML = `
                <span class="log-time">${time}</span>
                <span class="log-message">${text}</span>
            `;
            
            this.logContainer.appendChild(entry);
            this.logContainer.scrollTop = this.logContainer.scrollHeight;
        }
    }
    
    addLogEntry(message, type = 'info') {
        const time = new Date().toLocaleTimeString('en-US', { hour12: false });
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.innerHTML = `
            <span class="log-time">${time}</span>
            <span class="log-message">${message}</span>
        `;
        this.logContainer.appendChild(entry);
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
    }
    
    clearLog() {
        this.logContainer.innerHTML = '';
        this.addLogEntry('Log cleared', 'info');
    }
    
    updateButtons() {
        this.startBtn.disabled = this.isRunning;
        this.stopBtn.disabled = !this.isRunning;
    }
    
    updateCharCount() {
        const length = this.messageTemplateInput.value.length;
        this.charCount.textContent = length;
        
        const countContainer = this.charCount.parentElement;
        countContainer.classList.remove('warning', 'error');
        
        if (length > 300) {
            countContainer.classList.add('error');
        } else if (length > 250) {
            countContainer.classList.add('warning');
        }
    }
    
    insertPlaceholder(placeholder) {
        const textarea = this.messageTemplateInput;
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const text = textarea.value;
        
        textarea.value = text.substring(0, start) + placeholder + text.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + placeholder.length;
        textarea.focus();
        
        this.updateCharCount();
    }
    
    validateForm() {
        const jobTitles = this.jobTitlesInput.value.trim();
        const messageTemplate = this.messageTemplateInput.value.trim();
        const crmStageId = this.crmStageIdInput.value.trim();
        
        if (!jobTitles) {
            this.addLogEntry('Please enter at least one job title to search for', 'error');
            return false;
        }
        
        if (!messageTemplate) {
            this.addLogEntry('Please enter a message template', 'error');
            return false;
        }
        
        if (messageTemplate.length > 300) {
            this.addLogEntry('Message template exceeds 300 character limit', 'error');
            return false;
        }
        
        if (!crmStageId) {
            this.addLogEntry('Please enter a CRM Pipeline Stage ID', 'error');
            return false;
        }
        
        return true;
    }
    
    async startBot() {
        if (!this.validateForm()) {
            return;
        }
        
        const jobTitles = this.jobTitlesInput.value
            .split('\n')
            .map(t => t.trim())
            .filter(t => t.length > 0);
        
        const payload = {
            job_titles: jobTitles,
            posted_within_days: parseInt(this.postedWithinSelect.value),
            message_template: this.messageTemplateInput.value,
            crm_stage_id: this.crmStageIdInput.value.trim(),
            crm_api_key: this.crmApiKeyInput.value.trim() || null,
            delay_between_connections: parseInt(this.delaySecondsInput.value),
            max_connections_per_session: parseInt(this.maxConnectionsInput.value)
        };
        
        try {
            this.addLogEntry('Starting bot...', 'info');
            this.startBtn.disabled = true;
            
            const response = await fetch('/api/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start bot');
            }
            
            const result = await response.json();
            this.addLogEntry(result.message, 'success');
            
        } catch (error) {
            this.addLogEntry(`Error: ${error.message}`, 'error');
            this.startBtn.disabled = false;
        }
    }
    
    async stopBot() {
        try {
            this.addLogEntry('Stopping bot...', 'warning');
            
            const response = await fetch('/api/stop', {
                method: 'POST'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to stop bot');
            }
            
            const result = await response.json();
            this.addLogEntry(result.message, 'warning');
            
        } catch (error) {
            this.addLogEntry(`Error: ${error.message}`, 'error');
        }
    }
}

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    window.app = new LinkedInSalesRobot();
});

