document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const navbar = document.querySelector('.navbar');
    const loginView = document.getElementById('loginView');
    const loadingView = document.getElementById('loadingView');
    const dashboardView = document.getElementById('dashboardView');
    const navActions = document.getElementById('navActions');
    const navTabs = document.getElementById('navTabs');
    const mobileBottomNav = document.getElementById('mobileBottomNav');

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
    const adviceText = document.getElementById('adviceText') || document.getElementById('adviceMessage');

    const totalAttendedCount = document.getElementById('totalAttendedCount');
    const totalConductedCount = document.getElementById('totalConductedCount');

    const searchInput = document.getElementById('searchInput');
    const sortSelect = document.getElementById('sortSelect');
    const viewGridBtn = document.getElementById('viewGridBtn');
    const viewTableBtn = document.getElementById('viewTableBtn');
    const subjectsGrid = document.getElementById('subjectsGrid');
    const subjectsTableWrapper = document.getElementById('subjectsTableWrapper');
    const subjectsTableBody = document.getElementById('subjectsTableBody');
    const exportPdfBtn = document.getElementById('exportPdfBtn');

    // Theme Switcher Elements
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const themeToggleIcon = document.getElementById('themeToggleIcon');

    // State Variables
    let currentAttendanceData = [];
    let currentViewMode = 'grid'; // 'grid' or 'table'
    let selectedTargetPerc = 75; // Default target percentage
    let barChartInstance = null;
    let doughnutChartInstance = null;
    let currentStudentName = localStorage.getItem('mits_student_name') || '';
    if (currentStudentName && ['code', 'subject code', 'course code', 'student', 'name', 'student name', 'status', 'title'].includes(currentStudentName.trim().toLowerCase())) {
        currentStudentName = '';
        localStorage.removeItem('mits_student_name');
    }
    let currentRegisterNumber = localStorage.getItem('mits_stu_id') ? localStorage.getItem('mits_stu_id').toUpperCase() : '';
    let currentLastLogin = localStorage.getItem('mits_last_login') || '';


    // -------------------------------------------------------------
    // 🎨 THEME ENGINE (DARK / LIGHT MODE WITH LOCALSTORAGE MEMORY)
    // -------------------------------------------------------------
    initTheme();

    function initTheme() {
        const savedTheme = localStorage.getItem('attendix_theme');
        if (savedTheme) {
            setTheme(savedTheme);
        } else {
            const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            setTheme(prefersDark ? 'dark' : 'light');
        }
    }

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('attendix_theme', theme);
        if (themeToggleIcon) {
            themeToggleIcon.className = theme === 'dark' ? 'fa-solid fa-sun' : 'fa-solid fa-moon';
        }
        if (barChartInstance || doughnutChartInstance) {
            renderCharts(currentAttendanceData);
        }
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const nextTheme = currentTheme === 'dark' ? 'light' : 'dark';
            setTheme(nextTheme);
        });
    }

    // Target Percentage Selector Handler (75%, 80%, 85%, 90%)
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
            displayUsername.textContent = currentStudentName || savedId.toUpperCase();


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

    // Toggle Password Visibility
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

    // Fetch Attendance Function
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

        function getApiEndpoint() {
            if (window.location.protocol === 'file:') {
                return 'http://localhost:8080/api/attendance';
            }
            if ((window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && window.location.port !== '8080' && window.location.port !== '') {
                return `http://${window.location.hostname}:8080/api/attendance`;
            }
            return '/api/attendance';
        }

        try {
            let apiEndpoint = getApiEndpoint();
            let response;
            try {
                response = await fetch(apiEndpoint, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                });
            } catch (firstErr) {
                if (apiEndpoint !== 'http://localhost:8080/api/attendance' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol === 'file:')) {
                    response = await fetch('http://localhost:8080/api/attendance', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ username, password })
                    });
                } else {
                    throw firstErr;
                }
            }

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
                currentRegisterNumber = username.toUpperCase();
                const rawName = (result.student_name && result.student_name.trim()) ? result.student_name.trim() : '';
                currentStudentName = (rawName && !invalidNames.includes(rawName.toLowerCase())) ? rawName : '';
                currentLastLogin = new Date().toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });


                // Cache data in localStorage for persistent session
                if (rememberMeCheckbox.checked || localStorage.getItem('mits_stu_id')) {
                    localStorage.setItem('mits_attendance_cache', JSON.stringify(currentAttendanceData));
                    if (currentStudentName) {
                        localStorage.setItem('mits_student_name', currentStudentName);
                    } else {
                        localStorage.removeItem('mits_student_name');
                    }
                    localStorage.setItem('mits_last_login', currentLastLogin);
                }
                displayUsername.textContent = currentStudentName || currentRegisterNumber;
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
            renderCharts(attendanceList);
            return;
        }

        // Animated Number Counting Effect
        animateValue(overallPercentage, 0, parseFloat(overallPerc), 800, '%');
        overallDetail.textContent = `Based on ${includedCount} courses`;
        animateValue(totalAttendedCount, 0, totalAttended, 600);
        animateValue(totalConductedCount, 0, totalConducted, 600);

        // 2. Set Overall Badge & Progress Ring
        const percVal = parseFloat(overallPerc);

        let statusStrokeColor = '#10b981';
        if (percVal >= selectedTargetPerc) {
            overallBadge.textContent = 'Safe Zone';
            overallBadge.className = 'status-badge success';
            statusStrokeColor = '#10b981';
        } else if (percVal >= selectedTargetPerc - 5) {
            overallBadge.textContent = 'Borderline';
            overallBadge.className = 'status-badge warning';
            statusStrokeColor = '#f59e0b';
        } else {
            overallBadge.textContent = 'Shortage';
            overallBadge.className = 'status-badge danger';
            statusStrokeColor = '#ef4444';
        }

        setOverallRingProgress(percVal, statusStrokeColor);

        // 3. Bunk / Target Attendance Advice Calculator
        calculateBunkAdvice(totalAttended, totalConducted, percVal);

        // 4. Update Student Profile Banner & Modal Metrics
        const profileBannerName = document.getElementById('profileBannerName');
        const profileBannerRoll = document.getElementById('profileBannerRoll');
        const profileBannerLastLogin = document.getElementById('profileBannerLastLogin');

        const modalStudentName = document.getElementById('modalStudentName');
        const modalRollNo = document.getElementById('modalRollNo');
        const modalLastLogin = document.getElementById('modalLastLogin');

        const modalOverallPerc = document.getElementById('modalOverallPerc');
        const modalTotalCourses = document.getElementById('modalTotalCourses');
        const modalAttendedClasses = document.getElementById('modalAttendedClasses');
        const modalStatusBadge = document.getElementById('modalStatusBadge');

        const activeRegNo = currentRegisterNumber || (displayUsername ? displayUsername.textContent.trim() : 'Student');
        const invalidNames = ['code', 'subject code', 'course code', 'student', 'name', 'student name', 'status', 'title'];
        const isNameValid = currentStudentName && !invalidNames.includes(currentStudentName.trim().toLowerCase());
        const activeName = isNameValid ? currentStudentName : activeRegNo;
        const activeLogin = currentLastLogin || 'Just now';

        if (profileBannerName) profileBannerName.textContent = activeName;
        if (profileBannerRoll) profileBannerRoll.textContent = activeRegNo;
        if (profileBannerLastLogin) profileBannerLastLogin.textContent = activeLogin;

        if (modalStudentName) modalStudentName.textContent = activeName;
        if (modalRollNo) modalRollNo.textContent = activeRegNo;
        if (modalLastLogin) modalLastLogin.textContent = activeLogin;

        if (modalOverallPerc) modalOverallPerc.textContent = `${overallPerc}%`;
        if (modalTotalCourses) modalTotalCourses.textContent = includedCount;
        if (modalAttendedClasses) modalAttendedClasses.textContent = `${totalAttended} / ${totalConducted}`;
        if (modalStatusBadge) {
            modalStatusBadge.textContent = overallBadge.textContent;
            modalStatusBadge.className = overallBadge.className;
        }


        // 5. Render Subject Views
        renderSubjectViews(attendanceList);

        // 6. Render Interactive Charts
        renderCharts(attendanceList);

        // 7. Update Master Checkbox States
        updateSelectAllState(attendanceList);
    }

    // Smooth Number Counter Animation
    function animateValue(element, start, end, duration, suffix = '') {
        if (!element) return;
        const startTime = performance.now();

        function updateNumber(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            const easedProgress = 1 - Math.pow(1 - progress, 3);
            const currentValue = (start + (end - start) * easedProgress).toFixed(suffix ? 1 : 0);

            element.textContent = `${currentValue}${suffix}`;

            if (progress < 1) {
                requestAnimationFrame(updateNumber);
            } else {
                element.textContent = `${end.toFixed(suffix ? 1 : 0)}${suffix}`;
            }
        }

        requestAnimationFrame(updateNumber);
    }

    // Set SVG Circular Progress Ring
    function setOverallRingProgress(percent, color = null) {
        if (!overallRing) return;
        const radius = overallRing.r.baseVal.value; // ~44
        const circumference = 2 * Math.PI * radius; // ~276.4
        const offset = circumference - (percent / 100) * circumference;
        overallRing.style.strokeDashoffset = Math.max(0, offset);
        if (color) {
            overallRing.style.stroke = color;
        } else {
            overallRing.style.stroke = 'url(#gradientRing)';
        }
    }

    // Dynamic Bunk / Attendance Advice Calculator Logic
    function calculateBunkAdvice(attended, total, overallPerc) {
        if (total === 0) {
            adviceTitle.textContent = 'No Data';
            adviceText.textContent = 'No active subjects selected for calculation.';
            if (adviceIconWrap) adviceIconWrap.className = 'advice-icon-wrap';
            if (adviceIcon) adviceIcon.className = 'fa-solid fa-circle-question';
            return;
        }

        const targetRatio = selectedTargetPerc / 100;

        if (overallPerc >= selectedTargetPerc) {
            const canBunk = Math.floor((attended - targetRatio * total) / targetRatio);
            if (canBunk > 0) {
                adviceTitle.textContent = `Can Skip ${canBunk} ${canBunk === 1 ? 'Class' : 'Classes'}`;
                adviceText.textContent = `Selected Aggregate: ${overallPerc}%. You can skip ${canBunk} upcoming ${canBunk === 1 ? 'class' : 'classes'} and maintain >= ${selectedTargetPerc}%.`;
                if (adviceIconWrap) adviceIconWrap.className = 'advice-icon-wrap safe';
                if (adviceIcon) adviceIcon.className = 'fa-solid fa-shield-halved';
            } else {
                adviceTitle.textContent = `On Target (${selectedTargetPerc}%)`;
                adviceText.textContent = `Selected Aggregate: ${overallPerc}%. You are right at the ${selectedTargetPerc}% threshold. Do not miss classes!`;
                if (adviceIconWrap) adviceIconWrap.className = 'advice-icon-wrap safe';
                if (adviceIcon) adviceIcon.className = 'fa-solid fa-circle-check';
            }
        } else {
            const mustAttend = Math.ceil((targetRatio * total - attended) / (1 - targetRatio));
            adviceTitle.textContent = `Need ${mustAttend} ${mustAttend === 1 ? 'Class' : 'Classes'}`;
            adviceText.textContent = `Selected Aggregate: ${overallPerc}%. You must attend the next ${mustAttend} consecutive ${mustAttend === 1 ? 'class' : 'classes'} to reach ${selectedTargetPerc}%.`;
            if (overallPerc >= selectedTargetPerc - 5) {
                if (adviceIconWrap) adviceIconWrap.className = 'advice-icon-wrap warning';
                if (adviceIcon) adviceIcon.className = 'fa-solid fa-triangle-exclamation';
            } else {
                if (adviceIconWrap) adviceIconWrap.className = 'advice-icon-wrap alert';
                if (adviceIcon) adviceIcon.className = 'fa-solid fa-circle-exclamation';
            }
        }
    }

    // Render Subject Cards & Table with Checkboxes & Sorting
    function renderSubjectViews(data) {
        const query = searchInput.value.toLowerCase().trim();
        let filtered = data.filter(item =>
            item.subject.toLowerCase().includes(query)
        );

        // Sorting Logic
        const sortVal = sortSelect ? sortSelect.value : 'default';
        if (sortVal === 'perc-desc') {
            filtered.sort((a, b) => (parseFloat(b.percentage) || 0) - (parseFloat(a.percentage) || 0));
        } else if (sortVal === 'perc-asc') {
            filtered.sort((a, b) => (parseFloat(a.percentage) || 0) - (parseFloat(b.percentage) || 0));
        } else if (sortVal === 'total-desc') {
            filtered.sort((a, b) => (parseInt(b.total, 10) || 0) - (parseInt(a.total, 10) || 0));
        } else if (sortVal === 'name-asc') {
            filtered.sort((a, b) => a.subject.localeCompare(b.subject));
        }

        // Grid View HTML
        subjectsGrid.innerHTML = '';
        if (filtered.length === 0) {
            subjectsGrid.innerHTML = `
                <div class="glass-card" style="grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-secondary);">
                    <i class="fa-solid fa-folder-open" style="font-size: 36px; margin-bottom: 12px; display: block; color: var(--text-muted);"></i>
                    No subject records found matching "${query}".
                </div>
            `;
        } else {
            filtered.forEach(item => {
                const perc = parseFloat(item.percentage) || 0;
                let statusClass = 'success';
                let badgeText = 'Safe (85%+)';

                if (perc < 60) {
                    statusClass = 'danger';
                    badgeText = 'Critical (<60%)';
                } else if (perc < 70) {
                    statusClass = 'orange';
                    badgeText = 'Warning (60-69%)';
                } else if (perc < 85) {
                    statusClass = 'warning';
                    badgeText = 'Good (70-84%)';
                }

                const isChecked = item.included !== false;
                const displaySubjectCode = item.subject ? item.subject.split(' - ')[0].trim() : item.subject;
                const fullSubjectName = item.subject && item.subject.includes(' - ') ? item.subject.split(' - ').slice(1).join(' - ').trim() : '';

                const cardHtml = `
                    <div class="subject-card glass-card ${isChecked ? '' : 'excluded'} animate-fade-in">
                        <div class="subject-header">
                            <div class="subject-card-check">
                                <input type="checkbox" class="sub-check" data-subject="${escapeHtml(item.subject)}" ${isChecked ? 'checked' : ''} title="Include in overall calculation">
                                <div>
                                    <h4 class="subject-title">${escapeHtml(displaySubjectCode)}</h4>
                                    ${fullSubjectName ? `<span class="subject-sub-name">${escapeHtml(fullSubjectName)}</span>` : ''}
                                </div>
                            </div>
                            <span class="status-badge ${statusClass}">${badgeText}</span>
                        </div>
                        <div class="subject-stats">
                            <span class="subject-perc ${statusClass}">${item.percentage}%</span>
                            <span class="subject-counts"><i class="fa-solid fa-check-double text-success"></i> ${item.attended} / ${item.total} Attended</span>
                        </div>
                        <div class="progress-bar-bg">
                            <div class="progress-bar-fill ${statusClass}" style="width: ${Math.min(100, Math.max(0, perc))}%;"></div>
                        </div>
                        ${!isChecked ? '<div class="excluded-tag"><i class="fa-solid fa-eye-slash"></i> Excluded from overall aggregate</div>' : ''}
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
            let badgeText = 'Safe Zone';

            if (perc < 60) {
                statusClass = 'danger';
                badgeText = 'Critical';
            } else if (perc < 70) {
                statusClass = 'orange';
                badgeText = 'Warning';
            } else if (perc < 85) {
                statusClass = 'warning';
                badgeText = 'Satisfactory';
            }

            const isChecked = item.included !== false;

            const trHtml = `
                <tr class="${isChecked ? '' : 'excluded-row'}">
                    <td><input type="checkbox" class="sub-check" data-subject="${escapeHtml(item.subject)}" ${isChecked ? 'checked' : ''} title="Include in overall calculation"></td>
                    <td>${idx + 1}</td>
                    <td><strong class="table-subject-name">${escapeHtml(item.subject)}</strong></td>
                    <td><span class="badge-count count-attended">${item.attended}</span></td>
                    <td><span class="badge-count count-total">${item.total}</span></td>
                    <td><strong class="table-perc ${statusClass}">${item.percentage}%</strong></td>
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

    // -------------------------------------------------------------
    // 📊 CHART.JS INTEGRATION (BAR & DOUGHNUT VISUALIZATIONS)
    // -------------------------------------------------------------
    function renderCharts(data) {
        if (!data || data.length === 0) return;

        const isDark = (document.documentElement.getAttribute('data-theme') || 'dark') === 'dark';
        const textColor = isDark ? '#94a3b8' : '#475569';
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)';

        // Included items only
        const activeData = data.filter(d => d.included !== false);
        if (activeData.length === 0) return;

        // 1. Subject Bar Chart
        const barCanvas = document.getElementById('subjectBarChart');
        if (barCanvas) {
            const labels = activeData.map(d => d.subject.split(' - ')[0].trim());
            const percentages = activeData.map(d => parseFloat(d.percentage) || 0);

            const backgroundColors = percentages.map(p => {
                if (p < 60) return '#ef4444';
                if (p < 70) return '#f59e0b';
                if (p < 85) return '#3b82f6';
                return '#10b981';
            });

            if (barChartInstance) {
                barChartInstance.destroy();
            }

            barChartInstance = new Chart(barCanvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Attendance %',
                        data: percentages,
                        backgroundColor: backgroundColors,
                        borderRadius: 8,
                        borderSkipped: false,
                        maxBarThickness: 40
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return ` Attendance: ${context.parsed.y}%`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: textColor, font: { family: 'Inter', size: 11 } },
                            grid: { display: false }
                        },
                        y: {
                            min: 0,
                            max: 100,
                            ticks: {
                                color: textColor,
                                font: { family: 'Inter', size: 11 },
                                callback: value => `${value}%`
                            },
                            grid: { color: gridColor }
                        }
                    }
                }
            });
        }

        // 2. Risk Distribution Doughnut Chart
        const doughnutCanvas = document.getElementById('riskDoughnutChart');
        if (doughnutCanvas) {
            let safeCount = 0;
            let blueCount = 0;
            let warningCount = 0;
            let criticalCount = 0;

            activeData.forEach(d => {
                const p = parseFloat(d.percentage) || 0;
                if (p >= 85) safeCount++;
                else if (p >= 70) blueCount++;
                else if (p >= 60) warningCount++;
                else criticalCount++;
            });

            if (doughnutChartInstance) {
                doughnutChartInstance.destroy();
            }

            doughnutChartInstance = new Chart(doughnutCanvas, {
                type: 'doughnut',
                data: {
                    labels: ['Safe (85%+)', 'Good (70-84%)', 'Warning (60-69%)', 'Critical (<60%)'],
                    datasets: [{
                        data: [safeCount, blueCount, warningCount, criticalCount],
                        backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'],
                        borderWidth: 3,
                        borderColor: isDark ? '#111827' : '#ffffff',
                        hoverOffset: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: textColor,
                                font: { family: 'Inter', size: 11 },
                                padding: 14,
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        }
                    },
                    cutout: '70%'
                }
            });
        }
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

    // Search & Sort Listeners
    if (searchInput) {
        searchInput.addEventListener('input', () => {
            renderSubjectViews(currentAttendanceData);
        });
    }

    if (sortSelect) {
        sortSelect.addEventListener('change', () => {
            renderSubjectViews(currentAttendanceData);
        });
    }

    // View Toggle Handlers
    if (viewGridBtn && viewTableBtn) {
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
    }

    // -------------------------------------------------------------
    // 🧭 NAVIGATION TAB SWITCHING & SMOOTH SCROLL HANDLERS
    // -------------------------------------------------------------
    const tabOverviewBtn = document.getElementById('tabOverviewBtn');
    const tabAnalyticsBtn = document.getElementById('tabAnalyticsBtn');
    const tabSubjectsBtn = document.getElementById('tabSubjectsBtn');

    const mobileTabOverview = document.getElementById('mobileTabOverview');
    const mobileTabAnalytics = document.getElementById('mobileTabAnalytics');
    const mobileTabRefresh = document.getElementById('mobileTabRefresh');

    function setActiveTab(tabName) {
        // Desktop Tabs Active State
        document.querySelectorAll('.nav-tab-btn').forEach(btn => btn.classList.remove('active'));
        if (tabName === 'overview' && tabOverviewBtn) tabOverviewBtn.classList.add('active');
        if (tabName === 'analytics' && tabAnalyticsBtn) tabAnalyticsBtn.classList.add('active');
        if (tabName === 'subjects' && tabSubjectsBtn) tabSubjectsBtn.classList.add('active');

        // Mobile Bottom Nav Active State
        document.querySelectorAll('.mobile-nav-item').forEach(item => item.classList.remove('active'));
        if (tabName === 'overview' && mobileTabOverview) mobileTabOverview.classList.add('active');
        if (tabName === 'analytics' && mobileTabAnalytics) mobileTabAnalytics.classList.add('active');

        // Smooth Scroll to Target Section
        if (tabName === 'overview') {
            const el = document.getElementById('summarySection') || dashboardView;
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else if (tabName === 'analytics') {
            const el = document.getElementById('chartsSection');
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else if (tabName === 'subjects') {
            const el = document.getElementById('controlsSection');
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    if (tabOverviewBtn) tabOverviewBtn.addEventListener('click', () => setActiveTab('overview'));
    if (tabAnalyticsBtn) tabAnalyticsBtn.addEventListener('click', () => setActiveTab('analytics'));
    if (tabSubjectsBtn) tabSubjectsBtn.addEventListener('click', () => setActiveTab('subjects'));

    if (mobileTabOverview) mobileTabOverview.addEventListener('click', () => setActiveTab('overview'));
    if (mobileTabAnalytics) mobileTabAnalytics.addEventListener('click', () => setActiveTab('analytics'));

    // -------------------------------------------------------------
    // 👤 STUDENT PROFILE MODAL HANDLERS
    // -------------------------------------------------------------
    const profileModal = document.getElementById('profileModal');
    const displayUserBadge = document.getElementById('displayUserBadge');
    const viewProfileDetailsBtn = document.getElementById('viewProfileDetailsBtn');
    const closeProfileModalBtn = document.getElementById('closeProfileModalBtn');
    const modalRefreshBtn = document.getElementById('modalRefreshBtn');
    const modalDownloadPdfBtn = document.getElementById('modalDownloadPdfBtn');
    const modalLogoutBtn = document.getElementById('modalLogoutBtn');

    function openProfileModal() {
        if (profileModal) profileModal.style.display = 'flex';
    }

    function closeProfileModal() {
        if (profileModal) profileModal.style.display = 'none';
    }

    if (displayUserBadge) {
        displayUserBadge.style.cursor = 'pointer';
        displayUserBadge.addEventListener('click', openProfileModal);
    }

    if (viewProfileDetailsBtn) {
        viewProfileDetailsBtn.addEventListener('click', openProfileModal);
    }

    if (closeProfileModalBtn) {
        closeProfileModalBtn.addEventListener('click', closeProfileModal);
    }

    if (profileModal) {
        profileModal.addEventListener('click', (e) => {
            if (e.target === profileModal) closeProfileModal();
        });
    }

    if (modalRefreshBtn) {
        modalRefreshBtn.addEventListener('click', () => {
            closeProfileModal();
            const username = studentIdInput.value.trim();
            const password = passwordInput.value.trim();
            if (username && password) fetchAttendance(username, password);
        });
    }

    if (modalDownloadPdfBtn) {
        modalDownloadPdfBtn.addEventListener('click', () => {
            closeProfileModal();
            downloadPdfReport();
        });
    }

    const modalCopyReportBtn = document.getElementById('modalCopyReportBtn');
    if (modalCopyReportBtn) {
        modalCopyReportBtn.addEventListener('click', () => {
            closeProfileModal();
            copyReportToClipboard();
        });
    }

    if (modalLogoutBtn) {
        modalLogoutBtn.addEventListener('click', () => {
            closeProfileModal();
            if (logoutBtn) logoutBtn.click();
        });
    }

    // Refresh Handler
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            const username = studentIdInput.value.trim();
            const password = passwordInput.value.trim();
            if (username && password) {
                fetchAttendance(username, password);
            }
        });
    }

    // Mobile Bottom Tab Refresh Handler
    if (mobileTabRefresh) {
        mobileTabRefresh.addEventListener('click', () => {
            const username = studentIdInput.value.trim();
            const password = passwordInput.value.trim();
            if (username && password) {
                fetchAttendance(username, password);
            }
        });
    }

    // Logout Handler
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            localStorage.removeItem('mits_stu_id');
            localStorage.removeItem('mits_stu_pass');
            localStorage.removeItem('mits_attendance_cache');
            localStorage.removeItem('mits_student_name');
            localStorage.removeItem('mits_last_login');
            currentAttendanceData = [];
            currentStudentName = '';
            currentRegisterNumber = '';
            currentLastLogin = '';
            studentIdInput.value = '';
            passwordInput.value = '';
            showLoginState();
        });
    }





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
        if (navTabs) navTabs.style.display = 'none';
        if (mobileBottomNav) mobileBottomNav.style.display = 'none';
    }

    function showLoadingState() {
        if (loginView) loginView.style.display = 'none';
        if (loadingView) loadingView.style.display = 'flex';
        if (dashboardView) dashboardView.style.display = 'none';
        if (navbar) navbar.style.display = 'flex';
        if (navActions) navActions.style.display = 'none';
        if (navTabs) navTabs.style.display = 'none';
        if (mobileBottomNav) mobileBottomNav.style.display = 'none';
    }

    function showDashboardState() {
        if (loginView) loginView.style.display = 'none';
        if (loadingView) loadingView.style.display = 'none';
        if (dashboardView) dashboardView.style.display = 'flex';
        if (navbar) navbar.style.display = 'flex';
        if (navActions) navActions.style.display = 'flex';
        if (navTabs) navTabs.style.display = 'flex';
        if (mobileBottomNav) mobileBottomNav.style.display = 'flex';
    }

    function updateLoadingStep(stepNum, text) {
        if (loadingStatusText) loadingStatusText.textContent = text;
        const loadingBarFill = document.getElementById('loadingBarFill');
        const loadingPercentText = document.getElementById('loadingPercentText');

        let perc = 15;
        if (stepNum === 1) perc = 35;
        if (stepNum === 2) perc = 70;
        if (stepNum === 3) perc = 95;

        if (loadingBarFill) loadingBarFill.style.width = `${perc}%`;
        if (loadingPercentText) loadingPercentText.textContent = `${perc}%`;

        [step1, step2, step3].forEach((el, index) => {
            if (!el) return;
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
        if (alertMessage) alertMessage.textContent = msg;
        if (loginAlert) loginAlert.style.display = 'flex';
    }

    function hideAlert() {
        if (loginAlert) loginAlert.style.display = 'none';
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

    // -------------------------------------------------------------
    // 📲 PWA APP INSTALL & SWIPEABLE TOP NOTIFICATION MODULE
    // -------------------------------------------------------------
    let deferredPrompt = null;

    const topNotificationBar = document.getElementById('topNotificationBar');
    const topNotifCloseBtn = document.getElementById('topNotifCloseBtn');
    const topNotifInstallBtn = document.getElementById('topNotifInstallBtn');

    const installModal = document.getElementById('installModal');
    const installNowBtn = document.getElementById('installNowBtn');
    const installLaterBtn = document.getElementById('installLaterBtn');
    const pwaInstallHeaderBtn = document.getElementById('pwaInstallHeaderBtn');

    const bannerInstallBtn = document.getElementById('bannerInstallBtn');
    const bannerHowToInstallBtn = document.getElementById('bannerHowToInstallBtn');
    const loginInstallAppBtn = document.getElementById('loginInstallAppBtn');
    const modalInstallAppBtn = document.getElementById('modalInstallAppBtn');



    // Check if running as standalone app
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;

    // Check if top notification was dismissed
    if (topNotificationBar) {
        if (localStorage.getItem('top_notif_dismissed') === 'true' || isStandalone) {
            topNotificationBar.style.display = 'none';
        }
    }

    // Function to trigger App Installation
    async function triggerAppInstall() {
        if (deferredPrompt) {
            deferredPrompt.prompt();
            const { outcome } = await deferredPrompt.userChoice;
            console.log(`[PWA] Install prompt outcome: ${outcome}`);
            if (outcome === 'accepted') {
                localStorage.setItem('pwa_installed', 'true');
                if (pwaInstallHeaderBtn) pwaInstallHeaderBtn.style.display = 'none';
                dismissTopNotification();
            }
            deferredPrompt = null;
        } else {
            showToast('Use your browser menu to install Attendix as an app.', 'info');
        }
    }

    function dismissTopNotification() {
        if (!topNotificationBar) return;
        topNotificationBar.classList.add('dismissed');
        localStorage.setItem('top_notif_dismissed', 'true');
        setTimeout(() => {
            topNotificationBar.style.display = 'none';
        }, 350);
    }

    // Touch & Mouse Drag / Swipe to Hide for Top Notification Bar
    if (topNotificationBar) {
        let startY = 0;
        let currentY = 0;
        let isDragging = false;

        function onDragStart(e) {
            isDragging = true;
            startY = e.touches ? e.touches[0].clientY : e.clientY;
            topNotificationBar.classList.add('dragging');
        }

        function onDragMove(e) {
            if (!isDragging) return;
            currentY = e.touches ? e.touches[0].clientY : e.clientY;
            const deltaY = currentY - startY;

            // Only drag upwards or slightly downwards
            if (deltaY < 0) {
                const opacity = Math.max(0, 1 + deltaY / 120);
                topNotificationBar.style.transform = `translate(-50%, ${deltaY}px)`;
                topNotificationBar.style.opacity = opacity;
            }
        }

        function onDragEnd(e) {
            if (!isDragging) return;
            isDragging = false;
            topNotificationBar.classList.remove('dragging');

            const deltaY = currentY - startY;
            if (deltaY < -40) {
                // Swipe up threshold met -> dismiss
                dismissTopNotification();
            } else {
                // Reset position
                topNotificationBar.style.transform = 'translateX(-50%)';
                topNotificationBar.style.opacity = '1';
            }
        }

        topNotificationBar.addEventListener('touchstart', onDragStart, { passive: true });
        topNotificationBar.addEventListener('touchmove', onDragMove, { passive: true });
        topNotificationBar.addEventListener('touchend', onDragEnd);

        topNotificationBar.addEventListener('mousedown', onDragStart);
        window.addEventListener('mousemove', onDragMove);
        window.addEventListener('mouseup', onDragEnd);
    }

    if (topNotifCloseBtn) topNotifCloseBtn.addEventListener('click', dismissTopNotification);
    if (topNotifInstallBtn) topNotifInstallBtn.addEventListener('click', triggerAppInstall);
    if (bannerInstallBtn) bannerInstallBtn.addEventListener('click', triggerAppInstall);
    if (loginInstallAppBtn) loginInstallAppBtn.addEventListener('click', triggerAppInstall);
    if (modalInstallAppBtn) modalInstallAppBtn.addEventListener('click', triggerAppInstall);

    if (installNowBtn) {
        installNowBtn.addEventListener('click', () => {
            if (installModal) installModal.style.display = 'none';
            triggerAppInstall();
        });
    }

    if (installLaterBtn) {
        installLaterBtn.addEventListener('click', () => {
            if (installModal) installModal.style.display = 'none';
        });
    }

    if (bannerHowToInstallBtn) {
        bannerHowToInstallBtn.addEventListener('click', () => {
            if (installModal) {
                installModal.style.display = 'flex';
            } else {
                window.location.href = '/install';
            }
        });
    }

    if (installModal) {
        installModal.addEventListener('click', (e) => {
            if (e.target === installModal) installModal.style.display = 'none';
        });
    }


    // PWA Install Event Listener
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;

        if (!isStandalone) {
            if (pwaInstallHeaderBtn) pwaInstallHeaderBtn.style.display = 'inline-flex';
            if (topNotificationBar && localStorage.getItem('top_notif_dismissed') !== 'true') {
                topNotificationBar.style.display = 'flex';
            }
        }
    });

    if (pwaInstallHeaderBtn) pwaInstallHeaderBtn.addEventListener('click', triggerAppInstall);

    window.addEventListener('appinstalled', () => {
        console.log('[PWA] App successfully installed!');
        dismissTopNotification();
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

    function getExportData() {
        if (Array.isArray(currentAttendanceData) && currentAttendanceData.length > 0) {
            return currentAttendanceData;
        }
        const data = [];
        const cards = document.querySelectorAll('.subject-card');
        cards.forEach(card => {
            const subjectEl = card.querySelector('.subject-title');
            const countEl = card.querySelector('.subject-counts');
            const percEl = card.querySelector('.subject-perc');
            if (subjectEl) {
                const subject = subjectEl.textContent.trim();
                const counts = countEl ? countEl.textContent.replace(/[^\d/]/g, '').split('/') : ['0', '0'];
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
            showToast('Unable to complete action. Please login first.', 'error');
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

            const primaryColor = [99, 102, 241];   // Indigo #6366F1
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
                let statusStr = 'Safe';
                if (percNum < 60) statusStr = 'Critical';
                else if (percNum < 70) statusStr = 'Warning';
                else if (percNum < 85) statusStr = 'Good';

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
                        5: { cellWidth: 22, halign: 'center', fontStyle: 'bold' }
                    },
                    didParseCell: function(data) {
                        if (data.section === 'body' && data.column.index === 5) {
                            const val = data.cell.raw;
                            if (val === 'Critical') {
                                data.cell.styles.textColor = [220, 38, 38];
                            } else if (val === 'Warning') {
                                data.cell.styles.textColor = [217, 119, 6];
                            } else if (val === 'Good') {
                                data.cell.styles.textColor = [37, 99, 235];
                            } else if (val === 'Safe') {
                                data.cell.styles.textColor = [5, 150, 105];
                            }
                        }
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
            showToast('Unable to generate PDF. Printing page...', 'error');
            window.print();
        } finally {
            if (downloadPdfBtn) {
                downloadPdfBtn.disabled = false;
                downloadPdfBtn.innerHTML = '<i class="fa-solid fa-file-pdf text-danger"></i> <span class="hide-mobile">PDF Report</span>';
            }
        }
    }

    // 📋 Copy Formatted Text Report to Clipboard Function
    async function copyReportToClipboard() {
        const data = getExportData();
        if (!data || data.length === 0) {
            showToast('Unable to copy report. Please login first.', 'error');
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
            showToast('Unable to copy to clipboard.', 'error');
        }
    }
});
