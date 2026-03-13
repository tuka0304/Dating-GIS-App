/* =========================================
   1. SCRIPT TRANG SETTINGS (GPS)
========================================= */
function getLocation() {
    const status = document.getElementById('geo-msg');
    const latInput = document.getElementById('id_latitude');
    const lonInput = document.getElementById('id_longitude');

    if(!status || !latInput || !lonInput) return; // Bỏ qua nếu không ở trang Settings

    status.innerHTML = '⏳ Đang tìm...';
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (p) => {
                latInput.value = p.coords.latitude;
                lonInput.value = p.coords.longitude;
                status.innerHTML = '✅ Đã tìm thấy!';
                status.style.color = 'green';
            },
            () => { status.innerHTML = '❌ Lỗi vị trí'; status.style.color = 'red'; }
        );
    }
}

/* =========================================
   2. SCRIPT TRANG MAP SEARCH
========================================= */
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
    if(!dataElement) return; // Nếu không ở trang Map thì ngưng chạy script này

    try {
        const users = JSON.parse(dataElement.textContent);
        // Nhận biến từ Django thông qua thẻ window ở file HTML
        const myLat = window.MY_LAT || 10.7769;
        const myLon = window.MY_LON || 106.7009;
        
        let currentIndex = 0;
        let map, routeLayer;
        let currentPartnerId = null;
        let currentRelStatus = 'none'; 
        let currentDatingStatus = 'none'; 
        let chatInterval;

        function initMap() {
            if(typeof L === 'undefined') throw new Error("Mất kết nối Map Library");
            map = L.map('mini-map', {zoomControl: false}).setView([myLat, myLon], 13);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
            
            const homeIcon = L.divIcon({html: '📍', className: '', iconSize: [24, 24]});
            L.marker([myLat, myLon], {icon: homeIcon}).addTo(map).bindPopup("Bạn đang ở đây").openPopup();
            L.control.zoom({position: 'bottomright'}).addTo(map);
        }

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

            // --- XỬ LÝ NÚT KẾT BẠN ---
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

            // --- XỬ LÝ NÚT HẸN HÒ ---
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

            // --- ẢNH & NHẠC ---
            const galleryDiv = document.getElementById('p-gallery-grid');
            let html = `<img src="${avatarUrl}" style="width:100%; height:100px; object-fit:cover; border-radius:8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">`;
            if(u.gallery) u.gallery.forEach(img => html += `<img src="${img}" style="width:100%; height:100px; object-fit:cover; border-radius:8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">`);
            galleryDiv.innerHTML = html;

            const musicDiv = document.getElementById('p-playlist');
            if (u.playlist && u.playlist.length > 0) {
                musicDiv.innerHTML = u.playlist.map(item => {
                    if (item.type === 'deezer' || item.type === 'soundcloud') {
                        return `<div style="margin-bottom: 10px; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                                    ${item.type === 'deezer' 
                                        ? `<iframe src="https://widget.deezer.com/widget/dark/track/${item.value}" width="100%" height="80" frameBorder="0" allowtransparency="true" allow="encrypted-media; clipboard-write"></iframe>`
                                        : item.value}
                                </div>`;
                    } else {
                        return `<div style="font-size:13px; color:#d81b60; margin:8px 0; background:#fff; padding:10px; border-radius:8px; border-left:3px solid #ff69b4;"><i class="fas fa-headphones-alt"></i> ${item.value}</div>`;
                    }
                }).join('');
            } else {
                musicDiv.innerHTML = '<div style="color:#999; font-size:13px; font-style:italic;">Người này chưa thêm nhạc vào playlist.</div>';
            }

            document.getElementById('p-hobbies').innerHTML = (u.hobbies && u.hobbies[0])
                ? u.hobbies.map(h => `<span class="tag"><i class="fas fa-hashtag" style="font-size:10px;"></i> ${h}</span>`).join('') : '<span style="color:#999; font-size:13px; font-style:italic;">Chưa cập nhật sở thích.</span>';

            drawVietnamRoute(u.lat, u.lon, myLat, myLon, map);
        }

        window.handleFriendAction = function() {
            if(!currentPartnerId) return;
            
            if (currentRelStatus === 'none') {
                fetch(`/api/friend/send/${currentPartnerId}/`).then(res => res.json()).then(data => {
                    if(data.status === 'ok') {
                        users[currentIndex].rel_status = 'pending_sent'; 
                        renderUser(currentIndex);
                    } else alert(data.message);
                });
            } 
            else if (currentRelStatus === 'pending_sent') {
                fetch(`/api/friend/cancel/${currentPartnerId}/`).then(res => res.json()).then(data => {
                    if(data.status === 'ok') {
                        users[currentIndex].rel_status = 'none';
                        renderUser(currentIndex);
                    }
                });
            }
            else if (currentRelStatus === 'pending_received') {
                fetch(`/api/friend/accept/${currentPartnerId}/`).then(res => res.json()).then(data => {
                    if(data.status === 'ok') {
                        users[currentIndex].rel_status = 'friends';
                        renderUser(currentIndex);
                        alert("Hai bạn đã trở thành bạn bè!");
                    }
                });
            }
            else if (currentRelStatus === 'friends') {
                alert("Hai bạn đã là bạn bè rồi! Nhắn tin cho nhau đi nào 💕");
            }
        };

        window.setDating = function() {
            if(!currentPartnerId) return;
            
            if (currentDatingStatus === 'none') {
                if(confirm("Bạn có chắc muốn gửi lời hẹn hò với người này? Trái tim chỉ có một ngăn thôi nhé! ❤️")) {
                    fetch(`/api/dating/send/${currentPartnerId}/`).then(res => res.json()).then(data => {
                        alert(data.message);
                        if(data.status === 'ok') {
                            users[currentIndex].dating_rel_status = 'pending_sent'; 
                            renderUser(currentIndex);
                        }
                    });
                }
            } 
            else if (currentDatingStatus === 'pending_sent') {
                fetch(`/api/dating/cancel/${currentPartnerId}/`).then(res => res.json()).then(data => {
                    if(data.status === 'ok') {
                        users[currentIndex].dating_rel_status = 'none';
                        renderUser(currentIndex);
                    }
                });
            }
            else if (currentDatingStatus === 'pending_received') {
                if(confirm("Đồng ý làm người yêu của nhau nhé? 💕")) {
                    fetch(`/api/dating/accept/${currentPartnerId}/`).then(res => res.json()).then(data => {
                        alert(data.message);
                        if(data.status === 'ok') {
                            users[currentIndex].dating_rel_status = 'dating';
                            users[currentIndex].marital_status = `Đang hẹn hò với bạn 💍`; 
                            renderUser(currentIndex);
                        }
                    });
                }
            }
            else if (currentDatingStatus === 'dating') {
                alert("Hai bạn đang là người yêu của nhau rồi! 💖");
            }
        };

        window.toggleRequests = function() {
            const modal = document.getElementById('req-modal');
            if (modal.style.display === 'flex') {
                modal.style.display = 'none';
            } else {
                modal.style.display = 'flex';
                fetch('/api/requests/list/').then(res => res.json()).then(data => {
                    const listDiv = document.getElementById('req-list');
                    const badge = document.getElementById('req-count');
                    
                    const totalReqs = data.friend_requests.length + data.dating_requests.length;
                    
                    if (totalReqs > 0) {
                        badge.innerText = totalReqs;
                        badge.style.display = 'flex';
                    } else {
                        badge.style.display = 'none';
                    }

                    if(totalReqs === 0) {
                        listDiv.innerHTML = "<div style='text-align:center; color:#999; padding:20px;'>Bạn chưa có thông báo nào.</div>";
                        return;
                    }

                    let html = "";
                    
                    if(data.dating_requests.length > 0) {
                        html += `<div style="font-size: 12px; font-weight: bold; color: #e91e63; margin: 10px 0 5px 0; padding-left: 5px;"><i class="fas fa-heartbeat"></i> LỜI TỎ TÌNH</div>`;
                        html += data.dating_requests.map(req => `
                            <div class="conv-item" style="background:#fff0f5; border-radius:8px; margin-bottom:8px; border:2px solid #ffb6c1;">
                                <img src="${req.avatar || 'https://via.placeholder.com/50'}" class="conv-avatar">
                                <div class="conv-info">
                                    <div class="conv-name" style="color: #d81b60;">${req.name}</div>
                                    <div style="font-size: 11px; color: #e91e63; font-style: italic; margin-bottom: 5px;">Muốn hẹn hò với bạn 💕</div>
                                    <div>
                                        <button onclick="respondDating(${req.sender_id}, 'accept')" style="background:linear-gradient(45deg, #ff4081, #f50057); border:none; color:white; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:11px; font-weight:bold;"><i class="fas fa-heart"></i> Đồng ý</button>
                                        <button onclick="respondDating(${req.sender_id}, 'reject')" style="background:#95a5a6; border:none; color:white; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:11px; font-weight:bold; margin-left:5px;"><i class="fas fa-times"></i> Từ chối</button>
                                    </div>
                                </div>
                            </div>
                        `).join('');
                    }

                    if(data.friend_requests.length > 0) {
                        html += `<div style="font-size: 12px; font-weight: bold; color: #2ecc71; margin: 15px 0 5px 0; padding-left: 5px;"><i class="fas fa-user-friends"></i> LỜI MỜI KẾT BẠN</div>`;
                        html += data.friend_requests.map(req => `
                            <div class="conv-item" style="background:#fff; border-radius:8px; margin-bottom:8px; border:1px solid #ffe4e1;">
                                <img src="${req.avatar || 'https://via.placeholder.com/50'}" class="conv-avatar">
                                <div class="conv-info">
                                    <div class="conv-name">${req.name}</div>
                                    <div style="margin-top:5px;">
                                        <button onclick="respondRequest(${req.req_id}, 'accept')" style="background:#2ecc71; border:none; color:white; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:11px; font-weight:bold;"><i class="fas fa-check"></i> Đồng ý</button>
                                        <button onclick="respondRequest(${req.req_id}, 'reject')" style="background:#e74c3c; border:none; color:white; padding:4px 10px; border-radius:4px; cursor:pointer; font-size:11px; font-weight:bold; margin-left:5px;"><i class="fas fa-times"></i> Xóa</button>
                                    </div>
                                </div>
                            </div>
                        `).join('');
                    }
                    listDiv.innerHTML = html;
                });
            }
        };

        window.respondRequest = function(reqId, action) {
            fetch(`/api/friend/${action}/${reqId}/`).then(res => res.json()).then(data => {
                toggleRequests(); toggleRequests(); 
                if(action === 'accept') {
                    alert("Chúc mừng! 2 bạn đã trở thành bạn bè 🎉");
                    window.location.reload(); 
                }
            });
        };

        window.respondDating = function(senderId, action) {
            fetch(`/api/dating/${action}/${senderId}/`).then(res => res.json()).then(data => {
                toggleRequests(); toggleRequests(); 
                alert(data.message);
                if(action === 'accept') window.location.reload(); 
            });
        };

        fetch('/api/requests/list/').then(r=>r.json()).then(d=>{
            const total = (d.friend_requests ? d.friend_requests.length : 0) + (d.dating_requests ? d.dating_requests.length : 0);
            if(total > 0) {
                const badge = document.getElementById('req-count');
                badge.innerText = total;
                badge.style.display = 'flex';
            }
        });

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

        function drawBackupLine(pointsArray, mapInstance) {
            const latLngs = pointsArray.map(p => [p[1], p[0]]);
            routeLayer = L.polyline(latLngs, { color: '#e91e63', weight: 4, dashArray: '5, 10' }).addTo(mapInstance);
            mapInstance.fitBounds(routeLayer.getBounds(), {padding: [50,50]});
        }

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
            if(users.length === 0) return;
            animateTransition(() => {
                currentIndex = (currentIndex + 1) % users.length; 
                renderUser(currentIndex); 
            });
        };

        window.prevUser = function() { 
            if(users.length === 0) return;
            animateTransition(() => {
                currentIndex = (currentIndex - 1 + users.length) % users.length; 
                renderUser(currentIndex); 
            });
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

        window.toggleConversationList = function() {
            const listModal = document.getElementById('list-modal');
            if (listModal.style.display === 'flex') {
                listModal.style.display = 'none';
            } else {
                listModal.style.display = 'flex';
                fetchConversations();
            }
        };

        function fetchConversations() {
            fetch('/api/chat/list/').then(res => res.json()).then(data => {
                const listDiv = document.getElementById('conversation-list');
                if (data.conversations.length === 0) {
                    listDiv.innerHTML = '<div style="padding:20px; text-align:center; color:#888;">Chưa có tin nhắn nào. Mở lời đi nào! 💌</div>';
                    return;
                }
                listDiv.innerHTML = data.conversations.map(c => {
                    const avatar = c.avatar || `https://ui-avatars.com/api/?name=${c.name}&background=random`;
                    return `
                        <div class="conv-item" onclick="openChat(${c.partner_id}, '${c.name}')">
                            <img src="${avatar}" class="conv-avatar">
                            <div class="conv-info">
                                <div class="conv-name">${c.name}</div>
                                <div class="conv-preview">${c.is_me ? 'Bạn: ' : ''}${c.last_msg}</div>
                            </div>
                            <div style="font-size: 11px; color: #ff69b4; text-align:right;">${c.time}</div>
                        </div>
                    `;
                }).join('');
            });
        }
        
        function loadMessages() {
            if(!currentPartnerId) return;
            fetch(`/api/chat/history/${currentPartnerId}/`).then(r=>r.json()).then(d=>{
                const div = document.getElementById('chat-history');
                div.innerHTML = d.messages.map(m => `
                    <div style="padding: 10px 15px; margin: 8px 0; border-radius: 18px; max-width: 80%; font-size: 14px; display: flex; flex-direction: column; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
                        ${m.sender==='me' ? 'background: linear-gradient(45deg, #ff69b4, #d81b60); color:white; margin-left:auto; border-bottom-right-radius:4px;' : 'background:#fff; color:#880e4f; margin-right:auto; border-bottom-left-radius:4px; border: 1px solid #ffe4e1;'}">
                        <span>${m.content}</span>
                        <span style="font-size: 10px; margin-top: 5px; opacity: 0.8; text-align: right;">${m.time}</span>
                    </div>
                `).join('');
                div.scrollTop = div.scrollHeight;
            });
        }

        window.sendMessage = function() {
            const txt = document.getElementById('msg-input');
            if(!txt.value) return;
            fetch('/api/chat/send/', {
                method:'POST', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({receiver_id: currentPartnerId, content: txt.value})
            }).then(r=>r.json()).then(d=>{ if(d.status==='ok'){ txt.value=''; loadMessages(); fetchConversations(); }});
        }
        window.handleEnter = function(e) { if(e.key==='Enter') sendMessage(); };

        initMap();
        toggleRadius();
        renderUser(0);

        document.addEventListener('keydown', (e) => {
            if (e.key === "ArrowRight") nextUser();
            if (e.key === "ArrowLeft") prevUser();
        });

    } catch (e) { showError(e.message); }
});