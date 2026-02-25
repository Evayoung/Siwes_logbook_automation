// Chat Manager - Handles chat functionality with SSE support

let eventSource = null;
let currentRecipientId = null;

// Initialize SSE connection for chat
function initChatSSE(recipientId) {
    // Close existing connection first
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    currentRecipientId = recipientId;
    
    // Create new SSE connection
    eventSource = new EventSource("/notifications/stream");
    
    eventSource.addEventListener('connected', function(e) {
        console.log('SSE Connected:', JSON.parse(e.data));
    });
    
    eventSource.addEventListener('new_message', function(e) {
        const data = JSON.parse(e.data);
        console.log('New message received:', data);
        
        // Append the message to the chat (it's already verified as being for this user)
        appendMessage(data.text, data.time, false);
    });
    
    eventSource.onerror = function(e) {
        console.log('SSE Error, attempting reconnect...');
        if (eventSource && eventSource.readyState === EventSource.CLOSED) {
            setTimeout(() => initChatSSE(currentRecipientId), 5000);
        }
    };
}

// Append a message bubble to the chat
function appendMessage(text, time, isMe) {
    // Try student messages list first, then supervisor
    let list = document.getElementById('chat-messages-list');
    if (!list) {
        list = document.getElementById('supervisor-messages-list');
    }
    if (!list) return;
    
    const align = isMe ? 'justify-content-end' : 'justify-content-start';
    const bg = isMe ? 'bg-primary text-white' : 'bg-light text-dark';
    const radius = isMe ? 'rounded-3 rounded-bottom-right-0' : 'rounded-3 rounded-bottom-left-0';
    const alignItems = isMe ? 'align-items-end' : 'align-items-start';
    
    const bubbleHtml = `
        <div class="d-flex ${align} mb-3">
            <div class="d-flex flex-column ${alignItems}">
                <div class="p-3 ${bg} ${radius}" style="max-width: 80%; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    ${text}
                </div>
                <div class="text-muted small mt-1 mx-1" style="font-size: 0.7rem;">${time}</div>
            </div>
        </div>
    `;
    
    list.insertAdjacentHTML('beforeend', bubbleHtml);
    list.scrollTop = list.scrollHeight;
}

// Send chat message
async function sendChatMessage(event) {
    event.preventDefault();
    
    const form = event.target;
    const recipientId = form.querySelector('input[name="recipient_id"]').value;
    const content = form.querySelector('input[name="content"]').value;
    
    if (!content.trim() || !recipientId) {
        return;
    }
    
    const formData = new FormData();
    formData.append('recipient_id', recipientId);
    formData.append('content', content);
    
    try {
        const response = await fetch('/api/chat/send', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Append own message immediately
            appendMessage(result.message.text, result.message.time, true);
            
            // Reset form
            form.reset();
        } else {
            console.error('Error sending message:', result.error);
            alert('Failed to send message: ' + result.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error sending message');
    }
    
    return false;
}

// Initialize SSE connection on page load
document.addEventListener('DOMContentLoaded', function() {
    // Get recipient ID from hidden input
    const recipientInput = document.querySelector('input[name="recipient_id"]');
    if (recipientInput && recipientInput.value) {
        initChatSSE(recipientInput.value);
    }
    
    // Setup form handlers for both student and supervisor chat forms
    const studentChatForm = document.getElementById('chat-form');
    if (studentChatForm) {
        studentChatForm.addEventListener('submit', sendChatMessage);
    }
    
    const supervisorChatForm = document.getElementById('supervisor-chat-form');
    if (supervisorChatForm) {
        supervisorChatForm.addEventListener('submit', sendChatMessage);
    }
});
