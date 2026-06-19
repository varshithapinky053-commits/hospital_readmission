const ChartsHelper = (() => {
    const colors = {
        primary: '#2563eb',
        purple: '#7c3aed',
        red: '#dc2626',
        orange: '#d97706',
        green: '#16a34a',
        gray: '#94a3b8',
    };

    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
    };

    function initDashboardCharts(data) {
        const monthlyEl = document.getElementById('monthlyChart');
        if (monthlyEl && data.monthly) {
            const labels = data.monthly.map(m => m.month).reverse();
            const totals = data.monthly.map(m => m.total).reverse();
            const highRisk = data.monthly.map(m => m.high_risk).reverse();

            new Chart(monthlyEl, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [
                        {
                            label: 'Total Predictions',
                            data: totals,
                            backgroundColor: colors.primary + '99',
                            borderRadius: 6,
                        },
                        {
                            label: 'High Risk',
                            data: highRisk,
                            backgroundColor: colors.red + '99',
                            borderRadius: 6,
                        },
                    ],
                },
                options: {
                    ...defaultOptions,
                    plugins: {
                        legend: { display: true, position: 'top', labels: { boxWidth: 12, font: { size: 11 } } },
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
                        x: { grid: { display: false } },
                    },
                },
            });
        }

        const riskEl = document.getElementById('riskChart');
        if (riskEl && data.risk) {
            new Chart(riskEl, {
                type: 'doughnut',
                data: {
                    labels: ['High', 'Medium', 'Low'],
                    datasets: [{
                        data: [data.risk.high, data.risk.medium, data.risk.low],
                        backgroundColor: [colors.red, colors.orange, colors.green],
                        borderWidth: 0,
                    }],
                },
                options: {
                    ...defaultOptions,
                    plugins: {
                        legend: { display: true, position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
                    },
                    cutout: '65%',
                },
            });
        }
    }

    function initAnalyticsCharts(data) {
        const trendEl = document.getElementById('trendChart');
        if (trendEl && data.monthly) {
            const labels = data.monthly.map(m => m.month).reverse();
            new Chart(trendEl, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: 'Predictions',
                        data: data.monthly.map(m => m.total).reverse(),
                        borderColor: colors.primary,
                        backgroundColor: colors.primary + '22',
                        fill: true,
                        tension: 0.3,
                    }],
                },
                options: {
                    ...defaultOptions,
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#f1f5f9' } },
                        x: { grid: { display: false } },
                    },
                },
            });
        }

        const breakdownEl = document.getElementById('breakdownChart');
        if (breakdownEl && data.riskBreakdown) {
            const levelColors = { High: colors.red, Medium: colors.orange, Low: colors.green };
            new Chart(breakdownEl, {
                type: 'pie',
                data: {
                    labels: data.riskBreakdown.map(r => r.risk_level),
                    datasets: [{
                        data: data.riskBreakdown.map(r => r.count),
                        backgroundColor: data.riskBreakdown.map(r => levelColors[r.risk_level] || colors.gray),
                        borderWidth: 0,
                    }],
                },
                options: {
                    ...defaultOptions,
                    plugins: { legend: { display: true, position: 'bottom' } },
                },
            });
        }

        const avgEl = document.getElementById('avgRiskChart');
        if (avgEl && data.monthly) {
            const labels = data.monthly.map(m => m.month).reverse();
            new Chart(avgEl, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [{
                        label: 'Avg Risk %',
                        data: data.monthly.map(m => m.avg_risk).reverse(),
                        backgroundColor: colors.purple + '99',
                        borderRadius: 6,
                    }],
                },
                options: {
                    ...defaultOptions,
                    scales: {
                        y: { beginAtZero: true, max: 100, grid: { color: '#f1f5f9' } },
                        x: { grid: { display: false } },
                    },
                },
            });
        }
    }

    return { initDashboardCharts, initAnalyticsCharts };
})();

window.ChartsHelper = ChartsHelper;
