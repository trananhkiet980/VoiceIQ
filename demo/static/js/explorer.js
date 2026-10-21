// explorer.js

let currentTenantId = '916180a7-0b43-5c08-b3c8-c738826880bb';
let currentSelectedCallId = null;
let currentCallData = null;

document.addEventListener('DOMContentLoaded', async () => {
    // 1. Khởi tạo danh sách Tenant
    const tenantSelect = document.getElementById('tenant-id');
    try {
        const tenants = [
            { id: '916180a7-0b43-5c08-b3c8-c738826880bb', name: '916180a7-0b43-5c08-b3c8-c738826880bb' },
            { id: '47094484-5042-5449-8a50-4f75daf54b25', name: '47094484-5042-5449-8a50-4f75daf54b25' }
        ];
        
        tenantSelect.innerHTML = '';
        tenants.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.id;
            opt.textContent = t.name;
            tenantSelect.appendChild(opt);
        });
        
        currentTenantId = tenantSelect.value;
        
        tenantSelect.addEventListener('change', (e) => {
            currentTenantId = e.target.value;
            loadExplorerCalls();
        });
    } catch (e) {
        console.error('Error loading tenants:', e);
    }

    // Lắng nghe sự kiện Check-all
    document.getElementById('check-all').addEventListener('change', (e) => {
        const checkboxes = document.querySelectorAll('.call-checkbox:not(:disabled)');
        checkboxes.forEach(cb => cb.checked = e.target.checked);
        updateBatchAnalyzeButton();
    });

    // Event delegation cho từng checkbox riêng lẻ
    document.getElementById('calls-tbody').addEventListener('change', (e) => {
        if (e.target.classList.contains('call-checkbox')) {
            updateBatchAnalyzeButton();
            
            // Cập nhật trạng thái của check-all
            const allCheckboxes = document.querySelectorAll('.call-checkbox:not(:disabled)');
            const checkedBoxes = document.querySelectorAll('.call-checkbox:not(:disabled):checked');
            const checkAllBtn = document.getElementById('check-all');
            
            if (allCheckboxes.length > 0) {
                checkAllBtn.checked = allCheckboxes.length === checkedBoxes.length;
                checkAllBtn.indeterminate = checkedBoxes.length > 0 && checkedBoxes.length < allCheckboxes.length;
            }
        }
    });

    // Lần đầu tải danh sách
    loadExplorerCalls();
});

let globalCallsList = [];
let currentSortField = 'created_at';
let currentSortOrder = 'asc'; // ascending by default

// ============================================
// HÀM TẢI DANH SÁCH CUỘC GỌI
// ============================================
async function loadExplorerCalls() {
    const status = document.getElementById('filter-status').value;
    const tbody = document.getElementById('calls-tbody');
    tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-slate-400 italic">Đang tải dữ liệu...</td></tr>';
    
    try {
        let fetchUrl = `/api/v1/demo/explorer/calls?tenant_id=${currentTenantId}&status=${status === 'all' ? 'all' : status}`;
        const res = await fetch(fetchUrl);
        if (!res.ok) throw new Error('API Error');
        const data = await res.json();
        
        globalCallsList = data.calls || [];
        
        // Bỏ việc điền động Mức độ khẩn cấp (NBA) bằng toàn bộ chuỗi text vì ta đã fix cứng 4 priority.
        
        applyFiltersAndSort();
        
    } catch (error) {
        console.error('Lỗi tải danh sách:', error);
        tbody.innerHTML = `<tr><td colspan="5" class="p-8 text-center text-red-500 font-bold">Lỗi tải dữ liệu: ${error.message}</td></tr>`;
    }
}

function toggleSort(field) {
    if (currentSortField === field) {
        currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortField = field;
        currentSortOrder = 'asc'; // reset to desc on change? Requirement: "ấn lần 1 là giảm dần, lần 2 là tăng dần". Wait, default is 'asc'. So if they click, it becomes 'desc'. Let's set it to 'desc' on first click for a new field.
        currentSortOrder = 'desc'; 
    }
    
    // Update icons
    document.getElementById('icon-sort-created').innerText = currentSortField === 'created_at' ? (currentSortOrder === 'asc' ? '↑' : '↓') : '-';
    document.getElementById('icon-sort-analysis').innerText = currentSortField === 'analysis_created_at' ? (currentSortOrder === 'asc' ? '↑' : '↓') : '-';
    
    // Highlight buttons
    document.getElementById('btn-sort-created').className = currentSortField === 'created_at' 
        ? "px-3 py-1 text-xs font-bold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors flex items-center gap-1"
        : "px-3 py-1 text-xs font-bold text-slate-500 hover:bg-slate-50 transition-colors flex items-center gap-1";
        
    document.getElementById('btn-sort-analysis').className = currentSortField === 'analysis_created_at'
        ? "px-3 py-1 text-xs font-bold bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors flex items-center gap-1"
        : "px-3 py-1 text-xs font-bold text-slate-500 hover:bg-slate-50 transition-colors flex items-center gap-1";
        
    applyFiltersAndSort();
}

function applyFiltersAndSort() {
    const status = document.getElementById('filter-status').value;
    const qaFilter = document.getElementById('filter-qa').value;
    const nbaFilter = document.getElementById('filter-nba').value;
    
    let callsToRender = [...globalCallsList];
    
    // Lọc theo Status
    if (status !== 'all') {
         callsToRender = callsToRender.filter(c => c.status === (status === 'pending' ? 'pending' : 'processed'));
    }

    // Lọc theo QA Score
    if (qaFilter !== 'all') {
        callsToRender = callsToRender.filter(c => {
            const s = c.qa_score;
            if (s == null) return false;
            if (qaFilter === 'high') return s >= 80;
            if (qaFilter === 'medium') return s >= 50 && s < 80;
            if (qaFilter === 'low') return s < 50;
            return true;
        });
    }
    
    // Lọc theo NBA Priority
    if (nbaFilter !== 'all') {
        callsToRender = callsToRender.filter(c => c.nba_priority && typeof c.nba_priority === 'string' && c.nba_priority.toLowerCase().includes(nbaFilter.toLowerCase()));
    }
    
    // Lọc theo Deadline
    const deadlineFilter = document.getElementById('filter-deadline')?.value;
    if (deadlineFilter) {
        callsToRender = callsToRender.filter(c => c.nba_deadline && c.nba_deadline === deadlineFilter);
    }
    
    // Lọc theo Sentiment
    const sentimentFilter = document.getElementById('filter-sentiment')?.value || 'all';
    if (sentimentFilter !== 'all') {
        callsToRender = callsToRender.filter(c => {
            const analysisObj = (typeof c.raw_llm_analysis === 'object' && c.raw_llm_analysis) ? c.raw_llm_analysis : (c.call_analysis || c.post_call_summary || {});
            const s = (analysisObj.sentiment_trend || analysisObj.customer_sentiment || '').toLowerCase();
            if (sentimentFilter === 'positive') return s.includes('positive') || s.includes('hài lòng') || s.includes('tích cực');
            if (sentimentFilter === 'negative') return s.includes('negative') || s.includes('tức giận') || s.includes('tiêu cực');
            if (sentimentFilter === 'neutral') return s === '' || s.includes('neutral') || s.includes('bình thường');
            return false;
        });
    }

    // Lọc theo Escalation
    const escFilter = document.getElementById('filter-escalation')?.value || 'all';
    if (escFilter !== 'all') {
        callsToRender = callsToRender.filter(c => {
            const analysisObj = (typeof c.raw_llm_analysis === 'object' && c.raw_llm_analysis) ? c.raw_llm_analysis : (c.call_analysis || c.post_call_summary || {});
            const e = (analysisObj.escalation_level || 'none').toLowerCase();
            if (escFilter === 'none') return e === 'none' || e === '' || e === 'low' || e === 'normal';
            if (escFilter === 'high') return e === 'high' || e === 'critical';
            return e.includes('medium') || e === escFilter;
        });
    }

    // Lọc theo Toxicity
    const toxFilter = document.getElementById('filter-toxicity')?.value || 'all';
    if (toxFilter !== 'all') {
        callsToRender = callsToRender.filter(c => {
            const analysisObj = (typeof c.raw_llm_analysis === 'object' && c.raw_llm_analysis) ? c.raw_llm_analysis : (c.call_analysis || c.post_call_summary || {});
            const t = analysisObj.toxicity_tags || [];
            if (toxFilter === 'none') return t.length === 0;
            if (toxFilter === 'toxic') return t.length > 0;
            return false;
        });
    }
    
    // Sắp xếp
    callsToRender.sort((a, b) => {
        let valA = a[currentSortField] ? new Date(a[currentSortField]).getTime() : 0;
        let valB = b[currentSortField] ? new Date(b[currentSortField]).getTime() : 0;
        
        if (currentSortOrder === 'asc') {
            return valA - valB;
        } else {
            return valB - valA;
        }
    });

    renderCallsList(callsToRender, status);
    updateAnalyticsCharts(callsToRender);
}

function renderCallsList(calls, currentStatusFilter) {
    const tbody = document.getElementById('calls-tbody');
    if (!calls || calls.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-slate-400 italic">Không có cuộc gọi nào.</td></tr>';
        updateBatchAnalyzeButton();
        return;
    }

    let html = '';
    calls.forEach(c => {
        const cid = c.call_id || c.id;
        const time = new Date(c.created_at || Date.now()).toLocaleString('vi-VN');
        const duration = c.duration ? `${c.duration}s` : ((c.metadata && c.metadata.duration) ? `${c.metadata.duration}s` : '--');
        
        let isProcessed = c.status === 'processed' || c.message_analyses?.length > 0 || c.post_call_summary;
        if (currentStatusFilter === 'pending') isProcessed = false;
        
        const trClass = isProcessed 
            ? "border-b border-slate-100 hover:bg-slate-50 transition-colors cursor-pointer" 
            : "border-b border-slate-100 hover:bg-yellow-50/50 bg-yellow-50/20 transition-colors cursor-pointer";
        
        let statusBadge = '';
        if (isProcessed) {
            const analysisTime = c.analysis_created_at ? new Date(c.analysis_created_at).toLocaleString('vi-VN') : '';
            statusBadge = `
                <div class="flex flex-col items-end gap-1">
                    <span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-100 text-emerald-800">Đã phân tích</span>
                    ${analysisTime ? `<span class="text-[9px] text-slate-400 font-mono">${analysisTime}</span>` : ''}
                </div>
            `;
        } else {
            statusBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">Chờ phân tích</span>`;
        }

        let qaScoreHtml = '--';
        if (isProcessed && c.qa_score != null && c.qa_score > 0) {
            let qaClass = 'text-slate-600';
            if (c.qa_score >= 80) qaClass = 'text-emerald-600 font-bold';
            else if (c.qa_score >= 50) qaClass = 'text-amber-500 font-bold';
            else qaClass = 'text-rose-600 font-bold';
            qaScoreHtml = `<span class="${qaClass}">${c.qa_score}</span>`;
        }

        const intentHtml = c.main_intent 
            ? `<span class="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${c.intent_color || 'bg-slate-100 text-slate-700'} max-w-[180px] truncate" title="${c.main_intent}">${c.main_intent}</span>` 
            : '<span class="text-slate-400 italic text-xs">--</span>';
            
        const nbaHtml = c.nba
            ? `<div class="text-[10px] text-slate-500 mt-1 truncate max-w-[180px]" title="${c.nba}">💡 ${c.nba}</div>`
            : '';

        html += `
            <tr class="${trClass}" onclick="selectCall('${cid}')">
                <td class="px-4 py-3 text-center" onclick="event.stopPropagation()">
                    <input type="checkbox" class="call-checkbox rounded border-slate-300 text-primary-600 focus:ring-primary-500" value="${cid}" data-processed="${isProcessed}">
                </td>
                <td class="px-4 py-3">
                    <div class="font-mono text-xs text-primary-600 font-bold">${cid.substring(0,8)}...</div>
                    <div class="text-[10px] text-slate-500 mt-0.5">${time} • ${duration}</div>
                </td>
                <td class="px-4 py-3 text-center text-sm">
                    ${qaScoreHtml}
                </td>
                <td class="px-4 py-3 text-sm">
                    ${intentHtml}
                    ${nbaHtml}
                </td>
                <td class="px-4 py-3 text-right">
                    ${statusBadge}
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
    updateBatchAnalyzeButton();
}

function updateBatchAnalyzeButton() {
    const checkboxes = document.querySelectorAll('.call-checkbox:checked');
    const btnAnalyze = document.getElementById('btn-batch-analyze');
    const btnReset = document.getElementById('btn-batch-reset');
    
    if (checkboxes.length > 0) {
        if(btnAnalyze) {
            btnAnalyze.disabled = false;
            btnAnalyze.innerText = `▶ Phân tích (${checkboxes.length})`;
        }
        if(btnReset) {
            btnReset.disabled = false;
            btnReset.innerText = `↺ Hủy (${checkboxes.length})`;
        }
    } else {
        if(btnAnalyze) {
            btnAnalyze.disabled = true;
            btnAnalyze.innerText = `▶ Phân tích`;
        }
        if(btnReset) {
            btnReset.disabled = true;
            btnReset.innerText = `↺ Hủy`;
        }
    }
}

// ============================================
// BATCH ANALYSIS LOGIC
// ============================================
async function startBatchReset() {
    const checkboxes = document.querySelectorAll('.call-checkbox:checked');
    const callIds = Array.from(checkboxes).map(cb => cb.value);
    if (callIds.length === 0) return;

    if (!confirm(`Bạn có chắc muốn hủy phân tích và làm sạch dữ liệu của ${callIds.length} cuộc gọi này không?`)) {
        return;
    }

    const btn = document.getElementById('btn-batch-reset');
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = `Đang hủy...`;

    try {
        const res = await fetch(`/api/v1/demo/transcripts/mark-unprocessed?tenant_id=${currentTenantId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ call_ids: callIds })
        });
        if (res.ok) {
            document.getElementById('check-all').checked = false;
            loadExplorerCalls(); // Tải lại danh sách
        } else {
            alert('Có lỗi xảy ra khi hủy phân tích!');
        }
    } catch (e) {
        console.error(e);
        alert('Có lỗi xảy ra: ' + e);
    } finally {
        btn.innerText = originalText;
        updateBatchAnalyzeButton();
    }
}

function openAnalyzeConfigModal() {
    const checkboxes = document.querySelectorAll('.call-checkbox:checked');
    if (checkboxes.length === 0) return;
    document.getElementById('analyze-config-modal').classList.remove('hidden');
}

function closeAnalyzeConfigModal() {
    document.getElementById('analyze-config-modal').classList.add('hidden');
}

async function startBatchAnalysis() {
    const checkboxes = document.querySelectorAll('.call-checkbox:checked');
    const callIds = Array.from(checkboxes).map(cb => cb.value);
    if (callIds.length === 0) return;

    const promptMode = document.getElementById('config-prompt').value;
    const modelName = document.getElementById('config-model').value;
    
    closeAnalyzeConfigModal();

    // Hiển thị Modal
    document.getElementById('analysis-modal').classList.remove('hidden');
    document.getElementById('btn-analysis-close').classList.add('hidden');
    const spinner = document.getElementById('analysis-spinner');
    spinner.classList.remove('hidden');
    
    const logEl = document.getElementById('analysis-logs');
    logEl.innerHTML = '';
    
    function logMsg(msg, color = '#34d399') {
        const time = new Date().toLocaleTimeString('vi-VN');
        logEl.innerHTML += `<div style="color: ${color}">[${time}] ${msg}</div>`;
        logEl.scrollTop = logEl.scrollHeight;
    }
    
    let successCount = 0;
    
    for (let i = 0; i < callIds.length; i++) {
        const cid = callIds[i];
        document.getElementById('analysis-progress').innerText = `Đang xử lý ${i + 1}/${callIds.length} cuộc gọi...`;
        document.getElementById('analysis-bar').style.width = `${((i) / callIds.length) * 100}%`;
        
        logMsg(`Tiến hành tải dữ liệu cuộc gọi ${cid.substring(0,8)}...`, '#60a5fa'); // blue
        
        try {
            // Lấy dữ liệu transcript hiện tại
            const getRes = await fetch(`/api/v1/demo/transcripts/${cid}?tenant_id=${currentTenantId}`);
            const callData = await getRes.json();
            
            if (callData && callData.transcript_json) {
                logMsg(`  ↳ Đã tải xong. Bắt đầu gửi lệnh phân tích (Prompt: ${promptMode}, Model: ${modelName})...`, '#94a3b8'); // slate
                
                // Định dạng payload gửi đi
                const payload = {
                    tenant_id: currentTenantId,
                    call_id: cid,
                    transcript_json: callData.transcript_json.map(m => ({
                        speaker: m.speaker,
                        text: m.text,
                        start_time: m.start_time || 0.0,
                        end_time: m.end_time || 1.0
                    })),
                    duration_seconds: callData.duration_seconds || 120.0,
                    save_to_db: true,
                    pipeline_mode: promptMode,
                    model: modelName
                };

                const analyzeRes = await fetch('/api/v1/demo/simulate/postcall', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                if (analyzeRes.ok) {
                    successCount++;
                    logMsg(`  ↳ Thành công! Đã lưu kết quả phân tích.`, '#34d399'); // emerald
                } else {
                    const errText = await analyzeRes.text();
                    logMsg(`  ↳ Lỗi API ${analyzeRes.status}: ${errText.substring(0,50)}...`, '#f87171'); // red
                    console.error(`API Error ${analyzeRes.status}:`, errText);
                }
            } else {
                logMsg(`  ↳ Lỗi: Không tìm thấy dữ liệu hội thoại!`, '#fbbf24'); // amber
            }
        } catch (error) {
            logMsg(`  ↳ Ngoại lệ xảy ra: ${error.message}`, '#f87171');
            console.error(`Lỗi phân tích Call ${cid}:`, error);
        }
        logMsg(`----------------------------------------`, '#475569');
    }

    // Hoàn thành
    document.getElementById('analysis-bar').style.width = `100%`;
    document.getElementById('analysis-progress').innerText = `Đã phân tích thành công ${successCount}/${callIds.length} cuộc gọi.`;
    document.getElementById('analysis-title').innerText = "Phân tích Hoàn tất!";
    spinner.classList.add('hidden');
    document.getElementById('btn-analysis-close').classList.remove('hidden');
    logMsg(`Xong toàn bộ tiến trình!`, '#a78bfa'); // purple
}

// ============================================
// BATCH COMPARE LOGIC
// ============================================
function openCompareModal() {
    const checkboxes = document.querySelectorAll('.call-checkbox:checked');
    if (checkboxes.length === 0) return;
    document.getElementById('compare-modal').classList.remove('hidden');
}

function closeCompareModal() {
    document.getElementById('compare-modal').classList.add('hidden');
}

async function startBatchCompare() {
    const checkboxes = document.querySelectorAll('.call-checkbox:checked');
    const callIds = Array.from(checkboxes).map(cb => cb.value);
    if (callIds.length === 0) return;

    // Get selected prompt and models
    const promptMode = document.getElementById('compare-prompt').value;
    const modelCheckboxes = document.querySelectorAll('#compare-models input[type="checkbox"]:checked');
    const selectedModels = Array.from(modelCheckboxes).map(cb => cb.value);
    
    if (selectedModels.length === 0) {
        alert('Vui lòng chọn ít nhất 1 model để so sánh!');
        return;
    }

    closeCompareModal();
    
    // Hiển thị Modal Progress
    document.getElementById('analysis-modal').classList.remove('hidden');
    document.getElementById('btn-analysis-close').classList.add('hidden');
    const spinner = document.getElementById('analysis-spinner');
    spinner.classList.remove('hidden');
    
    const logEl = document.getElementById('analysis-logs');
    logEl.innerHTML = '';
    
    function logMsg(msg, color = '#34d399') {
        const time = new Date().toLocaleTimeString('vi-VN');
        logEl.innerHTML += `<div style="color: ${color}">[${time}] ${msg}</div>`;
        logEl.scrollTop = logEl.scrollHeight;
    }
    
    let successCount = 0;
    let totalTasks = callIds.length * selectedModels.length;
    let completedTasks = 0;
    
    // Lưu kết quả compare tạm thời (trong memory)
    window.compareResults = window.compareResults || {};
    
    for (let i = 0; i < callIds.length; i++) {
        const cid = callIds[i];
        
        logMsg(`Bắt đầu phân tích cuộc gọi ${cid.substring(0,8)}...`, '#60a5fa');
        window.compareResults[cid] = window.compareResults[cid] || { models: {} };
        
        try {
            const getRes = await fetch(`/api/v1/demo/transcripts/${cid}?tenant_id=${currentTenantId}`);
            const callData = await getRes.json();
            
            if (callData && callData.transcript_json) {
                // Chạy các model tuần tự (hoặc song song nếu muốn nhanh hơn)
                for (let j = 0; j < selectedModels.length; j++) {
                    const modelName = selectedModels[j];
                    completedTasks++;
                    document.getElementById('analysis-progress').innerText = `Đang xử lý ${completedTasks}/${totalTasks} (Model: ${modelName})...`;
                    document.getElementById('analysis-bar').style.width = `${((completedTasks - 1) / totalTasks) * 100}%`;
                    
                    logMsg(`  ↳ Đang chạy model ${modelName}...`, '#94a3b8');
                    
                    const payload = {
                        tenant_id: currentTenantId,
                        call_id: cid,
                        transcript_json: callData.transcript_json.map(m => ({
                            speaker: m.speaker,
                            text: m.text,
                            start_time: m.start_time || 0.0,
                            end_time: m.end_time || 1.0
                        })),
                        duration_seconds: callData.duration_seconds || 120.0,
                        save_to_db: false, // CHỈ lưu memory để so sánh
                        pipeline_mode: promptMode,
                        model: modelName
                    };

                    const analyzeRes = await fetch('/api/v1/demo/simulate/postcall', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    
                    if (analyzeRes.ok) {
                        const resultData = await analyzeRes.json();
                        window.compareResults[cid].models[modelName] = resultData;
                        successCount++;
                        logMsg(`    ✓ ${modelName} xong!`, '#34d399');
                    } else {
                        const errText = await analyzeRes.text();
                        logMsg(`    ✗ Lỗi ${modelName}: ${errText.substring(0,50)}...`, '#f87171');
                    }
                }
            }
        } catch (error) {
            logMsg(`  ↳ Lỗi: ${error.message}`, '#f87171');
        }
        logMsg(`----------------------------------------`, '#475569');
    }

    document.getElementById('analysis-bar').style.width = `100%`;
    document.getElementById('analysis-progress').innerText = `Đã phân tích xong các model.`;
    document.getElementById('analysis-title').innerText = "So sánh Hoàn tất!";
    spinner.classList.add('hidden');
    document.getElementById('btn-analysis-close').classList.remove('hidden');
    logMsg(`Xong tiến trình so sánh!`, '#a78bfa');
}

function closeAnalysisModal() {
    document.getElementById('analysis-modal').classList.add('hidden');
    document.getElementById('analysis-bar').style.width = `0%`;
    document.getElementById('analysis-title').innerText = "Đang phân tích LLM_Only";
    document.getElementById('analysis-spinner').classList.remove('hidden');
    const logEl = document.getElementById('analysis-logs');
    if (logEl) logEl.innerHTML = '';
    // Tải lại trang/danh sách
    loadExplorerCalls();
}

// ============================================
// HIỂN THỊ CHI TIẾT CUỘC GỌI
// ============================================
async function selectCall(callId) {
    currentSelectedCallId = callId;
    
    // Đổi trạng thái UI
    document.getElementById('preview-placeholder').classList.add('hidden');
    document.getElementById('preview-toggles').classList.remove('hidden');
    
    // Mặc định luôn hiện Summary
    switchPreviewMode('summary');
    
    try {
        const res = await fetch(`/api/v1/demo/transcripts/${callId}?tenant_id=${currentTenantId}`);
        currentCallData = await res.json();
        
        // Update Title with Prompt and Model if available
        let titleText = `Kết quả: ${callId.substring(0,8)}`;
        let dateText = '';
        
        if (currentCallData.call_analysis) {
            const promptName = currentCallData.call_analysis.pipeline_version || 'LLM_ONLY';
            const modelName = currentCallData.call_analysis.summary_model || 'N/A';
            titleText += ` <span class="text-xs text-primary-600 bg-primary-50 px-2 py-0.5 rounded-full ml-2 lowercase normal-case tracking-normal border border-primary-100">💻 ${promptName} | 🤖 ${modelName}</span>`;
            
            if (currentCallData.analysis_created_at) {
                dateText = `Phân tích lúc: ${new Date(currentCallData.analysis_created_at).toLocaleString('vi-VN')}`;
            }
        }
        
        document.getElementById('preview-title').innerHTML = titleText;
        const dateEl = document.getElementById('preview-date');
        if (dateText) {
            dateEl.innerText = dateText;
            dateEl.classList.remove('hidden');
        } else {
            dateEl.classList.add('hidden');
        }
        
        // Render Compare Tabs if they exist
        renderCompareTabs(callId);
        
        renderSummary(currentCallData);
        renderTranscript(currentCallData);
        
    } catch (e) {
        console.error('Error viewing call:', e);
        alert('Lỗi khi tải chi tiết cuộc gọi!');
    }
}

function renderCompareTabs(callId) {
    const existing = document.getElementById('compare-tabs');
    if (existing) existing.remove();

    if (window.compareResults && window.compareResults[callId] && Object.keys(window.compareResults[callId].models).length > 0) {
        let html = `<div class="flex items-center gap-2 mt-4 bg-slate-50 p-1.5 rounded-lg border border-slate-200 inline-flex" id="compare-tabs">`;
        html += `<span class="text-xs text-slate-500 px-2 font-semibold uppercase">So sánh AI:</span>`;
        html += `<button onclick="switchCompareData('db')" class="px-3 py-1 text-xs font-bold rounded-md bg-white text-primary-600 shadow-sm transition-all" id="tab-db">Dữ liệu gốc (DB)</button>`;
        
        const models = Object.keys(window.compareResults[callId].models);
        models.forEach(m => {
            html += `<button onclick="switchCompareData('${m}')" class="px-3 py-1 text-xs font-bold rounded-md text-slate-500 hover:text-slate-700 transition-all" id="tab-${m}">${m}</button>`;
        });
        
        html += `</div>`;
        const tabsContainer = document.createElement('div');
        tabsContainer.innerHTML = html;
        document.getElementById('preview-toggles').parentElement.after(tabsContainer.firstElementChild);
    }
}

window.currentActiveModel = 'db';

function switchCompareData(modelName) {
    window.currentActiveModel = modelName;
    const cid = currentSelectedCallId;
    
    // Update active tab style
    const tabsContainer = document.getElementById('compare-tabs');
    if (tabsContainer) {
        Array.from(tabsContainer.children).forEach(btn => {
            btn.className = "px-3 py-1 text-xs font-bold rounded-md text-slate-500 hover:text-slate-700 transition-all";
        });
        const activeBtn = document.getElementById(`tab-${modelName}`);
        if (activeBtn) {
            activeBtn.className = "px-3 py-1 text-xs font-bold rounded-md bg-white text-primary-600 shadow-sm transition-all";
        }
    }
    
    if (modelName === 'db') {
        renderSummary(currentCallData);
    } else {
        if (window.compareResults && window.compareResults[cid] && window.compareResults[cid].models[modelName]) {
            const modelData = window.compareResults[cid].models[modelName];
            const qaArr = modelData.qa_evaluation_llm || modelData.qa_evaluation || [];
            // Render the raw llm analysis directly since it doesn't have the same db wrapper structure
            renderSummary({
                call_analysis: modelData,
                raw_llm_analysis: modelData,
                qa_score: qaArr.length > 0 ? qaArr.reduce((acc, curr) => (curr.scoring_type === 'deduction' || curr.scoring_type === 'penalty' || curr.auto_fail) && curr.passed ? acc - (curr.score_value||100) : acc, 100) : '--'
            });
        }
    }
}

function switchPreviewMode(mode) {
    const btnSummary = document.getElementById('btn-mode-summary');
    const btnTranscript = document.getElementById('btn-mode-transcript');
    const btnJson = document.getElementById('btn-mode-json');
    const viewSummary = document.getElementById('preview-summary');
    const viewTranscript = document.getElementById('preview-transcript');
    const viewJson = document.getElementById('preview-json');

    const activeBtnClass = "px-3 py-1 text-xs font-bold rounded-md bg-white text-primary-600 shadow-sm transition-all";
    const inactiveBtnClass = "px-3 py-1 text-xs font-bold rounded-md text-slate-500 hover:text-slate-700 transition-all";

    btnSummary.className = inactiveBtnClass;
    btnTranscript.className = inactiveBtnClass;
    btnJson.className = inactiveBtnClass;
    
    viewSummary.classList.add('hidden');
    viewSummary.classList.remove('flex');
    viewTranscript.classList.add('hidden');
    viewTranscript.classList.remove('flex');
    viewJson.classList.add('hidden');
    viewJson.classList.remove('flex');

    if (mode === 'summary') {
        btnSummary.className = activeBtnClass;
        viewSummary.classList.remove('hidden');
        viewSummary.classList.add('flex');
    } else if (mode === 'transcript') {
        btnTranscript.className = activeBtnClass;
        viewTranscript.classList.remove('hidden');
        viewTranscript.classList.add('flex');
    } else if (mode === 'json') {
        btnJson.className = activeBtnClass;
        viewJson.classList.remove('hidden');
        viewJson.classList.add('flex');
    }
}

function showQADetails() {
    let qaEval = null;
    
    if (window.currentActiveModel === 'db') {
        if (currentCallData && currentCallData.raw_llm_analysis) {
            qaEval = currentCallData.raw_llm_analysis.qa_evaluation_llm || currentCallData.raw_llm_analysis.qa_evaluation;
        }
    } else {
        const cid = currentSelectedCallId;
        if (window.compareResults && window.compareResults[cid] && window.compareResults[cid].models[window.currentActiveModel]) {
            const modelData = window.compareResults[cid].models[window.currentActiveModel];
            qaEval = modelData.qa_evaluation_llm || (modelData.qa_evaluation || []);
        }
    }
    
    if (!qaEval || qaEval.length === 0) {
        alert('Không có chi tiết QA cho cuộc gọi/model này.');
        return;
    }
    
    let additions = [];
    let deductions = [];
    
    qaEval.forEach(q => {
        if (q.scoring_type === 'deduction' || q.scoring_type === 'penalty' || q.auto_fail) {
            deductions.push(q);
        } else {
            additions.push(q);
        }
    });

    let html = '';
    
    if (additions.length > 0) {
        html += '<h3 class="font-bold text-slate-800 mb-3 border-b pb-2">✅ Tiêu chí cộng điểm</h3><div class="space-y-3 mb-6">';
        additions.forEach(q => {
            const isPassed = q.passed === true;
            const colorClass = isPassed ? 'text-emerald-600' : 'text-slate-500';
            const bgClass = isPassed ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-200';
            const icon = isPassed ? '✅' : '❌';
            const scoreText = isPassed ? `+${q.score_value || 1} điểm` : '0 điểm';
            
            html += renderCard(q, bgClass, icon, colorClass, scoreText);
        });
        html += '</div>';
    }

    if (deductions.length > 0) {
        html += '<h3 class="font-bold text-slate-800 mb-3 border-b pb-2 text-rose-700">⚠️ Tiêu chí phạt & Điểm liệt</h3><div class="space-y-3">';
        deductions.forEach(q => {
            const isPassed = q.passed === true; // true means violated!
            const colorClass = isPassed ? 'text-rose-600' : 'text-emerald-600';
            const bgClass = isPassed ? 'bg-rose-50 border-rose-200' : 'bg-emerald-50 border-emerald-200';
            const icon = isPassed ? '❌ (Vi phạm)' : '✅ (Tốt)';
            
            let scoreText = isPassed ? `-${q.score_value || 100} điểm` : '0 điểm';
            if (isPassed && q.auto_fail) {
                scoreText = 'ĐIỂM LIỆT (Về 0)';
            }
            
            html += renderCard(q, bgClass, icon, colorClass, scoreText);
        });
        html += '</div>';
    }
    
    function renderCard(q, bgClass, icon, colorClass, scoreText) {
        return `
            <div class="p-4 border rounded-lg ${bgClass}">
                <div class="flex justify-between items-start mb-2">
                    <h4 class="font-bold text-slate-800 text-sm flex items-center gap-2">
                        ${icon} ${q.code || ''}: ${q.criterion}
                    </h4>
                    <span class="text-xs font-bold px-2 py-1 rounded bg-white shadow-sm border ${colorClass}">
                        ${scoreText}
                    </span>
                </div>
                <p class="text-xs text-slate-500 mb-2"><i>Mô tả: ${q.rule_description || '--'}</i></p>
                <div class="bg-white p-3 rounded border text-sm text-slate-700">
                    <span class="font-bold">Lý do:</span> ${q.reason || 'Không có giải thích'}
                </div>
            </div>
        `;
    }
    
    document.getElementById('qa-modal-content').innerHTML = html;
    document.getElementById('qa-modal').classList.remove('hidden');
}

function closeQADetails() {
    document.getElementById('qa-modal').classList.add('hidden');
}

function renderSummary(data) {
    // Check if call is analyzed by looking for call_analysis or qa_score
    const isAnalyzed = data.call_analysis != null || data.qa_score != null;
    
    if (!isAnalyzed) {
        document.getElementById('not-analyzed-warning').classList.remove('hidden');
        document.getElementById('summary-content').classList.add('hidden');
        document.getElementById('summary-content').classList.remove('flex');
        document.getElementById('btn-qa-details').style.display = 'none';
        return;
    }
    
    document.getElementById('not-analyzed-warning').classList.add('hidden');
    document.getElementById('summary-content').classList.remove('hidden');
    document.getElementById('summary-content').classList.add('flex');

    // Cập nhật điểm QA
    let qaTotal = '--';
    if (data.qa_score?.total_score != null) qaTotal = data.qa_score.total_score;
    else if (data.qa_score != null) qaTotal = data.qa_score;
    
    document.getElementById('preview-qa').innerText = `${qaTotal}`;
    if(qaTotal !== '--' && qaTotal >= 80) document.getElementById('preview-qa').className = 'text-3xl font-bold text-emerald-600';
    else if(qaTotal !== '--' && qaTotal >= 50) document.getElementById('preview-qa').className = 'text-3xl font-bold text-amber-500';
    else document.getElementById('preview-qa').className = 'text-3xl font-bold text-rose-600';

    if (data.raw_llm_analysis && (data.raw_llm_analysis.qa_evaluation_llm || data.raw_llm_analysis.qa_evaluation)) {
        if (document.getElementById('btn-qa-details')) document.getElementById('btn-qa-details').style.display = 'block';
    } else {
        if (document.getElementById('btn-qa-details')) document.getElementById('btn-qa-details').style.display = 'none';
    }

    const analysisObj = data.call_analysis || data.post_call_summary || {};

    // Sentiment Tổng quan, KH, Agent
    const rawLlm = data.raw_llm_analysis || {};
    
    // Map function for Sentiment
    const getSentiment = (val) => {
        if (!val) return '--';
        const s = val.toLowerCase();
        if(s.includes('positive') || s.includes('hài lòng')) return 'Tích cực 😊';
        if(s.includes('negative') || s.includes('tức giận') || s.includes('không hài lòng')) return 'Tiêu cực 😠';
        return 'Bình thường 😐';
    };

    const sentCust = data.sentiment_customer || analysisObj.customer_sentiment || rawLlm.sentiment_customer || '--';
    const sentAgent = data.sentiment_agent || analysisObj.agent_sentiment || rawLlm.sentiment_agent || '--';
    const sentAll = data.sentiment_overall || analysisObj.overall_sentiment || rawLlm.sentiment_overall || '--';

    if (document.getElementById('preview-sentiment-customer')) {
        document.getElementById('preview-sentiment-customer').innerText = getSentiment(sentCust);
    }
    if (document.getElementById('preview-sentiment-agent')) {
        document.getElementById('preview-sentiment-agent').innerText = getSentiment(sentAgent);
    }
    if (document.getElementById('preview-sentiment-overall')) {
        document.getElementById('preview-sentiment-overall').innerText = getSentiment(sentAll);
    }

    // Emotion KH, Agent, Tổng thể
    const dictEmotion = {
        'anger': 'Tức giận 😡',
        'unhappy': 'Không vui 😞',
        'mid_priority': 'Gấp gáp ⏱️',
        'normal': 'Bình thường 😐'
    };
    const emCust = data.emotion_customer || rawLlm.emotion_customer || 'normal';
    const emAgent = data.emotion_agent || rawLlm.emotion_agent || 'normal';
    const emAll = data.emotion_overall || rawLlm.emotion_overall || 'normal';
    if(document.getElementById('preview-emotion-customer')) {
        document.getElementById('preview-emotion-customer').innerText = dictEmotion[emCust.toLowerCase()] || emCust;
    }
    if(document.getElementById('preview-emotion-agent')) {
        document.getElementById('preview-emotion-agent').innerText = dictEmotion[emAgent.toLowerCase()] || emAgent;
    }
    if(document.getElementById('preview-emotion-overall')) {
        document.getElementById('preview-emotion-overall').innerText = dictEmotion[emAll.toLowerCase()] || emAll;
    }



    // Tóm tắt văn bản
    let summaryText = 'Không có tóm tắt.';
    
    if (analysisObj && analysisObj.summary && typeof analysisObj.summary === 'object' && !analysisObj.summary_text) {
        let md = `**Vấn đề:** ${analysisObj.summary.issue || ''}\n\n`;
        md += `**Xử lý:** ${analysisObj.summary.resolution || ''}\n\n`;
        if (analysisObj.summary.summary_bullets && analysisObj.summary.summary_bullets.length > 0) {
            md += "**Chi tiết:**\n" + analysisObj.summary.summary_bullets.map(b => `- ${b}`).join("\n");
        }
        summaryText = marked.parse(md);
    } else if (data.call_analysis && data.call_analysis.summary_text) {
        let md = data.call_analysis.summary_text;
        if (data.call_analysis.summary_bullets && data.call_analysis.summary_bullets.length > 0) {
            md += "\n\n**Chi tiết:**\n" + data.call_analysis.summary_bullets.map(b => `- ${b}`).join("\n");
        }
        summaryText = marked.parse(md);
    } else if (data.post_call_summary) {
        let md = `**Đánh giá:** ${data.post_call_summary.agent_performance_evaluation || ''}\n\n`;
        md += `**Next Action:** ${data.post_call_summary.next_best_action || ''}\n\n`;
        md += `**Khách hàng phản hồi:** ${data.post_call_summary.customer_sentiment || ''}\n`;
        summaryText = marked.parse(md);
    }
    
    // Prepend reasoning if available
    let reasoningHtml = '';
    const reasoningText = rawLlm.reasoning || (analysisObj.extracted_fields && analysisObj.extracted_fields.raw_llm_analysis && analysisObj.extracted_fields.raw_llm_analysis.reasoning);
    if (reasoningText) {
        reasoningHtml = `<div class="bg-blue-50 border-l-4 border-blue-500 p-3 mb-4 rounded-r-lg text-blue-900 text-sm italic">
            <span class="font-bold block text-blue-700 not-italic mb-1">🤔 Logic Suy luận (Reasoning):</span>
            ${reasoningText}
        </div>`;
    }
    summaryText = reasoningHtml + summaryText;

    // Add Entities if available
    let entities = [];
    if (analysisObj && analysisObj.entities) {
        entities = analysisObj.entities;
    } else if (data.call_analysis && data.call_analysis.extracted_fields && data.call_analysis.extracted_fields.entities) {
        entities = data.call_analysis.extracted_fields.entities;
    }
    
    if (entities && entities.length > 0) {
        summaryText += '<h4 class="font-bold text-slate-700 mt-4 mb-2 text-xs uppercase">Entities</h4>';
        summaryText += '<div class="flex flex-wrap gap-2">';
        entities.forEach(ent => {
            const type = ent.type || ent.entity_type || 'Entity';
            const text = ent.text || ent.entity_value || ent.value || '';
            if (text) {
                summaryText += `<span class="bg-blue-50 border border-blue-200 text-blue-700 px-2 py-1 rounded text-xs"><b>${type}:</b> ${text}</span>`;
            }
        });
        summaryText += '</div>';
    }
    
    document.getElementById('preview-summary-text').innerHTML = summaryText;
    
    // JSON Raw LLM
    const jsonContent = data.raw_llm_analysis || analysisObj;
    
    // Đảm bảo thứ tự key hiển thị giống schema trong prompt
    const desiredOrder = [
        "reasoning", "sentiment_overall", "sentiment_customer", "sentiment_agent",
        "emotion_overall", "emotion_agent", "emotion_customer", "topics", "summary",
        "entities", "escalation_analysis", "toxicity_analysis", "nba_recommendations",
        "qa_evaluation"
    ];
    
    let orderedJson = {};
    if (jsonContent && typeof jsonContent === 'object') {
        desiredOrder.forEach(key => {
            if (key in jsonContent) {
                orderedJson[key] = jsonContent[key];
            }
        });
        // Thêm các key còn lại nếu có
        Object.keys(jsonContent).forEach(key => {
            if (!desiredOrder.includes(key)) {
                orderedJson[key] = jsonContent[key];
            }
        });
    } else {
        orderedJson = jsonContent;
    }
    
    document.getElementById('preview-json-content').innerText = JSON.stringify(orderedJson, null, 2);
}

function renderTranscript(data) {
    const chatBox = document.getElementById('preview-chat-box');
    
    if (!data.transcript_json || data.transcript_json.length === 0) {
        chatBox.innerHTML = '<div class="text-center text-slate-400 text-sm mt-10">Không có dữ liệu hội thoại</div>';
        return;
    }

    let html = '';
    data.transcript_json.forEach((m, idx) => {
        const turnId = m.turn_id || (idx + 1);
        const isCust = (m.speaker || '').toLowerCase() === 'customer';
        const alignClass = isCust ? 'justify-start' : 'justify-end';
        const bgClass = isCust ? 'bg-slate-700/80 text-white rounded-bl-none mr-8' : 'bg-blue-600/90 text-white rounded-br-none ml-8';
        const iconClass = isCust ? '👤' : '🤖';
        const senderName = isCust ? 'Customer' : 'Agent';
        
        html += `
            <div class="flex flex-col mb-4 w-full ${alignClass}">
                <div class="flex items-end gap-2 w-full ${isCust ? 'flex-row' : 'flex-row-reverse'}">
                    <div class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-slate-800 border border-slate-600 text-xs">${iconClass}</div>
                    <div class="flex flex-col gap-1 max-w-[85%]">
                        <span class="text-[10px] text-slate-400 px-1 ${isCust ? 'text-left' : 'text-right'}">${senderName} • Turn ${turnId}</span>
                        <div class="px-3.5 py-2.5 rounded-2xl ${bgClass} shadow-md text-sm border border-slate-600/30">
                            ${m.text}
                        </div>
                    </div>
                </div>
            </div>
        `;
    });
    chatBox.innerHTML = html;
}

// ============================================
// BIEU DO ANALYTICS (CHART.JS)
// ============================================
let chartQA, chartIntent, chartSentiment, chartEscalation, chartNBA, chartToxicity;

function updateAnalyticsCharts(calls) {
    const processedCalls = calls.filter(c => c.status === 'processed' || c.message_analyses?.length > 0 || c.post_call_summary || c.call_analysis);
    
    // 1. QA Score
    const qaScores = { 'High (>=80)': 0, 'Medium (50-79)': 0, 'Low (<50)': 0 };
    // 2. Intents
    const intents = {};
    // 3. Sentiment
    const sentiments = { 'Positive': 0, 'Neutral': 0, 'Negative': 0 };
    // 4. Escalation
    const escalations = { 'None/Normal': 0, 'Medium': 0, 'High/Critical': 0 };
    // 5. NBA Priority
    const priorities = { 'Mức độ 1': 0, 'Mức độ 2': 0, 'Mức độ 3': 0, 'Mức độ 4': 0, 'Không rõ': 0 };
    // 6. Toxicity
    const toxicities = { 'None': 0, 'Toxic': 0 };

    processedCalls.forEach(c => {
        // QA Score
        let score = c.qa_score;
        if (typeof score === 'object' && score !== null) score = score.total_score;
        if (score != null) {
            if (score >= 80) qaScores['High (>=80)']++;
            else if (score >= 50) qaScores['Medium (50-79)']++;
            else qaScores['Low (<50)']++;
        }

        const analysisObj = typeof c.raw_llm_analysis === 'object' && c.raw_llm_analysis !== null ? c.raw_llm_analysis : (c.call_analysis || c.post_call_summary || {});

        // Intent
        if (c.main_intent) {
            intents[c.main_intent] = (intents[c.main_intent] || 0) + 1;
        }

        // Sentiment
        const sent = (analysisObj.sentiment_trend || analysisObj.customer_sentiment || '').toLowerCase();
        if (sent.includes('positive') || sent.includes('hài lòng') || sent.includes('tích cực')) sentiments['Positive']++;
        else if (sent.includes('negative') || sent.includes('tức giận') || sent.includes('không hài lòng') || sent.includes('tiêu cực')) sentiments['Negative']++;
        else sentiments['Neutral']++;

        // Escalation
        const escLevel = (analysisObj.escalation_level || 'none').toLowerCase();
        if (escLevel === 'high' || escLevel === 'critical') escalations['High/Critical']++;
        else if (escLevel === 'medium') escalations['Medium']++;
        else escalations['None/Normal']++;

        // Priority
        const p = (c.nba_priority || '').toLowerCase();
        if (p.includes('ngay lập tức')) priorities['Mức độ 1']++;
        else if (p.includes('thời gian nhất định')) priorities['Mức độ 2']++;
        else if (p.includes('đã xử lý')) priorities['Mức độ 3']++;
        else if (p.includes('ngoài giờ')) priorities['Mức độ 4']++;
        else if (c.nba) priorities['Không rõ']++;

        // Toxicity
        const toxTags = analysisObj.toxicity_tags || [];
        if (toxTags.length > 0) toxicities['Toxic']++;
        else toxicities['None']++;
    });

    // Helper to draw/update charts
    const drawChart = (chartInstance, ctxId, type, dataLabels, dataValues, colors, title, extraOptions = {}) => {
        const ctx = document.getElementById(ctxId);
        if (!ctx) return null;
        if (chartInstance) chartInstance.destroy();
        
        return new Chart(ctx, {
            type: type,
            data: {
                labels: dataLabels,
                datasets: [{
                    label: title,
                    data: dataValues,
                    backgroundColor: colors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { 
                        position: type === 'pie' || type === 'doughnut' ? 'right' : 'top',
                        labels: { boxWidth: 12, font: { size: 10 } }
                    },
                    ...extraOptions
                }
            }
        });
    };

    // Colors
    const pieColors = ['#10B981', '#F59E0B', '#EF4444', '#3B82F6', '#8B5CF6'];
    const barColors = ['#3B82F6', '#8B5CF6', '#EC4899', '#10B981', '#F59E0B'];

    // Draw charts
    chartQA = drawChart(chartQA, 'chart-qa', 'doughnut', Object.keys(qaScores), Object.values(qaScores), pieColors, 'QA Score');
    
    chartSentiment = drawChart(chartSentiment, 'chart-sentiment', 'pie', Object.keys(sentiments), Object.values(sentiments), ['#10B981', '#94A3B8', '#EF4444'], 'Sentiment');
    
    chartEscalation = drawChart(chartEscalation, 'chart-escalation', 'pie', Object.keys(escalations), Object.values(escalations), pieColors, 'Escalation');
    
    chartToxicity = drawChart(chartToxicity, 'chart-toxicity', 'pie', Object.keys(toxicities), Object.values(toxicities), ['#10B981', '#EF4444'], 'Toxicity');

    const sortedIntents = Object.entries(intents).sort((a,b) => b[1] - a[1]).slice(0, 5); // top 5
    chartIntent = drawChart(chartIntent, 'chart-intent', 'bar', sortedIntents.map(x=>x[0]), sortedIntents.map(x=>x[1]), barColors, 'Main Intent');

    // Draw NBA Priority
    Object.keys(priorities).forEach(k => { if(priorities[k] === 0) delete priorities[k]; });
    const priorityOptions = {
        tooltip: {
            callbacks: {
                label: function(context) {
                    let label = context.label || '';
                    if (label === 'Mức độ 1') label = 'Xử lý ngay lập tức';
                    else if (label === 'Mức độ 2') label = 'Xử lý trong thời gian nhất định';
                    else if (label === 'Mức độ 3') label = 'Đã xử lý trong cuộc gọi';
                    else if (label === 'Mức độ 4') label = 'Xử lý ngoài giờ hành chính';
                    
                    if (label) label += ': ';
                    if (context.parsed !== null) label += context.parsed;
                    return label;
                }
            }
        }
    };
    chartNBA = drawChart(chartNBA, 'chart-nba', 'pie', Object.keys(priorities), Object.values(priorities), pieColors, 'Priority', priorityOptions);
}
