// ==================== Configuration ====================
// API_BASE and USER_ID are defined in the HTML file


// State
let currentYear = new Date().getFullYear();
let currentMonth = new Date().getMonth() + 1;
let filterMode = 'month'; // 'month' | 'all'
const FILTER_MODE_KEY = 'insight_filter_mode';
const FILTER_YEAR_KEY = 'insight_filter_year';
const FILTER_MONTH_KEY = 'insight_filter_month';
let emotionChart = null;
let categoryChart = null;
let isEditMode = false;
let selectedExpenses = new Set();

// ==================== Utility Functions ====================

function formatCurrency(amount) {
    return new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(amount);
}

// Return Icon HTML instead of Emoji
function getEmotionIcon(emotion) {
    const iconMap = {
        'Senang': '<i class="bi bi-emoji-smile-fill"></i>',
        'Sedih': '<i class="bi bi-emoji-frown-fill"></i>',
        'Marah': '<i class="bi bi-emoji-angry-fill"></i>',
        'Stress': '<i class="bi bi-emoji-dizzy-fill"></i>',
        'Lapar': '<i class="bi bi-fire"></i>',
        'Netral': '<i class="bi bi-emoji-neutral-fill"></i>'
    };
    return iconMap[emotion] || '<i class="bi bi-emoji-expressionless-fill"></i>';
}

function getEmotionColor(emotion) {
    const colorMap = {
        'Senang': '#10b981',
        'Sedih': '#6366f1',
        'Marah': '#ef4444',
        'Stress': '#f59e0b',
        'Lapar': '#f97316',
        'Netral': '#64748b'
    };
    return colorMap[emotion] || '#6b7280';
}

function getMonthName(month) {
    const months = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ];
    return months[month - 1];
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('id-ID', {
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function loadFilterState() {
    const storedMode = localStorage.getItem(FILTER_MODE_KEY);
    const storedYear = parseInt(localStorage.getItem(FILTER_YEAR_KEY), 10);
    const storedMonth = parseInt(localStorage.getItem(FILTER_MONTH_KEY), 10);

    if (storedMode === 'all' || storedMode === 'month') {
        filterMode = storedMode;
    }

    if (!Number.isNaN(storedYear)) {
        currentYear = storedYear;
    }
    if (!Number.isNaN(storedMonth) && storedMonth >= 1 && storedMonth <= 12) {
        currentMonth = storedMonth;
    }
}

function saveFilterState() {
    localStorage.setItem(FILTER_MODE_KEY, filterMode);
    localStorage.setItem(FILTER_YEAR_KEY, String(currentYear));
    localStorage.setItem(FILTER_MONTH_KEY, String(currentMonth));
}

function updateFilterUI() {
    const monthNav = document.getElementById('monthNav');
    const monthlyBtn = document.getElementById('filterMonthly');
    const allTimeBtn = document.getElementById('filterAllTime');
    const monthLabel = document.getElementById('currentMonth');
    const summaryTitle = document.getElementById('summaryTitle');

    if (monthlyBtn && allTimeBtn) {
        monthlyBtn.classList.toggle('active', filterMode === 'month');
        allTimeBtn.classList.toggle('active', filterMode === 'all');
    }

    if (monthNav) {
        monthNav.classList.toggle('hidden', filterMode === 'all');
    }

    if (monthLabel) {
        monthLabel.textContent = filterMode === 'all'
            ? 'Semua waktu'
            : `${getMonthName(currentMonth)} ${currentYear}`;
    }

    if (summaryTitle) {
        summaryTitle.innerHTML = `<i class="bi bi-activity"></i> Ringkasan ${filterMode === 'all' ? 'Semua Waktu' : `${getMonthName(currentMonth)} ${currentYear}`}`;
    }
}

function setFilterMode(mode) {
    filterMode = mode;
    saveFilterState();
    updateFilterUI();
    if (isEditMode) {
        isEditMode = false;
        const btn = document.getElementById('editModeBtn');
        const list = document.getElementById('historyList');
        if (btn) {
            btn.classList.remove('active');
            btn.innerHTML = '<i class="bi bi-list-check"></i> Edit';
        }
        if (list) {
            list.classList.remove('edit-mode');
        }
    }
    selectedExpenses.clear();
    updateDeleteButton();
    loadAllData();
}

function getPeriodLabel() {
    return filterMode === 'all'
        ? 'Semua waktu'
        : `${getMonthName(currentMonth)} ${currentYear}`;
}

// ==================== API Functions ====================

async function fetchMonthlyReport() {
    try {
        const response = await fetch(
            `${API_BASE}/api/report/monthly?user_id=${USER_ID}&year=${currentYear}&month=${currentMonth}`
        );
        return await response.json();
    } catch (error) {
        console.error('Error fetching monthly report:', error);
        return null;
    }
}

async function fetchExpensesForPeriod() {
    try {
        const params = new URLSearchParams({ user_id: USER_ID });

        if (filterMode === 'month') {
            params.set('year', currentYear);
            params.set('month', currentMonth);
        } else {
            params.set('limit', 5000);
        }

        const response = await fetch(`${API_BASE}/api/expenses?${params.toString()}`);
        return await response.json();
    } catch (error) {
        console.error('Error fetching expenses:', error);
        return null;
    }
}

async function updateExpenseParams(id, data) {
    try {
        const response = await fetch(`${API_BASE}/api/expenses/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        return await response.json();
    } catch (error) {
        console.error('Error updating expense:', error);
        return null;
    }
}

// ==================== Render Functions ====================

function renderStats(stats) {
    if (!stats) return;

    document.getElementById('statTotal').textContent = formatCurrency(stats.total || 0);
    document.getElementById('statCount').textContent = stats.count || 0;
    document.getElementById('statAverage').textContent = formatCurrency(stats.average || 0);
}

function renderTopEmotion(emotionSummary) {
    const topEmotionEl = document.getElementById('topEmotion');
    const topEmotionIcon = document.getElementById('topEmotionIcon');

    if (!topEmotionEl || !topEmotionIcon) return;

    if (!emotionSummary || emotionSummary.length === 0) {
        topEmotionEl.textContent = '-';
        topEmotionIcon.innerHTML = '<i class="bi bi-emoji-neutral"></i>';
        return;
    }

    const topEmotion = emotionSummary[0].emotion;
    topEmotionEl.textContent = topEmotion;
    topEmotionIcon.innerHTML = getEmotionIcon(topEmotion);
}

function buildStatsFromExpenses(expenses) {
    const stats = {
        total: 0,
        count: 0,
        average: 0,
        highest: null,
        categories: {}
    };

    if (!expenses || expenses.length === 0) {
        return stats;
    }

    expenses.forEach((expense) => {
        const amount = Number(expense.amount) || 0;
        stats.total += amount;
        stats.count += 1;

        const category = expense.category || 'Lainnya';
        stats.categories[category] = (stats.categories[category] || 0) + amount;

        if (!stats.highest || amount > (stats.highest.amount || 0)) {
            stats.highest = {
                item: expense.item_name,
                amount: amount,
                date: expense.date
            };
        }
    });

    stats.average = stats.count > 0 ? Math.floor(stats.total / stats.count) : 0;
    return stats;
}

function buildEmotionSummary(expenses) {
    if (!expenses || expenses.length === 0) return [];

    const totals = {};
    expenses.forEach((expense) => {
        const emotion = expense.emotion_label || 'Netral';
        const amount = Number(expense.amount) || 0;
        if (!totals[emotion]) {
            totals[emotion] = { total: 0, count: 0 };
        }
        totals[emotion].total += amount;
        totals[emotion].count += 1;
    });

    const summary = Object.entries(totals).map(([emotion, data]) => ({
        emotion,
        total: data.total,
        count: data.count,
        percentage: 0
    }));

    const totalAmount = summary.reduce((acc, item) => acc + item.total, 0);
    summary.forEach((item) => {
        item.percentage = totalAmount > 0 ? Math.round((item.total / totalAmount) * 100) : 0;
    });

    summary.sort((a, b) => b.total - a.total);
    return summary;
}

function buildEmotionInsight(summary) {
    if (!summary || summary.length === 0) {
        return null;
    }

    const top = summary[0];
    const emotion = top.emotion;
    const percentage = top.percentage || 0;

    const insights = {
        "Stress": `Wah, ${percentage}% pengeluaran kamu karena stress. Coba cari aktivitas stress relief yang lebih murah ya!`,
        "Sedih": `Hmm, ${percentage}% keluar pas lagi sedih. Curhat sama temen kadang lebih healing lho daripada belanja.`,
        "Senang": `Nice! ${percentage}% pengeluaran kamu pas lagi senang. Boleh lah treat yourself, asal terkontrol~`,
        "Marah": `Hmm, ${percentage}% keluar pas lagi kesel. Deep breath dulu sebelum checkout next time!`,
        "Lapar": `Wkwk ${percentage}% buat makan. Wajar sih, siapa yang tahan sama lapar.`,
        "Netral": `${percentage}% pengeluaran kamu terencana dengan baik. Mantap!`
    };

    return insights[emotion] || `Emosi ${emotion} mendominasi ${percentage}% pengeluaran kamu.`;
}

function buildNarrativeFallback(stats, emotionSummary) {
    if (!stats || stats.count === 0) {
        return 'Belum ada data untuk periode ini. Yuk mulai catat pengeluaranmu!';
    }

    const topEmotion = emotionSummary && emotionSummary.length > 0 ? emotionSummary[0].emotion : 'Netral';
    return `Total pengeluaran ${formatCurrency(stats.total)} dari ${stats.count} transaksi. Emosi dominan: ${topEmotion}.`;
}

function renderHighlights(stats, expenses) {
    const grid = document.getElementById('highlightGrid');
    if (!grid) return;

    let topCategoryName = '-';
    let topCategoryAmount = 0;
    if (stats && stats.categories) {
        for (const [category, amount] of Object.entries(stats.categories)) {
            if (amount > topCategoryAmount) {
                topCategoryAmount = amount;
                topCategoryName = category;
            }
        }
    }

    const highest = stats?.highest || null;

    const dayTotals = {};
    expenses.forEach((expense) => {
        const date = new Date(expense.date);
        if (Number.isNaN(date.getTime())) return;
        const key = date.toISOString().slice(0, 10);
        dayTotals[key] = (dayTotals[key] || 0) + (expense.amount || 0);
    });

    const topDay = Object.entries(dayTotals).sort((a, b) => b[1] - a[1])[0];
    const topDayLabel = topDay ? new Date(topDay[0]).toLocaleDateString('id-ID', {
        day: 'numeric',
        month: 'short'
    }) : '-';
    const topDayAmount = topDay ? topDay[1] : 0;

    grid.innerHTML = `
                <div class="highlight-card">
                    <div class="highlight-label">Kategori Paling Boros</div>
                    <div class="highlight-value">${topCategoryName}</div>
                    <div class="highlight-meta">${formatCurrency(topCategoryAmount)}</div>
                </div>
                <div class="highlight-card">
                    <div class="highlight-label">Transaksi Terbesar</div>
                    <div class="highlight-value">${highest?.item || '-'}</div>
                    <div class="highlight-meta">${highest ? formatCurrency(highest.amount) : 'Rp 0'}</div>
                </div>
                <div class="highlight-card">
                    <div class="highlight-label">Hari Paling Boros</div>
                    <div class="highlight-value">${topDayLabel}</div>
                    <div class="highlight-meta">${formatCurrency(topDayAmount)}</div>
                </div>
            `;
}

function renderEmotionInsight(emotionData) {
    const insightEl = document.getElementById('emotionInsightText');
    if (!insightEl) return;

    if (!emotionData || !emotionData.insight) {
        insightEl.textContent = 'Belum ada insight emosi. Yuk tambah transaksi biar polanya kebaca.';
        return;
    }

    insightEl.textContent = emotionData.insight;
}

function renderNarrative(narrative) {
    const narrativeContent = document.getElementById('narrativeContent');
    if (!narrativeContent) return;

    const text = typeof narrative === 'string' ? narrative : narrative?.narrative;

    if (!text) {
        narrativeContent.textContent = 'Belum ada data untuk periode ini. Yuk mulai catat pengeluaranmu!';
        return;
    }

    narrativeContent.textContent = text;
}

function renderEmotionChart(emotionData) {
    const ctx = document.getElementById('emotionChart').getContext('2d');
    const meta = document.getElementById('emotionMeta');

    if (emotionChart) {
        emotionChart.destroy();
    }

    if (!emotionData || !emotionData.emotional_spending || emotionData.emotional_spending.length === 0) {
        ctx.font = '16px Inter';
        ctx.fillStyle = '#64748b';
        ctx.textAlign = 'center';
        ctx.fillText('Belum ada data emosi', ctx.canvas.width / 2, ctx.canvas.height / 2);
        if (meta) {
            meta.innerHTML = '<span class="meta-pill">Total: Rp 0</span><span class="meta-pill">Dominan: -</span>';
        }
        return;
    }

    const labels = emotionData.emotional_spending.map(e => e.emotion);
    const data = emotionData.emotional_spending.map(e => e.total);
    const colors = emotionData.emotional_spending.map(e => getEmotionColor(e.emotion));
    const total = data.reduce((acc, value) => acc + value, 0);
    const topIndex = data.indexOf(Math.max(...data));

    if (meta) {
        meta.innerHTML = `
                    <span class="meta-pill">Total: ${formatCurrency(total)}</span>
                    <span class="meta-pill">Dominan: ${labels[topIndex] || '-'}</span>
                `;
    }

    emotionChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderWidth: 0,
                borderRadius: 8,
                spacing: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        color: '#475569',
                        padding: 16,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            return `${context.label}: ${formatCurrency(context.raw)}`;
                        }
                    }
                }
            }
        }
    });
}

function renderCategoryChart(stats) {
    const ctx = document.getElementById('categoryChart').getContext('2d');
    const meta = document.getElementById('categoryMeta');

    if (categoryChart) {
        categoryChart.destroy();
    }

    if (!stats || !stats.categories || Object.keys(stats.categories).length === 0) {
        ctx.font = '16px Inter';
        ctx.fillStyle = '#64748b';
        ctx.textAlign = 'center';
        ctx.fillText('Belum ada data kategori', ctx.canvas.width / 2, ctx.canvas.height / 2);
        if (meta) {
            meta.innerHTML = '<span class="meta-pill">Top kategori: -</span>';
        }
        return;
    }

    const labels = Object.keys(stats.categories);
    const data = Object.values(stats.categories);

    const topIndex = data.indexOf(Math.max(...data));
    if (meta) {
        meta.innerHTML = `<span class="meta-pill">Top kategori: ${labels[topIndex] || '-'}</span>`;
    }

    const categoryColors = [
        '#6366f1', '#10b981', '#f59e0b', '#ef4444',
        '#8b5cf6', '#ec4899', '#06b6d4'
    ];

    categoryChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Pengeluaran',
                data: data,
                backgroundColor: categoryColors.slice(0, labels.length),
                borderRadius: 10,
                barThickness: 22
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (context) => formatCurrency(context.raw)
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#64748b' },
                    grid: { display: false }
                },
                y: {
                    ticks: {
                        color: '#64748b',
                        callback: (value) => formatCurrency(value)
                    },
                    grid: { color: 'rgba(148, 163, 184, 0.12)' }
                }
            }
        }
    });
}

function renderHistory(expenses) {
    const historyList = document.getElementById('historyList');
    const historySubtitle = document.getElementById('historySubtitle');

    if (!expenses || expenses.length === 0) {
        historyList.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon"><i class="bi bi-journal-x"></i></div>
                        <p>Belum ada transaksi. Yuk mulai catat!</p>
                    </div>
                `;
        if (historySubtitle) {
            historySubtitle.textContent = `Belum ada transaksi untuk ${getPeriodLabel()}.`;
        }
        updateSelectAllButton();
        return;
    }

    window.currentExpenses = expenses;

    if (historySubtitle) {
        historySubtitle.textContent = `Menampilkan ${expenses.length} transaksi • ${getPeriodLabel()}.`;
    }

    historyList.innerHTML = expenses.map((expense, index) => {
        const isSelected = selectedExpenses.has(expense.id);
        return `
                <div class="history-item">
                    <div class="history-item-left">
                        <input type="checkbox" class="history-checkbox" 
                               ${isSelected ? 'checked' : ''} 
                               onclick="event.stopPropagation(); toggleSelection(${expense.id})">
                        
                        <div class="history-emotion-icon" style="background: ${getEmotionColor(expense.emotion_label)}20; color: ${getEmotionColor(expense.emotion_label)}">
                            ${getEmotionIcon(expense.emotion_label)}
                        </div>
                        <div class="history-item-info">
                            <h4>${expense.item_name}</h4>
                            <span>${expense.category} • ${formatDate(expense.date)}</span>
                        </div>
                    </div>
                    <div class="history-item-right">
                        <div class="history-item-amount">${formatCurrency(expense.amount)}</div>
                        <button class="history-edit-btn" onclick="openEditModal(${index})" title="Edit">
                            <i class="bi bi-pencil"></i>
                        </button>
                    </div>
                </div>
            `}).join('');

    if (isEditMode) {
        historyList.classList.add('edit-mode');
    } else {
        historyList.classList.remove('edit-mode');
    }

    updateSelectAllButton();
}

// ==================== Bulk Delete Logic ====================

function toggleEditMode() {
    isEditMode = !isEditMode;

    const btn = document.getElementById('editModeBtn');
    const list = document.getElementById('historyList');

    if (isEditMode) {
        btn.classList.add('active');
        list.classList.add('edit-mode');
        btn.innerHTML = '<i class="bi bi-check-lg"></i> Selesai';
    } else {
        btn.classList.remove('active');
        list.classList.remove('edit-mode');
        btn.innerHTML = '<i class="bi bi-list-check"></i> Edit';
        selectedExpenses.clear();
        updateDeleteButton();
        renderHistory(window.currentExpenses);
    }

    updateSelectAllButton();
}

function toggleSelectAll() {
    const items = window.currentExpenses || [];
    if (items.length === 0) return;

    const allSelected = items.every(expense => selectedExpenses.has(expense.id));
    if (allSelected) {
        selectedExpenses.clear();
    } else {
        items.forEach(expense => selectedExpenses.add(expense.id));
    }

    updateDeleteButton();
    renderHistory(items);
}

function updateSelectAllButton() {
    const btn = document.getElementById('selectAllBtn');
    if (!btn) return;

    if (!isEditMode) {
        btn.classList.add('hidden');
        return;
    }

    btn.classList.remove('hidden');
    const items = window.currentExpenses || [];
    const allSelected = items.length > 0 && items.every(expense => selectedExpenses.has(expense.id));

    if (allSelected) {
        btn.innerHTML = '<i class="bi bi-dash-square"></i> Batal pilih';
    } else {
        btn.innerHTML = '<i class="bi bi-check2-square"></i> Pilih semua';
    }

    btn.disabled = items.length === 0;
}

function toggleSelection(id) {
    if (selectedExpenses.has(id)) {
        selectedExpenses.delete(id);
    } else {
        selectedExpenses.add(id);
    }
    updateDeleteButton();
}

function updateDeleteButton() {
    const btn = document.getElementById('deleteBtn');
    const countSpan = document.getElementById('deleteCount');

    if (selectedExpenses.size > 0 && isEditMode) {
        btn.classList.remove('hidden');
        countSpan.textContent = selectedExpenses.size;
    } else {
        btn.classList.add('hidden');
    }

    updateSelectAllButton();
}

async function deleteSelected() {
    if (selectedExpenses.size === 0) return;

    if (!confirm(`Yakin ingin menghapus ${selectedExpenses.size} transaksi ini?`)) return;

    const deleteBtn = document.getElementById('deleteBtn');
    const originalContent = deleteBtn.innerHTML;
    deleteBtn.disabled = true;
    deleteBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Hapus...';

    try {
        for (const id of selectedExpenses) {
            await fetch(`${API_BASE}/api/expenses/${id}`, { method: 'DELETE' });
        }

        toggleEditMode();
        loadAllData();

    } catch (error) {
        console.error('Delete error:', error);
        alert('Gagal menghapus beberapa data. Coba lagi.');
    } finally {
        deleteBtn.disabled = false;
        deleteBtn.innerHTML = originalContent;
    }
}

// ==================== Edit Modal Logic ====================

function openEditModal(index) {
    const expense = window.currentExpenses[index];
    if (!expense) return;

    document.getElementById('editId').value = expense.id;
    document.getElementById('editItem').value = expense.item_name;
    document.getElementById('editAmount').value = expense.amount;
    document.getElementById('editCategory').value = expense.category;
    document.getElementById('editMood').value = expense.emotion_label;

    document.getElementById('editModal').classList.add('active');
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
}

async function saveExpense() {
    const id = document.getElementById('editId').value;
    const item = document.getElementById('editItem').value;
    const amount = document.getElementById('editAmount').value;
    const category = document.getElementById('editCategory').value;
    const mood = document.getElementById('editMood').value;

    if (!item || !amount) {
        alert("Mohon lengkapi data");
        return;
    }

    const saveBtn = document.querySelector('.modal-actions .btn-primary');
    const originalText = saveBtn.innerText;
    saveBtn.innerText = 'Menyimpan...';
    saveBtn.disabled = true;

    const result = await updateExpenseParams(id, {
        item_name: item,
        amount: parseInt(amount),
        category: category,
        emotion_label: mood
    });

    if (result && result.success) {
        closeEditModal();
        loadAllData();
    } else {
        alert("Gagal menyimpan data");
    }

    saveBtn.innerText = originalText;
    saveBtn.disabled = false;
}

// ==================== Data Loading ====================

// ==================== New Features: Audit & Scatter ====================

async function loadAuditData() {
    try {
        const response = await fetch(`${API_BASE}/api/report/audit`);
        const result = await response.json();

        if (result.success) {
            renderAuditList(result.candidates);
            const regretTotalEl = document.getElementById('regretTotalAmount');
            if (regretTotalEl) regretTotalEl.textContent = formatCurrency(result.stats.total_wasted || 0);
        }
    } catch (error) {
        console.error('Error loading audit data:', error);
    }
}

function renderAuditList(candidates) {
    const container = document.getElementById('auditList');
    if (!container) return;

    if (!candidates || candidates.length === 0) {
        container.innerHTML = `
                    <div class="audit-card-empty" style="color: var(--text-muted); font-style: italic; width: 100%; text-align: center; padding: 2rem;">
                        <i class="bi bi-check-circle-fill" style="color: var(--emotion-senang); font-size: 2rem; margin-bottom: 0.5rem; display:block;"></i>
                        Tidak ada transaksi yang perlu diaudit. Aman!
                    </div>`;
        return;
    }

    container.innerHTML = candidates.map(exp => `
                <div class="audit-card" style="min-width: 250px; background: var(--bg-card); padding: 1rem; border-radius: var(--radius-lg); border: 1px solid var(--glass-border); box-shadow: var(--shadow-sm);">
                    <div style="font-weight: 600; margin-bottom: 0.2rem; font-size: 0.95rem;">${exp.item_name}</div>
                    <div style="color: var(--secondary); font-size: 1.1rem; margin-bottom: 0.5rem; font-weight: 700;">${formatCurrency(exp.amount)}</div>
                    <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem; display: flex; align-items: center; gap: 5px;">
                        <span style="color: #ef4444; background: rgba(239, 68, 68, 0.1); padding: 2px 6px; border-radius: 4px;">${exp.emotion_label}</span> 
                        <span>${new Date(exp.date).toLocaleDateString('id-ID', { day: 'numeric', month: 'short' })}</span>
                    </div>
                    <div style="display: flex; gap: 0.5rem;">
                        <button onclick="markRegret(${exp.id}, false)" style="flex: 1; border: 1px solid #10b981; background: transparent; color: #10b981; padding: 0.5rem; border-radius: var(--radius-md); cursor: pointer; font-size: 0.85rem; transition: all 0.2s;">
                            Worth It
                        </button>
                        <button onclick="markRegret(${exp.id}, true)" style="flex: 1; background: #ef4444; border: 1px solid #ef4444; color: white; padding: 0.5rem; border-radius: var(--radius-md); cursor: pointer; font-size: 0.85rem; transition: all 0.2s;">
                            Nyesel
                        </button>
                    </div>
                </div>
            `).join('');
}

async function markRegret(id, isRegret) {
    try {
        // Optimistic UI update
        const btn = document.querySelector(`button[onclick="markRegret(${id}, true)"]`);
        if (btn) {
            const card = btn.closest('.audit-card');
            if (card) card.style.opacity = '0.5';
        }

        await fetch(`${API_BASE}/api/report/audit/${id}?is_regret=${isRegret}`, {
            method: 'POST'
        });

        // Refresh data
        loadAuditData();
    } catch (error) {
        console.error('Error marking regret:', error);
        alert('Gagal update status.');
    }
}

let scatterChartInstance = null;

async function loadScatterData() {
    try {
        const response = await fetch(`${API_BASE}/api/report/scatter`);
        const result = await response.json();

        if (result.success) {
            renderScatterChart(result.data);
        }
    } catch (error) {
        console.error('Error loading scatter data:', error);
    }
}

function renderScatterChart(dataPoints) {
    const ctxEl = document.getElementById('scatterChart');
    if (!ctxEl) return;
    const ctx = ctxEl.getContext('2d');

    if (scatterChartInstance) {
        scatterChartInstance.destroy();
    }

    scatterChartInstance = new Chart(ctx, {
        type: 'scatter',
        data: {
            datasets: [{
                label: 'Transaksi',
                data: dataPoints, // {x, y}
                backgroundColor: (ctx) => {
                    const val = ctx.raw?.x;
                    if (val <= -1.5) return '#ef4444'; // Marah/Stress parah
                    if (val < 0) return '#f59e0b'; // Sedih/Stress ringan
                    if (val === 0) return '#94a3b8'; // Netral
                    if (val >= 2) return '#10b981'; // Senang/Bahagia
                    return '#8b5cf6'; // Others
                },
                pointRadius: (ctx) => {
                    // Scale size by amount slightly
                    const amt = ctx.raw?.y || 0;
                    return Math.max(6, Math.min(18, Math.log10(amt + 1) * 2.5));
                },
                pointHoverRadius: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            const pt = context.raw;
                            return `${pt.item}: ${formatCurrency(pt.y)}`;
                        },
                        afterLabel: function (context) {
                            const pt = context.raw;
                            const date = new Date(pt.date).toLocaleDateString('id-ID');
                            return `Emosi: ${pt.emotion} (${date})`;
                        }
                    }
                },
                legend: { display: false }
            },
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: { display: true, text: 'Mood (Negatif ⬅ ➡ Positif)', color: '#94a3b8' },
                    min: -3,
                    max: 3,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    title: { display: true, text: 'Nominal (Rp)', color: '#94a3b8' },
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}


// ==================== Data Loading ====================

async function loadAllData() {
    const overlay = document.getElementById('loadingOverlay');
    overlay.classList.add('active');

    try {
        updateFilterUI();

        const reportPromise = filterMode === 'month'
            ? fetchMonthlyReport()
            : Promise.resolve(null);

        const results = await Promise.allSettled([
            fetchExpensesForPeriod(),
            reportPromise
        ]);

        const expensesResult = results[0].status === 'fulfilled' ? results[0].value : null;
        const report = results[1].status === 'fulfilled' ? results[1].value : null;

        if (results[0].status === 'rejected') {
            console.error('API call expenses failed:', results[0].reason);
        }
        if (results[1].status === 'rejected') {
            console.error('API call report failed:', results[1].reason);
        }

        const expenseList = expensesResult?.expenses || [];
        const stats = buildStatsFromExpenses(expenseList);
        const emotionSummary = buildEmotionSummary(expenseList);
        const emotionData = {
            emotional_spending: emotionSummary,
            insight: buildEmotionInsight(emotionSummary)
        };

        renderStats(stats);
        renderTopEmotion(emotionSummary);
        renderHighlights(stats, expenseList);
        renderEmotionInsight(emotionData);
        renderEmotionChart(emotionData);
        renderCategoryChart(stats);
        renderHistory(expenseList);

        // NEW: Load Regret Audit & Scatter
        await loadAuditData();
        await loadScatterData();

        let narrativeText = filterMode === 'month' ? report?.narrative : '';
        if (!narrativeText) {
            narrativeText = buildNarrativeFallback(stats, emotionSummary);
        }
        renderNarrative(narrativeText);

    } catch (error) {
        console.error("Critical error loading data:", error);
    } finally {
        if (overlay) overlay.classList.remove('active');
    }
}

// ==================== Event Handlers ====================

document.getElementById('prevMonth').addEventListener('click', () => {
    if (filterMode === 'all') return;
    currentMonth--;
    if (currentMonth < 1) {
        currentMonth = 12;
        currentYear--;
    }
    saveFilterState();
    selectedExpenses.clear();
    updateDeleteButton();
    loadAllData();
});

document.getElementById('nextMonth').addEventListener('click', () => {
    if (filterMode === 'all') return;
    currentMonth++;
    if (currentMonth > 12) {
        currentMonth = 1;
        currentYear++;
    }
    saveFilterState();
    selectedExpenses.clear();
    updateDeleteButton();
    loadAllData();
});

document.getElementById('filterMonthly').addEventListener('click', () => {
    setFilterMode('month');
});

document.getElementById('filterAllTime').addEventListener('click', () => {
    setFilterMode('all');
});

// ==================== Initialize ====================

document.addEventListener('DOMContentLoaded', () => {
    loadFilterState();
    saveFilterState();
    updateFilterUI();
    loadAllData();
});
