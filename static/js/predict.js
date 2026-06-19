document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('predictForm');
    if (!form) return;

    form.addEventListener('submit', () => {
        const btn = form.querySelector('[type="submit"]');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Analyzing...';
        }
    });

    const params = new URLSearchParams(window.location.search);
    const patientId = params.get('patient');
    if (patientId) {
        const select = document.getElementById('patient_id');
        if (select) select.value = patientId;
    }
});
