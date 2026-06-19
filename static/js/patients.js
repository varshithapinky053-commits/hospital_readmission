document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('patientModal');
    const addBtn = document.getElementById('addPatientBtn');
    const closeBtn = document.getElementById('closeModal');
    const cancelBtn = document.getElementById('cancelModal');
    const form = document.getElementById('patientForm');

    function openModal() {
        modal.hidden = false;
        fetch('/api/patients/next-id')
            .then(res => res.json())
            .then(data => {
                const input = document.getElementById('new_patient_id');
                if (input && data.patient_id) {
                    input.placeholder = `Leave blank to auto-generate (e.g. ${data.patient_id})`;
                }
            })
            .catch(() => {});
    }
    function closeModal() { modal.hidden = true; form.reset(); }

    if (addBtn) addBtn.addEventListener('click', openModal);
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    if (modal) modal.querySelector('.modal-backdrop')?.addEventListener('click', closeModal);

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = Object.fromEntries(new FormData(form));

            try {
                const res = await fetch('/api/patients', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data),
                });
                const result = await res.json();
                if (!res.ok) throw new Error(result.error || 'Failed to save patient');
                if (result.patient_id) {
                    alert(`Patient saved with ID: ${result.patient_id}`);
                }
                window.location.reload();
            } catch (err) {
                alert(err.message);
            }
        });
    }

    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.dataset.id;
            if (!confirm(`Delete patient ${id}?`)) return;

            try {
                const res = await fetch(`/api/patients/${id}`, { method: 'DELETE' });
                if (!res.ok) throw new Error('Delete failed');
                btn.closest('tr').remove();
            } catch (err) {
                alert(err.message);
            }
        });
    });
});
