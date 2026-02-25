// Video call handler
function handleVideoCallClick(event, callType = 'video') {
    event.preventDefault();

    // Get ID from data attribute or context
    const supervisorId = event.target.closest('[data-supervisor-id]')?.dataset.supervisorId;
    const studentId = event.target.closest('[data-student-id]')?.dataset.studentId;

    console.log('[CALL JS] Button clicked');
    console.log('[CALL JS] Supervisor ID:', supervisorId);
    console.log('[CALL JS] Student ID:', studentId);
    console.log('[CALL JS] Call type:', callType);

    // Prepare request body
    const body = { call_type: callType };
    if (supervisorId) body.supervisor_id = supervisorId;
    if (studentId) body.student_id = studentId;

    console.log('[CALL JS] Request body:', JSON.stringify(body));

    // Create call room
    fetch('/api/calls/create', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(body)
    })
        .then(async response => {
            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return response.json();
            } else {
                // Return text if not JSON
                const text = await response.text();
                console.error('[CALL ERROR] Non-JSON response:', text);
                return { error: text, success: false };
            }
        })
        .then(data => {
            console.log('[CALL RESPONSE]', data);
            if (data.success) {
                // Redirect to call page using server-provided URL
                window.location.href = data.redirect_url;
            } else {
                alert('Failed to create call: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error creating call:', error);
            alert('Failed to create call. Please try again.');
        });
}
