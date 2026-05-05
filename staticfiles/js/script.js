/* =========================================================================
   1. KHU VỰC CÀI ĐẶT (SETTINGS) - GPS VÀ MINI MAP
   ========================================================================= */
window.getLocation = function() {
    const status = document.getElementById('geo-msg');
    const latInput = document.getElementById('id_latitude');
    const lonInput = document.getElementById('id_longitude');
    const latDisplay = document.getElementById('lat-display');
    const lonDisplay = document.getElementById('lon-display');

    if (!latInput || !lonInput) return; // Chỉ chạy ở trang Settings

    status.innerHTML = '⏳ Đang tìm...';
    status.style.color = '#888';
    
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (p) => {
                const lat = p.coords.latitude;
                const lon = p.coords.longitude;
                
                latInput.value = lat;
                lonInput.value = lon;
                if (latDisplay) latDisplay.innerText = lat.toFixed(6);
                if (lonDisplay) lonDisplay.innerText = lon.toFixed(6);
                
                status.innerHTML = '✅ Đã tìm thấy!';
                status.style.color = 'green';

                // Nếu có mini map ở trang Settings thì nhảy tới vị trí mới
                if (window.settingsMap && window.settingsMarker) {
                    window.settingsMap.setView([lat, lon], 16);
                    window.settingsMarker.setLatLng([lat, lon]);
                }
            },
            (error) => { 
                console.error("Lỗi GPS:", error);
                status.innerHTML = '❌ Trình duyệt từ chối cấp quyền'; 
                status.style.color = 'red'; 
            }
        );
    } else {
        status.innerHTML = '❌ Trình duyệt không hỗ trợ';
    }
};

// Khởi tạo bản đồ Mini trong trang Settings
document.addEventListener("DOMContentLoaded", () => {
    const mapDiv = document.getElementById('settings-mini-map');
    if (!mapDiv) return; 

    const latInput = document.getElementById('id_latitude');
    const lonInput = document.getElementById('id_longitude');
    const latDisplay = document.getElementById('lat-display');
    const lonDisplay = document.getElementById('lon-display');

    // ÉP BUỘC TẠO CỜ BÁO HIỆU BÊN CẠNH Ô INPUT TỌA ĐỘ
    let interactedInput = document.getElementById('map_interacted_flag');
    if (!interactedInput) {
        interactedInput = document.createElement('input');
        interactedInput.type = 'hidden';
        interactedInput.name = 'map_interacted';
        interactedInput.id = 'map_interacted_flag';
        interactedInput.value = 'false'; // Mặc định là chưa đụng vào bản đồ
        
        if (latInput && latInput.parentNode) {
            latInput.parentNode.appendChild(interactedInput);
        } else {
            const form = mapDiv.closest('form') || document.querySelector('form');
            if (form) form.appendChild(interactedInput);
        }
    }

    const initialLat = parseFloat(latInput ? latInput.value.replace(',', '.') : 0) || 10.7769;
    const initialLon = parseFloat(lonInput ? lonInput.value.replace(',', '.') : 0) || 106.7009;

    window.settingsMap = L.map('settings-mini-map').setView([initialLat, initialLon], 15);
    L.tileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
        maxZoom: 20,
        subdomains:['mt0','mt1','mt2','mt3']
    }).addTo(window.settingsMap);

    window.settingsMarker = L.marker([initialLat, initialLon], { draggable: true }).addTo(window.settingsMap);

    function updateHiddenInputs(lat, lon) {
        if (latInput) latInput.value = lat.toFixed(6);
        if (lonInput) lonInput.value = lon.toFixed(6);
        if (latDisplay) latDisplay.innerText = lat.toFixed(6);
        if (lonDisplay) lonDisplay.innerText = lon.toFixed(6);
    }

    // Load lần đầu, giữ nguyên vị trí cũ
    updateHiddenInputs(initialLat, initialLon);

    // KHI CHẠM/KÉO BẢN ĐỒ -> Bật cờ sang 'true'
    window.settingsMap.on('click', function(e) {
        window.settingsMarker.setLatLng(e.latlng);
        updateHiddenInputs(e.latlng.lat, e.latlng.lng);
        if(interactedInput) interactedInput.value = 'true'; 
    });

    window.settingsMarker.on('dragend', function() {
        const coords = window.settingsMarker.getLatLng();
        updateHiddenInputs(coords.lat, coords.lng);
        if(interactedInput) interactedInput.value = 'true';
    });

    // KHI BẤM LẤY VỊ TRÍ GPS -> Bật cờ sang 'true'
    const oldGetLocation = window.getLocation;
    window.getLocation = function() {
        if (navigator.geolocation) {
            const status = document.getElementById('geo-msg');
            if(status) { status.innerHTML = '⏳ Đang tìm...'; status.style.color = '#888'; }
            
            navigator.geolocation.getCurrentPosition((p) => {
                const lat = p.coords.latitude;
                const lon = p.coords.longitude;
                
                window.settingsMap.setView([lat, lon], 16);
                window.settingsMarker.setLatLng([lat, lon]);
                updateHiddenInputs(lat, lon);
                if(interactedInput) interactedInput.value = 'true'; 
                
                if(status) {
                    status.innerHTML = '✅ Đã cập nhật trên bản đồ!';
                    status.style.color = 'green';
                }
            }, (error) => {
                if(status) { status.innerHTML = '❌ Bị từ chối quyền GPS'; status.style.color = 'red'; }
            });
        }
    };
}); 

/* =========================================================================
   2. KHU VỰC BẢN ĐỒ CHÍNH (MAP SEARCH) & TƯƠNG TÁC NGƯỜI DÙNG
   ========================================================================= */
function getCSRFToken() {
    let cookieValue = null;
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        let cleanCookie = cookie.trim();
        if (cleanCookie.startsWith('csrftoken=')) {
            cookieValue = cleanCookie.substring('csrftoken='.length);
        }
    }
    return cookieValue;
}

const DA_NANG = { lat: 16.0544, lon: 108.2022 }; 
const NHA_TRANG = { lat: 12.2388, lon: 109.1967 };

function showError(msg) {
    console.error(msg);
    const errDiv = document.getElementById('js-error-msg');
    if(errDiv) {
        errDiv.innerText = "Lỗi: " + msg;
        errDiv.style.display = 'block';
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const dataElement = document.getElementById('users-data');
    if(!dataElement) return; // Nếu không ở trang Map chính thì ngưng

    try {
        const users = JSON.parse(dataElement.textContent);
        const myLat = window.MY_LAT || 10.7769;
        const myLon = window.MY_LON || 106.7009;
        
        let currentIndex = 0;
        let map, routeLayer;
        let currentPartnerId = null;
        let currentRelStatus = 'none'; 
        let currentDatingStatus = 'none'; 
        let chatInterval;
        let profileStartTime = 0; 
        let currentViewedUserId = null;
        let isAnimating = false; 

        // Khởi tạo bản đồ tìm kiếm
        function initMap() {
            if(typeof L === 'undefined') throw new Error("Mất kết nối Map Library");
            map = L.map('mini-map', {zoomControl: false}).setView([myLat, myLon], 13);
            L.tileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
                maxZoom: 20, subdomains:['mt0','mt1','mt2','mt3']
            }).addTo(map);
            
            const homeIcon = L.divIcon({html: '📍', className: '', iconSize: [24, 24]});
            L.marker([myLat, myLon], {icon: homeIcon}).addTo(map).bindPopup("Bạn đang ở đây").openPopup();
            L.control.zoom({position: 'bottomright'}).addTo(map);
        }

        // Hiển thị Profile người dùng
        window.renderUser = function(index) {
            if(!users || users.length === 0) {
                document.getElementById('p-name').innerText = "Vũ trụ vắng lặng!";
                document.getElementById('p-status').innerText = "Hãy nới rộng khoảng cách để tìm kiếm nửa kia nhé!";
                return;
            }
            const u = users[index];
            
            if (!document.getElementById('chat-modal').style.display || document.getElementById('chat-modal').style.display === 'none') {
                currentPartnerId = u.id; 
            }

            document.getElementById('p-name').innerText = u.name;
            document.getElementById('p-status').innerText = u.status || "Đang online";
            document.getElementById('p-age').innerText = u.age;
            document.getElementById('p-gender').innerText = u.gender;
            document.getElementById('p-dist').innerText = u.distance;
            document.getElementById('p-marital').innerText = u.marital_status || "Bí mật";
            document.getElementById('p-bio').innerText = u.bio || "Người này chưa cập nhật tiểu sử.";
            
            const avatarUrl = u.avatar ? u.avatar : `https://ui-avatars.com/api/?name=${u.name}&background=ff69b4&color=fff`;
            document.getElementById('p-avatar').src = avatarUrl;

            // Xử lý nút Kết bạn
            currentRelStatus = u.rel_status || 'none';
            const btnFriend = document.getElementById('btn-friend');
            if (currentRelStatus === 'friends') {
                btnFriend.innerHTML = '<i class="fas fa-user-check"></i> Bạn bè';
                btnFriend.style.background = '#4e5058';
            } else if (currentRelStatus === 'pending_sent') {
                btnFriend.innerHTML = '<i class="fas fa-user-minus"></i> Gỡ lời mời';
                btnFriend.style.background = '#f23f42';
            } else if (currentRelStatus === 'pending_received') {
                btnFriend.innerHTML = '<i class="fas fa-user-check"></i> Chấp nhận';
                btnFriend.style.background = '#f1c40f';
            } else {
                btnFriend.innerHTML = '<i class="fas fa-user-plus"></i> Kết bạn';
                btnFriend.style.background = 'linear-gradient(45deg, #2ecc71, #27ae60)';
            }

            // Xử lý nút Hẹn hò
            currentDatingStatus = u.dating_rel_status || 'none';
            const btnDate = document.getElementById('btn-date');
            if (currentDatingStatus === 'dating') {
                btnDate.innerHTML = '<i class="fas fa-heartbeat"></i> Đang hẹn hò';
                btnDate.style.background = 'linear-gradient(45deg, #e91e63, #880e4f)';
                btnDate.classList.add('heartbeat-btn');
            } else if (currentDatingStatus === 'pending_sent') {
                btnDate.innerHTML = '<i class="fas fa-times"></i> Rút lời hẹn hò';
                btnDate.style.background = '#95a5a6';
                btnDate.classList.remove('heartbeat-btn');
            } else if (currentDatingStatus === 'pending_received') {
                btnDate.innerHTML = '<i class="fas fa-kiss-wink-heart"></i> Chấp nhận Hẹn hò';
                btnDate.style.background = 'linear-gradient(45deg, #9b59b6, #8e44ad)';
                btnDate.classList.add('heartbeat-btn');
            } else {
                btnDate.innerHTML = '<i class="fas fa-heart"></i> Hẹn hò';
                btnDate.style.background = 'linear-gradient(45deg, #ff4081, #f50057)';
                btnDate.classList.remove('heartbeat-btn');
            }

            // Ảnh Gallery
            // --- ẢNH GALLERY ---
                const galleryDiv = document.getElementById('p-gallery-grid');
                
                // MỚI: Dàn hàng ngang các ảnh, cách nhau 10px, hết chỗ tự động rớt dòng
                galleryDiv.style.display = 'flex';
                galleryDiv.style.flexWrap = 'wrap';
                galleryDiv.style.gap = '10px';
                
                // MỚI: Đổi width thành 85px để ảnh bé lại, vẫn giữ tỷ lệ vuông 1:1
                const imgStyle = "width: 85px; aspect-ratio: 1/1; object-fit: cover; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); cursor: zoom-in; transition: 0.2s;";
                const hoverEffect = "onmouseover=\"this.style.transform='scale(1.1)'\" onmouseout=\"this.style.transform='scale(1)'\"";

                let html = `<img src="${avatarUrl}" onclick="viewImage('${avatarUrl}')" style="${imgStyle}" ${hoverEffect}>`;
                
                if(u.gallery) {
                    u.gallery.forEach(img => {
                        html += `<img src="${img}" onclick="viewImage('${img}')" style="${imgStyle}" ${hoverEffect}>`;
                    });
                }
                galleryDiv.innerHTML = html;

            // Xử lý Playlist
            const musicDiv = document.getElementById('p-playlist');
            if (u.playlist && u.playlist.length > 0) {
                musicDiv.innerHTML = u.playlist.map(item => {
                    let val = item.value || item;
                    let type = item.type || 'text';
                    if (type === 'soundcloud' && val.includes('<iframe')) {
                        let encodedVal = encodeURIComponent(val);
                        return `<div style="margin-bottom: 10px; background: #fff; padding: 12px; border-radius: 12px; border-left: 4px solid #1db954; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                                    <div style="font-size: 13px; color: #333; margin-bottom: 8px;"><b>🎵 Có 1 bài hát đính kèm</b></div>
                                    <button onclick="loadProfileMusic(this, '${encodedVal}')" style="background: #1db954; color: white; border: none; padding: 6px 12px; border-radius: 20px; font-size: 11px; cursor: pointer; font-weight: bold;">
                                        <i class="fas fa-play"></i> Nghe thử (Sẽ tạm tắt Chill Radio)
                                    </button>
                                </div>`;
                    } else if (type === 'deezer') {
                        return `<div style="margin-bottom: 10px; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                                    <iframe src="https://widget.deezer.com/widget/dark/track/${val}" width="100%" height="80" frameBorder="0" allowtransparency="true" allow="encrypted-media; clipboard-write"></iframe>
                                </div>`;
                    } else {
                        return `<div style="font-size:13px; color:#d81b60; margin:8px 0; background:#fff; padding:10px; border-radius:8px; border-left:3px solid #ff69b4;"><i class="fas fa-headphones-alt"></i> ${val}</div>`;
                    }
                }).join('');
            } else {
                musicDiv.innerHTML = '<div style="color:#999; font-size:13px; font-style:italic;">Người này chưa thêm nhạc vào playlist.</div>';
            }
            
            document.getElementById('p-hobbies').innerHTML = (u.hobbies && u.hobbies[0])
                ? u.hobbies.map(h => `<span class="tag"><i class="fas fa-hashtag" style="font-size:10px;"></i> ${h}</span>`).join('') 
                : '<span style="color:#999; font-size:13px; font-style:italic;">Chưa cập nhật sở thích.</span>';

            drawVietnamRoute(u.lat, u.lon, myLat, myLon, map);
            currentViewedUserId = u.id;
            profileStartTime = Date.now();
        };

        // Các nút chuyển qua lại
        function animateTransition(callback) {
            const card = document.getElementById('user-info-card');
            card.classList.remove('tear-off-enter'); 
            card.classList.add('tear-off-exit');
            setTimeout(() => {
                callback();
                card.classList.remove('tear-off-exit');
                card.classList.add('tear-off-enter');
            }, 500); 
        }

        window.nextUser = function() { 
            if(!users || users.length <= 1 || isAnimating) return; 
            isAnimating = true; 
            sendDwellTime(); 
            animateTransition(() => {
                currentIndex = (currentIndex + 1) % users.length; 
                renderUser(currentIndex); 
                setTimeout(() => { isAnimating = false; }, 600); 
            });
        };

        window.prevUser = function() { 
            if(!users || users.length <= 1 || isAnimating) return; 
            isAnimating = true; 
            sendDwellTime(); 
            animateTransition(() => {
                currentIndex = (currentIndex - 1 + users.length) % users.length; 
                renderUser(currentIndex); 
                setTimeout(() => { isAnimating = false; }, 600); 
            });
        };

        // Giao tiếp API Tương tác
        window.handleFriendAction = function() {
            if(!currentPartnerId) return;
            if (currentRelStatus === 'none') {
                fetch(`/api/friend/send/${currentPartnerId}/`).then(r=>r.json()).then(d => { if(d.status==='ok') { users[currentIndex].rel_status = 'pending_sent'; renderUser(currentIndex); } else alert(d.message); });
            } else if (currentRelStatus === 'pending_sent') {
                fetch(`/api/friend/cancel/${currentPartnerId}/`).then(r=>r.json()).then(d => { if(d.status==='ok') { users[currentIndex].rel_status = 'none'; renderUser(currentIndex); }});
            } else if (currentRelStatus === 'pending_received') {
                fetch(`/api/friend/accept/${currentPartnerId}/`).then(r=>r.json()).then(d => { if(d.status==='ok') { users[currentIndex].rel_status = 'friends'; renderUser(currentIndex); alert("Đã trở thành bạn bè!"); }});
            } else alert("Đã là bạn bè rồi!");
        };

        window.setDating = function() {
            if(!currentPartnerId) return;
            if (currentDatingStatus === 'none') {
                if(confirm("Gửi lời hẹn hò với người này? ❤️")) {
                    fetch(`/api/dating/send/${currentPartnerId}/`).then(r=>r.json()).then(d => { alert(d.message); if(d.status==='ok') { users[currentIndex].dating_rel_status = 'pending_sent'; renderUser(currentIndex); }});
                }
            } else if (currentDatingStatus === 'pending_sent') {
                fetch(`/api/dating/cancel/${currentPartnerId}/`).then(r=>r.json()).then(d => { if(d.status==='ok') { users[currentIndex].dating_rel_status = 'none'; renderUser(currentIndex); }});
            } else if (currentDatingStatus === 'pending_received') {
                if(confirm("Đồng ý làm người yêu nhé? 💕")) {
                    fetch(`/api/dating/accept/${currentPartnerId}/`).then(r=>r.json()).then(d => { alert(d.message); if(d.status==='ok') { users[currentIndex].dating_rel_status = 'dating'; users[currentIndex].marital_status = `Đang hẹn hò 💍`; renderUser(currentIndex); }});
                }
            } else alert("Hai bạn đang hẹn hò rồi! 💖");
        };

        // --- KHU VỰC CHAT VÀ ẨN DANH ---
        window.openChat = function(partnerId = null, partnerName = null) {
            if (partnerId) {
                currentPartnerId = partnerId;
                document.getElementById('chat-partner-name').innerHTML = `<i class="fas fa-heart" style="color:#ffb6c1"></i> ${partnerName}`;
            } else {
                currentPartnerId = users[currentIndex].id;
                document.getElementById('chat-partner-name').innerHTML = `<i class="fas fa-heart" style="color:#ffb6c1"></i> ${users[currentIndex].name}`;
            }
            document.getElementById('chat-modal').style.display = 'flex';
            document.getElementById('list-modal').style.display = 'none';
            
            loadMessages();
            if(chatInterval) clearInterval(chatInterval);
            chatInterval = setInterval(loadMessages, 3000);
        };

        window.closeChat = function() { 
            document.getElementById('chat-modal').style.display = 'none'; 
            clearInterval(chatInterval); 
        };

        window.sendMessage = function() {
            const txt = document.getElementById('msg-input');
            if(!txt.value) return;
            
            // Bắt cờ ẩn danh từ radio button
            const modeInput = document.querySelector('input[name="send_mode"]:checked');
            const isAnonMode = modeInput ? (modeInput.value === 'anon') : false;
            
            fetch('/api/chat/send/', {
                method:'POST', 
                headers:{'Content-Type':'application/json', 'X-CSRFToken': getCSRFToken()},
                body: JSON.stringify({
                    receiver_id: currentPartnerId, 
                    content: txt.value, 
                    is_anonymous: isAnonMode // Đẩy trạng thái ẩn danh lên server
                })
            }).then(r=>r.json()).then(d=>{ 
                if(d.status === 'ok') { 
                    txt.value=''; 
                    loadMessages(); 
                    if(typeof fetchConversations === 'function') fetchConversations(); 
                }
            });
        };
        window.handleEnter = function(e) { if(e.key==='Enter') sendMessage(); };

        function loadMessages() {
    if(!currentPartnerId) return;
    fetch(`/api/chat/history/${currentPartnerId}/`).then(r=>r.json()).then(d=>{
        const div = document.getElementById('chat-history');
        
        div.innerHTML = d.messages.map(m => {
            // 1. Tự động gọi class bong bóng hồng/trắng từ file style.css
            let bubbleClass = (m.sender === 'me') ? 'msg-me' : 'msg-them';
            
            // 2. Nếu là nhắn Ẩn danh -> Thêm style đen thui để ghi đè lên màu hồng
            let anonStyle = '';
            let anonLabel = '';
            
            if (m.is_anonymous) {
                let bgColor = (m.sender === 'me') ? '#444' : '#222';
                anonStyle = `background: ${bgColor} !important; color: #fff !important; border: none !important; box-shadow: none !important;`;
                anonLabel = `<div style="font-size:11px; color:#bbb; font-style:italic; margin-bottom:4px; font-weight:normal;">
                                ${m.sender === 'me' ? '🕵️ Bạn (Ẩn danh)' : '🕵️ Người lạ ẩn danh'}
                             </div>`;
            }

            // 3. Trả về khối bong bóng hoàn chỉnh
            return `
                <div class="${bubbleClass}" style="${anonStyle}">
                    ${anonLabel}
                    <span>${m.content}</span>
                    <span style="font-size: 10px; margin-top: 5px; opacity: 0.8; text-align: right; color: ${m.is_anonymous ? '#888' : 'inherit'};">
                        ${m.time}
                    </span>
                </div>
            `;
        }).join('');
        
        div.scrollTop = div.scrollHeight;
    });
}

        // --- CÁC HÀM TIỆN ÍCH UI KHÁC ---
        window.toggleConversationList = function() {
            const listModal = document.getElementById('list-modal');
            if (listModal.style.display === 'flex') listModal.style.display = 'none';
            else { listModal.style.display = 'flex'; fetchConversations(); }
        };

        window.fetchConversations = function() {
            fetch('/api/chat/list/').then(r=>r.json()).then(data => {
                const listDiv = document.getElementById('conversation-list');
                if (data.conversations.length === 0) { listDiv.innerHTML = '<div style="padding:20px; text-align:center; color:#888;">Chưa có tin nhắn nào. Mở lời đi nào! 💌</div>'; return; }
                listDiv.innerHTML = data.conversations.map(c => `
                    <div class="conv-item" onclick="openChat(${c.partner_id}, '${c.name}')">
                        <img src="${c.avatar || `https://ui-avatars.com/api/?name=${c.name}`}" class="conv-avatar">
                        <div class="conv-info">
                            <div class="conv-name">${c.name}</div>
                            <div class="conv-preview">${c.is_me ? 'Bạn: ' : ''}${c.last_msg}</div>
                        </div>
                        <div style="font-size: 11px; color: #ff69b4; text-align:right;">${c.time}</div>
                    </div>
                `).join('');
            });
        };

        window.toggleRequests = function() {
            const modal = document.getElementById('req-modal');
            modal.style.display = modal.style.display === 'flex' ? 'none' : 'flex';
            // Gọi API load danh sách (lấy từ logic cũ của bạn)
        };

        window.switchTab = function(id, btn) {
            document.querySelectorAll('.tab-content').forEach(e => e.style.display = 'none');
            document.getElementById('tab-'+id).style.display = 'block';
            document.querySelectorAll('.nav-btn').forEach(e => e.style.borderBottom = '3px solid transparent');
            btn.style.borderBottom = '3px solid #ff69b4';
        };
        
        window.toggleRadius = function() {
            const val = document.getElementById('province-select').value;
            document.getElementById('radius-input').disabled = (val !== 'ALL');
        };

        // Ghi lại thời gian xem hồ sơ
        window.sendDwellTime = function() {
            if (!currentViewedUserId || profileStartTime === 0) return;
            let timeSpent = Date.now() - profileStartTime;
            if (timeSpent > 3000) {
                fetch('/api/ai/record-dwell/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCSRFToken() },
                    body: JSON.stringify({ viewed_user_id: currentViewedUserId, time_spent: timeSpent })
                });
            }
        };

        // Vẽ đường đi
       // Vẽ đường đi
        function drawVietnamRoute(targetLat, targetLon, myLat, myLon, mapInstance) {
            if(!mapInstance) return;
            if(routeLayer) mapInstance.removeLayer(routeLayer);
            if(targetLat === myLat && targetLon === myLon) return;

            let waypoints = [];
            waypoints.push([myLon, myLat]);
            const minLat = Math.min(myLat, targetLat);
            const maxLat = Math.max(myLat, targetLat);

            if (minLat < NHA_TRANG.lat && maxLat > (NHA_TRANG.lat + 0.5)) {
                if (myLat < targetLat) { waypoints.push([NHA_TRANG.lon, NHA_TRANG.lat]); } 
            }
            if (minLat < DA_NANG.lat && maxLat > (DA_NANG.lat + 0.5)) {
                if (myLat < targetLat) waypoints.push([DA_NANG.lon, DA_NANG.lat]);
            }
            if (myLat > targetLat) {
                if (minLat < DA_NANG.lat && maxLat > (DA_NANG.lat + 0.5)) waypoints.push([DA_NANG.lon, DA_NANG.lat]);
                if (minLat < NHA_TRANG.lat && maxLat > (NHA_TRANG.lat + 0.5)) waypoints.push([NHA_TRANG.lon, NHA_TRANG.lat]);
            }

            waypoints.push([targetLon, targetLat]);
            const coordsString = waypoints.map(p => p.join(',')).join(';');
            const url = `https://router.project-osrm.org/route/v1/driving/${coordsString}?overview=full&geometries=geojson`;

            fetch(url).then(res => res.json()).then(data => {
                if(data.routes && data.routes.length > 0) {
                    routeLayer = L.geoJSON(data.routes[0].geometry, {
                        color: '#e91e63', weight: 5, opacity: 0.9, lineCap: 'round'
                    }).addTo(mapInstance);
                    mapInstance.fitBounds(routeLayer.getBounds(), {padding: [50, 50]});
                } else drawBackupLine(waypoints, mapInstance);
            }).catch(err => { console.error(err); drawBackupLine(waypoints, mapInstance); });
        }

        // Hàm vẽ nét đứt dự phòng nếu OSRM lỗi
        function drawBackupLine(pointsArray, mapInstance) {
            const latLngs = pointsArray.map(p => [p[1], p[0]]);
            routeLayer = L.polyline(latLngs, { color: '#e91e63', weight: 4, dashArray: '5, 10' }).addTo(mapInstance);
            mapInstance.fitBounds(routeLayer.getBounds(), {padding: [50,50]});
        }
        // Bắt đầu chạy khi tải xong
        initMap();
        toggleRadius();
        renderUser(0);

        document.addEventListener('keydown', (e) => {
            if (e.key === "ArrowRight") nextUser();
            if (e.key === "ArrowLeft") prevUser();
        });

    } catch (e) { showError(e.message); }
});

/* =========================================================================
   3. CHILL RADIO VÀ TIỆN ÍCH ÂM NHẠC
   ========================================================================= */
window.loadProfileMusic = function(btnElement, encodedHtml) {
    btnElement.parentElement.innerHTML = decodeURIComponent(encodedHtml);
};

window.toggleMusicPlayer = function() {
    const modal = document.getElementById('music-modal');
    if (modal.style.display === 'none' || modal.style.display === '') {
        modal.style.display = 'flex'; modal.style.flexDirection = 'column';
    } else { modal.style.display = 'none'; }
};

window.searchRadioMusic = function() {
    const input = document.getElementById('radio-search-input');
    const query = input.value.trim();
    if (!query) return;

    const iconBtn = document.getElementById('radio-search-btn');
    const resultsDiv = document.getElementById('radio-results');
    iconBtn.className = 'fas fa-spinner fa-spin'; 

    fetch(`/api/music/search/?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
            iconBtn.className = 'fas fa-search'; 
            if (data.status === 'ok' && data.tracks.length > 0) {
                resultsDiv.innerHTML = data.tracks.map(track => {
                    const safeName = track.name.replace(/'/g, "\\'"); 
                    return `
                        <div class="track-item" onclick="playRadioTrack('${track.id}', '${safeName}')">
                            <img src="${track.image}" alt="cover" style="width:40px; height:40px; border-radius:5px; margin-right:12px;">
                            <div class="track-info">
                                <div style="color:white; font-size:13px; font-weight:bold;">${track.name}</div>
                                <div style="color:#aaa; font-size:11px;">${track.artist}</div>
                            </div>
                        </div>
                    `;
                }).join('');
                resultsDiv.style.display = 'block'; 
            } else {
                resultsDiv.innerHTML = '<div style="padding: 15px; color: #aaa; text-align: center; font-size: 13px;">Không tìm thấy bài hát này 😢</div>';
                resultsDiv.style.display = 'block';
            }
        })
        .catch(err => { iconBtn.className = 'fas fa-search'; console.error("Lỗi API:", err); });
};

window.playRadioTrack = function(trackId, trackName) {
    const iframe = document.getElementById('radio-iframe');
    
    // URL chuẩn của trình phát nhạc Spotify Embed (đã fix)
    iframe.src = 'https://' + 'open.spotify.com/embed/track/' + trackId + '?utm_source=generator&theme=0&autoplay=1';
    
    const input = document.getElementById('radio-search-input');
    input.value = ''; 
    input.placeholder = "Đang phát: " + trackName;
    document.getElementById('radio-results').style.display = 'none';
};

document.addEventListener('click', function(e) {
    const resultsDiv = document.getElementById('radio-results');
    if (resultsDiv && !e.target.closest('.radio-search')) {
        resultsDiv.style.display = 'none';
    }
});
/* =========================================
       HÀM ZOOM ẢNH CHO THƯ VIỆN
    ========================================= */
    window.viewImage = function(url) {
        // Tạo lớp màn sương mù màu đen
        const overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed; top:0; left:0; width:100vw; height:100vh; background:rgba(0,0,0,0.85); display:flex; justify-content:center; align-items:center; z-index:9999; cursor:zoom-out; opacity:0; transition:opacity 0.3s;';
        
        // Tạo thẻ ảnh phóng to
        const img = document.createElement('img');
        img.src = url;
        img.style.cssText = 'max-width:90%; max-height:90%; border-radius:12px; box-shadow:0 10px 30px rgba(0,0,0,0.5); transform:scale(0.8); transition:transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);';
        
        overlay.appendChild(img);
        document.body.appendChild(overlay);

        // Kích hoạt hiệu ứng từ từ hiện ra (Fade in & Scale)
        requestAnimationFrame(() => {
            overlay.style.opacity = '1';
            img.style.transform = 'scale(1)';
        });

        // Bấm vào bất cứ đâu để đóng ảnh
        overlay.onclick = function() {
            overlay.style.opacity = '0';
            img.style.transform = 'scale(0.8)';
            setTimeout(() => document.body.removeChild(overlay), 300); // Đợi 0.3s cho mượt rồi mới xóa
        };
    };

/* =========================================
   HỆ THỐNG KIỂM TRA TIN NHẮN CHƯA ĐỌC (CHẤM ĐỎ)
========================================= */
function checkUnreadMessages() {
    fetch('/api/messages/unread/')
        .then(res => res.json())
        .then(data => {
            const badge = document.getElementById('unread-badge');
            if (badge) {
                if (data.has_unread) {
                    badge.style.display = 'block';
                    badge.innerText = data.count > 99 ? '99+' : data.count; // Nhiều quá thì hiện 99+
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(err => console.error("Lỗi check tin nhắn:", err));
}

// Chạy ngay khi vừa load xong trang
document.addEventListener("DOMContentLoaded", () => {
    checkUnreadMessages();
    
    // Đặt lịch chạy ngầm kiểm tra mỗi 5 giây
    setInterval(checkUnreadMessages, 5000);
});

// Mẹo nhỏ: Khi bạn click mở hộp thoại chat list, cũng nên gọi lại checkUnreadMessages() 
// để nó cập nhật lại số ngay lập tức.