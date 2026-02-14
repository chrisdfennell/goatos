/* --- DARK MODE --- */
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    localStorage.setItem('goatOS_darkMode', isDark);
    updateThemeIcon(isDark);
}
function updateThemeIcon(isDark) {
    const btn = document.getElementById('themeBtn');
    if(btn) btn.textContent = isDark ? '\u2600\uFE0F' : '\uD83C\uDF19';
}
document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = localStorage.getItem('goatOS_darkMode') === 'true';
    if (savedTheme) document.body.classList.add('dark-mode');
    updateThemeIcon(savedTheme);
});

/* --- TOASTS --- */
function showToast(message, type) {
    type = type || 'success';
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast-custom ' + type;
    var icon = type === 'success' ? '\u2705' : '\u26A0\uFE0F';
    if (type === 'info') icon = '\u2139\uFE0F';
    toast.innerHTML = icon + ' ' + message;
    container.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 3000);
}

/* --- SETTINGS MODAL --- */
function openSettings() { document.getElementById('settings-modal').style.display = 'flex'; }
function closeSettings() { document.getElementById('settings-modal').style.display = 'none'; }

/* --- GLOBAL KEYBOARD SHORTCUTS --- */
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeSettings();
});

/* --- GPS HELPER --- */
function getCurrentLoc() {
    if (navigator.geolocation) {
        showToast("Requesting location...", "info");
        navigator.geolocation.getCurrentPosition(function(pos) {
            document.getElementById('lat-input').value = pos.coords.latitude;
            document.getElementById('lng-input').value = pos.coords.longitude;
            showToast("Location acquired!");
        }, function() {
            showToast("Error getting location.", "error");
        }, { enableHighAccuracy: false, timeout: 10000 });
    } else {
        showToast("Browser does not support Geolocation", "error");
    }
}

/* --- MAP PICKER BRIDGE --- */
function enableMapPick() {
    closeSettings();
    if (typeof window.activateMapPicker === 'function') {
        window.activateMapPicker();
        showToast("Click anywhere on the map to move the farm pin.", "info");
    } else {
        showToast("Go to the Dashboard to use the map picker.", "error");
    }
}

/* --- SCROLL TOP --- */
window.onscroll = function() {
    var btn = document.getElementById("scrollTopBtn");
    if(btn) btn.style.display = (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) ? "block" : "none";
};
function scrollToTop() { window.scrollTo({top: 0, behavior: 'smooth'}); }
