// Sample Data for easy testing
        const sampleData = [
            { "turn": 1, "speaker": "agent", "text": "Dạ VoiceIQ xin chào anh ạ, em gọi hỗ trợ thông tin khóa học ACCA cho mình đây ạ.", "start_time": 0.0, "end_time": 4.0 },
            { "turn": 2, "speaker": "customer", "text": "À ừ em tư vấn cho anh lộ trình học ACCA nhé.", "start_time": 4.0, "end_time": 7.5 },
            { "turn": 3, "speaker": "agent", "text": "Dạ vâng, để em giới thiệu lộ trình học bên em. Khóa học được chia làm 3 giai đoạn cơ bản đến nâng cao ạ.", "start_time": 8.0, "end_time": 12.0 },
            { "turn": 4, "speaker": "customer", "text": "Thế học phí bao nhiêu em? Anh muốn đăng ký luôn.", "start_time": 12.0, "end_time": 15.0 },
            { "turn": 5, "speaker": "agent", "text": "Dạ học phí toàn khóa hiện đang có ưu đãi giảm 20% ạ, để em gửi link hướng dẫn đăng ký cho anh nhé.", "start_time": 15.0, "end_time": 20.0 }
        ];

        document.getElementById('transcript-input').value = JSON.stringify(sampleData, null, 2);

        let ws;
        let isSimulating = false;
        let analysisHistory = {}; // Luôn lưu kết quả phân tích
        let liveTurns = []; // Lưu trữ các lượt thoại đang hiển thị để xuất JSON
        let taxonomyData = { topics: [], intents: [] };
        window.hasUnsavedTaxonomy = false;

        window.addEventListener('beforeunload', function (e) {
            if (window.hasUnsavedTaxonomy) {
                const confirmationMessage = 'Bạn có thay đổi nhãn chưa được lưu. Nếu rời đi, các thay đổi sẽ bị mất.';
                e.returnValue = confirmationMessage; 
                return confirmationMessage;
            }
        });

        const startBtn = document.getElementById('start-btn');
        const chatBox = document.getElementById('chat-box');
        const connStatus = document.getElementById('connection-status');

        window.openTurnInspector = function(turnId) {
            const data = analysisHistory[turnId];
            if (!data) return;
            updateAIInsightsBoard(data);
        };

        function createMessageBubbleElement(m) {
            // m: { turn_id, speaker, text, intent_label, topic_label, toxicity_score, ... }
            const isCust = (m.speaker || '').toLowerCase() === 'customer';
            // Khách hàng bên trái (justify-start), Agent bên phải (justify-end)
            const alignClass = isCust ? 'justify-start' : 'justify-end';
            // Màu sắc: Khách (Xám đậm - trái), Agent (Xanh dương - phải)
            const bgClass = isCust ? 'bg-slate-700/80 text-white rounded-bl-none mr-8' : 'bg-blue-600/90 text-white rounded-br-none ml-8';
            const iconClass = isCust ? '👤' : '🤖';
            const senderName = isCust ? 'Customer' : 'Agent';
            
            const msgDiv = document.createElement('div');
            msgDiv.className = `flex flex-col mb-4 w-full ${alignClass}`;
            msgDiv.id = `msg-wrap-${m.turn_id}`;
            
            let badgesHtml = '';
            if (m.intent_label && m.intent_label !== 'None') {
                badgesHtml += `<span class="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">${m.intent_label}</span>`;
            }
            if (m.topic_label && m.topic_label !== 'Unknown') {
                badgesHtml += `<span class="inline-flex items-center rounded-md bg-purple-50 px-2 py-1 text-xs font-medium text-purple-700 ring-1 ring-inset ring-purple-700/10">${m.topic_label}</span>`;
            }
            if (m.toxicity_score >= 0.5) {
                badgesHtml += `<span class="inline-flex items-center rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-700/10">⚠️ Độc hại</span>`;
            }
            // Thêm khoảng trống nếu chưa có badge (để dành chỗ cho WS append sau)
            
            msgDiv.innerHTML = `
                <div class="flex items-end gap-2 w-full ${isCust ? 'flex-row' : 'flex-row-reverse'} cursor-pointer hover:opacity-90 transition-opacity" onclick="openTurnInspector(${m.turn_id})">
                    <div class="w-6 h-6 rounded-full flex items-center justify-center shrink-0 bg-slate-800 border border-slate-600 text-xs">${iconClass}</div>
                    <div class="flex flex-col gap-1 max-w-[85%]">
                        <span class="text-[10px] text-slate-400 px-1 ${isCust ? 'text-left' : 'text-right'}">${senderName} • Turn ${m.turn_id}</span>
                        <div class="px-3.5 py-2.5 rounded-2xl ${bgClass} shadow-md text-sm border border-slate-600/30">
                            ${m.text}
                        </div>
                        <div id="badges-${m.turn_id}" class="flex gap-1 flex-wrap mt-1 justify-${isCust ? 'start' : 'end'} min-h-[20px]">
                            ${badgesHtml}
                        </div>
                    </div>
                </div>
            `;
            return msgDiv;
        }

        function appendMessage(speaker, text, turnId) {
            // Lưu vào mảng để xuất JSON đồng bộ
            const existingIdx = liveTurns.findIndex(t => t.turn === turnId);
            if (existingIdx === -1) {
                liveTurns.push({ turn: turnId, speaker, text });
            }

            const el = createMessageBubbleElement({ turn_id: turnId, speaker: speaker, text: text });
            chatBox.appendChild(el);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function copyLiveJSON() {
            if (!liveTurns || liveTurns.length === 0) {
                alert("Không có dữ liệu hội thoại để copy!");
                return;
            }
            const combinedData = liveTurns.map((t) => {
                const ai = analysisHistory[t.turn] || {};
                return {
                    turn: t.turn,
                    speaker: t.speaker,
                    text: t.text,
                    topic: ai.topic_label || null,
                    topic_confidence: ai.topic_confidence || null,
                    intent: ai.intent_label || null,
                    intent_confidence: ai.intent_confidence || null,
                    sentiment: ai.sentiment || null,
                    sentiment_confi: ai.sentiment_score || null
                };
            });
            navigator.clipboard.writeText(JSON.stringify(combinedData, null, 2));
            alert('Copied JSON from Live Dialog Stream!');
        }

        function updateAIInsightsBoard(data) {
            if (!data) return;
            
            // Turn ID
            const turnEl = document.getElementById('ai-board-turn');
            if(turnEl) turnEl.innerText = `Turn #${data.turn_id || '--'}`;
            
            // Topic & Intent
            document.getElementById('ai-board-topic').innerText = data.topic_label || 'N/A';
            document.getElementById('ai-board-topic-conf').innerText = data.topic_confidence ? Math.round(data.topic_confidence * 100) + '%' : '--';
            document.getElementById('ai-board-intent').innerText = data.intent_label || 'N/A';
            document.getElementById('ai-board-intent-conf').innerText = data.intent_confidence ? Math.round(data.intent_confidence * 100) + '%' : '--';
            
            // Sentiment
            let sentimentConf = data.sentiment_score ? ` (${Math.round(data.sentiment_score * 100)}%)` : '';
            document.getElementById('ai-board-sentiment').innerText = (data.sentiment || 'Neutral') + sentimentConf;
            let icon = '😐';
            if (data.sentiment === 'negative') icon = '😠';
            if (data.sentiment === 'positive') icon = '😊';
            document.getElementById('ai-board-sentiment-icon').innerText = icon;
            
            // QA Score
            const qaEl = document.getElementById('ai-board-qa');
            if (qaEl) {
                if (data.qa_compliance) {
                    qaEl.innerHTML = `<span class="text-green-600 font-medium">✅ Đạt (Tuân thủ kịch bản)</span>`;
                } else if (data.intent_label === 'Cam kết quá lời') {
                    qaEl.innerHTML = `<span class="text-red-600 font-medium">❌ Vi phạm (Cam kết lố)</span>`;
                } else {
                    qaEl.innerHTML = `<span class="text-slate-400 italic">--</span>`;
                }
            }
            
            // NBA Rule Trigger
            const nbaEl = document.getElementById('ai-board-nba');
            if (nbaEl) {
                const intent = data.intent_label || '';
                const isCust = (data.speaker || '').toLowerCase() === 'customer';
                let nbaTrigger = '';
                
                if (isCust) {
                    if (["Hỏi học phí", "Hỏi ngày khai giảng", "Yêu cầu đăng ký", "Hỏi lệ phí thi, hội viên", "Hỏi thông tin khóa học"].includes(intent)) {
                        nbaTrigger = `🔍 Khách hỏi mua -> Push Promotion`;
                    } else if (intent === "Từ chối vì giá") {
                        nbaTrigger = `💸 Objection (Giá) -> Deal giảm học phí`;
                    } else if (intent === "Từ chối vì bận" || intent === "Trì hoãn quyết định") {
                        nbaTrigger = `⏳ Objection (Thời gian) -> Follow-up tháng sau`;
                    }
                }
                
                if (nbaTrigger) {
                    nbaEl.innerHTML = `<span class="bg-amber-100 text-amber-700 px-2 py-0.5 rounded text-[11px] font-bold">⚡ ${nbaTrigger}</span>`;
                } else {
                    nbaEl.innerHTML = `<span class="text-slate-400 italic">--</span>`;
                }
            }
            
            // NER
            const nerBox = document.getElementById('ai-board-ner');
            if (nerBox) {
                if (data.entities && data.entities.length > 0) {
                    nerBox.innerHTML = '';
                    data.entities.forEach(ent => {
                        nerBox.innerHTML += `<div class="mb-1">
                            <span class="text-[10px] font-bold text-indigo-500 uppercase">${ent.entity_type || ent.label || ''}:</span>
                            <span class="text-slate-700 text-sm ml-1">${ent.entity_value || ent.text || ''}</span>
                        </div>`;
                    });
                } else {
                    nerBox.innerHTML = '<div class="text-xs text-slate-400 italic">-- Không phát hiện --</div>';
                }
            }
            
            // Outbox Events
            const outboxBox = document.getElementById('ai-board-outbox');
            if (outboxBox) {
                if (data.outbox_events && data.outbox_events.length > 0) {
                    outboxBox.innerHTML = '';
                    data.outbox_events.forEach(ev => {
                        outboxBox.innerHTML += `<div class="mb-1">
                            <span class="text-[10px] font-bold text-rose-600 uppercase">⚡ ${ev.event_name}</span>
                            <div class="text-slate-500 text-xs font-mono ml-3 truncate" title='${JSON.stringify(ev.payload)}'>${JSON.stringify(ev.payload)}</div>
                        </div>`;
                    });
                } else {
                    outboxBox.innerHTML = '<div class="text-xs text-slate-400 italic">-- Trống --</div>';
                }
            }
            
            // Latency
            const latEl = document.getElementById('ai-board-latency');
            if(latEl && data.latency_ms) latEl.innerText = `Phân tích trong ${data.latency_ms}ms`;
        }
 
        async function startSimulation() {
            if (isSimulating) return;
            
            const tenantId = document.getElementById('tenant-id').value.trim();
            const callId = document.getElementById('call-id').value.trim();
            const rawData = document.getElementById('transcript-input').value;
            let turns = [];

            try {
                turns = JSON.parse(rawData);
            } catch(e) {
                alert("JSON không hợp lệ!");
                return;
            }

            chatBox.innerHTML = '';
            if (document.getElementById('qa-score-badge')) document.getElementById('qa-score-badge').innerText = '--%';
            
            // Xóa dữ liệu cũ trong bảng realtime
            const rtContainer = document.getElementById('realtime-tables-container');
            if (rtContainer) rtContainer.classList.remove('hidden');
            const rtMsgTbBody = document.getElementById('rt-tb-msg');
            if (rtMsgTbBody) rtMsgTbBody.innerHTML = '';
            const rtEntTbBody = document.getElementById('rt-tb-ent');
            if (rtEntTbBody) rtEntTbBody.innerHTML = '';
            const rtEvtTbBody = document.getElementById('rt-tb-evt');
            if (rtEvtTbBody) rtEvtTbBody.innerHTML = '';
            
            // Connect WS
            if (ws) ws.close();
            const labelFormat = document.getElementById('label-format').value;
            ws = new WebSocket(`ws://localhost:8000/ws/v1/live/${callId}?tenant_id=${tenantId}&label_format=${labelFormat}`);
            
            ws.onopen = () => {
                connStatus.innerHTML = '🟢 Connected';
                connStatus.className = 'text-sm bg-green-500 px-3 py-1 rounded-full';
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.turn_id) {
                    analysisHistory[data.turn_id] = data;
                    const statusIcon = document.getElementById(`status-${data.turn_id}`);
                    if (statusIcon) {
                        const threshold = parseFloat(document.getElementById('label-threshold').value);
                        let isBelow = false;
                        if (data.topic_label && data.topic_label !== 'Unknown' && data.topic_confidence < threshold) isBelow = true;
                        if (data.intent_label && data.intent_label !== 'None' && data.intent_confidence < threshold) isBelow = true;
                        if (data.sentiment_score && data.sentiment_score < threshold) isBelow = true;
                        
                        statusIcon.innerText = isBelow ? '❌' : '✅';
                    }

                    const badgeContainer = document.getElementById(`badges-${data.turn_id}`);
                    if (badgeContainer) {
                        badgeContainer.innerHTML = '';
                        
                        // 1. Thêm Topic & Intent Badges (Từ AI trả về)
                        if (data.intent_label && data.intent_label !== 'None') {
                            badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">${data.intent_label}</span>`;
                        }
                        if (data.topic_label && data.topic_label !== 'Unknown') {
                            badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-purple-50 px-2 py-1 text-xs font-medium text-purple-700 ring-1 ring-inset ring-purple-700/10">${data.topic_label}</span>`;
                        }
                        if (data.toxicity_score >= 0.5) {
                            badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-700/10">⚠️ Độc hại</span>`;
                        }

                        // 2. Thêm các Logic Badges (Dựa theo quy tắc)
                        const isCust = (data.speaker || '').toLowerCase() === 'customer';
                        const intent = data.intent_label || '';
                        
                        if (isCust) {
                            if (["Hỏi học phí", "Hỏi ngày khai giảng", "Yêu cầu đăng ký", "Hỏi lệ phí thi, hội viên", "Hỏi thông tin khóa học"].includes(intent)) {
                                badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-green-50 px-2 py-1 text-xs font-medium text-green-700 ring-1 ring-inset ring-green-600/20">🛒 Tín hiệu mua</span>`;
                            }
                            const objMap = {"Từ chối vì giá": "Giá", "Từ chối vì bận": "Thời gian", "Trì hoãn quyết định": "Trì hoãn"};
                            if (objMap[intent]) {
                                badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/10">⚠️ Băn khoăn: ${objMap[intent]}</span>`;
                            }
                        } else {
                            if (data.qa_compliance) {
                                badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">✅ Tuân thủ QA</span>`;
                            }
                            if (intent.includes("Xử lý từ chối") || intent.includes("Xử lý khiếu nại")) {
                                badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-purple-50 px-2 py-1 text-xs font-medium text-purple-700 ring-1 ring-inset ring-purple-700/10">🛡️ Xử lý từ chối</span>`;
                            }
                            if (intent === "Cam kết quá lời") {
                                badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-red-50 px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/10">🚨 Cam kết lố</span>`;
                            }
                        }
                        
                        // Thêm badge hiển thị thời gian phân tích
                        if (data.latency_ms) {
                            badgeContainer.innerHTML += `<span class="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 text-[10px] font-medium text-slate-500 ring-1 ring-inset ring-slate-200/50 ml-1">⏱️ ${data.latency_ms}ms</span>`;
                        }
                    }
                }
                
                // Update bảng Insights thay vì gọi hàm cũ
                updateAIInsightsBoard(data);
                
                // Realtime Streaming cho Bảng
                const rtMsgTb = document.getElementById('rt-tb-msg');
                if (rtMsgTb) {
                    const tr = document.createElement('tr');
                    tr.className = "hover:bg-indigo-50 transition-colors";
                    tr.innerHTML = `
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 border-r text-center">${data.turn_id}</td>
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 border-r capitalize">${data.speaker || ''}</td>
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 border-r truncate max-w-[150px]" title="${data.text_content || ''}">${data.text_content || ''}</td>
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 border-r truncate max-w-[80px]" title="${data.topic_label || ''}">${data.topic_label || ''}</td>
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 border-r text-center">${data.topic_confidence ? data.topic_confidence.toFixed(2) : ''}</td>
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 border-r truncate max-w-[80px]" title="${data.intent_label || ''}">${data.intent_label || ''}</td>
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 border-r text-center">${data.intent_confidence ? data.intent_confidence.toFixed(2) : ''}</td>
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 border-r text-center">${data.sentiment || ''}</td>
                        <td class="px-2 py-1.5 text-[11px] text-gray-800 text-center">${data.sentiment_score ? data.sentiment_score.toFixed(2) : ''}</td>
                    `;
                    rtMsgTb.appendChild(tr);
                }
                
                // Note: NER, NBA, and QA UI updates are now entirely handled inside updateAIState() 
                // which is called right above this. This allows historical clicks to perfectly restore the UI state.
                
                const rtContent = document.getElementById('realtime-tables-content');
                if (rtContent) {
                    const isAtBottom = Math.abs(rtContent.scrollHeight - rtContent.scrollTop - rtContent.clientHeight) < 10;
                    if (isAtBottom) {
                        rtContent.scrollTop = rtContent.scrollHeight;
                    }
                }
            };

            ws.onclose = () => {
                connStatus.innerHTML = '🔴 Disconnected';
                connStatus.className = 'text-sm bg-indigo-800 px-3 py-1 rounded-full';
                isSimulating = false;
                startBtn.disabled = false;
                startBtn.innerText = "▶ Chạy lại mô phỏng";
                
                const jsonContent = document.getElementById('json-output-content');
                if (jsonContent) {
                    jsonContent.innerText = JSON.stringify(Object.values(analysisHistory), null, 2);
                }
            };

            isSimulating = true;
            startBtn.disabled = true;
            startBtn.innerText = "⏳ Simulating...";
            startBtn.classList.replace('bg-green-500', 'bg-gray-400');

            // Đợi WS mở
            await new Promise(r => setTimeout(r, 500));

            let currentTime = 0;
            let index = 0;
            
            for (const turn of turns) {
                index++;
                const currentTurnId = turn.turn || turn.turn_index || index;
                
                // Tính khoảng thời gian chờ (mô phỏng real-time)
                const delay = Math.max(0, turn.start_time - currentTime) * 1000;
                
                await new Promise(r => setTimeout(r, delay));
                currentTime = turn.start_time;

                appendMessage(turn.speaker, turn.text, currentTurnId);

                // Gửi lên WebSocket
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({
                        call_id: callId,
                        speaker: turn.speaker,
                        text: turn.text,
                        start_time: turn.start_time,
                        end_time: turn.end_time,
                        turn_id: currentTurnId,
                        save_to_db: true
                    }));
                }
                
                // Đợi server xử lý xong turn này trước khi bắn tiếp (tránh làm sập LLM Gateway do quá tải)
                let waitSim = 0;
                while (!analysisHistory[currentTurnId] && waitSim < 20000) {
                    await new Promise(r => setTimeout(r, 200));
                    waitSim += 200;
                }
                
                // Cập nhật currentTime thành end_time sau khi giả vờ "nói xong"
                const speakingDuration = Math.max(0.5, turn.end_time - turn.start_time) * 1000;
                await new Promise(r => setTimeout(r, speakingDuration));
                currentTime = turn.end_time;
            }
            isSimulating = false;
            startBtn.disabled = false;
            startBtn.innerText = "▶ Restart Simulation";
            startBtn.classList.replace('bg-gray-400', 'bg-green-500');

            // Đợi server trả về hết kết quả (tối đa 10 giây)
            let waitTime = 0;
            while (Object.keys(analysisHistory).length < turns.length && waitTime < 10000) {
                await new Promise(r => setTimeout(r, 500));
                waitTime += 500;
            }

            // Generate JSON output when finished
            const combinedData = turns.map((t, idx) => {
                const turnId = t.turn || t.turn_index || (idx + 1);
                const ai = analysisHistory[turnId] || {};
                return {
                    turn: turnId,
                    speaker: t.speaker,
                    text: t.text,
                    topic: ai.topic_label || null,
                    topic_confidence: ai.topic_confidence || null,
                    intent: ai.intent_label || null,
                    intent_confidence: ai.intent_confidence || null,
                    sentiment: ai.sentiment || null,
                    sentiment_confi: ai.sentiment_score || null
                };
            });
            // JSON output logic removed since the modal was deleted
        }

        async function generatePostCall() {
            const btn = document.getElementById('btn-postcall');
            const resultBox = document.getElementById('summary-result');
            const tenantId = document.getElementById('tenant-id').value.trim();
            const callId = document.getElementById('call-id').value.trim();
            const mode = document.getElementById('pipeline-mode').value;
            const rawData = document.getElementById('transcript-input').value;
            let turns = [];
            try { 
                turns = JSON.parse(rawData); 
            } catch(e) {
                alert("Lỗi: Dữ liệu JSON hội thoại không hợp lệ. Vui lòng kiểm tra lại dấu phẩy, ngoặc kép.");
                return;
            }
            if (!turns || turns.length === 0) {
                alert("Lỗi: Không có câu thoại nào để phân tích.");
                return;
            }
            
            btn.disabled = true;
            btn.innerText = "⏳ Đang chạy...";
            resultBox.classList.remove('hidden');
            resultBox.innerHTML = '<div class="text-center text-gray-500 py-4 ai-pulse">Đang gọi AI Gateway để tóm tắt...</div>';

            try {
                const isSaveToDb = (!isManualMode) ? true : false;
                
                const res = await fetch('http://localhost:8000/api/v1/demo/simulate/postcall', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        call_id: callId,
                        tenant_id: tenantId,
                        pipeline_mode: mode,
                        transcript_json: turns,
                        save_to_db: isSaveToDb,
                        label_format: document.getElementById('label-format').value,
                        threshold: parseFloat(document.getElementById('label-threshold').value)
                    })
                });
                
                const data = await res.json();
                if (!res.ok) {
                    alert("LỖI KIẾN TRÚC:\n\n" + (data.detail || "Có lỗi xảy ra") + "\n\nBước 1: Ở giao diện UI, bạn phải bật luồng Real-time (Agent Assist) và đánh dấu tick vào ô 'Lưu vào Database' rồi chạy cho xong 20 câu. Việc này giúp DB có sẵn dữ liệu của 20 câu.\nBước 2: Sau khi Real-time chạy xong, bạn mới bấm nút chạy Post-call (ở chế độ COMPOSITE) cho đúng cái call_id đó. Khi ấy DB đã có dữ liệu, code sẽ tự động bốc 20 câu lên gộp Topic/Intent và gọi LLM ra Summary một cách mỹ mãn mà không bị văng lỗi.");
                    resultBox.innerHTML = `<div class="text-red-500 font-bold text-center py-4">Lỗi: ${data.detail || 'Failed to process post-call'}</div>`;
                    btn.disabled = false;
                    btn.innerText = "Thực thi Post-Call (Simulate)";
                    return;
                }
                
                const rawJson = JSON.stringify(data, null, 2);
                
                let dbReportHtml = '';
                if (data.db_report) {
                    const isSuccess = data.db_report.saved_status === 'Success';
                    const icon = isSuccess ? '💾' : '🛡️';
                    const statusText = isSuccess ? 'Đã lưu DB thành công' : 'Không lưu DB - Đang mô phỏng';
                    
                    dbReportHtml = `
                        <div class="h-full flex flex-col p-3 ${isSuccess ? 'bg-indigo-50 border-indigo-200' : 'bg-gray-50 border-gray-300'} border rounded-lg overflow-hidden">
                            <h4 class="font-bold ${isSuccess ? 'text-indigo-800' : 'text-gray-700'} mb-2 flex items-center shrink-0">
                                <span class="mr-2">${icon}</span> ${statusText} (Call ID: ${callId})
                            </h4>
                            <div class="flex-grow overflow-y-auto space-y-4 pr-2">
                                ${(()=>{
                                    const turnTables = ['message_analyses'];
                                    const callTables = ['transcripts', 'conversation_summaries', 'call_analysis', 'call_topics', 'call_intents', 'event_outbox'];
                                    
                                    const renderTable = (t) => {
                                        const rows = Array.isArray(t.raw_data) ? t.raw_data : (Object.keys(t.raw_data || {}).length ? [t.raw_data] : []);
                                        let tableContent = '<div class="text-xs text-gray-400 italic p-2 border rounded bg-gray-50">Không có dữ liệu lưu vào bảng này</div>';
                                        if (rows.length > 0) {
                                            const isIdOrTime = c => c.endsWith('id') || c.endsWith('at') || c.endsWith('time');
                                            const validCols = t.columns.filter(c => {
                                                if (isIdOrTime(c)) return true;
                                                return rows.some(row => {
                                                    const val = row[c];
                                                    if (val === null || val === undefined || val === "") return false;
                                                    if (val === "none" || val === "None" || val === 0 || val === 0.0) return false;
                                                    if (Array.isArray(val) && val.length === 0) return false;
                                                    if (typeof val === 'object' && !Array.isArray(val) && Object.keys(val).length === 0) return false;
                                                    return true;
                                                });
                                            });
                                            tableContent = `
                                                <div class="overflow-x-auto max-h-60 rounded border border-gray-200">
                                                    <table class="min-w-full divide-y divide-gray-200 text-left bg-white" style="table-layout: fixed;">
                                                        <thead class="bg-indigo-100 sticky top-0 z-10 shadow-sm">
                                                            <tr>
                                                                ${validCols.map(c => `<th class="px-2 py-1.5 text-[10px] font-bold text-gray-700 uppercase border-r border-indigo-200 truncate w-32" title="${c}">${c}</th>`).join('')}
                                                            </tr>
                                                        </thead>
                                                        <tbody class="divide-y divide-gray-200">
                                                            ${rows.map(row => `
                                                                <tr class="hover:bg-indigo-50 transition-colors">
                                                                    ${validCols.map(c => {
                                                                        let val = row[c] ?? '';
                                                                        if (typeof val === 'object') val = JSON.stringify(val);
                                                                        const valStr = String(val).replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                                                                        return `<td class="px-2 py-1.5 text-[11px] text-gray-800 border-r truncate max-w-0" title="${valStr}">${valStr}</td>`;
                                                                    }).join('')}
                                                                </tr>
                                                            `).join('')}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            `;
                                        }
                                        return `
                                            <div class="bg-white p-3 rounded border border-indigo-100 shadow-sm mb-3">
                                                <div class="font-bold text-indigo-900 mb-2 border-b pb-1 flex items-center gap-2">
                                                    <span>📊 Table: ${t.table}</span>
                                                    <span class="text-[10px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-semibold">${rows.length} row(s)</span>
                                                </div>
                                                ${tableContent}
                                            </div>
                                        `;
                                    };

                                    let html = '';
                                    if (data.db_report.tables_affected) {
                                        const tGroup1 = data.db_report.tables_affected.filter(t => turnTables.includes(t.table));
                                        const tGroup2 = data.db_report.tables_affected.filter(t => callTables.includes(t.table));
                                        html += '<div class="bg-purple-50 border border-purple-200 rounded p-2"><h5 class="text-sm font-bold text-purple-800 mb-2">📌 Dữ liệu Post-call (Tổng hợp sau khi kết thúc)</h5>';
                                        html += tGroup2.map(renderTable).join('');
                                        html += '</div>';
                                    }

                                    return html;
                                })()}
                            </div>
                        </div>
                    `;
                }

                let summaryMd = data.call_analysis?.summary_text || "Không có dữ liệu tóm tắt.";
                let parsedSummary = typeof marked !== 'undefined' ? marked.parse(summaryMd) : `<pre class="whitespace-pre-wrap">${summaryMd}</pre>`;
                
                let html = `
                    <div id="tab-summary-content" class="prose prose-slate max-w-none prose-h2:text-primary-700 prose-a:text-blue-600 prose-ul:list-none prose-li:relative">
                        <style>
                            .prose li::before {
                                content: "•";
                                color: #64748b;
                                position: absolute;
                                left: -1em;
                            }
                            .prose input[type="checkbox"] {
                                margin-right: 0.5em;
                                accent-color: #0ea5e9;
                            }
                            .prose li:has(input[type="checkbox"])::before {
                                display: none;
                            }
                            .prose strong {
                                color: #334155;
                            }
                        </style>
                        <div class="bg-white p-8 rounded-xl border border-slate-200 shadow-sm text-slate-700 leading-relaxed">
                            ${parsedSummary}
                        </div>
                    </div>
                    
                    <div id="tab-raw-content" class="hidden grid grid-cols-1 md:grid-cols-2 gap-4 h-[600px]">
                        ${(()=>{
                            const sysOutput = JSON.parse(JSON.stringify(data));
                            const llmOutput = sysOutput.raw_llm_analysis || {};
                            delete sysOutput.raw_llm_analysis;

                            return `
                            <!-- Hộp 1: LLM Trả về -->
                            <div class="flex flex-col h-full overflow-hidden">
                                <div class="flex justify-between items-center mb-1 shrink-0">
                                    <p class="font-bold text-[11px] text-orange-600">📝 JSON LLM (${data.pipeline_version || 'Unknown'})</p>
                                    <button onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.innerText); alert('Copied!')" class="text-[9px] bg-slate-200 hover:bg-slate-300 px-2 py-0.5 rounded text-slate-700 font-bold">📋 Copy</button>
                                </div>
                                <div class="bg-slate-900 text-orange-300 font-mono text-[10px] p-2.5 rounded-lg overflow-y-auto flex-grow shadow-inner border border-slate-700 custom-scrollbar">
                                    <pre class="whitespace-pre-wrap m-0">${JSON.stringify(llmOutput, null, 2)}</pre>
                                </div>
                            </div>
                            
                            <!-- Hộp 2: API & DB Schema -->
                            <div class="flex flex-col h-full overflow-hidden">
                                <div class="flex justify-between items-center mb-1 shrink-0">
                                    <p class="font-bold text-[11px] text-blue-600">📝 JSON DB (${data.pipeline_version || 'Unknown'})</p>
                                    <button onclick="navigator.clipboard.writeText(this.parentElement.nextElementSibling.innerText); alert('Copied!')" class="text-[9px] bg-slate-200 hover:bg-slate-300 px-2 py-0.5 rounded text-slate-700 font-bold">📋 Copy</button>
                                </div>
                                <div class="bg-slate-900 text-blue-300 font-mono text-[10px] p-2.5 rounded-lg overflow-y-auto flex-grow shadow-inner border border-slate-700 custom-scrollbar">
                                    <pre class="whitespace-pre-wrap m-0">${JSON.stringify(sysOutput, null, 2)}</pre>
                                </div>
                            </div>
                            `;
                        })()}
                    </div>
                `;
                
                resultBox.innerHTML = html;
                const postcallLatencyEl = document.getElementById('postcall-latency');
                if (postcallLatencyEl) postcallLatencyEl.innerText = `Post-call Latency: ${data.latency_ms} ms`;
                
                // Extract and update QA score
                if (data.call_analysis && data.call_analysis.script_compliance) {
                    const badge = document.getElementById('qa-score-badge');
                    if (badge) {
                        badge.innerText = data.call_analysis.script_compliance.score + '%';
                    }
                }

                // Extract and update SAPP Analysis (NBA & Trend)
                if (data.call_analysis && data.call_analysis.sapp_analysis) {
                    const sapp = data.call_analysis.sapp_analysis;
                    
                    // Update Sentiment Trend
                    if (sapp.sentiment_trend) {
                        const sentIcon = document.getElementById('ai-sentiment-icon');
                        const sentLabel = document.getElementById('ai-sentiment');
                        if (sentLabel && sentIcon) {
                            if (sapp.sentiment_trend === 'Cải thiện') {
                                sentIcon.innerText = '📈';
                                sentLabel.innerText = 'Cải thiện';
                                sentLabel.className = 'text-xs font-bold text-center mt-2 ml-2 text-green-600';
                            } else if (sapp.sentiment_trend === 'Xấu đi') {
                                sentIcon.innerText = '📉';
                                sentLabel.innerText = 'Xấu đi';
                                sentLabel.className = 'text-xs font-bold text-center mt-2 ml-2 text-red-600';
                            } else {
                                sentIcon.innerText = '➖';
                                sentLabel.innerText = 'Giữ nguyên';
                            }
                        }
                    }

                    // Update NBA
                    const nbaBox = document.getElementById('nba-box');
                    if (nbaBox && sapp.next_best_actions) {
                        nbaBox.innerHTML = '';
                        if (sapp.next_best_actions.length > 0) {
                            sapp.next_best_actions.forEach(act => {
                                const isHigh = act.priority === 'Cao';
                                const color = isHigh ? 'red' : (act.type === 'task' ? 'blue' : 'amber');
                                nbaBox.innerHTML += `<div class="bg-white p-2.5 border border-slate-100 rounded-lg shadow-sm mb-2 border-l-4 border-l-${color}-400">
                                    <div class="flex justify-between items-center mb-1">
                                        <span class="text-[10px] font-bold text-${color}-600 uppercase">${act.type}</span>
                                        <span class="text-[9px] bg-${color}-50 text-${color}-600 px-1 rounded border border-${color}-200">${act.priority}</span>
                                    </div>
                                    <span class="text-slate-700 font-bold text-xs block mb-1">${act.title}</span>
                                    <span class="text-slate-600 font-medium text-[11px] block">${act.action}</span>
                                    <span class="text-slate-400 italic text-[10px] mt-1 block">💡 ${act.coaching}</span>
                                </div>`;
                            });
                        } else {
                            nbaBox.innerHTML = '<div class="text-xs text-slate-400 italic text-center bg-white p-3 rounded-lg border border-slate-100 shadow-sm">Không có hành động gợi ý.</div>';
                        }
                    }
                }
            } catch(e) {
                resultBox.innerHTML = `<div class="text-red-500">Lỗi: ${e.message}</div>`;
            } finally {
                btn.disabled = false;
                btn.innerText = "Tạo lại Summary";
            }
        }

        async function addTranscriptToQueue() {
            const tenantId = document.getElementById('tenant-id').value.trim();
            const callId = document.getElementById('call-id').value.trim();
            const rawData = document.getElementById('transcript-input').value;
            let turns = [];
            try { 
                turns = JSON.parse(rawData); 
            } catch(e) {
                alert("Lỗi: Dữ liệu JSON hội thoại không hợp lệ.");
                return;
            }
            if (!turns || turns.length === 0) {
                alert("Lỗi: Không có câu thoại nào.");
                return;
            }
            
            const btn = document.getElementById('start-btn');
            const originalText = btn.innerHTML;
            btn.innerHTML = '⏳ Đang thêm...';
            btn.disabled = true;
            
            try {
                const res = await fetch(`/api/v1/demo/transcripts?tenant_id=${tenantId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        call_id: callId,
                        transcript_json: turns,
                        duration_seconds: 120.0
                    })
                });
                if(res.ok) {
                    alert('Đã thêm vào hàng đợi thành công!');
                } else {
                    alert('Lỗi khi thêm vào hàng đợi.');
                }
            } catch(e) {
                alert('Lỗi kết nối: ' + e.message);
            } finally {
                btn.innerHTML = originalText;
                btn.disabled = false;
            }
        }

        startBtn.addEventListener('click', () => {
            if (isManualMode) {
                addTranscriptToQueue();
            } else {
                startSimulation();
            }
        });
        document.getElementById('btn-postcall').addEventListener('click', generatePostCall);
    
        // --- TAXONOMY JS LOGIC ---

        async function initTenantDropdown() {
            try {
                const res = await fetch('http://localhost:8000/api/v1/demo/all-labels?label_format=ONLY_LABEL');
                const data = await res.json();
                const select = document.getElementById('tenant-id');
                select.innerHTML = '';
                
                // Thu thập các tenant từ API labels
                const tenants = new Set();
                data.forEach(t => tenants.add(t.tenant_id));
                
                // Thêm thủ công tenant user yêu cầu
                tenants.add('47094484-5042-5449-8a50-4f75daf54b25');
                
                tenants.forEach(tenant_id => {
                    const opt = document.createElement('option');
                    opt.value = tenant_id;
                    opt.textContent = tenant_id;
                    select.appendChild(opt);
                });
            } catch (e) {
                console.error("Failed to fetch tenants", e);
            }
        }

        async function openTaxonomyModal() {
            const tenantId = document.getElementById('tenant-id').value;
            if (!tenantId) {
                alert("Vui lòng chọn Tenant ID trước!");
                return;
            }
            document.getElementById('taxonomy-modal').classList.remove('hidden');
            await loadTaxonomy(tenantId);
        }

        function closeTaxonomyModal() {
            document.getElementById('taxonomy-modal').classList.add('hidden');
        }

        async function loadTaxonomy(tenantId) {
            try {
                const res = await fetch(`http://localhost:8000/api/v1/demo/taxonomy/${tenantId}`);
                taxonomyData = await res.json();
                renderTaxonomy();
            } catch (e) {
                console.error(e);
                alert("Lỗi tải Taxonomy!");
            }
        }
        function getSpeakerBadge(rules) {
            if (!rules || !rules.applicable_speaker) return '<span class="text-[10px] bg-gray-100 text-gray-500 px-1 rounded border border-gray-200">ALL</span>';
            const spk = rules.applicable_speaker.toLowerCase();
            if (spk === 'customer') return '<span class="text-[10px] bg-orange-50 text-orange-600 px-1 rounded border border-orange-200">KHÁCH</span>';
            if (spk === 'agent') return '<span class="text-[10px] bg-teal-50 text-teal-600 px-1 rounded border border-teal-200">AGENT</span>';
            return '<span class="text-[10px] bg-gray-100 text-gray-500 px-1 rounded border border-gray-200">ALL</span>';
        }

        async function openQaModal() {
            document.getElementById('qa-modal').classList.remove('hidden');
            const tenantId = document.getElementById('tenant-id').value.trim();
            if (!tenantId) return;
            
            try {
                const res = await fetch(`http://localhost:8000/api/v1/demo/simulate/scorecard-config?tenant_id=${tenantId}`);
                if (!res.ok) throw new Error("Failed to fetch");
                const data = await res.json();
                
                // Render QA
                const qaList = document.getElementById('qa-rules-list');
                if (data.criteria && data.criteria.length > 0) {
                    qaList.innerHTML = data.criteria.map(c => {
                        const intentsHtml = c.intent_codes.map(i => `<span class="bg-blue-50 text-blue-700 px-2 py-1 rounded text-[11px] font-bold border border-blue-200 inline-block mr-1 mb-1">${i}</span>`).join('');
                        const isAutoFail = c.auto_fail;
                        const statusHtml = isAutoFail ? 
                            '<span class="bg-red-100 text-red-800 px-2 py-1 rounded text-[11px] font-bold border border-red-300 w-full inline-block text-center shadow-sm">Cấm kỵ (Auto-fail)</span>' : 
                            `<span class="bg-green-100 text-green-800 px-2 py-1 rounded text-[11px] font-bold border border-green-300 w-full inline-block text-center shadow-sm">+${c.score_value || 0} điểm</span>`;
                            
                        return `
                        <tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                            <td class="p-3">
                                <div class="font-bold text-slate-700 text-sm">${c.title}</div>
                                <div class="text-slate-500 text-[11px] uppercase tracking-wider mt-1 opacity-70">Type: ${c.type}</div>
                            </td>
                            <td class="p-3">
                                ${intentsHtml || '<span class="text-slate-400 italic text-xs">Không yêu cầu Intent</span>'}
                            </td>
                            <td class="p-3">
                                ${statusHtml}
                            </td>
                        </tr>
                    `}).join('');
                } else {
                    qaList.innerHTML = '<tr><td colspan="3" class="p-6 text-center text-slate-400 italic">Chưa có tiêu chí QA nào được cấu hình...</td></tr>';
                }
            } catch(e) {
                console.error(e);
            }
        }
        
        function closeQaModal() {
            document.getElementById('qa-modal').classList.add('hidden');
        }

        function openNbaModal() {
            document.getElementById('nba-modal').classList.remove('hidden');
        }

        function closeNbaModal() {
            document.getElementById('nba-modal').classList.add('hidden');
        }

        function renderTaxonomy() {
            if (!taxonomyData || !taxonomyData.topics || !taxonomyData.intents) {
                console.warn("Taxonomy data is incomplete or failed to load:", taxonomyData);
                return;
            }
            // Render Topics (Tree view) with Intents nested under leaf Topics
            const treeBox = document.getElementById('taxonomy-tree');
            if (treeBox) {
                treeBox.innerHTML = buildTopicTree(null, 0);
            }
        }

        function buildTopicTree(parentId, level) {
            const children = taxonomyData.topics.filter(t => t.parent_id === parentId);
            
            // If this is a leaf topic (no children), we render all intents here for simplicity in UI
            // In a real system, you might map specific intents to specific topics.
            // For this demo, we'll append all intents to the root if parentId is null, 
            // or you can just list intents at the bottom.
            
            let html = '';
            if (children.length > 0) {
                html += `<ul class="${level > 0 ? 'pl-6 border-l-2 border-indigo-100 ml-3 mt-2' : ''}">`;
                children.forEach(t => {
                    html += `
                        <li class="mt-3 bg-white p-3 rounded-xl border border-slate-200 shadow-sm">
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="flex items-center gap-2 mb-1">
                                        <span class="font-bold text-slate-800 text-sm">📁 ${t.label}</span>
                                        ${getSpeakerBadge(t.metadata)}
                                    </div>
                                    <p class="text-[11px] text-slate-500">${t.label_vi || ''}</p>
                                    <p class="text-[10px] text-slate-400 italic mt-1">${t.description_nli || 'Chưa có mô tả'}</p>
                                </div>
                            </div>
                            ${buildTopicTree(t.id, level + 1)}
                        </li>
                    `;
                });
                html += `</ul>`;
            }
            
            // Append intents that belong to this topic
            let currentTopic = null;
            if (parentId !== null) {
                 currentTopic = taxonomyData.topics.find(x => x.id === parentId);
            }
            
            // If we are at the root (parentId === null), we find intents without a parent topic.
            // If we are at a specific topic, we find intents whose parent_topic matches this topic's label.
            const topicIntents = taxonomyData.intents.filter(i => {
                 if (parentId === null) {
                     return !i.detection_rules || !i.detection_rules.parent_topic;
                 } else {
                     return i.detection_rules && i.detection_rules.parent_topic === currentTopic.label;
                 }
            });

            if (topicIntents.length > 0) {
                html += `<div class="mt-3 ${parentId === null ? 'pt-5 border-t border-slate-200' : 'pl-6 ml-3'}">
                    <h5 class="font-bold text-purple-600 uppercase text-[11px] tracking-wider mb-2">🎯 ${parentId === null ? 'Intents chưa phân loại' : 'Intents thuộc chủ đề này'}</h5>
                    <div class="grid ${parentId === null ? 'grid-cols-2' : 'grid-cols-1'} gap-2">
                `;
                topicIntents.forEach(i => {
                    html += `
                        <div class="bg-white p-2 rounded-lg border border-purple-100 shadow-sm">
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="flex items-center gap-2 mb-1">
                                        <span class="font-bold text-purple-700 text-xs">${i.label}</span>
                                        ${getSpeakerBadge(i.detection_rules)}
                                    </div>
                                    <p class="text-[10px] text-slate-500">${i.display_name_vi || ''}</p>
                                </div>
                            </div>
                        </div>
                    `;
                });
                html += `</div></div>`;
            }
            
            return html;
        }


        // Call initTenantDropdown on load
        window.addEventListener('DOMContentLoaded', initTenantDropdown);
    
        
        // TAB LOGIC
        const tabManual = document.getElementById('tab-manual');
        const tabQueue = document.getElementById('tab-queue');
        const paneManual = document.getElementById('pane-manual');
        const paneQueue = document.getElementById('pane-queue');
        
        let isManualMode = true;
        
        function updateStartButtonState() {
            const startBtn = document.getElementById('start-btn');
            const btnPostCall = document.getElementById('btn-postcall');
            if (isManualMode) {
                startBtn.disabled = false;
                startBtn.innerHTML = '📥 Thêm vào Hàng đợi';
                startBtn.className = "w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-3 px-4 rounded-xl shadow-md transition-all";
                if (btnPostCall) btnPostCall.classList.add('hidden');
            } else {
                startBtn.innerHTML = '▶ Khởi động Phân tích (Realtime)';
                const checkedBoxes = document.querySelectorAll('.queue-row-checkbox:checked');
                if (checkedBoxes.length === 1) {
                    startBtn.disabled = false;
                    startBtn.className = "w-full bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-500 hover:to-primary-400 text-white font-bold py-3 px-4 rounded-xl shadow-md transition-all transform active:scale-[0.98]";
                } else {
                    startBtn.disabled = true;
                    startBtn.className = "w-full bg-gray-400 text-white font-bold py-3 px-4 rounded-xl shadow-md cursor-not-allowed opacity-80";
                }
                if (btnPostCall) btnPostCall.classList.remove('hidden');
            }
        }
        
        tabManual.addEventListener('click', () => {
            isManualMode = true;
            tabManual.className = "flex-1 py-2 px-4 text-sm font-bold text-indigo-600 border-b-2 border-indigo-600 focus:outline-none";
            tabQueue.className = "flex-1 py-2 px-4 text-sm font-bold text-gray-500 hover:text-gray-700 focus:outline-none";
            paneManual.classList.remove('hidden');
            paneManual.classList.add('flex');
            paneQueue.classList.add('hidden');
            paneQueue.classList.remove('flex');
            updateStartButtonState();
        });
        
        tabQueue.addEventListener('click', () => {
            isManualMode = false;
            tabQueue.className = "flex-1 py-2 px-4 text-sm font-bold text-indigo-600 border-b-2 border-indigo-600 focus:outline-none";
            tabManual.className = "flex-1 py-2 px-4 text-sm font-bold text-gray-500 hover:text-gray-700 focus:outline-none";
            paneQueue.classList.remove('hidden');
            paneQueue.classList.add('flex');
            paneManual.classList.add('hidden');
            paneManual.classList.remove('flex');
            
            updateStartButtonState();
            
            // Auto fetch if empty
            if(document.getElementById('queue-tbody').innerText.includes('Bấm')) {
                document.getElementById('btn-refresh-queue').click();
            }
        });
        
        document.getElementById('queue-check-all').addEventListener('change', (e) => {
            const checked = e.target.checked;
            document.querySelectorAll('.queue-row-checkbox').forEach(cb => {
                cb.checked = checked;
                const tr = cb.closest('tr');
                if (checked) tr.classList.add('bg-indigo-50');
                else tr.classList.remove('bg-indigo-50');
            });
            updateQueueActionButtons();
        });
        
        function updateQueueActionButtons() {
            const checkedBoxes = document.querySelectorAll('.queue-row-checkbox:checked');
            const statusFilter = document.getElementById('queue-status-filter').value;
            const btnMarkUnprocessed = document.getElementById('btn-mark-unprocessed');
            const btnDeleteCall = document.getElementById('btn-delete-call');
            
            if (checkedBoxes.length > 0 && statusFilter === 'processed') {
                btnMarkUnprocessed.classList.remove('hidden');
            } else {
                btnMarkUnprocessed.classList.add('hidden');
            }
            if (checkedBoxes.length > 0) {
                btnDeleteCall.classList.remove('hidden');
            } else {
                btnDeleteCall.classList.add('hidden');
            }
            
            // Update the single active JSON if exactly 1 is checked
            if (checkedBoxes.length === 1) {
                const tr = checkedBoxes[0].closest('tr');
                const callId = checkedBoxes[0].value;
                const jsonStr = tr.getAttribute('data-json');
                document.getElementById('call-id').value = callId;
                document.getElementById('transcript-input').value = jsonStr;
            }
            updateStartButtonState();
        }
        
        document.getElementById('queue-status-filter').addEventListener('change', () => {
            document.getElementById('btn-refresh-queue').click();
        });
        
        document.getElementById('btn-mark-unprocessed').addEventListener('click', async () => {
            const checkedBoxes = document.querySelectorAll('.queue-row-checkbox:checked');
            if (checkedBoxes.length === 0) return;
            
            const callIds = Array.from(checkedBoxes).map(cb => cb.value);
            const tenantId = document.getElementById('tenant-id').value;
            const btn = document.getElementById('btn-mark-unprocessed');
            btn.innerText = 'Đang xử lý...';
            btn.disabled = true;
            
            try {
                const res = await fetch(`/api/v1/demo/transcripts/mark-unprocessed?tenant_id=${tenantId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ call_ids: callIds })
                });
                if (res.ok) {
                    // Refresh the queue
                    document.getElementById('btn-refresh-queue').click();
                } else {
                    alert("Lỗi khi hủy phân tích!");
                }
            } catch(e) {
                alert("Lỗi mạng: " + e.message);
            } finally {
                btn.innerText = '↩️ Hủy phân tích';
                btn.disabled = false;
            }
        });

        document.getElementById('btn-delete-call').addEventListener('click', async () => {
            const checkedBoxes = document.querySelectorAll('.queue-row-checkbox:checked');
            if (checkedBoxes.length === 0) return;
            
            if (!confirm(`Bạn có chắc chắn muốn xóa vĩnh viễn ${checkedBoxes.length} cuộc gọi này khỏi DB không?`)) return;
            
            const callIds = Array.from(checkedBoxes).map(cb => cb.value);
            const tenantId = document.getElementById('tenant-id').value;
            const btn = document.getElementById('btn-delete-call');
            btn.innerText = 'Đang xóa...';
            btn.disabled = true;
            
            try {
                const res = await fetch(`/api/v1/demo/transcripts?tenant_id=${tenantId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ call_ids: callIds })
                });
                if (res.ok) {
                    document.getElementById('btn-refresh-queue').click();
                } else {
                    alert("Lỗi khi xóa cuộc gọi!");
                }
            } catch(e) {
                alert("Lỗi mạng: " + e.message);
            } finally {
                btn.innerText = '🗑️ Xóa';
                btn.disabled = false;
            }
        });
        
        document.getElementById('btn-refresh-queue').addEventListener('click', async () => {
            const tenantId = document.getElementById('tenant-id').value;
            const status = document.getElementById('queue-status-filter').value;
            const tbody = document.getElementById('queue-tbody');
            tbody.innerHTML = '<tr><td colspan="4" class="px-2 py-4 text-center text-gray-400">Đang tải...</td></tr>';
            document.getElementById('queue-check-all').checked = false;
            updateQueueActionButtons();
            
            try {
                const res = await fetch(`/api/v1/demo/queue-transcripts?tenant_id=${tenantId}&status=${status}`);
                if (!res.ok) {
                    throw new Error(`API Error: ${res.status}`);
                }
                const data = await res.json();
                
                if(!data || data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" class="px-2 py-6 text-center text-gray-500">Không có cuộc gọi nào</td></tr>';
                    return;
                }
                
                tbody.innerHTML = '';
                data.forEach(call => {
                    const tr = document.createElement('tr');
                    tr.className = "hover:bg-gray-50 transition-colors";
                    
                    let jsonStr = "";
                    try {
                        jsonStr = typeof call.transcript_json === 'string' ? call.transcript_json : JSON.stringify(call.transcript_json, null, 2);
                    } catch(err) {
                        jsonStr = "Error stringifying JSON";
                    }
                    tr.setAttribute('data-json', jsonStr);
                    
                    const callIdShort = call.call_id.substring(0, 18) + '...';
                    const duration = call.duration_seconds ? call.duration_seconds.toFixed(0) + 's' : '-';
                    
                    // Format time
                    let timeStr = '-';
                    if (call.created_at) {
                        const d = new Date(call.created_at);
                        timeStr = d.toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit'}) + ' ' + d.toLocaleDateString('vi-VN', {day:'2-digit', month:'2-digit'});
                    }
                    
                    tr.innerHTML = `
                        <td class="px-2 py-2 text-center" onclick="event.stopPropagation()">
                            <input type="checkbox" value="${call.call_id}" class="queue-row-checkbox rounded border-gray-400">
                        </td>
                        <td class="px-2 py-2 font-mono text-[11px] text-gray-700 cursor-pointer" title="${call.call_id}">${callIdShort}</td>
                        <td class="px-2 py-2 text-[10px] text-gray-500 cursor-pointer">${timeStr}</td>
                        <td class="px-2 py-2 text-[11px] text-gray-500 text-right cursor-pointer">${duration}</td>
                    `;
                    
                    // Click row to toggle checkbox
                    tr.addEventListener('click', (e) => {
                        if (e.target.type !== 'checkbox') {
                            const cb = tr.querySelector('.queue-row-checkbox');
                            cb.checked = !cb.checked;
                        }
                        const cb = tr.querySelector('.queue-row-checkbox');
                        if (cb.checked) tr.classList.add('bg-indigo-50');
                        else tr.classList.remove('bg-indigo-50');
                        
                        updateQueueActionButtons();
                    });
                    
                    // Direct checkbox click
                    tr.querySelector('.queue-row-checkbox').addEventListener('change', (e) => {
                        if (e.target.checked) tr.classList.add('bg-indigo-50');
                        else tr.classList.remove('bg-indigo-50');
                        updateQueueActionButtons();
                    });
                    
                    tbody.appendChild(tr);
                });
            } catch(e) {
                tbody.innerHTML = `<tr><td colspan="4" class="px-2 py-6 text-center text-red-500">Lỗi: ${e.message}</td></tr>`;
            }
        });

// Tab switching function for Post Call Panel
window.switchTab = function(tabId) {
    const tabsContainer = document.getElementById('postcall-tabs');
    if (!tabsContainer) return;
    const buttons = tabsContainer.querySelectorAll('button');
    
    if (tabId === 'summary') {
        buttons[0].className = 'pb-2 font-bold text-primary-600 border-b-2 border-primary-600';
        buttons[1].className = 'pb-2 font-bold text-slate-500 hover:text-slate-700';
        document.getElementById('tab-summary-content').classList.remove('hidden');
        document.getElementById('tab-raw-content').classList.add('hidden');
    } else {
        buttons[1].className = 'pb-2 font-bold text-primary-600 border-b-2 border-primary-600';
        buttons[0].className = 'pb-2 font-bold text-slate-500 hover:text-slate-700';
        document.getElementById('tab-raw-content').classList.remove('hidden');
        document.getElementById('tab-summary-content').classList.add('hidden');
    }
};
