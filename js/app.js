/* ===================================================================
   Wire Bond Group — Activity Flow System
   Frontend JavaScript
   =================================================================== */

// ===================================================================
// DARK MODE TOGGLE
// ===================================================================
function toggleTheme() {
    var html = document.documentElement;
    var current = html.getAttribute('data-theme') || 'light';
    var next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('wb-theme', next);
    // Update label text
    var label = document.querySelector('.theme-label');
    if (label) label.textContent = next === 'dark' ? 'Light Mode' : 'Dark Mode';
}
// Set correct label on load
document.addEventListener('DOMContentLoaded', function() {
    var current = document.documentElement.getAttribute('data-theme') || 'light';
    var label = document.querySelector('.theme-label');
    if (label) label.textContent = current === 'dark' ? 'Light Mode' : 'Dark Mode';
});

// ---- Modal toggle ----
function toggleModal(modalId) {
    var modal = document.getElementById(modalId);
    if (!modal) return;
    modal.style.display = modal.style.display === 'none' ? 'flex' : 'none';
}

// Close modal on backdrop click
document.addEventListener('click', function (e) {
    if (e.target.classList.contains('modal')) {
        e.target.style.display = 'none';
    }
});

// Close modal on Escape key
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal').forEach(function (m) {
            m.style.display = 'none';
        });
    }
});

// ---- Auto-dismiss flash messages after 5 seconds ----
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.flash').forEach(function (flash) {
        setTimeout(function () {
            flash.style.transition = 'opacity 0.4s ease';
            flash.style.opacity = '0';
            setTimeout(function () { flash.remove(); }, 400);
        }, 5000);
    });
});

// ---- File input preview label ----
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('input[type="file"]').forEach(function (input) {
        input.addEventListener('change', function () {
            var count = this.files.length;
            var hint = this.parentElement.querySelector('.form-hint');
            if (hint && count > 0) {
                hint.textContent = count + ' file(s) selected';
            }
        });
    });
});

// ---- Flash close button ----
document.addEventListener('click', function (e) {
    if (e.target.classList.contains('flash-close')) {
        var flash = e.target.closest('.flash');
        if (flash) {
            flash.style.transition = 'opacity 0.2s ease';
            flash.style.opacity = '0';
            setTimeout(function () { flash.remove(); }, 200);
        }
    }
});

// ===================================================================
// PROGRESS TYPE DYNAMIC FORM SWITCHING (Admin Activities)
// ===================================================================
/**
 * Show/hide progress-related fields based on the selected progress type.
 * @param {HTMLSelectElement} select - The progress_type <select> element
 * @param {string} prefix - 'create' or 'edit' to scope to the right modal
 */
function onProgressTypeChange(select, prefix) {
    var type = select.value;

    var numericFields  = document.getElementById(prefix + '_numeric_fields');
    var customFields   = document.getElementById(prefix + '_custom_fields');
    var checklistFields= document.getElementById(prefix + '_checklist_fields');

    // Hide all first
    if (numericFields)   numericFields.style.display   = 'none';
    if (customFields)    customFields.style.display    = 'none';
    if (checklistFields) checklistFields.style.display = 'none';

    // Show relevant section
    if (type === 'machine_count' || type === 'units_bonded') {
        if (numericFields) numericFields.style.display = 'block';
    } else if (type === 'custom') {
        if (customFields) customFields.style.display = 'block';
    } else if (type === 'checklist') {
        if (checklistFields) checklistFields.style.display = 'block';
    }
    // 'none' and 'done_not_done' need no extra fields
}

// ===================================================================
// CHECKLIST ITEM TOGGLE  (Activity Detail page)
// ===================================================================
/**
 * Called when user clicks a checklist item — submits the toggle form.
 * @param {HTMLFormElement} form
 */
function toggleChecklistItem(form) {
    form.submit();
}

// ===================================================================
// PROGRESS UPDATE PANEL SWITCHING  (Activity Detail page)
// ===================================================================
/**
 * If the progress panel has tab-like buttons to select update mode, handle them.
 * This is a progressive enhancement; the form works without JS too.
 */
document.addEventListener('DOMContentLoaded', function () {
    var progressTypeTabs = document.querySelectorAll('.progress-tab-btn');
    progressTypeTabs.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var target = this.dataset.target;
            document.querySelectorAll('.progress-tab-panel').forEach(function (p) {
                p.style.display = 'none';
            });
            progressTypeTabs.forEach(function (b) { b.classList.remove('active'); });
            var panel = document.getElementById(target);
            if (panel) panel.style.display = 'block';
            this.classList.add('active');
        });
    });
});

// ===================================================================
// PHOTO LIGHTBOX  (click photo thumb to view larger)
// ===================================================================
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.photo-thumb img').forEach(function (img) {
        img.style.cursor = 'pointer';
        img.addEventListener('click', function () {
            var overlay = document.createElement('div');
            overlay.style.cssText = [
                'position:fixed;top:0;left:0;right:0;bottom:0;',
                'background:rgba(0,0,0,0.85);z-index:9999;',
                'display:flex;align-items:center;justify-content:center;cursor:pointer;'
            ].join('');
            var large = document.createElement('img');
            large.src = img.src;
            large.style.cssText = 'max-width:90vw;max-height:90vh;border-radius:6px;box-shadow:0 8px 32px rgba(0,0,0,0.5);';
            overlay.appendChild(large);
            overlay.addEventListener('click', function () { overlay.remove(); });
            document.body.appendChild(overlay);
        });
    });
});

// ===================================================================
// ANNOUNCEMENT DISMISS (sessionStorage)
// ===================================================================
function dismissAnnouncement(annId) {
    var el = document.getElementById('ann-' + annId);
    if (el) {
        el.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateY(-8px)';
        setTimeout(function() { el.remove(); }, 300);
    }
    // Remember dismissed in session
    var dismissed = JSON.parse(sessionStorage.getItem('wb-dismissed-ann') || '[]');
    if (dismissed.indexOf(annId) === -1) dismissed.push(annId);
    sessionStorage.setItem('wb-dismissed-ann', JSON.stringify(dismissed));
}

// Auto-hide previously dismissed announcements on page load
document.addEventListener('DOMContentLoaded', function() {
    var dismissed = JSON.parse(sessionStorage.getItem('wb-dismissed-ann') || '[]');
    dismissed.forEach(function(annId) {
        var el = document.getElementById('ann-' + annId);
        if (el) el.remove();
    });
});

// ===================================================================
// SHIFT CALENDAR NAVIGATION (AJAX)
// ===================================================================
var calCurrentYear = null;
var calCurrentMonth = null;

function initCalendar(year, month) {
    calCurrentYear = year;
    calCurrentMonth = month;
}

function navigateCalendar(direction) {
    if (!calCurrentYear || !calCurrentMonth) return;
    if (direction === 'prev') {
        calCurrentMonth--;
        if (calCurrentMonth < 1) { calCurrentMonth = 12; calCurrentYear--; }
    } else {
        calCurrentMonth++;
        if (calCurrentMonth > 12) { calCurrentMonth = 1; calCurrentYear++; }
    }
    fetchCalendarMonth(calCurrentYear, calCurrentMonth);
}

function fetchCalendarMonth(year, month) {
    var url = '/api/shift-calendar?year=' + year + '&month=' + month;
    fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            calCurrentYear = data.year;
            calCurrentMonth = data.month;
            renderCalendar(data);
        })
        .catch(function(err) { console.error('Calendar fetch error:', err); });
}

function renderCalendar(data) {
    var label = document.getElementById('cal-month-label');
    if (label) label.textContent = data.month_name + ' ' + data.year;

    var tbody = document.getElementById('cal-tbody');
    if (!tbody) return;

    var html = '';
    data.weeks.forEach(function(week) {
        html += '<tr>';
        html += '<td class="ww-col">WW' + week.ww + '</td>';
        week.days.forEach(function(day) {
            var cls = '';
            if (!day.in_month) cls += ' cal-day-out';
            if (day.is_today) cls += ' cal-day-today';
            if (day.holiday) cls += ' cal-day-holiday';

            html += '<td class="' + cls.trim() + '">';
            html += '<div class="cal-day-num">' + day.day + '</div>';
            if (day.holiday) {
                html += '<span class="cal-holiday-name">' + day.holiday + '</span>';
            }
            html += '<div class="cal-crews">';
            ['A','B','C','D'].forEach(function(crew) {
                var shift = day.crews[crew];
                var tagCls = 'cal-crew-tag crew-' + crew.toLowerCase();
                var label = crew + ':' + shift;
                if (shift === 'O') {
                    tagCls = 'cal-crew-tag crew-off';
                } else if (shift === 'REP') {
                    tagCls = 'cal-crew-tag crew-rep';
                    label = crew + ':R';
                }
                html += '<span class="' + tagCls + '">' + label + '</span>';
            });
            html += '</div></td>';
        });
        html += '</tr>';
    });
    tbody.innerHTML = html;
}

// ===================================================================
// SHIFT BADGE COLOR UPDATE in nav (cosmetic)
// ===================================================================
document.addEventListener('DOMContentLoaded', function () {
    // Ensure shift letter badge has correct color class applied via JS backup
    document.querySelectorAll('.shift-letter-badge').forEach(function (badge) {
        var letter = badge.textContent.trim().toUpperCase();
        badge.classList.remove('shift-a', 'shift-b', 'shift-c', 'shift-d', 'shift-ds');
        if (letter === 'A') badge.classList.add('shift-a');
        else if (letter === 'B') badge.classList.add('shift-b');
        else if (letter === 'C') badge.classList.add('shift-c');
        else if (letter === 'D') badge.classList.add('shift-d');
        else if (letter === 'DS') badge.classList.add('shift-ds');
    });
});
