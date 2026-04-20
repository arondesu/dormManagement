function loadAssignments() {
    const userSelect = document.getElementById('student_select');
    const assignmentSelect = document.getElementById('assignment_select');

    if (!userSelect || !assignmentSelect) {
        return;
    }

    const userId = userSelect.value;

    if (!userId) {
        assignmentSelect.innerHTML = '<option value="">Select student first</option>';
        return;
    }

    fetch(`/api/assignments/${userId}`)
        .then((response) => response.json())
        .then((data) => {
            assignmentSelect.innerHTML = '<option value="">No assignment (general payment)</option>';
            data.assignments.forEach((assignment) => {
                const option = document.createElement('option');
                option.value = assignment.assignment_id;
                option.textContent = `${assignment.building_name} - Room ${assignment.room_number} (₱${assignment.monthly_rate})`;
                assignmentSelect.appendChild(option);
            });
        })
        .catch(() => {
            assignmentSelect.innerHTML = '<option value="">Error loading assignments</option>';
        });
}

document.addEventListener('DOMContentLoaded', () => {
    const userSelect = document.getElementById('student_select');
    if (userSelect) {
        userSelect.addEventListener('change', loadAssignments);
        loadAssignments();
    }
});
