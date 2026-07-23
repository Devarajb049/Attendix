document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const navbar = document.querySelector('.navbar');
    const loginView = document.getElementById('loginView');
    const loadingView = document.getElementById('loadingView');
    const dashboardView = document.getElementById('dashboardView');
    const navActions = document.getElementById('navActions');


    const loginForm = document.getElementById('loginForm');
    const studentIdInput = document.getElementById('studentId');
    const passwordInput = document.getElementById('password');
    const rememberMeCheckbox = document.getElementById('rememberMe');
    const togglePasswordBtn = document.getElementById('togglePasswordBtn');
    const togglePasswordIcon = document.getElementById('togglePasswordIcon');
    const loginAlert = document.getElementById('loginAlert');
    const alertMessage = document.getElementById('alertMessage');
    const submitLoginBtn = document.getElementById('submitLoginBtn');

    const displayUsername = document.getElementById('displayUsername');
    const refreshBtn = document.getElementById('refreshBtn');
    const logoutBtn = document.getElementById('logoutBtn');

    const loadingStatusText = document.getElementById('loadingStatusText');
    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3');

    const overallPercentage = document.getElementById('overallPercentage');
    const overallDetail = document.getElementById('overallDetail');
    const overallBadge = document.getElementById('overallBadge');
    const overallRing = document.getElementById('overallRing');

    const adviceIconWrap = document.getElementById('adviceIconWrap');
    const adviceIcon = document.getElementById('adviceIcon');
    const adviceTitle = document.getElementById('adviceTitle');
    const adviceText = document.getElementById('adviceText');

    const totalAttendedCount = document.getElementById('totalAttendedCount');
    const totalConductedCount = document.getElementById('totalConductedCount');

    const searchInput = document.getElementById('searchInput');
    const viewGridBtn = document.getElementById('viewGridBtn');
    const viewTableBtn = document.getElementById('viewTableBtn');
    const subjectsGrid = document.getElementById('subjectsGrid');
    const subjectsTableWrapper = document.getElementById('subjectsTableWrapper');
    const subjectsTableBody = document.getElementById('subjectsTableBody');
    const exportPdfBtn = document.getElementById('exportPdfBtn');

    // State Variables
    let currentAttendanceData = [];
    let currentViewMode = 'grid'; // 'grid' or 'table'
    let selectedTargetPerc = 75; // Default target percentage

    // Target Percentage Selector Handler (75%, 80%, 85%)
    document.querySelectorAll('.target-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.target-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            selectedTargetPerc = parseInt(e.target.getAttribute('data-target'), 10) || 75;
            if (currentAttendanceData.length > 0) {
                renderDashboard(currentAttendanceData);
            }
        });
    });

    // Initialize: Check Local Storage for Saved Credentials & Cached Data
    initApp();

    function initApp() {
        const savedId = localStorage.getItem('mits_stu_id');
        const savedPass = localStorage.getItem('mits_stu_pass');
        const cachedData = localStorage.getItem('mits_attendance_cache');

        if (savedId && savedPass) {
            studentIdInput.value = savedId;
            passwordInput.value = savedPass;
            rememberMeCheckbox.checked = true;
            displayUsername.textContent = savedId;

            // Load cached data instantly if available to stay on Dashboard
            if (cachedData) {
                try {
                    currentAttendanceData = JSON.parse(cachedData);
                    renderDashboard(currentAttendanceData);
                    showDashboardState();
                    // Background refresh
                    fetchAttendance(savedId, savedPass, true);
                    return;
                } catch (e) {
                    localStorage.removeItem('mits_attendance_cache');
                }
            }

            // Otherwise fetch attendance
            fetchAttendance(savedId, savedPass, false);
        } else {
            showLoginState();
        }
    }

    // Toggle Password Visibility (with e.preventDefault to prevent HTML5 form validation trigger)
    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const isPassword = passwordInput.type === 'password';
            passwordInput.type = isPassword ? 'text' : 'password';
            if (togglePasswordIcon) {
                togglePasswordIcon.className = isPassword ? 'fa-solid fa-eye-slash' : 'fa-solid fa-eye';
            }
        });
    }


    // Form Submit Handler
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = studentIdInput.value.trim();
        const password = passwordInput.value.trim();

        if (!username || !password) {
            showAlert('Please enter both Register Number and Password.');
            return;
        }

        if (rememberMeCheckbox.checked) {
            localStorage.setItem('mits_stu_id', username);
            localStorage.setItem('mits_stu_pass', password);
        } else {
            localStorage.removeItem('mits_stu_id');
            localStorage.removeItem('mits_stu_pass');
            localStorage.removeItem('mits_attendance_cache');
        }

        fetchAttendance(username, password, false);
    });

    // Fetch Attendance Function (with silent background refresh parameter)
    async function fetchAttendance(username, password, silent = false) {
        if (!silent) {
            hideAlert();
            showLoadingState();

            updateLoadingStep(1, 'Connecting to MITS IMS portal...');

            setTimeout(() => {
                updateLoadingStep(2, 'Authenticating credentials...');
            }, 1500);

            setTimeout(() => {
                updateLoadingStep(3, 'Scraping subject-wise attendance...');
            }, 3500);
        }

        try {
            const response = await fetch('/api/attendance', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password })
            });

            let result;
            try {
                result = await response.json();
            } catch (parseErr) {
                result = { error: `Server error (${response.status} ${response.statusText})` };
            }

            if (response.ok && result.success) {
                currentAttendanceData = result.data.map(item => ({
                    ...item,
                    included: true
                }));
                // Cache data in localStorage for persistent session
                if (rememberMeCheckbox.checked || localStorage.getItem('mits_stu_id')) {
                    localStorage.setItem('mits_attendance_cache', JSON.stringify(currentAttendanceData));
                }
                displayUsername.textContent = username;
                renderDashboard(currentAttendanceData);
                showDashboardState();
            } else {
                if (!silent) {
                    const errorMsg = result.error || result.detail || 'Login failed. Please check your credentials.';
                    showAlert(errorMsg);
                    showLoginState();
                }
            }
        } catch (err) {
            if (!silent) {
                showAlert('Network error: Unable to connect to server. Please check your connection.');
                showLoginState();
            }
        }
    }

    // Render Dashboard & Calculate Metrics based on Selected/Included Subjects
    function renderDashboard(attendanceList) {
        let totalAttended = 0;
        let totalConducted = 0;
        let includedCount = 0;

        attendanceList.forEach(item => {
            if (item.included !== false) {
                includedCount++;
                const att = parseInt(item.attended, 10) || 0;
                const tot = parseInt(item.total, 10) || 0;
                totalAttended += att;
                totalConducted += tot;
            }
        });

        // 1. Overall Percentage Calculation
        let overallPerc = 0;
        if (totalConducted > 0) {
            overallPerc = ((totalAttended / totalConducted) * 100).toFixed(2);
        }

        if (includedCount === 0) {
            overallPercentage.textContent = `N/A`;
            overallDetail.textContent = `0 Subjects Included`;
            overallBadge.textContent = 'Excluded';
            overallBadge.className = 'status-badge danger';
            totalAttendedCount.textContent = 0;
            totalConductedCount.textContent = 0;
            setOverallRingProgress(0);
            calculateBunkAdvice(0, 0, 0);
            renderSubjectViews(attendanceList);
            updateSelectAllState(attendanceList);
            return;
        }

        overallPercentage.textContent = `${overallPerc}%`;
        overallDetail.textContent = `Based on ${includedCount} courses`;
        totalAttendedCount.textContent = totalAttended;
        totalConductedCount.textContent = totalConducted;

        // 2. Set Overall Badge & Progress Ring
        const percVal = parseFloat(overallPerc);
        setOverallRingProgress(percVal);

        if (percVal >= selectedTargetPerc) {
            overallBadge.textContent = 'Safe Zone';
            overallBadge.className = 'status-badge success';
        } else if (percVal >= selectedTargetPerc - 5) {
            overallBadge.textContent = 'Borderline';
            overallBadge.className = 'status-badge warning';
        } else {
            overallBadge.textContent = 'Shortage';
            overallBadge.className = 'status-badge danger';
        }

        // 3. Bunk / Target Attendance Advice Calculator
        calculateBunkAdvice(totalAttended, totalConducted, percVal);


        // 4. Render Subject Views
        renderSubjectViews(attendanceList);

        // 5. Update Master Checkbox States
        updateSelectAllState(attendanceList);
    }

    // Set SVG Circular Progress Ring
    function setOverallRingProgress(percent) {
        const radius = overallRing.r.baseVal.value;
        const circumference = 2 * Math.PI * radius; // ~251.2
        const offset = circumference - (percent / 100) * circumference;
        overallRing.style.strokeDashoffset = Math.max(0, offset);
    }

    // Dynamic Bunk / Attendance Advice Calculator Logic (for selectedTargetPerc)
    function calculateBunkAdvice(attended, total, overallPerc) {
        if (total === 0) {
            adviceTitle.textContent = 'No Data';
            adviceText.textContent = 'No active subjects selected for calculation.';
            adviceIconWrap.className = 'advice-icon-wrap';
            adviceIcon.className = 'fa-solid fa-circle-question';
            return;
        }

        const targetRatio = selectedTargetPerc / 100; // Dynamic target threshold (75%, 80%, 85%)

        if (overallPerc >= selectedTargetPerc) {
            const canBunk = Math.floor((attended - targetRatio * total) / targetRatio);
            if (canBunk > 0) {
                adviceTitle.textContent = `Can Skip ${canBunk} ${canBunk === 1 ? 'Class' : 'Classes'}`;
                adviceText.textContent = `Selected Aggregate: ${overallPerc}%. You can skip ${canBunk} upcoming ${canBunk === 1 ? 'class' : 'classes'} and maintain >= ${selectedTargetPerc}%.`;
                adviceIconWrap.className = 'advice-icon-wrap safe';
                adviceIcon.className = 'fa-solid fa-shield-check';
            } else {
                adviceTitle.textContent = `On Target (${selectedTargetPerc}%)`;
                adviceText.textContent = `Selected Aggregate: ${overallPerc}%. You are right at the ${selectedTargetPerc}% threshold. Do not miss classes!`;
                adviceIconWrap.className = 'advice-icon-wrap safe';
                adviceIcon.className = 'fa-solid fa-circle-check';
            }
        } else {
            const mustAttend = Math.ceil((targetRatio * total - attended) / (1 - targetRatio));
            adviceTitle.textContent = `Need ${mustAttend} ${mustAttend === 1 ? 'Class' : 'Classes'}`;
            adviceText.textContent = `Selected Aggregate: ${overallPerc}%. You must attend the next ${mustAttend} consecutive ${mustAttend === 1 ? 'class' : 'classes'} to reach ${selectedTargetPerc}%.`;
            adviceIconWrap.className = 'advice-icon-wrap alert';
            adviceIcon.className = 'fa-solid fa-triangle-exclamation';
        }

    }


    // Render Subject Cards & Table with Checkboxes
    function renderSubjectViews(data) {
        const query = searchInput.value.toLowerCase().trim();
        const filtered = data.filter(item =>
            item.subject.toLowerCase().includes(query)
        );

        // Grid View HTML
        subjectsGrid.innerHTML = '';
        if (filtered.length === 0) {
            subjectsGrid.innerHTML = `
                <div class="glass-card" style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-folder-open" style="font-size: 32px; margin-bottom: 12px; display: block;"></i>
                    No subject records found matching "${query}".
                </div>
            `;
        } else {
            filtered.forEach(item => {
                const perc = parseFloat(item.percentage) || 0;
                let statusClass = 'success';
                let badgeText = 'Good';

                if (perc < 65) {
                    statusClass = 'danger';
                    badgeText = 'Low';
                } else if (perc < 75) {
                    statusClass = 'warning';
                    badgeText = 'Borderline';
                }

                const isChecked = item.included !== false;

                const cardHtml = `
                    <div class="subject-card glass-card ${isChecked ? '' : 'excluded'}">
                        <div class="subject-header">
                            <div class="subject-card-check">
                                <input type="checkbox" class="sub-check" data-subject="${escapeHtml(item.subject)}" ${isChecked ? 'checked' : ''} title="Include in overall calculation">
                                <h4 class="subject-title">${escapeHtml(item.subject)}</h4>
                            </div>
                            <span class="status-badge ${statusClass}">${badgeText}</span>
                        </div>
                        <div class="subject-stats">
                            <span class="subject-perc">${item.percentage}%</span>
                            <span class="subject-counts">${item.attended} / ${item.total} Attended</span>
                        </div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill ${statusClass}" style="width: ${Math.min(100, Math.max(0, perc))}%;"></div>
                        </div>
                        ${!isChecked ? '<div class="excluded-tag" style="margin-top: 8px;"><i class="fa-solid fa-eye-slash"></i> Excluded from calculation</div>' : ''}
                    </div>
                `;
                subjectsGrid.insertAdjacentHTML('beforeend', cardHtml);
            });
        }

        // Table View HTML
        subjectsTableBody.innerHTML = '';
        filtered.forEach((item, idx) => {
            const perc = parseFloat(item.percentage) || 0;
            let statusClass = 'success';
            let badgeText = 'Good';

            if (perc < 65) {
                statusClass = 'danger';
                badgeText = 'Low';
            } else if (perc < 75) {
                statusClass = 'warning';
                badgeText = 'Borderline';
            }

            const isChecked = item.included !== false;

            const trHtml = `
                <tr class="${isChecked ? '' : 'excluded-row'}">
                    <td><input type="checkbox" class="sub-check" data-subject="${escapeHtml(item.subject)}" ${isChecked ? 'checked' : ''} title="Include in overall calculation"></td>
                    <td>${idx + 1}</td>
                    <td><strong>${escapeHtml(item.subject)}</strong></td>
                    <td>${item.attended}</td>
                    <td>${item.total}</td>
                    <td><strong>${item.percentage}%</strong></td>
                    <td><span class="status-badge ${statusClass}">${badgeText}</span></td>
                </tr>
            `;
            subjectsTableBody.insertAdjacentHTML('beforeend', trHtml);
        });

        // Attach Checkbox Listeners
        document.querySelectorAll('.sub-check').forEach(chk => {
            chk.addEventListener('change', (e) => {
                const subjName = e.target.getAttribute('data-subject');
                const targetItem = currentAttendanceData.find(i => i.subject === subjName);
                if (targetItem) {
                    targetItem.included = e.target.checked;
                    renderDashboard(currentAttendanceData);
                }
            });
        });
    }

    // Helper to sync Select All button & Master Table Checkbox
    function updateSelectAllState(data) {
        const selectAllBtnText = document.getElementById('selectAllBtnText');
        const masterTableCheckbox = document.getElementById('masterTableCheckbox');

        const allIncluded = data.length > 0 && data.every(i => i.included !== false);

        if (selectAllBtnText) {
            selectAllBtnText.textContent = allIncluded ? 'Deselect All' : 'Select All';
        }

        if (masterTableCheckbox) {
            masterTableCheckbox.checked = allIncluded;
        }
    }

    // Select All / Deselect All Handlers
    const selectAllBtn = document.getElementById('selectAllBtn');
    const masterTableCheckbox = document.getElementById('masterTableCheckbox');

    function toggleAllSubjects(targetState) {
        currentAttendanceData.forEach(item => {
            item.included = targetState;
        });
        renderDashboard(currentAttendanceData);
    }

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            const anyUnchecked = currentAttendanceData.some(i => i.included === false);
            toggleAllSubjects(anyUnchecked);
        });
    }

    if (masterTableCheckbox) {
        masterTableCheckbox.addEventListener('change', (e) => {
            toggleAllSubjects(e.target.checked);
        });
    }


    // Search Input Listener
    searchInput.addEventListener('input', () => {
        renderSubjectViews(currentAttendanceData);
    });

    // View Toggle Handlers
    viewGridBtn.addEventListener('click', () => {
        currentViewMode = 'grid';
        viewGridBtn.classList.add('active');
        viewTableBtn.classList.remove('active');
        subjectsGrid.style.display = 'grid';
        subjectsTableWrapper.style.display = 'none';
    });

    viewTableBtn.addEventListener('click', () => {
        currentViewMode = 'table';
        viewTableBtn.classList.add('active');
        viewGridBtn.classList.remove('active');
        subjectsGrid.style.display = 'none';
        subjectsTableWrapper.style.display = 'block';
    });

    // Refresh Handler
    refreshBtn.addEventListener('click', () => {
        const username = studentIdInput.value.trim();
        const password = passwordInput.value.trim();
        if (username && password) {
            fetchAttendance(username, password);
        }
    });

    // Logout Handler - Clears session & data so user only logs out when clicking this
    logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('mits_stu_id');
        localStorage.removeItem('mits_stu_pass');
        localStorage.removeItem('mits_attendance_cache');
        currentAttendanceData = [];
        studentIdInput.value = '';
        passwordInput.value = '';
        showLoginState();
    });

    // Print / Export PDF Handler
    if (typeof exportPdfBtn !== 'undefined' && exportPdfBtn) {
        exportPdfBtn.addEventListener('click', () => {
            window.print();
        });
    }


    // View State Switchers
    function showLoginState() {
        if (loginView) loginView.style.display = 'flex';
        if (loadingView) loadingView.style.display = 'none';
        if (dashboardView) dashboardView.style.display = 'none';
        if (navbar) navbar.style.display = 'flex';
        if (navActions) navActions.style.display = 'none';
    }

    function showLoadingState() {
        if (loginView) loginView.style.display = 'none';
        if (loadingView) loadingView.style.display = 'flex';
        if (dashboardView) dashboardView.style.display = 'none';
        if (navbar) navbar.style.display = 'flex';
        if (navActions) navActions.style.display = 'none';
    }

    function showDashboardState() {
        if (loginView) loginView.style.display = 'none';
        if (loadingView) loadingView.style.display = 'none';
        if (dashboardView) dashboardView.style.display = 'flex';
        if (navbar) navbar.style.display = 'flex';
        if (navActions) navActions.style.display = 'flex';
    }


    function updateLoadingStep(stepNum, text) {
        loadingStatusText.textContent = text;
        const loadingBarFill = document.getElementById('loadingBarFill');
        const loadingPercentText = document.getElementById('loadingPercentText');

        let perc = 15;
        if (stepNum === 1) perc = 35;
        if (stepNum === 2) perc = 70;
        if (stepNum === 3) perc = 95;

        if (loadingBarFill) loadingBarFill.style.width = `${perc}%`;
        if (loadingPercentText) loadingPercentText.textContent = `${perc}%`;

        [step1, step2, step3].forEach((el, index) => {
            if (index + 1 < stepNum) {
                el.className = 'step-item done';
            } else if (index + 1 === stepNum) {
                el.className = 'step-item active';
            } else {
                el.className = 'step-item';
            }
        });
    }


    function showAlert(msg) {
        alertMessage.textContent = msg;
        loginAlert.style.display = 'flex';
    }

    function hideAlert() {
        loginAlert.style.display = 'none';
    }

    function escapeHtml(str) {
        return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // PWA Service Worker Registration
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('/service-worker.js', { scope: '/' })
                .then(reg => console.log('[PWA] Service Worker registered:', reg.scope))
                .catch(err => console.error('[PWA] SW registration error:', err));
        });
    }

    // Custom PWA Install Prompt (A2HS) Logic
    let deferredPrompt = null;
    const installModal = document.getElementById('installModal');
    const installNowBtn = document.getElementById('installNowBtn');
    const installLaterBtn = document.getElementById('installLaterBtn');
    const pwaInstallHeaderBtn = document.getElementById('pwaInstallHeaderBtn');

    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent default mini-infobar from showing
        e.preventDefault();
        deferredPrompt = e;

        // Check if user already dismissed or installed
        const isDismissed = localStorage.getItem('pwa_dismissed') === 'true';
        const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;

        if (!isStandalone) {
            if (pwaInstallHeaderBtn) {
                pwaInstallHeaderBtn.style.display = 'inline-flex';
            }

            if (!isDismissed && installModal) {
                setTimeout(() => {
                    installModal.style.display = 'flex';
                }, 2000);
            }
        }
    });

    if (installNowBtn) {
        installNowBtn.addEventListener('click', async () => {
            if (installModal) installModal.style.display = 'none';
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                console.log(`[PWA] Install prompt outcome: ${outcome}`);
                if (outcome === 'accepted') {
                    localStorage.setItem('pwa_installed', 'true');
                }
                deferredPrompt = null;
            }
        });
    }

    if (installLaterBtn) {
        installLaterBtn.addEventListener('click', () => {
            if (installModal) installModal.style.display = 'none';
            localStorage.setItem('pwa_dismissed', 'true');
        });
    }

    if (pwaInstallHeaderBtn) {
        pwaInstallHeaderBtn.addEventListener('click', async () => {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                if (outcome === 'accepted') {
                    localStorage.setItem('pwa_installed', 'true');
                    pwaInstallHeaderBtn.style.display = 'none';
                }
                deferredPrompt = null;
            } else {
                alert('App is ready to install! Open your browser menu (⋮) and tap "Add to Home screen".');
            }
        });
    }

    // Hide install header button if already in standalone mode
    window.addEventListener('appinstalled', () => {
        console.log('[PWA] App successfully installed!');
        if (installModal) installModal.style.display = 'none';
        if (pwaInstallHeaderBtn) pwaInstallHeaderBtn.style.display = 'none';
        localStorage.setItem('pwa_installed', 'true');
    });

    // -------------------------------------------------------------
    // 📄 PROFESSIONAL PDF GENERATION & COPY TO CLIPBOARD MODULE
    // -------------------------------------------------------------
    const downloadPdfBtn = document.getElementById('downloadPdfBtn');
    const copyReportBtn = document.getElementById('copyReportBtn');

    if (downloadPdfBtn) {
        downloadPdfBtn.addEventListener('click', downloadPdfReport);
    }

    if (copyReportBtn) {
        copyReportBtn.addEventListener('click', copyReportToClipboard);
    }

    // Toast Notification System
    function showToast(message, type = 'success') {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = type === 'success'
            ? `<i class="fa-solid fa-circle-check text-success"></i> <span>${escapeHtml(message)}</span>`
            : `<i class="fa-solid fa-circle-xmark text-danger"></i> <span>${escapeHtml(message)}</span>`;

        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // Helper to get attendance data safely (from state or DOM fallback)
    function getExportData() {
        if (Array.isArray(currentAttendanceData) && currentAttendanceData.length > 0) {
            return currentAttendanceData;
        }
        const data = [];
        const cards = document.querySelectorAll('.subject-card');
        cards.forEach(card => {
            const subjectEl = card.querySelector('.subject-name');
            const countEl = card.querySelector('.count-val') || card.querySelector('.attended-count');
            const percEl = card.querySelector('.perc-val') || card.querySelector('.subject-perc');
            if (subjectEl) {
                const subject = subjectEl.textContent.trim();
                const counts = countEl ? countEl.textContent.trim().split('/') : ['0', '0'];
                const attended = counts[0]?.trim() || '0';
                const total = counts[1]?.trim() || '0';
                const percentage = percEl ? percEl.textContent.replace('%', '').trim() : '0';
                data.push({ subject, attended, total, percentage, included: true });
            }
        });
        return data;
    }

    // 📄 Download Vector A4 PDF Function
    async function downloadPdfReport() {
        const data = getExportData();
        if (!data || data.length === 0) {
            showToast('❌ Unable to complete the requested action. Please try again.', 'error');
            alert('Please login to fetch attendance data before downloading PDF.');
            return;
        }

        const username = (displayUsername && displayUsername.textContent.trim()) ? displayUsername.textContent.trim() : 'Student';
        const dateStr = new Date().toISOString().split('T')[0];
        const formattedDate = new Date().toLocaleString('en-US', {
            dateStyle: 'medium',
            timeStyle: 'short'
        });

        if (downloadPdfBtn) {
            downloadPdfBtn.disabled = true;
            downloadPdfBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Generating...</span>';
        }

        try {
            const jsPDFObj = (window.jspdf && window.jspdf.jsPDF) ? window.jspdf.jsPDF : window.jsPDF;
            if (!jsPDFObj) {
                showToast('PDF generator unavailable. Opening print window...', 'error');
                window.print();
                return;
            }

            const doc = new jsPDFObj('p', 'mm', 'a4');
            const pageWidth = doc.internal.pageSize.getWidth();

            const primaryColor = [37, 99, 235];   // Royal Blue #2563EB
            const darkColor = [15, 23, 42];      // Slate 900 #0F172A
            const textSecondary = [71, 85, 105];  // Slate 600 #475569

            // 1. Header Banner
            doc.setFillColor(...primaryColor);
            doc.rect(0, 0, pageWidth, 28, 'F');

            doc.setTextColor(255, 255, 255);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(15);
            doc.text('ATTENDIX ATTENDANCE REPORT', 14, 18);

            // 2. Student Information Box
            doc.setTextColor(...darkColor);
            doc.setFontSize(10);
            doc.setFont('helvetica', 'bold');
            doc.text(`Register Number     : `, 14, 38);
            doc.setFont('helvetica', 'normal');
            doc.text(`${username}`, 56, 38);

            doc.setFont('helvetica', 'bold');
            doc.text(`Generated On        : `, 14, 44);
            doc.setFont('helvetica', 'normal');
            doc.text(`${formattedDate}`, 56, 44);

            // 3. Summary KPI Box
            let totalAttended = 0;
            let totalConducted = 0;
            data.forEach(item => {
                if (item.included !== false) {
                    totalAttended += parseInt(item.attended, 10) || 0;
                    totalConducted += parseInt(item.total, 10) || 0;
                }
            });

            const overallPerc = totalConducted > 0 ? ((totalAttended / totalConducted) * 100).toFixed(2) : '0.0';

            doc.setFillColor(248, 250, 252);
            doc.roundedRect(14, 50, pageWidth - 28, 20, 3, 3, 'F');

            doc.setFont('helvetica', 'bold');
            doc.setFontSize(11);
            doc.setTextColor(...primaryColor);
            doc.text(`Overall Attendance: ${overallPerc}%`, 20, 62);

            doc.setTextColor(...darkColor);
            doc.setFontSize(10);
            doc.text(`Total Subjects: ${data.length}`, 95, 62);
            doc.text(`Target Criteria: ${selectedTargetPerc || 75}%`, 155, 62);

            // 4. Subject Table (jsPDF AutoTable)
            const tableRows = data.map((item, index) => {
                const percNum = parseFloat(item.percentage) || 0;
                let statusStr = '🟢 Safe';
                if (percNum < 65) statusStr = '🔴 Critical';
                else if (percNum < 75) statusStr = '🟡 Warning';

                return [
                    index + 1,
                    item.subject,
                    item.attended,
                    item.total,
                    `${item.percentage}%`,
                    statusStr
                ];
            });

            if (doc.autoTable) {
                doc.autoTable({
                    startY: 76,
                    head: [['#', 'Subject', 'Present', 'Total', 'Percentage', 'Status']],
                    body: tableRows,
                    theme: 'striped',
                    headStyles: {
                        fillColor: primaryColor,
                        textColor: [255, 255, 255],
                        fontStyle: 'bold',
                        fontSize: 10
                    },
                    bodyStyles: {
                        fontSize: 9,
                        textColor: [15, 23, 42]
                    },
                    columnStyles: {
                        0: { cellWidth: 12 },
                        1: { cellWidth: 82 },
                        2: { cellWidth: 22, halign: 'center' },
                        3: { cellWidth: 24, halign: 'center' },
                        4: { cellWidth: 24, halign: 'center' },
                        5: { cellWidth: 22, halign: 'center' }
                    }
                });
            }

            // 5. Page Numbers & Footer
            const totalPages = doc.internal.getNumberOfPages();
            for (let i = 1; i <= totalPages; i++) {
                doc.setPage(i);
                doc.setFontSize(8);
                doc.setTextColor(...textSecondary);
                doc.text(`Page ${i} of ${totalPages}`, pageWidth - 30, doc.internal.pageSize.getHeight() - 10);
                doc.text('Generated by Attendix', 14, doc.internal.pageSize.getHeight() - 10);
            }

            const fileName = `Attendance_Report_${username}_${dateStr}.pdf`;
            doc.save(fileName);

            showToast('✅ Attendance report downloaded successfully.', 'success');
        } catch (err) {
            console.error('PDF Generation Error:', err);
            showToast('❌ Unable to complete the requested action. Please try again.', 'error');
            window.print();
        } finally {
            if (downloadPdfBtn) {
                downloadPdfBtn.disabled = false;
                downloadPdfBtn.innerHTML = '<i class="fa-solid fa-file-pdf"></i> <span>Download PDF</span>';
            }
        }
    }

    // 📋 Copy Formatted Text Report to Clipboard Function
    async function copyReportToClipboard() {
        const data = getExportData();
        if (!data || data.length === 0) {
            showToast('❌ Unable to complete the requested action. Please try again.', 'error');
            alert('Please login to fetch attendance data before copying report.');
            return;
        }

        const username = (displayUsername && displayUsername.textContent.trim()) ? displayUsername.textContent.trim() : 'Student';
        const formattedDate = new Date().toLocaleString('en-US', {
            dateStyle: 'medium',
            timeStyle: 'short'
        });

        let totalAttended = 0;
        let totalConducted = 0;

        data.forEach(item => {
            if (item.included !== false) {
                totalAttended += parseInt(item.attended, 10) || 0;
                totalConducted += parseInt(item.total, 10) || 0;
            }
        });

        const overallPerc = totalConducted > 0 ? ((totalAttended / totalConducted) * 100).toFixed(2) : '0.0';

        let reportText = `=============================\n`;
        reportText += `ATTENDIX ATTENDANCE REPORT\n`;
        reportText += `=============================\n\n`;
        reportText += `Register Number : ${username}\n`;
        reportText += `Overall Attendance : ${overallPerc}%\n\n`;
        reportText += `--------------------------------\n\n`;
        reportText += `Subject-wise Attendance\n\n`;

        data.forEach((item, index) => {
            reportText += `${index + 1}. ${item.subject}\n`;
            reportText += `Present    : ${item.attended}\n`;
            reportText += `Total      : ${item.total}\n`;
            reportText += `Attendance : ${item.percentage}%\n\n`;
        });

        reportText += `--------------------------------\n\n`;
        reportText += `Generated on: ${formattedDate}\n`;
        reportText += `Generated using Attendix\n`;
        reportText += `=============================\n`;

        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(reportText);
            } else {
                const textarea = document.createElement('textarea');
                textarea.value = reportText;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
            }

            showToast('✅ Attendance report copied to clipboard.', 'success');
        } catch (err) {
            console.error('Clipboard Error:', err);
            showToast('❌ Unable to complete the requested action. Please try again.', 'error');
        }
    }
});



