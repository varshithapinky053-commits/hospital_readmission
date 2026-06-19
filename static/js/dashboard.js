document.addEventListener('DOMContentLoaded', () => {
    if (window.dashboardData && window.ChartsHelper) {
        ChartsHelper.initDashboardCharts(window.dashboardData);
    }
});
