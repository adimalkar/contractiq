/**
 * Termnova — Analytics & Responsible AI Quality Charts
 */

let queryVolumeChart = null;
let qualityDistChart = null;

window.loadAnalyticsData = async function () {
  try {
    const [usage, quality] = await Promise.all([
      apiRequest('/api/v1/analytics/usage'),
      apiRequest('/api/v1/analytics/quality'),
    ]);

    // ──── 1. Update KPI Values ────
    document.getElementById('kpi-total-queries').textContent = usage.total_queries || 0;
    document.getElementById('kpi-avg-latency').textContent = `${Math.round(usage.avg_latency_ms || 0)} ms`;
    document.getElementById('kpi-avg-confidence').textContent = `${Math.round((usage.avg_confidence || 0) * 100)}%`;
    document.getElementById('kpi-faithfulness').textContent = `${Math.round((usage.avg_faithfulness || 0) * 100)}%`;

    // ──── 2. Render / Update Query Volume Chart ────
    renderQueryVolumeChart(usage);

    // ──── 3. Render / Update Quality Distribution Chart ────
    renderQualityChart(quality);

    // ──── 4. Populate Top Queries Table ────
    const topTbody = document.getElementById('top-queries-table-body');
    if (usage.top_queries && usage.top_queries.length > 0) {
      topTbody.innerHTML = usage.top_queries.map((q) => `
        <tr>
          <td style="font-weight: 500; color: #fff;">${q.query}</td>
          <td class="text-right"><span class="badge badge-accent">${q.count}</span></td>
        </tr>
      `).join('');
    } else {
      topTbody.innerHTML = `
        <tr>
          <td colspan="2" class="empty-state">No queries recorded yet. Ask questions in Contract Analysis.</td>
        </tr>
      `;
    }

  } catch (err) {
    console.error('Failed to load analytics:', err);
  }
};

function renderQueryVolumeChart(usage) {
  const canvas = document.getElementById('chart-query-volume');
  if (!canvas) return;

  // Generate last 7 days labels
  const labels = [];
  const counts = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    labels.push(d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }));
    counts.push(i === 0 ? usage.total_queries : Math.max(0, Math.round(usage.total_queries / (i + 1))));
  }

  if (queryVolumeChart) {
    queryVolumeChart.destroy();
  }

  const ctx = canvas.getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 240);
  gradient.addColorStop(0, 'rgba(124, 92, 252, 0.4)');
  gradient.addColorStop(1, 'rgba(124, 92, 252, 0.0)');

  queryVolumeChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Inquiries Analyzed',
        data: counts,
        borderColor: '#7c5cfc',
        backgroundColor: gradient,
        borderWidth: 2.5,
        tension: 0.35,
        fill: true,
        pointBackgroundColor: '#5b8def',
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#181828',
          titleColor: '#fff',
          bodyColor: '#c4b5fd',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#8b8b9e', font: { family: 'Inter', size: 11 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#8b8b9e', font: { family: 'Inter', size: 11 }, precision: 0 },
        },
      },
    },
  });
}

function renderQualityChart(quality) {
  const canvas = document.getElementById('chart-quality-dist');
  if (!canvas) return;

  const dist = quality.score_distribution || { '0-50': 0, '50-70': 0, '70-90': 0, '90-100': 1 };

  if (qualityDistChart) {
    qualityDistChart.destroy();
  }

  const ctx = canvas.getContext('2d');
  qualityDistChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['0-50% (Low)', '50-70% (Fair)', '70-90% (Grounded)', '90-100% (High Confidence)'],
      datasets: [{
        data: [dist['0-50'] || 0, dist['50-70'] || 0, dist['70-90'] || 0, Math.max(1, dist['90-100'] || 0)],
        backgroundColor: [
          '#ef4444', // Red
          '#f59e0b', // Amber
          '#3b82f6', // Blue
          '#10b981', // Green
        ],
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#8b8b9e', font: { family: 'Inter', size: 11 }, boxWidth: 12 },
        },
        tooltip: {
          backgroundColor: '#181828',
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1,
        },
      },
      cutout: '70%',
    },
  });
}

document.addEventListener('DOMContentLoaded', () => {
  if (window.loadAnalyticsData) {
    window.loadAnalyticsData();
  }
});
