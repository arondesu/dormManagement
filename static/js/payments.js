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

function loadInvoices() {
    const userSelect = document.getElementById('student_select');
    const invoiceSelect = document.getElementById('invoice_select');

    if (!userSelect || !invoiceSelect) {
        return;
    }

    const userId = userSelect.value;

    if (!userId) {
        invoiceSelect.innerHTML = '<option value="">Auto-allocate by due date</option>';
        return;
    }

    fetch(`/api/invoices/user/${userId}`)
        .then((response) => response.json())
        .then((data) => {
            invoiceSelect.innerHTML = '<option value="">Auto-allocate by due date</option>';

            if (!data.invoices || !data.invoices.length) {
                return;
            }

            data.invoices.forEach((invoice) => {
                const option = document.createElement('option');
                option.value = invoice.invoice_id;
                option.textContent = `${invoice.invoice_number} | Due ${invoice.due_date} | Balance ₱${invoice.balance_due}`;
                invoiceSelect.appendChild(option);
            });
        })
        .catch(() => {
            invoiceSelect.innerHTML = '<option value="">Error loading invoices</option>';
        });
}

document.addEventListener('DOMContentLoaded', () => {
    const userSelect = document.getElementById('student_select');
    if (userSelect) {
        const loadRelatedData = () => {
            loadAssignments();
            loadInvoices();
        };

        userSelect.addEventListener('change', loadRelatedData);
        loadRelatedData();
    }
});
