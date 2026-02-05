/**
 * Dompet Curhat - Dashboard Script V2
 */

const API_BASE = '';
const USER_ID = window.CURRENT_USER_ID || null;
let SAVINGS_DATA = [];

// ==================== THEME MANAGER ====================
// ==================== THEME MANAGER ====================
// Theme logic moved to theme.js


// ==================== UTILS ====================
const EMOTION_META = {
    'Senang': { icon: 'bi-emoji-smile-fill', color: '#10b981' },
    'Sedih': { icon: 'bi-emoji-frown-fill', color: '#6366f1' },
    'Marah': { icon: 'bi-emoji-angry-fill', color: '#ef4444' },
    'Stress': { icon: 'bi-emoji-dizzy-fill', color: '#f59e0b' },
    'Lapar': { icon: 'bi-fire', color: '#f97316' },
    'Netral': { icon: 'bi-emoji-neutral-fill', color: '#64748b' }
};

const CATEGORY_ICONS = {
    'Makanan & Minuman': 'bi-cup-hot-fill',
    'Transport': 'bi-bus-front-fill',
    'Fashion': 'bi-handbag-fill',
    'Hiburan': 'bi-controller',
    'Belanja': 'bi-cart-fill',
    'Tagihan': 'bi-receipt',
    'Lainnya': 'bi-grid-fill'
};

function formatCurrency(amount) {
    return new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount || 0);
}

// ==================== DATA FETCHING ====================
async function loadDashboard() {
    // 1. Fetch Expenses for Weekly Chart & Emotion
    // 2. Fetch Aggregates for Donut & Forecast
    // 3. Fetch Savings Goals

    try {
        const [expensesRes, statsRes, savingsRes] = await Promise.allSettled([
            fetch(`/api/expenses?user_id=${USER_ID}&limit=1000`),
            fetch(`/api/dashboard/stats`),
            fetch(`/api/dashboard/savings`)
        ]);

        // Weekly & Emotion Data (Client-side calc for now)
        if (expensesRes.status === 'fulfilled') {
            const data = await expensesRes.value.json();
            const expenses = data.expenses || [];
            processWeeklyAndEmotion(expenses);
        }

        // Stats (Top Categories & Forecast)
        if (statsRes.status === 'fulfilled') {
            const data = await statsRes.value.json();
            if (data.success) {
                renderTopCategories(data.data.top_categories);
                renderForecast(data.data.forecast);
            }
        }

        // Savings
        if (savingsRes.status === 'fulfilled') {
            const data = await savingsRes.value.json();
            if (data.success) {
                renderSavings(data.data);
            }
        }

    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

function processWeeklyAndEmotion(expenses) {
    // Basic logic to get last 7 days from NOW
    // This simplifies the legacy logic which was handling months/filters.
    // Dashboard V2 focuses on "This Week".

    const now = new Date();
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(now.getDate() - 7);

    // Filter expenses for last 7 days
    const weeklyExpenses = expenses.filter(e => {
        const d = new Date(e.date);
        return d >= oneWeekAgo && d <= now;
    });

    // Calculate Daily Totals
    const dailyTotals = new Array(7).fill(0);
    const dayLabels = [];
    // Initialize labels
    for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(now.getDate() - i);
        dayLabels.push(d.toLocaleDateString('id-ID', { weekday: 'short' }));
    }

    let totalWeek = 0;
    weeklyExpenses.forEach(e => {
        const d = new Date(e.date);
        // Find rough index 0-6
        // Simple diff in days
        const diffTime = Math.abs(now - d);
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
        if (diffDays < 7) {
            const idx = 6 - diffDays;
            if (idx >= 0 && idx < 7) dailyTotals[idx] += e.amount;
        }
        totalWeek += e.amount;
    });

    // Render Weekly Text
    document.getElementById('weeklyTotal').textContent = formatCurrency(totalWeek);
    document.getElementById('weeklyChange').textContent = '7 hari terakhir';

    // Render Mini Bar Chart
    const weeklyBars = document.getElementById('weeklyBars');
    if (weeklyBars) {
        const max = Math.max(...dailyTotals, 1);
        weeklyBars.innerHTML = dailyTotals.map((total, i) => {
            const height = Math.max(10, (total / max) * 60); // Max 60px height
            return `<div class="weekly-bar">
                        <div class="bar-fill" style="height:${height}px" title="${dayLabels[i]}: ${formatCurrency(total)}"></div>
                    </div>`;
        }).join('');
    }

    // Emotion Logic (Simple Dominant)
    if (expenses.length > 0) {
        const counts = {};
        weeklyExpenses.forEach(e => {
            const emo = e.emotion_label || 'Netral';
            counts[emo] = (counts[emo] || 0) + 1;
        });

        let dominant = 'Netral';
        let maxCount = 0;
        Object.entries(counts).forEach(([emo, cnt]) => {
            if (cnt > maxCount) {
                maxCount = cnt;
                dominant = emo;
            }
        });

        const meta = EMOTION_META[dominant] || EMOTION_META['Netral'];
        document.getElementById('emotionName').textContent = dominant;
        document.getElementById('emotionCount').textContent = maxCount + 'x';
        document.getElementById('emotionBadge').style.color = meta.color;
        document.getElementById('emotionBadge').style.borderColor = meta.color;
        document.getElementById('emotionIcon').innerHTML = `<i class="${meta.icon}"></i>`;

        // Correlation Logic
        calculateEmotionCorrelation(expenses);
    }
}

function calculateEmotionCorrelation(allExpenses) {
    if (!allExpenses || allExpenses.length < 5) return; // Need some data

    const emotionStats = {};
    let globalTotal = 0;
    let globalCount = 0;

    allExpenses.forEach(e => {
        const emo = e.emotion_label || 'Netral';
        const amt = e.amount || 0;

        if (!emotionStats[emo]) emotionStats[emo] = { total: 0, count: 0 };
        emotionStats[emo].total += amt;
        emotionStats[emo].count += 1;

        globalTotal += amt;
        globalCount += 1;
    });

    const globalAvg = globalCount > 0 ? globalTotal / globalCount : 0;

    // Find biggest outlier (highest avg spending)
    let maxDiffPercent = 0;
    let worstEmotion = null;

    Object.entries(emotionStats).forEach(([emo, stats]) => {
        if (stats.count < 2) return; // Ignore if only 1 occurrence
        const avg = stats.total / stats.count;
        const diffPercent = ((avg - globalAvg) / globalAvg) * 100;

        if (diffPercent > 20 && diffPercent > maxDiffPercent) {
            maxDiffPercent = diffPercent;
            worstEmotion = emo;
        }
    });

    const correlationEl = document.getElementById('emotionCorrelation');
    if (worstEmotion) {
        let msg = '';
        if (worstEmotion === 'Senang' || worstEmotion === 'Bahagia') {
            msg = `Kamu hobi <b>self-reward</b> saat lagi <b>${worstEmotion}</b> (+${Math.round(maxDiffPercent)}% boros).`;
        } else if (worstEmotion === 'Sedih' || worstEmotion === 'Stress' || worstEmotion === 'Marah') {
            msg = `Tiati, kamu <b>emotional buying</b> pas lagi <b>${worstEmotion}</b> (+${Math.round(maxDiffPercent)}% boros).`;
        } else if (worstEmotion === 'Lapar') {
            msg = `Pengeluaranmu membengkak saat <b>Lapar</b> (+${Math.round(maxDiffPercent)}% boros).`;
        } else {
            msg = `Kamu cenderung lebih boros saat <b>${worstEmotion}</b> (+${Math.round(maxDiffPercent)}%).`;
        }

        correlationEl.innerHTML = `
            <div style="display:flex; align-items:start; gap:10px;">
                <i class="bi bi-lightbulb-fill" style="color:var(--secondary); font-size:1.2rem; margin-top:2px;"></i>
                <div style="line-height:1.4;">${msg}</div>
            </div>
        `;
        correlationEl.style.background = 'rgba(245, 158, 11, 0.1)'; // Amber tint
        correlationEl.style.borderLeftColor = 'var(--secondary)';
    } else {
        // Safe spending / No correlation found yet
        // Keep default or show "Safe" message
        // For now, let's just keep the "Analisis akan muncul..." default if no strong correlation
    }
}

// ==================== RENDERERS ====================

let categoryChart = null;

function renderTopCategories(categories) {
    const ctx = document.getElementById('categoryDonut');
    if (!ctx) return;

    if (categoryChart) categoryChart.destroy();

    if (!categories || categories.length === 0) {
        // Handle empty
        return;
    }

    const labels = categories.map(c => c.name);
    const data = categories.map(c => c.total);
    const colors = ['#8b5cf6', '#ec4899', '#f59e0b', '#10b981', '#3b82f6'];

    categoryChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            cutout: '70%'
        }
    });

    // Custom Legend
    const legendEl = document.getElementById('categoryLegend');
    legendEl.innerHTML = categories.map((c, i) => {
        const iconClass = CATEGORY_ICONS[c.name] || 'bi-circle-fill';
        const iconStyle = CATEGORY_ICONS[c.name] ? `color: ${colors[i]}` : `width:8px; height:8px; border-radius:50%; background:${colors[i]}`;
        const iconHtml = CATEGORY_ICONS[c.name]
            ? `<i class="${iconClass}" style="${iconStyle}"></i>`
            : `<span style="${iconStyle}"></span>`;

        return `
        <div style="display:flex; align-items:center; gap:8px;">
            ${iconHtml}
            <span style="flex:1;">${c.name}</span>
            <span style="font-weight:600;">${Math.round(c.total / 1000)}k</span>
        </div>`;
    }).join('');
}

function renderForecast(forecast) {
    if (!forecast) return;
    document.getElementById('forecastText').textContent = forecast.message;
}

function renderSavings(goals) {
    SAVINGS_DATA = goals || [];
    const list = document.getElementById('savingsList');
    if (!goals || goals.length === 0) {
        list.innerHTML = `
        <div class="empty-placeholder">
            <i class="bi bi-piggy-bank"></i>
            <p>Belum ada target pengeluaran.</p>
            <small>Atur budget biar nggak boncos!</small>
        </div>`;
        return;
    }

    list.innerHTML = goals.map(g => {
        const percent = Math.min(100, Math.round((g.current_amount / g.target_amount) * 100));
        const isOverBudget = g.current_amount > g.target_amount;
        const overClass = isOverBudget ? 'over-budget' : '';
        const warningIcon = isOverBudget ? '<i class="bi bi-exclamation-triangle-fill warning-icon"></i>' : '';
        const periodLabel = g.period_type === 'this_week' ? 'Minggu ini' :
            g.period_type === 'custom' ? 'Custom' : 'Bulan ini';

        return `
        <div class="savings-item ${overClass}" onclick="editSavings(${g.id})">
            <div class="savings-info">
                <div class="savings-name">${warningIcon}${g.name}</div>
                <div class="savings-progress-text">${formatCurrency(g.current_amount)} / ${formatCurrency(g.target_amount)}</div>
                <div class="savings-period-label">${periodLabel}</div>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill ${overClass}" style="width: ${percent}%;"></div>
            </div>
        </div>
        `;
    }).join('');
}

// ==================== MANUAL INPUT ====================
// ==================== EXPENSE SELECTION MODAL ====================
function showExpenseSelectionModal() {
    const modal = document.getElementById('expenseSelectionModal');
    if (modal) {
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
}

function closeExpenseSelectionModal() {
    const modal = document.getElementById('expenseSelectionModal');
    if (modal) {
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

function selectManual() {
    closeExpenseSelectionModal();
    setTimeout(() => showManualInputModal(), 300);
}

function selectChatAI() {
    window.location.href = '/chat';
}

// ==================== MANUAL INPUT MODAL ====================
function showManualInputModal() {
    const modal = document.getElementById('manualInputModal');
    if (modal) modal.showModal();
}

function closeManualInputModal() {
    const modal = document.getElementById('manualInputModal');
    if (modal) modal.close();
}

async function submitManualExpense(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    // Ambil data dari form
    const data = {
        item_name: formData.get('item_name'),
        amount: parseInt(formData.get('amount')),
        category: formData.get('category'),
        emotion_label: formData.get('emotion_label'),
        // Pastikan 'date' terambil dari input Flatpickr kamu
        date: formData.get('date') || undefined
    };

    if (!data.date) delete data.date;

    try {
        const res = await fetch('/api/expenses/manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        // 1. CEK STATUS UNAUTHORIZED (401) DULU
        if (res.status === 401) {
            console.warn("Sesi berakhir atau tidak terautentikasi.");
            window.location.href = '/login';
            alert('login untuk melanjutkan')
            return; // Berhenti di sini, jangan lanjut baca JSON
        }

        // 2. BACA JSON HANYA JIKA STATUS BUKAN 401
        const result = await res.json();

        if (res.ok && result.success) {
            closeManualInputModal();
            form.reset();
            if (typeof loadDashboard === 'function') loadDashboard();
            alert('Saved!');
        } else {
            // Tampilkan detail error dari backend (misal: saldo tidak cukup atau input salah)
            alert('Error: ' + (result.detail || 'Terjadi kesalahan sistem'));
        }

    } catch (e) {
        console.error("Fetch Error:", e);
        alert('Gagal terhubung ke server. Pastikan koneksi internet aktif.');
    }
}
// ==================== SAVINGS LOGIC ====================
function addSavingsGoal() {
    const modal = document.getElementById('savingsModal');
    const form = document.getElementById('savingsForm');

    document.getElementById('savingsModalTitle').textContent = 'Tambah Target';
    document.getElementById('savingsGoalId').value = '';
    document.getElementById('savingsCurrentGroup').style.display = 'none';
    document.getElementById('btnDeleteSavings').style.display = 'none';

    // Enable Target input
    document.getElementById('savingsName').readOnly = false;
    document.getElementById('savingsTarget').readOnly = false;

    form.reset();
    if (modal) modal.showModal();
}

function editSavings(id) {
    const goal = SAVINGS_DATA.find(g => g.id === id);
    if (!goal) return;

    const modal = document.getElementById('savingsModal');

    document.getElementById('savingsModalTitle').textContent = 'Edit Budget Settings';
    document.getElementById('savingsGoalId').value = goal.id;
    document.getElementById('savingsName').value = goal.name;
    document.getElementById('savingsTarget').value = goal.target_amount;
    document.getElementById('savingsCurrent').value = goal.current_amount;

    // Enable editing for name and target
    document.getElementById('savingsName').readOnly = false;
    document.getElementById('savingsTarget').readOnly = false;

    // Populate period fields
    const periodType = goal.period_type || 'this_month';
    document.getElementById('periodType').value = periodType;
    document.getElementById('periodStart').value = goal.period_start || '';
    document.getElementById('periodEnd').value = goal.period_end || '';

    // Update date display if custom range exists
    if (periodType === 'custom' && goal.period_start && goal.period_end) {
        const startDate = new Date(goal.period_start).toLocaleDateString('id-ID');
        const endDate = new Date(goal.period_end).toLocaleDateString('id-ID');
        document.getElementById('dateRangeDisplay').textContent = `${startDate} - ${endDate}`;
    }

    toggleCustomDates(); // Show/hide custom dates based on selection

    document.getElementById('savingsCurrentGroup').style.display = 'block';
    document.getElementById('btnDeleteSavings').style.display = 'block';
    if (modal) modal.showModal();
}

function closeSavingsModal() {
    const modal = document.getElementById('savingsModal');
    if (modal) modal.close();
}

async function submitSavingsGoal(event) {
    event.preventDefault(); // CRITICAL: Prevent form default submit
    console.log('📝 Submit savings goal called');

    const formData = new FormData(event.target);
    const id = formData.get('goal_id');

    // DEBUG: Log all form values
    console.log('📋 Form values from FormData:');
    console.log('  - goal_id:', id);
    console.log('  - name:', formData.get('name'));
    console.log('  - target_amount:', formData.get('target_amount'));
    console.log('  - period_type:', formData.get('period_type'));

    // DEBUG: Also read directly from inputs to compare
    const nameInput = document.getElementById('savingsName');
    const targetInput = document.getElementById('savingsTarget');
    const periodInput = document.getElementById('periodType');

    console.log('📋 Direct input values:');
    console.log('  - name (direct):', nameInput?.value);
    console.log('  - target (direct):', targetInput?.value);
    console.log('  - period (direct):', periodInput?.value);
    console.log('  - name readonly?', nameInput?.readOnly);
    console.log('  - target readonly?', targetInput?.readOnly);

    try {
        let url = '/api/dashboard/savings';
        let method = 'POST';
        let body = {};

        if (id) {
            // Edit Mode - send ALL editable fields
            // Use direct input values to ensure we get latest data
            url = `/api/dashboard/savings/${id}`;
            method = 'PUT';
            body = {
                name: nameInput.value,
                target_amount: parseInt(targetInput.value),
                period_type: periodInput.value
            };

            // Include custom dates only if period is custom AND dates are provided
            if (body.period_type === 'custom') {
                const startDate = formData.get('period_start');
                const endDate = formData.get('period_end');

                // Only add dates if they're not empty
                if (startDate && startDate.trim() !== '') {
                    body.period_start = startDate;
                }
                if (endDate && endDate.trim() !== '') {
                    body.period_end = endDate;
                }
            }
        } else {
            // Create Mode
            body = {
                name: formData.get('name'),
                target_amount: parseInt(formData.get('target_amount'))
            };
        }

        console.log('🚀 Sending:', method, url, body);

        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        console.log('📥 Response status:', res.status);
        const result = await res.json();
        console.log('📥 Response data:', result);

        if (result.success) {
            closeSavingsModal();
            loadDashboard();
        } else {
            alert('Gagal menyimpan.');
        }
    } catch (e) {
        console.error('❌ Error:', e);
        alert('Error: ' + e.message);
    }
}

async function deleteSavings() {
    const id = document.getElementById('savingsGoalId').value;
    if (!id || !confirm('Yakin hapus target ini?')) return;

    try {
        const res = await fetch(`/api/dashboard/savings/${id}`, { method: 'DELETE' });
        const result = await res.json();
        if (result.success) {
            closeSavingsModal();
            loadDashboard();
        } else {
            alert('Gagal menghapus.');
        }
    } catch (e) {
        alert('Error deleting.');
    }
}

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});

// Expose functions globally for HTML access
window.showManualInputModal = showManualInputModal;
window.closeManualInputModal = closeManualInputModal;
window.submitManualExpense = submitManualExpense;

window.addSavingsGoal = addSavingsGoal;
window.editSavings = editSavings;
window.closeSavingsModal = closeSavingsModal;
window.submitSavingsGoal = submitSavingsGoal;
window.deleteSavings = deleteSavings;

function toggleCustomDates() {
    const select = document.getElementById('periodType');
    const customGroup = document.getElementById('customDatesGroup');
    const displayMode = document.getElementById('customDatesDisplay');
    const inputMode = document.getElementById('customDatesInput');
    const startInput = document.getElementById('periodStart');
    const endInput = document.getElementById('periodEnd');

    if (select && customGroup) {
        const isCustom = select.value === 'custom';
        customGroup.style.display = isCustom ? 'block' : 'none';

        if (isCustom) {
            // Show display mode by default, hide input mode
            if (displayMode) displayMode.style.display = 'block';
            if (inputMode) inputMode.style.display = 'none';
        }

        // Clear values when not custom to avoid sending empty strings
        if (!isCustom && startInput && endInput) {
            startInput.value = '';
            endInput.value = '';
        }
    }
}

function enableDateEdit() {
    document.getElementById('customDatesDisplay').style.display = 'none';
    document.getElementById('customDatesInput').style.display = 'block';
}

function disableDateEdit() {
    const startInput = document.getElementById('periodStart');
    const endInput = document.getElementById('periodEnd');

    // Update display with new values
    if (startInput.value && endInput.value) {
        const startDate = new Date(startInput.value).toLocaleDateString('id-ID');
        const endDate = new Date(endInput.value).toLocaleDateString('id-ID');
        document.getElementById('dateRangeDisplay').textContent = `${startDate} - ${endDate}`;
    }

    document.getElementById('customDatesDisplay').style.display = 'block';
    document.getElementById('customDatesInput').style.display = 'none';
}

window.toggleCustomDates = toggleCustomDates;
window.enableDateEdit = enableDateEdit;
window.disableDateEdit = disableDateEdit;
