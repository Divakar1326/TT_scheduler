/**
 * Client-side script managing REST API calls, state transitions, grid renders, and CRUD.
 */

// Global State
const state = {
    token: localStorage.getItem("auth_token") || null,
    role: localStorage.getItem("auth_role") || null,
    currentPage: "landing",
    selectedDept: localStorage.getItem("auth_dept") || "ISC",
    timetableData: [],
    crudEntity: "faculties", // Current CRUD entity being managed
    crudData: [],
    ruleTab: "structured",
    timetableSubPage: "generate",
    theme: localStorage.getItem("ui_theme") || "orange",
    themeMode: localStorage.getItem("ui_theme_mode") || "light",
    compactMode: localStorage.getItem("ui_compact") || "disabled",
    sidebarCollapsed: localStorage.getItem("ui_sidebar_collapsed") === "true",
    // Legacy cache references (kept for compatibility, use cache object below)
    departmentsCache: null,
    facultiesCache: null,
    coursesCache: null,
    sectionsCache: null,
    roomsCache: null,
    laboratoriesCache: null
};

// ============================================================
// TTL-Based Intelligent Cache System
// Caches static data with 5-minute expiry. Invalidated on writes.
// ============================================================
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

const _cache = {
    departments: { data: null, ts: 0 },
    faculties: { data: null, ts: 0 },
    courses: { data: null, ts: 0 },
    sections: { data: null, ts: 0 },
    rooms: { data: null, ts: 0 },
    laboratories: { data: null, ts: 0 },
    settings: { data: null, ts: 0 }
};

function isCacheValid(key) {
    return _cache[key] && _cache[key].data !== null && (Date.now() - _cache[key].ts < CACHE_TTL_MS);
}

function setCache(key, data) {
    if (_cache[key] !== undefined) {
        _cache[key] = { data, ts: Date.now() };
    }
    // Also keep legacy state references in sync
    const legacyMap = {
        departments: "departmentsCache",
        faculties: "facultiesCache",
        courses: "coursesCache",
        sections: "sectionsCache",
        rooms: "roomsCache",
        laboratories: "laboratoriesCache"
    };
    if (legacyMap[key]) state[legacyMap[key]] = data;
}

function getCache(key) {
    return isCacheValid(key) ? _cache[key].data : null;
}

function invalidateCache(key) {
    if (key && _cache[key] !== undefined) {
        _cache[key] = { data: null, ts: 0 };
        // Sync legacy state
        const legacyMap = {
            departments: "departmentsCache",
            faculties: "facultiesCache",
            courses: "coursesCache",
            sections: "sectionsCache",
            rooms: "roomsCache",
            laboratories: "laboratoriesCache"
        };
        if (legacyMap[key]) state[legacyMap[key]] = null;
    } else if (!key) {
        Object.keys(_cache).forEach(k => _cache[k] = { data: null, ts: 0 });
        state.departmentsCache = null;
        state.facultiesCache = null;
        state.coursesCache = null;
        state.sectionsCache = null;
        state.roomsCache = null;
        state.laboratoriesCache = null;
    }
}

// ============================================================
// In-Flight Request Deduplication
// Prevents duplicate simultaneous API calls for the same URL.
// ============================================================
const _inFlight = {};

// Config APIs
const API_BASE = "";

// Help Documentation Topics List
const HELP_TOPICS = [
    {
        title: "1. Project Overview & Architecture Overview",
        category: "General",
        content: "UniSched ERP is an AI-powered academic resource planner. It models university timetabling as a Constraint Satisfaction Problem (CSP). It uses a hybrid repository architecture supporting high-performance Supabase PostgreSQL connections with an offline-ready SQLite fallback database. The system automates conflict-free timetable generation using a Backtracking Solver, Local Search Repair engine, and a multi-provider AI inference engine for natural language rule translation."
    },
    {
        title: "2. Authentication & Role Permissions",
        category: "Access Control",
        content: "Access to UniSched is role-based. (1) Super Admin: Global read/write access to configure all infrastructure (departments, rooms, labs) and HOD accounts. (2) Department HOD (Head of Department): Department-scoped permissions to generate timetables, customize rules, and manage assignments. Session verification is secured via JSON Web Tokens (JWT) stored locally."
    },
    {
        title: "3. Admin Workflow & System Flow",
        category: "System Flow",
        content: "The standard administrator flow is: (1) Create Departments. (2) Register Faculty and assign them to Departments. (3) Define Courses and link them to Departments. (4) Create Sections with Classrooms and Class Teachers. (5) Define structured or AI-parsed Rules. (6) Execute Timetable Generation. (7) Inspect, repair, and publish/export the final timetable."
    },
    {
        title: "4. Department Creation & Management",
        category: "Data setup",
        content: "Navigate to Academics > Departments. When creating a department, you must provide a unique Department ID/Code (e.g. ISC) and Name. You can select an active faculty member as the Head of Department (HOD). Opening a department card immediately displays related counts (faculty count, course count, sections, rooms, and labs) and the assigned HOD."
    },
    {
        title: "5. Faculty Creation & Availabilities",
        category: "Data setup",
        content: "Navigate to Academics > Faculty. Specify ID, Name, Department, Designation, Email, Phone, Professor Type (Regular/Adjunct/Visiting), Max Weekly Hours, Max Daily Hours, Status, Specialization, Preferred Days, and Preferred Time Slots. You can select assigned courses using the searchable checkboxes. The system prevents manual input of course IDs."
    },
    {
        title: "6. Course Creation & Lab Setup",
        category: "Data setup",
        content: "Navigate to Academics > Courses. Specify Course Code, Name, Department, Semester, Credits, Theory Hours, Lab Hours, Course Type (Core/Elective), Required Laboratory, and Course Color. Searchable dropdowns link assigned faculty and sections. Opening a course card shows active faculty, studying sections, and required lab room."
    },
    {
        title: "7. Section Creation & Mentorship",
        category: "Data setup",
        content: "Navigate to Academics > Sections. Specify Section Code, Name, Semester, Department, Capacity, Strength, Class Teacher, and classroom. Link courses via searchable checkboxes. Opening a section card displays the assigned class teacher, classroom, lab batches, and the generated weekly timetable."
    },
    {
        title: "8. Room & Laboratory Creation",
        category: "Data setup",
        content: "Navigate to Infrastructure > Rooms / Laboratories. For classrooms, specify Room Number, Capacity, Department, Room Type (Projector/Smart/Lab), and Availability. For labs, specify Lab Room Number, Name, Capacity, Lab Incharge, Equipment, and Availability. Opening a lab displays allocated timetable, courses, and active faculty."
    },
    {
        title: "9. Rule Builder & AI Translation",
        category: "Constraint Management",
        content: "Custom constraints prevent conflicts. (1) Structured Rule Builder: Use forms to restrict faculty, courses, or rooms. (2) AI Rule Builder: Describe rules in natural language (e.g. 'Dr. Rekha cannot teach on Friday after Period 4'). The AI inference engine translates this to structured JSON parameters. The system automatically routes through OpenRouter, Groq, and Cerebras with intelligent failover."
    },
    {
        title: "10. Scheduler Solver & Timetable Generation",
        category: "Core Engine",
        content: "The Backtracking CSP Solver ranks sections and courses. It generates candidates for each course session, enforcing hard constraints. For laboratory courses (Practical), it automatically schedules consecutive 2-period slots (e.g. P1-P2, P3-P4) in the same laboratory. Soft preferences are evaluated to optimize quality."
    },
    {
        title: "11. Export, Reports & Settings Preferences",
        category: "Reporting",
        content: "Timetables can be exported into three formats: Print/PDF (formatted page layout), Excel (styled spreadsheet report), and CSV (raw data table). The Settings page allows changing themes (Orange, Blue, Green, Purple, Red), toggling compact Density grids, and displays real-time Supabase/AI Engine connection statuses, last sync time, and API versions."
    },
    {
        title: "12. FAQs, Troubleshooting & Best Practices",
        category: "Support",
        content: "Q: 'Duplicate ID error' - Ensure ID case-insensitivity is respected; 'eee' and 'EEE' are treated as the same. Q: 'Solver fails' - Relax rules or ensure rooms have sufficient capacity for section strengths. Best Practice: Seed base entities first (Departments, Rooms, Faculty) before linking sections and courses."
    }
];

// Entity Specific Form Schemas
const CRUD_SCHEMAS = {
    departments: {
        title: "Departments",
        idField: "department_id",
        fields: [
            { name: "department_id", label: "Department Code / ID", type: "text", required: true },
            { name: "department_name", label: "Department Name", type: "text", required: true },
            { name: "hod", label: "Head of Department (HOD)", type: "select", optionsUrl: "/api/faculties", optionValue: "faculty_id", optionText: "faculty_name" }
        ]
    },
    faculties: {
        title: "Faculty",
        idField: "faculty_id",
        fields: [
            { name: "faculty_id", label: "Faculty ID", type: "text", required: true },
            { name: "faculty_name", label: "Faculty Name", type: "text", required: true },
            { name: "department_id", label: "Department", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" },
            { name: "designation", label: "Designation", type: "select", options: ["HOD", "Professor", "Associate Professor", "Assistant Professor", "Lab Instructor"] },
            { name: "professor_type", label: "Professor Type", type: "select", options: ["Regular", "Adjunct", "Visiting"] },
            { name: "email", label: "Email Address", type: "email" },
            { name: "phone", label: "Phone Number", type: "text" },
            { name: "max_hours_week", label: "Maximum Weekly Hours", type: "number", required: true, default: 30 },
            { name: "max_hours_daily", label: "Maximum Daily Hours", type: "number", required: true, default: 8 },
            { name: "availability", label: "Availability Pattern (JSON/Text)", type: "text", default: "All Slots" },
            { name: "specialization", label: "Specialization Areas", type: "text", placeholder: "e.g., AI, Machine Learning, Cyber Security" },
            { name: "preferred_days", label: "Preferred Days", type: "text", placeholder: "e.g., 1, 2, 3" },
            { name: "preferred_time_slots", label: "Preferred Periods", type: "text", placeholder: "e.g., 1, 2, 3, 4" },
            { name: "status", label: "Faculty Status", type: "select", options: ["ACTIVE", "ON_LEAVE", "TRANSFERRED", "RETIRED"] },
            { name: "assigned_courses", label: "Assigned Courses", type: "multiselect", optionsUrl: "/api/courses", optionValue: "course_id", optionText: "course_name" }
        ]
    },
    courses: {
        title: "Courses",
        idField: "course_id",
        fields: [
            { name: "course_id", label: "Course Code / ID", type: "text", required: true },
            { name: "course_name", label: "Course Name", type: "text", required: true },
            { name: "department_id", label: "Department", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" },
            { name: "semester", label: "Semester", type: "number", required: true },
            { name: "credits", label: "Academic Credits (C)", type: "number", required: true, default: 3 },
            { name: "theory_hours", label: "Theory Hours (L+T)", type: "number", required: true, default: 3 },
            { name: "lab_hours", label: "Lab / Practical Hours (P)", type: "number", required: true, default: 0 },
            { name: "course_type", label: "Course Type", type: "select", options: ["CORE", "ELECTIVE"] },
            { name: "has_lab", label: "Has Lab Component", type: "select", options: [{ value: 0, text: "No" }, { value: 1, text: "Yes" }] },
            { name: "required_laboratory", label: "Required Lab (Optional)", type: "select", optionsUrl: "/api/laboratories", optionValue: "lab_room_no", optionText: "lab_name" },
            { name: "course_color", label: "Schedule Visual Color", type: "color", default: "#3b82f6" },
            { name: "difficulty", label: "Solver Difficulty Weight", type: "number", min: 1, max: 5, default: 1 },
            { name: "weekly_hours", label: "Total Weekly Contact Hours", type: "number", required: true, default: 4 },
            { name: "assigned_faculty", label: "Assigned Faculty", type: "multiselect", optionsUrl: "/api/faculties", optionValue: "faculty_id", optionText: "faculty_name" },
            { name: "assigned_sections", label: "Assigned Sections", type: "multiselect", optionsUrl: "/api/sections", optionValue: "section_id", optionText: "section_name" }
        ]
    },
    rooms: {
        title: "Rooms",
        idField: "room_no",
        fields: [
            { name: "room_no", label: "Room Number / ID", type: "text", required: true },
            { name: "capacity", label: "Seating Capacity", type: "number", required: true },
            { name: "department_id", label: "Department Allocation", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" },
            { name: "room_type", label: "Classroom infrastructure Type", type: "select", options: ["PROJECTOR", "SMART", "LAB"] },
            { name: "availability", label: "Slot Availability Pattern", type: "text", default: "All Slots" }
        ]
    },
    laboratories: {
        title: "Laboratories",
        idField: "lab_room_no",
        fields: [
            { name: "lab_room_no", label: "Laboratory Room Code", type: "text", required: true },
            { name: "lab_name", label: "Laboratory Name", type: "text", required: true },
            { name: "capacity", label: "Workstation Capacity", type: "number", required: true },
            { name: "department_id", label: "Department Allocation", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" },
            { name: "lab_incharge_id", label: "Lab Incharge", type: "select", optionsUrl: "/api/faculties", optionValue: "faculty_id", optionText: "faculty_name" },
            { name: "equipment", label: "Equipment / Infrastructure Profile", type: "text", placeholder: "e.g., NVIDIA GPUs, Networking kits" },
            { name: "availability", label: "Slot Availability Pattern", type: "text", default: "All Slots" }
        ]
    },
    sections: {
        title: "Sections",
        idField: "section_id",
        fields: [
            { name: "section_id", label: "Section Code / ID", type: "text", required: true },
            { name: "section_name", label: "Section Name", type: "text", required: true },
            { name: "semester", label: "Academic Semester", type: "number", required: true },
            { name: "department_id", label: "Department Allocation", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" },
            { name: "capacity", label: "Section Max Capacity", type: "number", required: true, default: 60 },
            { name: "strength", label: "Current Class Strength", type: "number", required: true, default: 60 },
            { name: "classroom_id", label: "Assigned Primary Classroom", type: "select", optionsUrl: "/api/rooms", optionValue: "room_no", optionText: "room_no" },
            { name: "class_teacher_id", label: "Class Teacher / Mentor", type: "select", optionsUrl: "/api/faculties", optionValue: "faculty_id", optionText: "faculty_name" },
            { name: "assigned_courses", label: "Assigned Courses", type: "multiselect", optionsUrl: "/api/courses", optionValue: "course_id", optionText: "course_name" }
        ]
    },
    rules: {
        title: "Rules",
        idField: "rule_id",
        fields: [
            { name: "rule_id", label: "Rule ID (Slug)", type: "text", required: true },
            { name: "rule_name", label: "Rule Name", type: "text", required: true },
            { name: "priority", label: "Priority", type: "number", required: true, default: 1 },
            { name: "type", label: "Type", type: "select", options: ["HARD", "SOFT"] },
            { name: "enabled", label: "Enabled", type: "select", options: [{ value: 1, text: "Active" }, { value: 0, text: "Disabled" }] },
            { name: "description", label: "Natural Language (Description)", type: "textarea" },
            { name: "parameter", label: "JSON Parameter Preview / Value", type: "textarea" }
        ]
    }
};

// Helper: Headers
function getHeaders(extra = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...extra
    };
    if (state.token) {
        headers["Authorization"] = `Bearer ${state.token}`;
    }
    return headers;
}

// Toast Notifications
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ============================================================
// Global Loading Overlay — appears after 300ms to avoid flash on fast responses
// ============================================================
let _loaderCount = 0;
let _loaderTimer = null;

function showGlobalLoader() {
    _loaderCount++;
    if (_loaderCount === 1 && !_loaderTimer) {
        _loaderTimer = setTimeout(() => {
            const overlay = document.getElementById("global-loading-overlay");
            if (overlay && _loaderCount > 0) {
                overlay.classList.add("active");
            }
            _loaderTimer = null;
        }, 300); // only show if request takes longer than 300ms
    }
}

function hideGlobalLoader() {
    _loaderCount = Math.max(0, _loaderCount - 1);
    if (_loaderCount === 0) {
        if (_loaderTimer) {
            clearTimeout(_loaderTimer);
            _loaderTimer = null;
        }
        const overlay = document.getElementById("global-loading-overlay");
        if (overlay) overlay.classList.remove("active");
    }
}

// REST Client requests wrapper (with in-flight deduplication)
async function requestAPI(url, method = "GET", body = null) {
    // Deduplication: if a GET for this URL is already in-flight, return the same promise
    const dedupeKey = method === "GET" ? url : null;
    if (dedupeKey && _inFlight[dedupeKey]) {
        return _inFlight[dedupeKey];
    }

    showGlobalLoader();

    const promise = (async () => {
        try {
            const options = { method, headers: getHeaders() };
            if (body) {
                options.body = JSON.stringify(body);
            }
            const response = await fetch(url, options).catch(err => {
                throw new Error("Unable to connect to the server. Please check your network connection.");
            });
            if (response.status === 401 || response.status === 403) {
                showToast("Unauthorized. Please login again.", "error");
                logout();
                return null;
            }
            let data;
            try {
                data = await response.json();
            } catch (e) {
                throw new Error(`Server returned error status: ${response.status} ${response.statusText}`);
            }
            if (!response.ok) {
                throw new Error(data.error || "Request failed.");
            }
            return data;
        } catch (err) {
            showToast(err.message, "error");
            return null;
        } finally {
            if (dedupeKey) delete _inFlight[dedupeKey];
            hideGlobalLoader();
        }
    })();

    if (dedupeKey) _inFlight[dedupeKey] = promise;
    return promise;
}

/**
 * Secure file download helper — sends Authorization header instead of URL param.
 * Avoids token exposure in browser history, server logs, and referrer headers.
 */
async function _secureDownload(url, filename) {
    showGlobalLoader();
    try {
        const response = await fetch(url, { headers: getHeaders() });
        if (response.status === 401 || response.status === 403) {
            showToast("Unauthorized. Please login again.", "error");
            logout();
            return;
        }
        if (!response.ok) {
            let errMsg = "Export failed.";
            try { const d = await response.json(); errMsg = d.error || errMsg; } catch (_) {}
            showToast(errMsg, "error");
            return;
        }
        const blob = await response.blob();
        const objUrl = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = objUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(objUrl), 10000);
    } catch (err) {
        showToast("Download failed. Please try again.", "error");
    } finally {
        hideGlobalLoader();
    }
}

// Scroll to developer section on landing page
function scrollToAbout() {
    showDeveloperAboutModal();
}

async function showDeveloperAboutModal() {
    openModal("developer-about-modal");
    const contentEl = document.getElementById("developer-markdown-content");
    const photoEl = document.getElementById("developer-photo-img");

    if (photoEl) {
        photoEl.src = `/api/developer/photo?t=${new Date().getTime()}`;
        photoEl.style.display = "block";
        const fallbackEl = document.getElementById("developer-avatar-fallback");
        if (fallbackEl) fallbackEl.style.display = "none";
    }

    if (contentEl) {
        contentEl.innerHTML = "Loading developer profile...";
        try {
            const res = await requestAPI("/api/developer/about");
            if (res && res.markdown) {
                let html = res.markdown;
                html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
                html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
                html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
                html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
                html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color: var(--color-primary); text-decoration: underline;">$1</a>');
                html = html.replace(/\n/g, '<br>');
                contentEl.innerHTML = html;
            } else {
                contentEl.innerHTML = "Developer profile (about.md) is empty or unconfigured.";
            }
        } catch (e) {
            contentEl.innerHTML = "Failed to load developer profile details.";
        }
    }
}

// Fetch HODs for dynamic login selector
async function openLoginModal() {
    openModal('login-modal');

    const roleSelector = document.getElementById("login-role-selector");
    if (roleSelector) {
        handleLoginRoleSelect(roleSelector.value);
    }

    // Load departments for HOD dropdown dynamically
    const hodSelect = document.getElementById("login-hod-profile-select");
    if (hodSelect) {
        hodSelect.innerHTML = "<option value=''>Loading departments...</option>";
        const hods = await requestAPI("/api/auth/hods");
        hodSelect.innerHTML = "";
        if (hods && hods.length > 0) {
            hods.forEach(hod => {
                const opt = document.createElement("option");
                opt.value = hod.username;
                opt.dataset.deptId = hod.department_id || "";
                opt.innerText = hod.department_name || hod.department_id;
                hodSelect.appendChild(opt);
            });
            if (roleSelector && roleSelector.value === "hod") {
                fillHODUsername(hodSelect.value);
            }
        } else {
            hodSelect.innerHTML = "<option value=''>No departments available.</option>";
        }
    }
}

// Handle login role changes
function handleLoginRoleSelect(role) {
    const hodGroup = document.getElementById("login-hod-dropdown-group");
    const usernameInput = document.getElementById("login-username-input");

    if (role === "hod") {
        hodGroup.classList.remove("hidden");
        const hodSelect = document.getElementById("login-hod-profile-select");
        fillHODUsername(hodSelect.value);
    } else {
        hodGroup.classList.add("hidden");
        usernameInput.value = "admin";
    }
}

function fillHODUsername(val) {
    const usernameInput = document.getElementById("login-username-input");
    if (usernameInput && val) {
        usernameInput.value = val;
    }
}

// Quick Credential Autofill Helper
function quickFillLogin(username, password) {
    const form = document.querySelector("#login-modal form");
    const roleSelector = document.getElementById("login-role-selector");

    if (form) {
        form.username.value = username;
        form.password.value = password;
        if (username === "admin") {
            roleSelector.value = "admin";
            handleLoginRoleSelect("admin");
        } else {
            roleSelector.value = "hod";
            handleLoginRoleSelect("hod");
            // Set dynamic select option value
            const hodSelect = document.getElementById("login-hod-profile-select");
            if (hodSelect) {
                hodSelect.value = username;
            }
        }
    }
}

// Collapsible Sidebar Functions
function toggleSidebarCollapse() {
    state.sidebarCollapsed = !state.sidebarCollapsed;
    localStorage.setItem("ui_sidebar_collapsed", state.sidebarCollapsed);
    applySidebarState();
}

function applySidebarState() {
    const body = document.body;
    if (state.sidebarCollapsed) {
        body.classList.add("sidebar-collapsed");
    } else {
        body.classList.remove("sidebar-collapsed");
    }
}

/// Settings theme application
function applyUserThemeSetting(theme) {
    state.theme = theme;
    localStorage.setItem("ui_theme", theme);

    // Reset theme classes
    document.body.classList.remove("theme-blue", "theme-green", "theme-purple", "theme-red");
    if (theme !== "orange") {
        document.body.classList.add(`theme-${theme}`);
    }
}

function applyThemeMode(mode) {
    state.themeMode = mode;
    localStorage.setItem("ui_theme_mode", mode);

    document.body.classList.remove("theme-mode-light", "theme-mode-dark");
    if (mode === "dark") {
        document.body.classList.add("theme-mode-dark");
    } else if (mode === "light") {
        document.body.classList.add("theme-mode-light");
    } else if (mode === "system") {
        const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        document.body.classList.add(isDark ? "theme-mode-dark" : "theme-mode-light");
    }
}

function toggleCompactModeSetting(mode) {
    state.compactMode = mode;
    localStorage.setItem("ui_compact", mode);

    if (mode === "enabled") {
        document.body.classList.add("compact-mode");
    } else {
        document.body.classList.remove("compact-mode");
    }
}

function saveSystemPreferences() {
    showToast("Preferences saved successfully!");
}

function resetSystemPreferences() {
    document.getElementById("setting-theme").value = "orange";
    document.getElementById("setting-theme-mode").value = "light";
    document.getElementById("setting-compact").value = "disabled";
    applyUserThemeSetting("orange");
    applyThemeMode("light");
    toggleCompactModeSetting("disabled");
    showToast("Preferences reset to system defaults.");
}

// Check database connection pools (Supabase status check)
async function verifyDatabasePoolStatus() {
    try {
        const res = await requestAPI("/api/system/status");
        if (res) {
            const setVal = (id, text, color = null) => {
                const el = document.getElementById(id);
                if (el) {
                    el.innerText = text;
                    if (color) el.style.color = color;
                }
            };

            // Supabase Status
            if (res.supabase_status && res.supabase_status.includes("Connected")) {
                setVal("settings-supabase-val", "🟢 " + res.supabase_status, "var(--color-success)");
            } else {
                setVal("settings-supabase-val", `🔴 ${res.supabase_status}`, "var(--color-warning)");
            }

            // AI Engine Status (provider-agnostic)
            if (res.ai_health) {
                const status = res.ai_health.connection_status;
                if (status === "Connected") {
                    setVal("settings-ai-status-val", "🟢 Connected", "var(--color-success)");
                } else if (status === "Rate Limited") {
                    setVal("settings-ai-status-val", "🟠 Rate Limited", "var(--color-warning)");
                } else {
                    setVal("settings-ai-status-val", `🔴 Offline (${res.ai_health.connection_status})`, "var(--color-danger)");
                }

                setVal("settings-ai-provider-val", res.ai_health.current_provider);
                setVal("settings-ai-model-val", res.ai_health.current_model);
                setVal("settings-ai-fallback-val", res.ai_health.fallback_status);
                setVal("settings-ai-latency-val", res.ai_health.average_response_time);
            } else {
                setVal("settings-ai-status-val", "🔴 Offline", "var(--color-danger)");
            }

            setVal("settings-dbver-val", res.database_version);
            setVal("settings-apiver-val", res.api_version);
            setVal("settings-schedver-val", res.scheduler_version);
            setVal("settings-env-val", res.environment);

            // New diagnostic mappings
            if (res.supabase_status === "Connected" || res.supabase_status.includes("Local")) {
                setVal("settings-dbhealth-val", "🟢 Healthy", "var(--color-success)");
            } else {
                setVal("settings-dbhealth-val", "🔴 Unhealthy", "var(--color-danger)");
            }
            setVal("settings-tables-val", res.total_tables);
            setVal("settings-migration-val", res.migration_status);
            const statusVal = (res.validation_status || "").toUpperCase();
            const valEl = document.getElementById("settings-validation-val");
            if (valEl) {
                if (statusVal.startsWith("VALID")) {
                    valEl.innerText = "VALID";
                    valEl.style.color = "var(--color-success)";
                } else {
                    valEl.innerText = "ERROR";
                    valEl.style.color = "var(--color-danger)";
                }
            }

            setVal("settings-sync-val", res.last_sync_time);
        }
    } catch (e) {
        console.error("Failed to load connection status: ", e);
    }
}

// Searchable Help system index
function filterHelpTopics(query) {
    const container = document.getElementById("help-docs-container");
    if (!container) return;

    const normalizedQuery = query.toLowerCase().trim();
    const filtered = HELP_TOPICS.filter(t =>
        t.title.toLowerCase().includes(normalizedQuery) ||
        t.content.toLowerCase().includes(normalizedQuery) ||
        t.category.toLowerCase().includes(normalizedQuery)
    );

    renderHelpTopicsList(filtered);
}

function renderHelpTopicsList(topicsList) {
    const container = document.getElementById("help-docs-container");
    if (!container) return;

    container.innerHTML = "";
    if (topicsList.length === 0) {
        container.innerHTML = "<div class='card'>No matching documentation guides found.</div>";
        return;
    }

    topicsList.forEach(t => {
        const div = document.createElement("div");
        div.className = "card";
        div.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom: 0.5rem; align-items:center;">
                <h4 style="color:var(--text-main); font-size:1.1rem; font-weight:700;">${t.title}</h4>
                <span class="profile-badge" style="font-size:0.75rem; background:var(--bg-base); border-color:var(--border-color); color:var(--text-muted);">${t.category}</span>
            </div>
            <p style="color:var(--text-muted); font-size:0.925rem; line-height:1.6;">${t.content}</p>
        `;
        container.appendChild(div);
    });
}

function showLoadingProgress() {
    const bar = document.querySelector(".accent-progress-bar");
    if (bar) {
        bar.style.opacity = "1";
        bar.style.width = "0%";
        // Force reflow
        bar.offsetHeight;
        bar.style.width = "75%";
    }
}

function hideLoadingProgress() {
    const bar = document.querySelector(".accent-progress-bar");
    if (bar) {
        bar.style.width = "100%";
        setTimeout(() => {
            bar.style.opacity = "0";
            setTimeout(() => {
                bar.style.width = "0%";
            }, 250);
        }, 150);
    }
}

/// Navigation View Controller
async function navigateTo(pageId) {
    showLoadingProgress();
    state.currentPage = pageId;

    const footer = document.getElementById("app-footer");
    if (footer) {
        if (pageId === "landing" || !state.token) {
            footer.style.display = "none";
        } else {
            footer.style.display = "flex";
        }
    }

    // Hide all views
    document.querySelectorAll(".view-section").forEach(sec => sec.classList.add("hidden"));

    // Update elements
    const sidebar = document.getElementById("main-sidebar");
    const breadcrumbs = document.getElementById("app-breadcrumbs");
    const guestNav = document.getElementById("guest-nav");
    const authNav = document.getElementById("auth-nav");
    const headerTitle = document.getElementById("header-module-name");

    if (!state.token) {
        document.getElementById("view-landing").classList.remove("hidden");
        sidebar.classList.add("hidden");
        breadcrumbs.classList.add("hidden");
        guestNav.classList.remove("hidden");
        authNav.classList.add("hidden");
        if (headerTitle) {
            headerTitle.innerText = "Welcome Portal";
        }
        hideLoadingProgress();
        return;
    }

    sidebar.classList.remove("hidden");
    breadcrumbs.classList.remove("hidden");
    guestNav.classList.add("hidden");
    authNav.classList.remove("hidden");

    // Set profile badge text
    const badge = document.getElementById("user-profile-badge");
    if (badge) {
        badge.innerText = state.role === "SUPER_ADMIN" ? "System Admin" : "Dr. Rekha (HOD)";
    }

    // Set sidebar title based on role
    const titleText = document.getElementById("sidebar-role-title");
    if (titleText) {
        titleText.innerText = state.role === "SUPER_ADMIN" ? "Admin Portal" : "HOD Workspace";
    }

    // Set page specific details
    let displayTitle = pageId.charAt(0).toUpperCase() + pageId.slice(1);
    if (["departments", "faculty", "courses", "sections", "rooms", "laboratories"].includes(pageId)) {
        displayTitle = `Manage ${displayTitle}`;
    }
    if (headerTitle) {
        headerTitle.innerText = displayTitle;
    }

    // Update active class on sidebar items
    document.querySelectorAll("#main-sidebar ul li").forEach(li => {
        if (li.id === `sidebar-${pageId}`) {
            li.classList.add("active");
        } else {
            li.classList.remove("active");
        }
    });

    // Update Breadcrumb text
    const bcText = document.getElementById("breadcrumb-current");
    if (bcText) {
        bcText.innerText = displayTitle;
    }

    // Hide developer branding widgets after login
    const devLandingWidget = document.getElementById("about-developer-landing");
    if (devLandingWidget) {
        devLandingWidget.classList.add("hidden");
    }

    // Handle view showing
    if (pageId === "dashboard") {
        document.getElementById("view-dashboard").classList.remove("hidden");
        if (state.role === "SUPER_ADMIN") {
            document.getElementById("admin-dashboard-content").classList.remove("hidden");
            document.getElementById("hod-dashboard-content").classList.add("hidden");
            setTimeout(async () => {
                await loadAdminDashboard();
                hideLoadingProgress();
            }, 0);
        } else {
            document.getElementById("admin-dashboard-content").classList.add("hidden");
            document.getElementById("hod-dashboard-content").classList.remove("hidden");
            setTimeout(async () => {
                await loadHODDashboard();
                hideLoadingProgress();
            }, 0);
        }
    } else if (["departments", "faculty", "courses", "sections", "rooms", "laboratories"].includes(pageId)) {
        document.getElementById("view-crud-manager").classList.remove("hidden");
        // Map pageId to API entity name
        let entity = pageId;
        if (pageId === "faculty") entity = "faculties";
        setTimeout(async () => {
            await populateDepartmentFilters();
            await changeCRUDEntity(entity);
            hideLoadingProgress();
        }, 0);
    } else if (pageId === "rules") {
        document.getElementById("view-rule-builder").classList.remove("hidden");
        setTimeout(async () => {
            await loadRulesList();
            hideLoadingProgress();
        }, 0);
    } else if (pageId === "generate-timetable") {
        document.getElementById("view-generate-timetable").classList.remove("hidden");
        setTimeout(async () => {
            await loadGenerateSections();
            hideLoadingProgress();
        }, 0);
    } else if (pageId === "generated-timetables") {
        document.getElementById("view-generated-timetables").classList.remove("hidden");
        setTimeout(async () => {
            await updateViewerIdOptions();
            hideLoadingProgress();
        }, 0);
    } else if (pageId === "faculty-timetable") {
        document.getElementById("view-faculty-timetable").classList.remove("hidden");
        setTimeout(async () => {
            await loadFacultySelectOptions();
            hideLoadingProgress();
        }, 0);
    } else if (pageId === "lab-timetable") {
        document.getElementById("view-lab-timetable").classList.remove("hidden");
        setTimeout(async () => {
            await loadLabSelectOptions();
            hideLoadingProgress();
        }, 0);
    } else if (pageId === "settings") {
        document.getElementById("view-settings").classList.remove("hidden");
        document.getElementById("setting-theme").value = state.theme;
        document.getElementById("setting-theme-mode").value = state.themeMode || "light";
        document.getElementById("setting-compact").value = state.compactMode;
        verifyDatabasePoolStatus().then(() => hideLoadingProgress());
    } else if (pageId === "help") {
        document.getElementById("view-help").classList.remove("hidden");
        document.getElementById("help-search-input").value = "";
        renderHelpTopicsList(HELP_TOPICS);
        hideLoadingProgress();
    } else if (pageId === "about") {
        document.getElementById("view-about").classList.remove("hidden");
        hideLoadingProgress();
    }
}

// User Actions: Logins & Logouts
async function login(username, password) {
    const btn = document.getElementById("auth-submit-btn");
    const originalBtnHTML = btn ? btn.innerHTML : "Authenticate";

    // Disable button and show loading state
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="animation: spin 1s linear infinite; margin-right: 0.35rem;"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38"/></svg>Authenticating...`;
    }

    const data = await requestAPI("/api/auth/login", "POST", { username, password });

    if (data && data.token) {
        state.token = data.token;
        state.role = data.role;
        state.selectedDept = data.department_id || "ISC";
        localStorage.setItem("auth_token", data.token);
        localStorage.setItem("auth_role", data.role);
        localStorage.setItem("auth_dept", state.selectedDept);
        // Invalidate all caches on fresh login (stale data from previous session)
        invalidateCache(null);
        closeModal("login-modal");
        showToast("Logged in successfully!");
        navigateTo("dashboard");
        // Background prefetch: warm common caches so subsequent navigation feels instant
        setTimeout(prefetchCommonPages, 200);
    } else {
        // Re-enable button on failure
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalBtnHTML;
        }
    }
}

function logout() {
    state.token = null;
    state.role = null;
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_role");
    localStorage.removeItem("auth_dept");
    navigateTo("landing");
}

// Background prefetch: silently warm the TTL cache — runs all in parallel
async function prefetchCommonPages() {
    const endpoints = [
        { url: "/api/departments", key: "departments" },
        { url: "/api/faculties", key: "faculties" },
        { url: "/api/courses", key: "courses" },
        { url: "/api/sections", key: "sections" },
        { url: "/api/rooms", key: "rooms" },
        { url: "/api/laboratories", key: "laboratories" }
    ];
    // Fire all requests in parallel (Promise.all) — avoids sequential waterfall
    await Promise.all(endpoints.map(async (ep) => {
        if (!isCacheValid(ep.key)) {
            try {
                const data = await requestAPI(ep.url);
                if (data) setCache(ep.key, data);
            } catch (_) { /* silent */ }
        }
    }));
}

function showSkeletons() {
    const ids = [
        "stat-admin-depts", "stat-admin-faculty", "stat-admin-courses", "stat-admin-rooms", "stat-admin-labs", "stat-admin-rules",
        "stat-hod-faculty", "stat-hod-courses", "stat-hod-rooms", "stat-hod-labs", "stat-hod-sections", "stat-hod-students", "stat-hod-rules"
    ];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.classList.add("skeleton");
            el.innerText = "";
        }
    });
    // Start placeholder ticker so skeletons appear alive while data loads
    _startSkeletonTicker(ids);
}

// Continuous placeholder — shows stable dashes during loading (no random numbers)
const _skeletonTickerState = { rafId: null, active: false };
function _startSkeletonTicker(ids) {
    _skeletonTickerState.active = true;
    if (_skeletonTickerState.rafId) cancelAnimationFrame(_skeletonTickerState.rafId);
    // Show a pulsing dash placeholder — avoids the 'random number' glitch look
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el && el.classList.contains("skeleton")) {
            el.innerText = "...";
        }
    });
    // No periodic updates needed — skeleton CSS handles the pulse animation
}
function _stopSkeletonTicker() {
    _skeletonTickerState.active = false;
    if (_skeletonTickerState.rafId) clearTimeout(_skeletonTickerState.rafId);
}

// Dashboard Initializations
// Smooth Count-up Animation Utility — animates from 0 to target over duration ms
function animateCountUp(elementId, targetVal, duration = 1000) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.classList.remove("skeleton");
    const numMatch = String(targetVal).match(/^(\d+)(.*)$/);
    if (!numMatch) {
        el.innerText = targetVal || "0";
        return;
    }
    const end = parseInt(numMatch[1]) || 0;
    const suffix = numMatch[2] || "";
    if (end <= 0) {
        el.innerText = targetVal || "0";
        return;
    }
    let startTime = null;
    function step(timestamp) {
        if (!startTime) startTime = timestamp;
        // Use easeOutCubic for natural deceleration
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.innerText = Math.floor(eased * end) + suffix;
        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            el.innerText = end + suffix;
        }
    }
    window.requestAnimationFrame(step);
}

// Dashboard Initializations
async function loadAdminDashboard() {
    showSkeletons();
    const stats = await requestAPI("/api/dashboard/stats");

    _stopSkeletonTicker();
    const statKeys = [
        "stat-admin-depts", "stat-admin-faculty", "stat-admin-courses",
        "stat-admin-rooms", "stat-admin-labs", "stat-admin-rules"
    ];
    statKeys.forEach(k => {
        const el = document.getElementById(k);
        if (el) el.classList.remove("skeleton");
    });

    if (stats) {
        animateCountUp("stat-admin-depts", stats.department_count);

        animateCountUp("stat-admin-faculty", stats.faculty_count);
        const facEl = document.getElementById("stat-admin-faculty");
        if (facEl) {
            const parent = facEl.parentElement;
            let sub = parent.querySelector(".kpi-breakdown");
            if (!sub) {
                sub = document.createElement("div");
                sub.className = "kpi-breakdown";
                parent.appendChild(sub);
            }
            sub.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem; font-weight:normal;">${stats.faculty_hod_count} HODs, ${stats.faculty_prof_count} Profs, ${stats.faculty_asst_prof_count} Asst Profs</div>`;
        }

        animateCountUp("stat-admin-courses", stats.course_count);
        const courseEl = document.getElementById("stat-admin-courses");
        if (courseEl) {
            const parent = courseEl.parentElement;
            let sub = parent.querySelector(".kpi-breakdown");
            if (!sub) {
                sub = document.createElement("div");
                sub.className = "kpi-breakdown";
                parent.appendChild(sub);
            }
            sub.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem; font-weight:normal;">${stats.course_theory_count} Theory, ${stats.course_lab_count} Labs</div>`;
        }

        animateCountUp("stat-admin-rooms", stats.room_count);
        const roomEl = document.getElementById("stat-admin-rooms");
        if (roomEl) {
            const parent = roomEl.parentElement;
            let sub = parent.querySelector(".kpi-breakdown");
            if (!sub) {
                sub = document.createElement("div");
                sub.className = "kpi-breakdown";
                parent.appendChild(sub);
            }
            sub.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem; font-weight:normal;">${stats.room_classroom_count} Classrooms, ${stats.room_lab_count} Labs</div>`;
        }

        animateCountUp("stat-admin-labs", stats.lab_count);
        animateCountUp("stat-admin-rules", stats.rule_count);
    }
}

async function loadHODDashboard() {
    showSkeletons();
    const [stats, sections] = await Promise.all([
        requestAPI("/api/dashboard/stats"),
        requestAPI("/api/hod/sections-status")
    ]);

    _stopSkeletonTicker();
    const statKeys = [
        "stat-hod-faculty", "stat-hod-courses", "stat-hod-rooms",
        "stat-hod-labs", "stat-hod-sections", "stat-hod-students", "stat-hod-rules"
    ];
    statKeys.forEach(k => {
        const el = document.getElementById(k);
        if (el) el.classList.remove("skeleton");
    });

    if (stats) {
        animateCountUp("stat-hod-faculty", stats.faculty_count);
        const facEl = document.getElementById("stat-hod-faculty");
        if (facEl) {
            const parent = facEl.parentElement;
            let sub = parent.querySelector(".kpi-breakdown");
            if (!sub) {
                sub = document.createElement("div");
                sub.className = "kpi-breakdown";
                parent.appendChild(sub);
            }
            sub.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem; font-weight:normal;">${stats.faculty_hod_count} HODs, ${stats.faculty_prof_count} Profs, ${stats.faculty_asst_prof_count} Asst Profs</div>`;
        }

        animateCountUp("stat-hod-courses", stats.course_count);
        const courseEl = document.getElementById("stat-hod-courses");
        if (courseEl) {
            const parent = courseEl.parentElement;
            let sub = parent.querySelector(".kpi-breakdown");
            if (!sub) {
                sub = document.createElement("div");
                sub.className = "kpi-breakdown";
                parent.appendChild(sub);
            }
            sub.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem; font-weight:normal;">${stats.course_theory_count} Theory, ${stats.course_lab_count} Labs</div>`;
        }

        animateCountUp("stat-hod-rooms", stats.room_count);
        const roomEl = document.getElementById("stat-hod-rooms");
        if (roomEl) {
            const parent = roomEl.parentElement;
            let sub = parent.querySelector(".kpi-breakdown");
            if (!sub) {
                sub = document.createElement("div");
                sub.className = "kpi-breakdown";
                parent.appendChild(sub);
            }
            sub.innerHTML = `<div style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem; font-weight:normal;">${stats.room_classroom_count} Classrooms, ${stats.room_lab_count} Labs</div>`;
        }

        animateCountUp("stat-hod-labs", stats.lab_count);
        animateCountUp("stat-hod-sections", stats.section_count);
        animateCountUp("stat-hod-students", stats.student_count);
        animateCountUp("stat-hod-rules", stats.active_rules_count);

        const valSpan = document.getElementById("stat-hod-validation");
        if (valSpan) {
            const statusVal = (stats.validation_status || "").toUpperCase();
            if (statusVal.startsWith("VALID")) {
                valSpan.innerText = "VALID";
                valSpan.style.color = "var(--color-success)";
            } else {
                valSpan.innerText = "ERROR";
                valSpan.style.color = "var(--color-danger)";
            }
        }

        const schedEl = document.getElementById("stat-hod-section-scheduling");
        if (schedEl) {
            schedEl.innerText = stats.scheduled_sections_count || "0";
        }
    }

    // Load section statuses table
    const tbody = document.getElementById("hod-sections-tbody");
    tbody.innerHTML = "";
    if (sections && sections.length > 0) {
        sections.forEach(sec => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${sec.section_name}</strong> (${sec.section_id})</td>
                <td>${sec.room_no}</td>
                <td>${sec.class_teacher_name}</td>
                <td>${sec.class_teacher_phone}</td>
                <td>${sec.student_count}</td>
                <td><span style="color: ${sec.status === 'Generated' ? 'var(--color-success)' : 'var(--color-danger)'}; font-weight: 700;">${sec.status}</span></td>
                <td>
                    <div class="row-actions">
                        <button class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" onclick="viewSectionTimetableDirect('${sec.section_id}')">View</button>
                        <button class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" onclick="downloadSectionExportDirect('${sec.section_id}', 'html')">PDF</button>
                        <button class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" onclick="downloadSectionExportDirect('${sec.section_id}', 'csv')">Excel</button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } else {
        tbody.innerHTML = "<tr><td colspan='7'>No sections found.</td></tr>";
    }
}

// Direct action helpers for dashboard table
function viewSectionTimetableDirect(secId) {
    navigateTo("generated-timetables");
    setTimeout(async () => {
        document.getElementById("viewer-category-select").value = "section";
        await updateViewerIdOptions();
        const idSelect = document.getElementById("viewer-target-select");
        idSelect.value = secId;
        renderViewerGrid();
    }, 200);
}

async function downloadSectionExportDirect(secId, format) {
    const url = `/api/scheduler/export?type=section&id=${encodeURIComponent(secId)}&format=${encodeURIComponent(format)}`;
    await _secureDownload(url, `timetable_section_${secId}.${format}`);
}

// --- CRUD LOGIC MANAGER ---
async function populateDepartmentFilters() {
    const filterSelect = document.getElementById("crud-filter-select");
    if (!filterSelect) return;

    // Use TTL-based cache
    let depts = getCache("departments");
    if (!depts) {
        depts = await requestAPI("/api/departments");
        if (depts) setCache("departments", depts);
    }
    if (!depts) return;

    filterSelect.innerHTML = "";
    if (state.role === "SUPER_ADMIN") {
        const defaultOpt = document.createElement("option");
        defaultOpt.value = "";
        defaultOpt.innerText = "All Departments";
        filterSelect.appendChild(defaultOpt);
    }

    depts.forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.department_id;
        opt.innerText = d.department_name || d.department_id;
        filterSelect.appendChild(opt);
    });

    if (state.role === "HOD") {
        filterSelect.style.display = "none";
        filterSelect.value = state.selectedDept;
    } else {
        filterSelect.style.display = "";
    }
}

function changeCRUDEntity(entity) {
    state.crudEntity = entity;
    clearEntityCache(entity);
    loadCRUDEntityList();
}

async function loadCRUDEntityList() {
    const refreshBtn = document.getElementById("crud-refresh-btn");
    let originalHTML = "";

    // Serve from TTL cache instantly if available (avoids network round-trip)
    const cacheKey = state.crudEntity;
    const cached = getCache(cacheKey);
    if (cached) {
        state.crudData = cached;
        filterCRUDTable();
        return; // instant render — no loader needed
    }

    if (refreshBtn) {
        originalHTML = refreshBtn.innerHTML;
        refreshBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation: spin 1s linear infinite; margin-right: 0.25rem;"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Loading...`;
        refreshBtn.classList.add("disabled");
        refreshBtn.disabled = true;
    }

    try {
        const data = await requestAPI(`/api/${state.crudEntity}`);
        if (data) {
            setCache(cacheKey, data); // store in TTL cache for next visit
            state.crudData = data;
            filterCRUDTable();
        }
    } finally {
        if (refreshBtn) {
            refreshBtn.innerHTML = originalHTML;
            refreshBtn.classList.remove("disabled");
            refreshBtn.disabled = false;
        }
    }
}

function filterCRUDTable() {
    const searchVal = document.getElementById("crud-search-input").value.toLowerCase();
    let filterDept = document.getElementById("crud-filter-select").value;
    if (state.role === "HOD") {
        filterDept = state.selectedDept;
    }

    let filtered = state.crudData;
    if (searchVal) {
        filtered = filtered.filter(item => {
            return Object.values(item).some(val =>
                String(val).toLowerCase().includes(searchVal)
            );
        });
    }

    if (filterDept) {
        filtered = filtered.filter(item => item.department_id === filterDept);
    }

    renderCRUDTable(filtered);
}

function renderCRUDTable(data) {
    const schema = CRUD_SCHEMAS[state.crudEntity];
    const headers = document.getElementById("crud-table-headers");
    const body = document.getElementById("crud-table-body");

    headers.innerHTML = "";
    body.innerHTML = "";

    if (!schema) return;

    // Render headers
    const trHead = document.createElement("tr");
    schema.fields.forEach(f => {
        if (f.name !== "parameter" && f.name !== "description" && f.type !== "multiselect") {
            const th = document.createElement("th");
            th.innerText = f.label;
            trHead.appendChild(th);
        }
    });
    const thActions = document.createElement("th");
    thActions.innerText = "Actions";
    trHead.appendChild(thActions);
    headers.appendChild(trHead);

    // Render body
    if (data.length === 0) {
        body.innerHTML = `<tr><td colspan="${schema.fields.length + 1}">No matching records found.</td></tr>`;
        return;
    }

    data.forEach(row => {
        const tr = document.createElement("tr");
        schema.fields.forEach(f => {
            if (f.name !== "parameter" && f.name !== "description" && f.type !== "multiselect") {
                const td = document.createElement("td");
                let val = row[f.name];
                if (val === null || val === undefined) val = "";
                td.innerText = val;
                tr.appendChild(td);
            }
        });

        const idVal = row[schema.idField];
        const tdActions = document.createElement("td");
        tdActions.innerHTML = `
            <div class="row-actions">
                <button class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" onclick="viewEntityDetails('${idVal}')">View</button>
                <button class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" onclick="openEditModal('${idVal}')">Edit</button>
                <button class="btn btn-danger" style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" onclick="deleteCRUDEntity('${idVal}')">Delete</button>
            </div>
        `;
        tr.appendChild(tdActions);
        body.appendChild(tr);
    });
}

async function openAddModal() {
    const schema = CRUD_SCHEMAS[state.crudEntity];
    document.getElementById("crud-modal-title").innerText = `Create ${schema.title}`;
    const form = document.getElementById("crud-entity-form");
    form.reset();
    form.dataset.mode = "add";
    form.dataset.id = "";

    await renderFormFields(schema);
    if (state.role === "HOD") {
        const deptField = form.elements["department_id"];
        if (deptField) {
            deptField.value = state.selectedDept;
        }
    }
    form.querySelectorAll(".multiselect-skills-container").forEach(c => {
        if (c.clearPills) c.clearPills();
    });
    openModal("crud-modal");
}

async function openEditModal(idVal) {
    const schema = CRUD_SCHEMAS[state.crudEntity];
    document.getElementById("crud-modal-title").innerText = `Edit ${schema.title} (${idVal})`;
    const form = document.getElementById("crud-entity-form");
    form.dataset.mode = "edit";
    form.dataset.id = idVal;

    await renderFormFields(schema);

    const record = state.crudData.find(item => item[schema.idField] == idVal);
    if (record) {
        schema.fields.forEach(f => {
            if (f.type === "multiselect") {
                const container = form.querySelector(`.multiselect-skills-container[data-field-name='${f.name}']`);
                if (container) {
                    if (container.clearPills) container.clearPills();
                    const selected = record[f.name] || [];
                    selected.forEach(val => {
                        const text = container.optionsMap[val] || val;
                        if (container.addPill) container.addPill(val, text);
                    });
                }
            } else {
                const fieldEl = form.elements[f.name];
                if (fieldEl) {
                    fieldEl.value = record[f.name] !== null ? record[f.name] : "";
                }
            }
        });
    }
    openModal("crud-modal");
}

async function getCachedOptions(optionsUrl) {
    if (!optionsUrl) return [];

    const urlToKey = {
        "/api/departments": "departments",
        "/api/faculties": "faculties",
        "/api/courses": "courses",
        "/api/sections": "sections",
        "/api/rooms": "rooms",
        "/api/laboratories": "laboratories"
    };

    const cacheKey = urlToKey[optionsUrl];
    if (cacheKey) {
        const cached = getCache(cacheKey);
        if (cached) return cached;
        const data = await requestAPI(optionsUrl);
        if (data) setCache(cacheKey, data);
        return data || [];
    }
    return await requestAPI(optionsUrl) || [];
}

async function renderFormFields(schema) {
    const container = document.getElementById("crud-form-fields-container");
    container.innerHTML = "";

    for (const f of schema.fields) {
        const group = document.createElement("div");
        group.className = "form-group";
        if (f.name === "parameter" || f.name === "description" || f.type === "multiselect") {
            group.className = "form-group entity-form-full";
        }

        const label = document.createElement("label");
        label.innerText = f.label;
        group.appendChild(label);

        if (f.type === "select") {
            const selectContainer = document.createElement("div");
            selectContainer.style.display = "flex";
            selectContainer.style.flexDirection = "column";
            selectContainer.style.gap = "0.25rem";

            const filterInput = document.createElement("input");
            filterInput.type = "text";
            filterInput.placeholder = "Type to search...";
            filterInput.style.padding = "0.25rem 0.5rem";
            filterInput.style.fontSize = "0.8rem";
            filterInput.style.borderRadius = "var(--radius-sm)";
            filterInput.style.border = "1px solid var(--border-color)";

            const select = document.createElement("select");
            select.name = f.name;
            select.required = f.required || false;

            filterInput.oninput = (e) => {
                const txt = e.target.value.toLowerCase();
                Array.from(select.options).forEach(opt => {
                    if (opt.value === "") return;
                    const matches = opt.text.toLowerCase().includes(txt) || opt.value.toLowerCase().includes(txt);
                    opt.style.display = matches ? "" : "none";
                });
            };

            if (f.optionsUrl) {
                select.innerHTML = "<option value=''>Loading options...</option>";
                const options = await getCachedOptions(f.optionsUrl);
                select.innerHTML = "<option value=''>None (Optional)</option>";
                if (options) {
                    options.forEach(optVal => {
                        const opt = document.createElement("option");
                        opt.value = optVal[f.optionValue];
                        opt.innerText = optVal[f.optionText] || optVal[f.optionValue];
                        select.appendChild(opt);
                    });
                }
            } else if (f.options) {
                select.innerHTML = "<option value=''>Select option</option>";
                f.options.forEach(optVal => {
                    const opt = document.createElement("option");
                    if (typeof optVal === "object") {
                        opt.value = optVal.value;
                        opt.innerText = optVal.text;
                    } else {
                        opt.value = optVal;
                        opt.innerText = optVal;
                    }
                    select.appendChild(opt);
                });
            }
            selectContainer.appendChild(filterInput);
            selectContainer.appendChild(select);
            group.appendChild(selectContainer);
            if (f.name === "department_id" && state.role === "HOD") {
                select.value = state.selectedDept;
                group.style.display = "none";
            }
        } else if (f.type === "multiselect") {
            const container = document.createElement("div");
            container.className = "multiselect-skills-container";
            container.dataset.fieldName = f.name;
            container.style.display = "flex";
            container.style.flexDirection = "column";
            container.style.gap = "0.5rem";
            container.style.width = "100%";

            const pillsContainer = document.createElement("div");
            pillsContainer.className = "multiselect-pills-container";
            pillsContainer.style.display = "flex";
            pillsContainer.style.flexWrap = "wrap";
            pillsContainer.style.gap = "0.35rem";

            const searchWrapper = document.createElement("div");
            searchWrapper.style.position = "relative";
            searchWrapper.style.width = "100%";

            const searchInput = document.createElement("input");
            searchInput.type = "text";
            searchInput.placeholder = "Type to search and select...";
            searchInput.style.width = "100%";
            searchInput.style.padding = "0.6rem 0.75rem";
            searchInput.style.borderRadius = "var(--radius-sm)";
            searchInput.style.border = "1px solid var(--border-color)";
            searchInput.style.backgroundColor = "";
            searchInput.style.color = "var(--text-main)";

            const dropdownList = document.createElement("div");
            dropdownList.className = "multiselect-dropdown-list";
            dropdownList.style.position = "absolute";
            dropdownList.style.top = "100%";
            dropdownList.style.left = "0";
            dropdownList.style.right = "0";
            dropdownList.style.zIndex = "1000";
            dropdownList.style.maxHeight = "180px";
            dropdownList.style.overflowY = "auto";
            dropdownList.style.border = "1px solid var(--border-color)";
            dropdownList.style.borderRadius = "var(--radius-sm)";
            dropdownList.style.backgroundColor = "";
            dropdownList.style.boxShadow = "var(--shadow-md)";
            dropdownList.style.display = "none";
            dropdownList.style.flexDirection = "column";

            const hiddenInputsContainer = document.createElement("div");
            hiddenInputsContainer.style.display = "none";

            const options = await getCachedOptions(f.optionsUrl);
            const selectedValues = new Set();

            container.optionsMap = {};
            options.forEach(optVal => {
                container.optionsMap[optVal[f.optionValue]] = optVal[f.optionText] || optVal[f.optionValue];
            });

            const addPill = (val, text) => {
                if (selectedValues.has(val)) return;
                selectedValues.add(val);

                const hiddenInput = document.createElement("input");
                hiddenInput.type = "checkbox";
                hiddenInput.name = f.name;
                hiddenInput.value = val;
                hiddenInput.checked = true;
                hiddenInput.dataset.val = val;
                hiddenInputsContainer.appendChild(hiddenInput);

                const pill = document.createElement("span");
                pill.className = "profile-badge";
                pill.style.display = "inline-flex";
                pill.style.alignItems = "center";
                pill.style.gap = "0.35rem";
                pill.style.backgroundColor = "var(--color-primary-light)";
                pill.style.color = "var(--color-primary)";
                pill.style.border = "1px solid rgba(var(--color-primary-rgb), 0.1)";
                pill.style.padding = "0.25rem 0.5rem";
                pill.style.borderRadius = "var(--radius-sm)";
                pill.style.fontSize = "0.8rem";
                pill.style.fontWeight = "600";
                pill.dataset.val = val;

                const pillText = document.createElement("span");
                pillText.innerText = text;

                const removeBtn = document.createElement("span");
                removeBtn.innerHTML = "&times;";
                removeBtn.style.cursor = "pointer";
                removeBtn.style.fontWeight = "bold";
                removeBtn.style.fontSize = "1rem";
                removeBtn.onclick = () => {
                    removePill(val);
                };

                pill.appendChild(pillText);
                pill.appendChild(removeBtn);
                pillsContainer.appendChild(pill);

                renderOptions();
            };

            const removePill = (val) => {
                selectedValues.delete(val);
                const hiddenInput = hiddenInputsContainer.querySelector(`input[data-val='${val}']`);
                if (hiddenInput) hiddenInput.remove();

                const pill = pillsContainer.querySelector(`span[data-val='${val}']`);
                if (pill) pill.remove();

                renderOptions();
            };

            const renderOptions = () => {
                dropdownList.innerHTML = "";
                const filterText = searchInput.value.toLowerCase();
                let count = 0;

                options.forEach(optVal => {
                    const val = optVal[f.optionValue];
                    const text = optVal[f.optionText] || val;

                    if (selectedValues.has(val)) return;
                    if (filterText && !text.toLowerCase().includes(filterText) && !String(val).toLowerCase().includes(filterText)) return;

                    const item = document.createElement("div");
                    item.className = "multiselect-item";
                    item.style.padding = "0.5rem 0.75rem";
                    item.style.cursor = "pointer";
                    item.style.fontSize = "0.85rem";
                    item.style.color = "var(--text-main)";
                    item.innerText = text;

                    item.onmouseenter = () => {
                        item.style.backgroundColor = "var(--bg-base)";
                    };
                    item.onmouseleave = () => {
                        item.style.backgroundColor = "";
                    };

                    item.onclick = () => {
                        addPill(val, text);
                        searchInput.value = "";
                        searchInput.focus();
                        dropdownList.style.display = "none";
                    };

                    dropdownList.appendChild(item);
                    count++;
                });

                if (count === 0) {
                    const noResult = document.createElement("div");
                    noResult.style.padding = "0.5rem 0.75rem";
                    noResult.style.fontSize = "0.85rem";
                    noResult.style.color = "var(--text-muted)";
                    noResult.style.fontStyle = "italic";
                    noResult.innerText = "No matches found";
                    dropdownList.appendChild(noResult);
                }
            };

            container.addPill = addPill;
            container.clearPills = () => {
                const copy = Array.from(selectedValues);
                copy.forEach(val => removePill(val));
            };

            searchInput.onfocus = () => {
                renderOptions();
                dropdownList.style.display = "flex";
            };

            searchInput.oninput = () => {
                renderOptions();
                dropdownList.style.display = "flex";
            };

            searchInput.onkeydown = (e) => {
                if (e.key === "Backspace" && searchInput.value === "") {
                    const pills = pillsContainer.querySelectorAll("span");
                    if (pills.length > 0) {
                        const lastPill = pills[pills.length - 1];
                        removePill(lastPill.dataset.val);
                    }
                }
            };

            document.addEventListener("click", (e) => {
                if (!container.contains(e.target)) {
                    dropdownList.style.display = "none";
                }
            });

            searchWrapper.appendChild(searchInput);
            searchWrapper.appendChild(dropdownList);
            container.appendChild(pillsContainer);
            container.appendChild(searchWrapper);
            container.appendChild(hiddenInputsContainer);
            group.appendChild(container);
        } else if (f.type === "textarea") {
            const textarea = document.createElement("textarea");
            textarea.name = f.name;
            textarea.rows = 4;
            textarea.required = f.required || false;
            group.appendChild(textarea);
        } else {
            const input = document.createElement("input");
            input.name = f.name;
            input.type = f.type;
            input.required = f.required || false;
            if (f.default !== undefined) input.value = f.default;
            group.appendChild(input);
        }
        container.appendChild(group);
    }
}

function clearEntityCache(entity) {
    // Invalidate via new TTL cache system
    const entityToKey = {
        departments: "departments",
        faculties: "faculties",
        faculty: "faculties",
        courses: "courses",
        sections: "sections",
        rooms: "rooms",
        laboratories: "laboratories",
        labs: "laboratories"
    };
    const key = entityToKey[entity];
    if (key) invalidateCache(key);
}

async function saveEntitySubmit(event) {
    event.preventDefault();
    const form = event.target;
    const mode = form.dataset.mode;
    const idVal = form.dataset.id;

    const schema = CRUD_SCHEMAS[state.crudEntity];
    const payload = {};

    schema.fields.forEach(f => {
        if (f.type === "multiselect") {
            const checked = form.querySelectorAll(`input[name='${f.name}']:checked`);
            payload[f.name] = Array.from(checked).map(cb => cb.value);
        } else {
            const input = form.elements[f.name];
            if (input) {
                let val = input.value;
                if (f.type === "number") {
                    val = val ? parseInt(val) : 0;
                }
                payload[f.name] = val;
            }
        }
    });

    let url = `/api/${state.crudEntity}`;
    let method = "POST";
    if (mode === "edit") {
        url = `/api/${state.crudEntity}/${idVal}`;
        method = "PUT";
    }

    const res = await requestAPI(url, method, payload);
    if (res) {
        clearEntityCache(state.crudEntity);
        if (res.message && res.message.includes("HOD account")) {
            alert(res.message);
        } else {
            showToast("Record saved successfully!");
        }
        closeModal("crud-modal");
        loadCRUDEntityList();
    }
}

async function deleteCRUDEntity(idVal) {
    if (!confirm(`Are you sure you want to delete record ${idVal}?`)) return;
    const res = await requestAPI(`/api/${state.crudEntity}/${idVal}`, "DELETE");
    if (res) {
        clearEntityCache(state.crudEntity);
        showToast("Record deleted successfully.");
        loadCRUDEntityList();
    }
}

async function viewEntityDetails(idVal) {
    const record = await requestAPI(`/api/${state.crudEntity}/${idVal}`);
    if (!record) {
        showToast("Failed to load details.", "danger");
        return;
    }

    const titleEl = document.getElementById("details-modal-title");
    const bodyEl = document.getElementById("details-modal-body");

    const schema = CRUD_SCHEMAS[state.crudEntity];
    titleEl.innerText = `${schema.title} Details: ${idVal}`;

    let html = `<div style="display:flex; flex-direction:column; gap:1.25rem;">`;

    // Core properties mapping
    html += `
        <div style="background:var(--bg-base); padding:1rem; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
            <h4 style="margin-bottom:0.75rem; font-size:0.95rem; color:var(--text-main); font-weight:700; border-bottom:1px dashed var(--border-color); padding-bottom:0.25rem;">Core Specification</h4>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem 1rem; font-size:0.875rem;">
    `;

    schema.fields.forEach(f => {
        if (f.type !== "multiselect" && f.name !== "parameter" && f.name !== "description") {
            let val = record[f.name];
            if (val === null || val === undefined) val = "N/A";
            if (f.name === "course_color") {
                val = `<span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:${val}; margin-right:4px; vertical-align:middle;"></span> ${val}`;
            }
            html += `
                <div>
                    <strong style="color:var(--text-muted);">${f.label}:</strong> 
                    <span style="color:var(--text-main);">${val}</span>
                </div>
            `;
        }
    });

    html += `</div></div>`;

    // Relational metadata and statistics
    if (state.crudEntity === "departments") {
        html += `
            <div class="grid-stats" style="grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:0.75rem; margin-bottom:0;">
                <div class="card" style="padding:0.75rem; text-align:center; box-shadow:none; border-color:var(--border-color);">
                    <div style="font-size:0.75rem; text-transform:uppercase; color:var(--text-muted);">Faculty</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:var(--color-primary); margin-top:0.25rem;">${record.faculty_count || 0}</div>
                </div>
                <div class="card" style="padding:0.75rem; text-align:center; box-shadow:none; border-color:var(--border-color);">
                    <div style="font-size:0.75rem; text-transform:uppercase; color:var(--text-muted);">Courses</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:var(--color-primary); margin-top:0.25rem;">${record.course_count || 0}</div>
                </div>
                <div class="card" style="padding:0.75rem; text-align:center; box-shadow:none; border-color:var(--border-color);">
                    <div style="font-size:0.75rem; text-transform:uppercase; color:var(--text-muted);">Sections</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:var(--color-primary); margin-top:0.25rem;">${record.section_count || 0}</div>
                </div>
                <div class="card" style="padding:0.75rem; text-align:center; box-shadow:none; border-color:var(--border-color);">
                    <div style="font-size:0.75rem; text-transform:uppercase; color:var(--text-muted);">Rooms & Labs</div>
                    <div style="font-size:1.5rem; font-weight:bold; color:var(--color-primary); margin-top:0.25rem;">${(record.room_count || 0) + (record.lab_count || 0)}</div>
                </div>
            </div>
            
            <div style="background:var(--bg-base); padding:1rem; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
                <h4 style="margin-bottom:0.5rem; font-size:0.95rem; color:var(--text-main); font-weight:700;">Department HOD</h4>
                <div style="font-size:0.875rem; color:var(--text-main);">${record.hod_details || "No HOD assigned."}</div>
            </div>
        `;
    } else if (state.crudEntity === "faculties") {
        const courses = record.assigned_courses || [];
        const coursesList = courses.map(c => `<span class="profile-badge" style="background:var(--color-primary-light); color:var(--color-primary); border:none; margin:2px;">${c}</span>`).join("");
        html += `
            <div style="background:var(--bg-base); padding:1rem; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
                <h4 style="margin-bottom:0.75rem; font-size:0.95rem; color:var(--text-main); font-weight:700; border-bottom:1px dashed var(--border-color); padding-bottom:0.25rem;">Assigned Courses</h4>
                <div style="display:flex; flex-wrap:wrap; gap:0.25rem;">
                    ${coursesList || `<span style="color:var(--text-muted); font-size:0.875rem;">None assigned.</span>`}
                </div>
            </div>
        `;
    } else if (state.crudEntity === "courses") {
        const facs = record.assigned_faculty || [];
        const facsList = facs.map(f => `<span class="profile-badge" style="background:var(--bg-base); border-color:var(--border-color); margin:2px;">${f}</span>`).join("");
        const secs = record.assigned_sections || [];
        const secsList = secs.map(s => `<span class="profile-badge" style="background:var(--color-success-light); color:var(--color-success); border:none; margin:2px;">${s}</span>`).join("");

        html += `
            <div style="background:var(--bg-base); padding:1rem; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
                <h4 style="margin-bottom:0.75rem; font-size:0.95rem; color:var(--text-main); font-weight:700; border-bottom:1px dashed var(--border-color); padding-bottom:0.25rem;">Faculty Allocations</h4>
                <div style="display:flex; flex-wrap:wrap; gap:0.25rem; margin-bottom:1rem;">
                    ${facsList || `<span style="color:var(--text-muted); font-size:0.875rem;">No faculty linked.</span>`}
                </div>
                <h4 style="margin-bottom:0.75rem; font-size:0.95rem; color:var(--text-main); font-weight:700; border-bottom:1px dashed var(--border-color); padding-bottom:0.25rem;">Enrolled Sections</h4>
                <div style="display:flex; flex-wrap:wrap; gap:0.25rem;">
                    ${secsList || `<span style="color:var(--text-muted); font-size:0.875rem;">No sections studying this course.</span>`}
                </div>
            </div>
        `;
    } else if (state.crudEntity === "sections") {
        const courses = record.assigned_courses || [];
        const coursesList = courses.map(c => `<span class="profile-badge" style="background:var(--color-primary-light); color:var(--color-primary); border:none; margin:2px;">${c}</span>`).join("");
        html += `
            <div style="background:var(--bg-base); padding:1rem; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
                <h4 style="margin-bottom:0.75rem; font-size:0.95rem; color:var(--text-main); font-weight:700; border-bottom:1px dashed var(--border-color); padding-bottom:0.25rem;">Assigned Curriculum</h4>
                <div style="display:flex; flex-wrap:wrap; gap:0.25rem;">
                    ${coursesList || `<span style="color:var(--text-muted); font-size:0.875rem;">No courses assigned.</span>`}
                </div>
            </div>
        `;
    } else if (state.crudEntity === "laboratories") {
        html += `
            <div style="background:var(--bg-base); padding:1rem; border-radius:var(--radius-sm); border:1px solid var(--border-color);">
                <h4 style="margin-bottom:0.5rem; font-size:0.95rem; color:var(--text-main); font-weight:700;">Lab Mentor & Equipment</h4>
                <div style="font-size:0.875rem; color:var(--text-main); margin-bottom:0.5rem;"><strong>Incharge ID:</strong> ${record.lab_incharge_id || "None"}</div>
                <div style="font-size:0.875rem; color:var(--text-main);"><strong>Equipment:</strong> ${record.equipment || "No equipment listed."}</div>
            </div>
        `;
    }

    html += `</div>`;
    bodyEl.innerHTML = html;
    openModal("details-modal");
}

// Heuristics timetable solver triggers
function toggleGenerateScope() {
    const scope = document.getElementById("generate-scope-select").value;
    const secGroup = document.getElementById("generate-section-group");
    const deptGroup = document.getElementById("generate-dept-group");
    const confirmBox = document.getElementById("generate-confirm-box");
    if (confirmBox) confirmBox.classList.add("hidden");

    if (scope === "section") {
        secGroup.classList.remove("hidden");
        if (deptGroup) deptGroup.classList.add("hidden");
    } else {
        secGroup.classList.add("hidden");
        // Show dept selector for admin, auto-fill for HOD
        if (deptGroup) {
            if (state.role === "SUPER_ADMIN") {
                deptGroup.classList.remove("hidden");
            } else {
                deptGroup.classList.add("hidden");
            }
        }
    }
}

async function loadGenerateSections() {
    const select = document.getElementById("generate-section-select");
    select.innerHTML = "<option value=''>Loading sections...</option>";

    // Populate department dropdown (for admin Entire Dept scope)
    const deptSelect = document.getElementById("generate-dept-select");
    if (deptSelect) {
        deptSelect.innerHTML = "<option value=''>Loading...</option>";
        let depts = getCache("departments");
        if (!depts) {
            depts = await requestAPI("/api/departments");
            if (depts) setCache("departments", depts);
        }
        deptSelect.innerHTML = "<option value=''>-- Select Department --</option>";
        if (depts && depts.length > 0) {
            depts.forEach(d => {
                const opt = document.createElement("option");
                opt.value = d.department_id;
                opt.innerText = d.department_name || d.department_id;
                // Auto-select HOD's dept
                if (state.role === "HOD" && d.department_id === state.selectedDept) {
                    opt.selected = true;
                }
                deptSelect.appendChild(opt);
            });
        }
        // For HOD: hide the dept selector (it's auto-selected)
        const deptGroup = document.getElementById("generate-dept-group");
        if (deptGroup) {
            deptGroup.style.display = state.role === "SUPER_ADMIN" ? "" : "none";
        }
        // Wire up dept change to update confirm box
        deptSelect.onchange = updateGenerateConfirmBox;
    }

    // Use cached sections for instant load
    let data = getCache("sections");
    if (!data) {
        data = await requestAPI("/api/sections");
        if (data) setCache("sections", data);
    }
    select.innerHTML = "";
    if (data && data.length > 0) {
        data.forEach(item => {
            const opt = document.createElement("option");
            opt.value = item.section_id;
            opt.innerText = `${item.section_name} (${item.section_id})`;
            select.appendChild(opt);
        });
    } else {
        select.innerHTML = "<option value=''>No sections found</option>";
    }

    // Show initial confirm box state
    toggleGenerateScope();
    updateGenerateConfirmBox();
}

// Show a compact pre-generation summary so user knows what will be generated
async function updateGenerateConfirmBox() {
    const confirmBox = document.getElementById("generate-confirm-box");
    const confirmBody = document.getElementById("generate-confirm-body");
    if (!confirmBox || !confirmBody) return;

    const scope = document.getElementById("generate-scope-select").value;
    const deptSelect = document.getElementById("generate-dept-select");
    const deptId = (deptSelect && deptSelect.value) || state.selectedDept || "";
    const deptName = deptSelect ? (deptSelect.options[deptSelect.selectedIndex]?.text || deptId) : deptId;

    if (!deptId) {
        confirmBox.classList.add("hidden");
        return;
    }

    // Count sections and courses for this dept from cache
    const sections = getCache("sections") || [];
    const courses = getCache("courses") || [];
    const deptSections = sections.filter(s => s.department_id === deptId);
    const deptCourses = courses.filter(c => c.department_id === deptId);

    if (scope === "all") {
        confirmBody.innerHTML = `
            <span style="color:var(--color-primary); font-weight:600;">Department:</span> ${deptName} (${deptId})<br>
            <span style="color:var(--color-primary); font-weight:600;">Sections:</span> ${deptSections.length || '?'} &nbsp;
            <span style="color:var(--color-primary); font-weight:600;">Courses:</span> ${deptCourses.length || '?'}
        `;
    } else {
        const secVal = document.getElementById("generate-section-select").value;
        confirmBody.innerHTML = `<span style="color:var(--color-primary); font-weight:600;">Section:</span> ${secVal || '—'}`;
    }
    confirmBox.classList.remove("hidden");
}


async function executeGeneration() {
    showToast("Running backtracking CSP solver...");
    document.getElementById("generation-results-card").classList.add("hidden");

    const scope = document.getElementById("generate-scope-select").value;
    const secVal = document.getElementById("generate-section-select").value;
    const deptSelect = document.getElementById("generate-dept-select");
    const deptVal = (deptSelect && deptSelect.value) || state.selectedDept || "";

    const payload = {};
    if (scope === "section") {
        if (!secVal) return showToast("Please select a section first.", "error");
        payload["section_id"] = secVal;
    } else {
        if (!deptVal) {
            return showToast("Please select a department before generating.", "error");
        }
        payload["department_id"] = deptVal;
    }

    // Reset and open progress modal
    const setProgress = (stage, pct, elapsed, eta, scheduled, total, remaining, hard, soft) => {
        document.getElementById("progress-stage-name").innerText = stage;
        document.getElementById("progress-stage-name").style.color = "var(--text-main)";
        document.getElementById("progress-percentage-text").innerText = `${Math.round(pct)}%`;
        document.getElementById("progress-bar-fill").style.width = `${pct}%`;
        if (elapsed !== undefined) document.getElementById("progress-elapsed").innerText = `${Number(elapsed).toFixed(1)}s`;
        if (eta !== undefined) document.getElementById("progress-eta").innerText = eta === 0 ? "Completed" : `${Number(eta).toFixed(1)}s`;
        if (scheduled !== undefined) document.getElementById("progress-scheduled").innerText = scheduled;
        if (total !== undefined) document.getElementById("progress-total-classes").innerText = total || "-";
        if (remaining !== undefined) document.getElementById("progress-remaining").innerText = remaining;
        if (hard !== undefined) document.getElementById("progress-hard-score").innerText = `${Number(hard).toFixed(0)}%`;
        if (soft !== undefined) document.getElementById("progress-soft-penalty").innerText = `${Number(soft).toFixed(1)}%`;
    };

    setProgress("Connecting to database...", 0, 0, undefined, "0", "-", "-", "100", "0");
    document.getElementById("progress-eta").innerText = "Calculating...";
    document.getElementById("progress-error-container").classList.add("hidden");
    document.getElementById("progress-cancel-btn").classList.add("hidden");

    openModal("progress-modal");

    // ── Warmup animation ──────────────────────────────────────────────────────
    // Runs a smooth fake ticking from 0 → 15% while waiting for the first real
    // SSE event from the server. As soon as real data arrives, the warmup stops
    // and the real progress takes over seamlessly.
    const WARMUP_STAGES = [
        { pct: 2,  label: "Connecting to database..." },
        { pct: 5,  label: "Authenticating session..." },
        { pct: 8,  label: "Loading academic year..." },
        { pct: 11, label: "Loading departments..." },
        { pct: 14, label: "Loading courses & faculty..." },
    ];
    let warmupStopped = false;
    let warmupIdx = 0;
    const warmupStart = Date.now();

    const warmupTick = () => {
        if (warmupStopped) return;
        if (warmupIdx < WARMUP_STAGES.length) {
            const s = WARMUP_STAGES[warmupIdx++];
            const elapsed = (Date.now() - warmupStart) / 1000;
            setProgress(s.label, s.pct, elapsed, undefined, undefined, undefined, undefined, undefined, undefined);
        }
        if (!warmupStopped && warmupIdx < WARMUP_STAGES.length) {
            setTimeout(warmupTick, 600);
        } else if (!warmupStopped) {
            // Pulse the last label so it looks alive
            let pulse = 0;
            const dots = [".", "..", "..."];
            const pulseInterval = setInterval(() => {
                if (warmupStopped) { clearInterval(pulseInterval); return; }
                const elapsed = (Date.now() - warmupStart) / 1000;
                const lastLabel = WARMUP_STAGES[WARMUP_STAGES.length - 1].label.replace(/\.+$/, "");
                setProgress(lastLabel + dots[pulse % 3], 14, elapsed, undefined, undefined, undefined, undefined, undefined, undefined);
                pulse++;
            }, 500);
        }
    };
    setTimeout(warmupTick, 200);
    // ─────────────────────────────────────────────────────────────────────────

    try {
        const response = await fetch("/api/scheduler/generate", {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            warmupStopped = true;
            const errBody = await response.json().catch(() => ({}));
            throw new Error(errBody.error || `Server returned HTTP ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let firstRealEventReceived = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const dataStr = line.slice(6).trim();
                    if (!dataStr) continue;

                    try {
                        const chunk = JSON.parse(dataStr);

                        // Stop warmup the moment real data arrives
                        if (!firstRealEventReceived) {
                            firstRealEventReceived = true;
                            warmupStopped = true;
                        }

                        if (chunk.error) {
                            document.getElementById("progress-stage-name").innerText = "Failed";
                            document.getElementById("progress-stage-name").style.color = "#ef4444";
                            document.getElementById("progress-error-container").classList.remove("hidden");
                            document.getElementById("progress-failed-stage").innerText = chunk.stage || "Unknown";
                            document.getElementById("progress-failed-cause").innerText = chunk.message || "Unknown error";
                            document.getElementById("progress-failed-exception").innerText = chunk.root_cause || "No stacktrace available";
                            document.getElementById("progress-failed-fix").innerText = chunk.suggested_fix || "Please check server logs.";
                            document.getElementById("progress-cancel-btn").classList.remove("hidden");
                            return;
                        }

                        const total = chunk.scheduled_classes + chunk.remaining_classes;
                        setProgress(
                            chunk.stage,
                            chunk.percentage,
                            chunk.elapsed,
                            chunk.eta,
                            chunk.scheduled_classes,
                            total,
                            chunk.remaining_classes,
                            chunk.hard_score,
                            chunk.soft_penalty
                        );

                        if (chunk.success) {
                            showToast("Timetable generated and saved successfully!");
                            state.timetableData = chunk.allocations;

                            const card = document.getElementById("generation-results-card");
                            card.classList.remove("hidden");
                            document.getElementById("gen-status-val").innerText = "SUCCESS";
                            document.getElementById("gen-status-val").style.color = "var(--color-success)";
                            document.getElementById("gen-time-val").innerText = `${Number(chunk.stats.execution_time).toFixed(4)} seconds`;
                            document.getElementById("gen-validation-val").innerText = `Fitness Score: ${chunk.stats.fitness_score}% (Penalty: ${chunk.stats.soft_penalty_percent}%)`;

                            if (typeof loadActiveTimetable === 'function') {
                                loadActiveTimetable();
                            }

                            document.getElementById("progress-cancel-btn").classList.remove("hidden");
                            setTimeout(() => {
                                closeModal("progress-modal");
                            }, 1000);
                        }
                    } catch (err) {
                        console.error("Failed to parse SSE JSON line:", err);
                    }
                }
            }
        }
    } catch (error) {
        warmupStopped = true;
        showToast(`Generation failed: ${error.message}`, "error");
        document.getElementById("progress-stage-name").innerText = "Network Error";
        document.getElementById("progress-stage-name").style.color = "#ef4444";
        document.getElementById("progress-error-container").classList.remove("hidden");
        document.getElementById("progress-failed-stage").innerText = "Network Request";
        document.getElementById("progress-failed-cause").innerText = error.message;
        document.getElementById("progress-failed-exception").innerText = error.stack || "";
        document.getElementById("progress-failed-fix").innerText = "Ensure Flask server is running and database is reachable.";
        document.getElementById("progress-cancel-btn").classList.remove("hidden");
    }
}

// Constraints Report triggers
async function openModal(modalId) {
    document.getElementById(modalId).classList.remove("hidden");
    if (modalId === "validation-modal") {
        const rep = document.getElementById("validation-report-results");

        // Show loading spinner immediately so the modal never looks blank
        rep.innerHTML = `
            <div style="display:flex; flex-direction:column; align-items:center; gap:1rem; padding:2.5rem 1rem;">
                <div style="width:40px; height:40px; border:3px solid var(--border-color); border-top-color:var(--color-primary); border-radius:50%; animation:spin 0.8s linear infinite;"></div>
                <span style="color:var(--text-muted); font-size:0.95rem;">Verifying constraints against active timetable…</span>
            </div>
        `;
        showToast("Verifying constraints...");

        // Use raw fetch so we can read 4xx response bodies (requestAPI swallows errors and returns null)
        let res = null;
        let errMsg = null;
        try {
            const response = await fetch("/api/scheduler/validate", {
                method: "POST",
                headers: getHeaders()
            });
            const body = await response.json().catch(() => null);
            if (!response.ok) {
                errMsg = (body && body.error) ? body.error : `Server error ${response.status}`;
            } else {
                res = body;
            }
        } catch (e) {
            errMsg = "Unable to connect to the server. Please check your network connection.";
        }

        if (errMsg) {
            rep.innerHTML = `
                <div style="padding:1.25rem; border-radius:var(--radius-sm); background:var(--color-danger-light); border-left:4px solid var(--color-danger);">
                    <strong style="color:var(--color-danger);">⚠ Validation Unavailable</strong>
                    <p style="margin:0.5rem 0 0; font-size:0.9rem; color:var(--text-muted);">${errMsg}</p>
                    ${errMsg.includes("No active timetable") ? `<p style="margin:0.5rem 0 0; font-size:0.85rem; color:var(--text-muted);">Please run the <strong>Generate Timetable</strong> action first, then re-open this report.</p>` : ""}
                </div>
            `;
            return;
        }

        if (!res || !res.stats) {
            rep.innerHTML = `<span style="color:var(--color-danger);">Failed to retrieve validation diagnostics — unexpected server response.</span>`;
            return;
        }

        const stats = res.stats;
        const isAllPass = res.is_valid;
        const isDark = document.body.classList.contains("theme-mode-dark");

        const headerBg = isAllPass 
            ? (isDark ? "rgba(22, 163, 74, 0.15)" : "var(--color-success-light)") 
            : (isDark ? "rgba(220, 38, 38, 0.15)" : "var(--color-danger-light)");
        const headerBorder = isAllPass ? "var(--color-success)" : "var(--color-danger)";
        const headerColor = isAllPass 
            ? (isDark ? "#4ade80" : "var(--color-success)") 
            : (isDark ? "#f87171" : "var(--color-danger)");
        const headerIcon = isAllPass ? "✅" : "⚠";
        const headerLabel = isAllPass ? "All Constraints Satisfied" : "Constraint Violations Detected";

        let html = `
            <div style="margin-bottom:1.5rem; padding:1rem; border-radius:var(--radius-sm); background:${headerBg}; border-left:4px solid ${headerBorder};">
                <h4 style="color:${headerColor}; font-weight:700; margin-bottom:0.5rem;">${headerIcon} ${headerLabel}</h4>
                <div style="display:flex; flex-wrap:wrap; gap:1.25rem; font-size:0.9rem;">
                    <div><span style="color:var(--text-muted);">Fitness Score</span><br><strong style="font-size:1.1rem;">${stats.fitness_score ?? 0}%</strong></div>
                    <div><span style="color:var(--text-muted);">Constraint Satisfaction</span><br><strong style="font-size:1.1rem;">${stats.constraint_satisfaction ?? 0}%</strong></div>
                    <div><span style="color:var(--text-muted);">Total Allocations</span><br><strong style="font-size:1.1rem;">${stats.total_allocations ?? 0}</strong></div>
                    <div><span style="color:var(--text-muted);">Hard Violations</span><br><strong style="font-size:1.1rem; color:${(stats.error_count||0)>0?'var(--color-danger)':'var(--color-success)'};">${stats.error_count ?? 0}</strong></div>
                    <div><span style="color:var(--text-muted);">Soft Warnings</span><br><strong style="font-size:1.1rem; color:var(--color-warning);">${stats.warning_count ?? 0}</strong></div>
                </div>
            </div>
        `;

        if ((res.errors && res.errors.length > 0) || (res.warnings && res.warnings.length > 0)) {
            html += `<h4 style="margin-bottom:0.75rem; font-weight:700;">Violations & Warnings Log</h4>`;
            html += `<div style="display:flex; flex-direction:column; gap:0.5rem; margin-bottom:1.5rem;">`;
            if (res.errors && res.errors.length > 0) {
                res.errors.forEach(err => {
                    html += `
                        <div style="padding:0.6rem 0.85rem; border-radius:var(--radius-sm); background:rgba(220,38,38,0.08); border-left:3px solid var(--color-danger); font-size:0.875rem; color:${isDark ? '#f87171' : 'var(--color-danger)'};">
                            <strong>[ERROR]</strong> ${err}
                        </div>
                    `;
                });
            }
            if (res.warnings && res.warnings.length > 0) {
                res.warnings.forEach(warn => {
                    html += `
                        <div style="padding:0.6rem 0.85rem; border-radius:var(--radius-sm); background:rgba(217,119,6,0.08); border-left:3px solid var(--color-warning); font-size:0.875rem; color:${isDark ? '#fbbf24' : 'var(--color-warning)'};">
                            <strong>[WARNING]</strong> ${warn}
                        </div>
                    `;
                });
            }
            html += `</div>`;
        }

        const rules = stats.rule_statuses;
        if (rules && Object.keys(rules).length > 0) {
            html += `<h4 style="margin-bottom:0.75rem; font-weight:700;">Constraint Rules Breakdown</h4>`;
            for (const [name, r] of Object.entries(rules)) {
                const status = r.status || "PASS";
                const isFail = status !== "PASS";
                const borderCol = isFail ? "var(--color-danger)" : "var(--color-success)";
                const badgeBg   = isFail 
                    ? (isDark ? "rgba(220, 38, 38, 0.2)" : "var(--color-danger-light)") 
                    : (isDark ? "rgba(22, 163, 74, 0.2)" : "var(--color-success-light)");
                const badgeCol  = isFail 
                    ? (isDark ? "#f87171" : "var(--color-danger)") 
                    : (isDark ? "#4ade80" : "var(--color-success)");
                const icon      = isFail ? "✗" : "✓";
                const details   = r.details && r.details.length > 0
                    ? r.details.map(d => `<li style="margin-top:0.2rem;">${d}</li>`).join("")
                    : "<li>All checks passed — no violations found.</li>";
                html += `
                    <div style="margin-bottom:0.75rem; padding:0.75rem 1rem; border:1px solid var(--border-color); border-radius:var(--radius-sm); border-left:4px solid ${borderCol};">
                        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.35rem;">
                            <strong>${name}</strong>
                            <span style="font-size:0.7rem; padding:0.15rem 0.5rem; border-radius:999px; background:${badgeBg}; color:${badgeCol}; font-weight:700;">${icon} ${status}</span>
                            <span style="font-size:0.75rem; color:var(--text-muted); margin-left:auto;">${r.type || "Rule"}</span>
                        </div>
                        <ul style="margin:0; padding-left:1.25rem; font-size:0.83rem; color:var(--text-muted);">${details}</ul>
                    </div>
                `;
            }
        } else {
            html += `<div style="padding:1rem; color:var(--text-muted); font-style:italic;">No constraint rules were evaluated.</div>`;
        }

        // Suggested repairs
        if (res.suggested_repairs && res.suggested_repairs.length > 0) {
            html += `<h4 style="margin:1rem 0 0.5rem; font-weight:700;">💡 Suggested Repairs</h4>`;
            html += `<ul style="padding-left:1.25rem; font-size:0.85rem; color:var(--text-muted);">`;
            for (const r of res.suggested_repairs) {
                html += `<li style="margin-bottom:0.3rem;">${r}</li>`;
            }
            html += `</ul>`;
        }

        rep.innerHTML = html;
    }
}

// AI Rules Module & Structured Builder
function switchRuleTab(tabId) {
    state.ruleTab = tabId;
    document.querySelectorAll(".rule-tab-content").forEach(el => el.classList.add("hidden"));
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));

    document.getElementById(`tab-${tabId}`).classList.remove("hidden");
    const btn = document.getElementById(`tab-btn-${tabId}`);
    if (btn) btn.classList.add("active");
}

async function parseNaturalRule() {
    const text = document.getElementById("natural-rule-text").value.trim();
    if (!text) return showToast("Please enter rule text.", "error");

    const parseBtn = document.getElementById("ai-parse-btn");
    const saveBtn = document.getElementById("ai-save-btn");
    const progressEl = document.getElementById("ai-rule-progress");
    const progressStageEl = document.getElementById("ai-progress-stage");
    const progressTimerEl = document.getElementById("ai-progress-timer");
    const progressBarEl = document.getElementById("ai-progress-bar");
    const progressInfoEl = document.getElementById("ai-progress-info");

    // Disable buttons and show progress
    if (parseBtn) parseBtn.disabled = true;
    if (saveBtn) saveBtn.disabled = true;
    if (progressEl) progressEl.classList.remove("hidden");

    const stages = [
        { label: "Preparing request...", pct: 10, delay: 0 },
        { label: "Sending to AI engine...", pct: 25, delay: 400 },
        { label: "Waiting for AI...", pct: 45, delay: 900 },
        { label: "Parsing response...", pct: 75, delay: 0 },
        { label: "Building JSON...", pct: 88, delay: 0 },
        { label: "Complete", pct: 100, delay: 0 }
    ];

    let stageIdx = 0;
    const startTime = Date.now();

    // Start elapsed timer display
    const timerInterval = setInterval(() => {
        const sec = ((Date.now() - startTime) / 1000).toFixed(1);
        if (progressTimerEl) progressTimerEl.innerText = `${sec}s elapsed`;
    }, 100);

    const advanceStage = (idx) => {
        if (!stages[idx]) return;
        const s = stages[idx];
        if (progressStageEl) progressStageEl.innerText = s.label;
        if (progressBarEl) progressBarEl.style.width = s.pct + "%";
    };

    advanceStage(0);
    setTimeout(() => advanceStage(1), 400);
    setTimeout(() => advanceStage(2), 900);

    try {
        const res = await requestAPI("/api/rules/parse-natural", "POST", { rule_text: text });

        clearInterval(timerInterval);
        advanceStage(3);

        if (res) {
            advanceStage(4);
            if (res.warning) showToast(res.warning, "warning");
            const cleanRule = { ...res };
            delete cleanRule.warning;
            document.getElementById("rule-preview-json").innerText = JSON.stringify(cleanRule, null, 2);

            // Show provider/model info if available
            if (progressInfoEl) {
                const providerInfo = await requestAPI("/api/system/status").catch(() => null);
                if (providerInfo && providerInfo.ai_health) {
                    progressInfoEl.innerText = `Provider: ${providerInfo.ai_health.current_provider} · Model: ${providerInfo.ai_health.current_model}`;
                } else {
                    progressInfoEl.innerText = "AI inference complete";
                }
            }

            advanceStage(5);
            if (saveBtn) saveBtn.disabled = false;
        }
    } catch (err) {
        clearInterval(timerInterval);
        if (progressStageEl) {
            progressStageEl.innerText = "Failed — " + (err.message || "Unknown error");
            progressStageEl.style.color = "var(--color-danger)";
        }
    } finally {
        if (parseBtn) parseBtn.disabled = false;
    }
}

async function saveParsedRule() {
    const jsonStr = document.getElementById("rule-preview-json").innerText;
    if (!jsonStr) return showToast("No parsed rule to save.", "error");

    try {
        const payload = JSON.parse(jsonStr);
        payload["original_text"] = document.getElementById("natural-rule-text").value;
        const res = await requestAPI("/api/rules/save", "POST", payload);
        if (res) {
            showToast("Rule saved successfully.");
            loadRulesList();
        }
    } catch (e) {
        showToast("Invalid rule JSON.", "error");
    }
}

async function saveStructuredRule(event) {
    event.preventDefault();
    const form = event.target;
    const payload = {
        rule_id: form.rule_id.value,
        rule_name: form.rule_name.value,
        type: form.type.value,
        priority: parseInt(form.priority.value),
        parameter: {
            faculty_id: form.faculty_id.value || undefined,
            avoid_days: form.avoid_days.value ? [parseInt(form.avoid_days.value)] : undefined
        }
    };

    const res = await requestAPI("/api/rules/save", "POST", payload);
    if (res) {
        showToast("Structured Rule saved successfully.");
        loadRulesList();
    }
}

async function loadRulesList() {
    try {
        const rules = await requestAPI("/api/rules");
        const tbody = document.getElementById("rules-list-body");
        if (!tbody) return;

        tbody.innerHTML = "";
        if (!rules || rules.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No active scheduling rules found. Use the Structured Rule Builder or the AI Rule Builder above to create one.</td></tr>`;
            return;
        }

        rules.forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${r.rule_id}</td>
                <td>${r.rule_name}</td>
                <td>${r.type}</td>
                <td>${r.priority}</td>
                <td>${r.enabled ? 'Active' : 'Disabled'}</td>
                <td>
                    <div class="row-actions">
                        <button class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" onclick="viewRuleVersions('${r.rule_id}')">Versions</button>
                        <button class="btn btn-secondary" style="padding: 0.35rem 0.65rem; font-size: 0.8rem;" onclick="toggleRule('${r.rule_id}', ${r.version || 1}, ${r.enabled ? 0 : 1})">${r.enabled ? 'Disable' : 'Enable'}</button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        const tbody = document.getElementById("rules-list-body");
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--color-danger); padding: 1.5rem;">Failed to fetch active rules. Please make sure the backend server is running and database connections are active. (Error: ${err.message || err})</td></tr>`;
        }
    }
}

async function toggleRule(ruleId, version, enabled) {
    const res = await requestAPI("/api/rules/toggle", "POST", { rule_id: ruleId, version, enabled });
    if (res) {
        showToast("Toggled rule successfully.");
        loadRulesList();
    }
}

async function viewRuleVersions(ruleId) {
    const versions = await requestAPI(`/api/rules/versions/${ruleId}`);
    if (versions) {
        const modal = document.getElementById("versions-modal");
        const list = document.getElementById("versions-list");
        list.innerHTML = "";
        versions.forEach(v => {
            const li = document.createElement("li");
            li.style.padding = "0.75rem";
            li.style.borderBottom = "1px solid var(--border-color)";
            li.innerHTML = `
                <div style="display:flex; justify-content:space-between; margin-bottom: 0.25rem;">
                    <strong>Ver ${v.version}</strong>
                    <span style="font-size:0.75rem; color:var(--text-muted);">${v.created_at}</span>
                </div>
                <div style="font-size:0.85rem; color:var(--text-muted); margin-bottom: 0.5rem;">
                    Status: <span style="font-weight:600; color: ${v.enabled ? 'var(--color-success)' : 'var(--color-danger)'}">${v.enabled ? 'Active' : 'Disabled'}</span>
                </div>
                <pre style="font-size:0.8rem;background:var(--bg-base);padding:0.5rem;border-radius:4px;border:1px solid var(--border-color);overflow-x:auto;">${v.parameter}</pre>
            `;
            list.appendChild(li);
        });
        openModal("versions-modal");
    }
}

// Generated Timetables Viewer Functions
async function downloadTimetableExport(format) {
    const category = document.getElementById("viewer-category-select").value;
    const selectTarget = document.getElementById("viewer-target-select");
    const idVal = selectTarget.value;
    if (!idVal) return showToast("Please select a target first.", "error");
    const url = `/api/scheduler/export?type=${encodeURIComponent(category)}&id=${encodeURIComponent(idVal)}&format=${encodeURIComponent(format)}`;
    await _secureDownload(url, `timetable_${category}_${idVal}.${format}`);
}

async function updateViewerIdOptions() {
    const category = document.getElementById("viewer-category-select").value;
    const selectTarget = document.getElementById("viewer-target-select");
    selectTarget.innerHTML = "<option value=''>Loading...</option>";

    // Use cache for sections/departments to avoid redundant API calls
    let data;
    if (category === "section") {
        data = getCache("sections");
        if (!data) {
            data = await requestAPI("/api/sections");
            if (data) setCache("sections", data);
        }
    } else if (category === "department") {
        data = getCache("departments");
        if (!data) {
            data = await requestAPI("/api/departments");
            if (data) setCache("departments", data);
        }
    }

    selectTarget.innerHTML = "";
    if (data && data.length > 0) {
        data.forEach(item => {
            const opt = document.createElement("option");
            if (category === "section") {
                opt.value = item.section_id;
                opt.innerText = `${item.section_name} (${item.section_id})`;
            } else if (category === "department") {
                opt.value = item.department_id;
                opt.innerText = `${item.department_name} (${item.department_id})`;
            }
            selectTarget.appendChild(opt);
        });
    } else {
        selectTarget.innerHTML = "<option value=''>No targets found</option>";
    }
    renderViewerGrid();
}

async function renderViewerGrid() {
    const container = document.getElementById("timetable-grid-container");
    container.innerHTML = "";

    const category = document.getElementById("viewer-category-select").value;
    const selectTarget = document.getElementById("viewer-target-select");
    const activeFilterVal = selectTarget.value;

    const metadata = await requestAPI("/api/scheduler/metadata");
    if (metadata) {
        state.courseNames = metadata.course_names || {};
        state.facultyNames = metadata.faculty_names || {};
        state.labDetails = metadata.lab_details || {};
        state.departmentNames = metadata.department_names || {};
    }

    const metaCard = document.getElementById("timetable-metadata-card");
    if (activeFilterVal && metadata) {
        metaCard.classList.remove("hidden");
        const deptTitle = document.getElementById("tt-meta-dept-title");

        let deptId = "CSE";
        let deptName = "Department of Computer Science Engineering";

        if (category === "section") {
            const sec = metadata.sections[activeFilterVal] || {};
            deptId = sec.department_id || "CSE";
            deptName = state.departmentNames[deptId] || deptName;

            document.getElementById("tt-meta-semester").innerText = sec.semester || "N/A";
            document.getElementById("tt-meta-classroom").innerText = sec.classroom || "N/A";
            document.getElementById("tt-meta-teacher").innerText = sec.teacher || "N/A";
        } else if (category === "department") {
            deptId = activeFilterVal;
            deptName = state.departmentNames[deptId] || deptName;

            document.getElementById("tt-meta-semester").innerText = "All";
            document.getElementById("tt-meta-classroom").innerText = "Multiple";
            document.getElementById("tt-meta-teacher").innerText = "Multiple";
        }

        if (deptTitle) deptTitle.innerText = deptName;

        document.getElementById("tt-meta-version").innerText = `V${metadata.version}`;
        document.getElementById("tt-meta-date").innerText = metadata.gen_date || "N/A";
        document.getElementById("tt-meta-gentime").innerText = `${metadata.generation_time_seconds.toFixed(4)}s`;

    } else {
        metaCard.classList.add("hidden");
    }

    if (!activeFilterVal) {
        container.innerHTML = "<div class='card'>Please select a target first.</div>";
        return;
    }

    if (state.timetableData.length === 0) {
        const generated = await requestAPI("/api/scheduler/generate", "POST", { dry_run: true });
        if (generated && generated.allocations) {
            state.timetableData = generated.allocations;
        }
    }

    // Draw the grid instantly (taking less than 0.1 seconds)
    drawGridInContainer(container, category, activeFilterVal, metadata);

    // Fetch validation stats asynchronously in the background so it doesn't block rendering
    if (activeFilterVal && metadata) {
        const hardEl = document.getElementById("tt-meta-fitness");
        const softEl = document.getElementById("tt-meta-satisfaction");
        if (hardEl) hardEl.innerText = "...";
        if (softEl) softEl.innerText = "...";

        requestAPI("/api/scheduler/validate", "POST").then(valReport => {
            if (valReport && valReport.stats) {
                // Hard Status element (tt-meta-fitness) shows constraint_satisfaction %
                if (hardEl) {
                    hardEl.innerText = `${valReport.stats.constraint_satisfaction || 0}%`;
                }
                // Soft Penalty element (tt-meta-satisfaction) shows soft_penalty_percent %
                if (softEl) {
                    const softPenalty = valReport.stats.soft_penalty_percent !== undefined ?
                        valReport.stats.soft_penalty_percent :
                        (100 - (valReport.stats.fitness_score || 100));
                    softEl.innerText = `${Number(softPenalty).toFixed(1)}%`;
                }
            } else {
                if (hardEl) hardEl.innerText = "N/A";
                if (softEl) softEl.innerText = "N/A";
            }
        });
    }
}

// Helper: draw grid inside a target container
function drawGridInContainer(container, category, activeFilterVal, metadata) {
    const dayNames = { 1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday" };

    const renderSingleGrid = (targetType, targetId, titleText = "") => {
        if (titleText) {
            const h3 = document.createElement("h3");
            h3.style.marginTop = "2rem";
            h3.style.marginBottom = "0.5rem";
            h3.style.fontSize = "1.2rem";
            h3.style.fontWeight = "700";
            h3.style.color = "var(--text-main)";
            h3.innerText = titleText;
            container.appendChild(h3);
        }

        const gridWrapper = document.createElement("div");
        gridWrapper.className = "timetable-grid-wrapper";

        const innerWrapper = document.createElement("div");
        innerWrapper.className = "timetable-grid";

        innerWrapper.appendChild(createGridCell("Day / Period", "timetable-cell timetable-header"));
        innerWrapper.appendChild(createGridCell("P1<br>8:30-9:25", "timetable-cell timetable-header"));
        innerWrapper.appendChild(createGridCell("P2<br>9:25-10:20", "timetable-cell timetable-header"));
        innerWrapper.appendChild(createGridCell("BREAK<br>10:20-10:40", "timetable-cell timetable-header timetable-break-cell"));
        innerWrapper.appendChild(createGridCell("P3<br>10:40-11:35", "timetable-cell timetable-header"));
        innerWrapper.appendChild(createGridCell("P4<br>11:35-12:30", "timetable-cell timetable-header"));
        innerWrapper.appendChild(createGridCell("LUNCH<br>12:30-1:20", "timetable-cell timetable-header timetable-break-cell"));
        innerWrapper.appendChild(createGridCell("P5<br>1:20-2:15", "timetable-cell timetable-header"));
        innerWrapper.appendChild(createGridCell("P6<br>2:15-3:10", "timetable-cell timetable-header"));
        innerWrapper.appendChild(createGridCell("P7<br>3:10-4:05", "timetable-cell timetable-header"));

        for (let day = 1; day <= 6; day++) {
            innerWrapper.appendChild(createGridCell(dayNames[day], "timetable-cell day-header"));

            for (let period = 1; period <= 7; period++) {
                let match = state.timetableData.find(a => {
                    if (a.day_id !== day || a.period_no !== period) return false;
                    if (targetType === "section") return a.section_id === targetId;
                    if (targetType === "faculty") return a.faculty_id === targetId;
                    if (targetType === "lab") return a.lab_room_no === targetId;
                    return false;
                });

                let cellText = "";
                let cellClass = "timetable-cell";

                if (match) {
                    const room = match.room_no || match.lab_room_no || "Unassigned";
                    const courseName = state.courseNames[match.course_id] || match.course_id;
                    const facultyName = state.facultyNames[match.faculty_id] || match.faculty_id;

                    let isLab = !!match.lab_room_no;

                    if (isLab) cellClass += " lab";
                    else cellClass += " theory";

                    if (targetType === "section") {
                        cellText = `<div class="period-num">P${period}</div><div class="tt-course">${courseName}</div><div class="tt-faculty">${facultyName}</div><div class="tt-room">${room}</div>`;
                    } else if (targetType === "faculty") {
                        cellText = `<div class="period-num">P${period}</div><div class="tt-course">${courseName}</div><div class="tt-faculty">Sec: ${match.section_id}</div><div class="tt-room">${room}</div>`;
                    } else if (targetType === "lab") {
                        cellText = `<div class="period-num">P${period}</div><div class="tt-course">${courseName}</div><div class="tt-faculty">Sec: ${match.section_id}</div><div class="tt-room">${facultyName}</div>`;
                    }
                } else {
                    cellText = `<div class="period-num">P${period}</div><div style="color:var(--text-muted);font-style:italic;">No Class</div>`;
                }

                innerWrapper.appendChild(createGridCell(cellText, cellClass));

                if (period === 2) {
                    innerWrapper.appendChild(createGridCell("BREAK", "timetable-cell timetable-break-cell"));
                }
                if (period === 4) {
                    innerWrapper.appendChild(createGridCell("LUNCH", "timetable-cell timetable-break-cell"));
                }
            }
        }
        gridWrapper.appendChild(innerWrapper);
        container.appendChild(gridWrapper);
    };

    if (category === "department") {
        const sectionsInDept = [];
        for (const [secId, details] of Object.entries(metadata.sections || {})) {
            if (details.department_id === activeFilterVal) {
                sectionsInDept.push(secId);
            }
        }
        sectionsInDept.sort();

        if (sectionsInDept.length === 0) {
            container.innerHTML = "<div class='card'>No sections found in this department.</div>";
            return;
        }

        for (const secId of sectionsInDept) {
            renderSingleGrid("section", secId, `Section: ${secId}`);
        }
    } else {
        renderSingleGrid(category, activeFilterVal);
    }
}

function createGridCell(text, className = "timetable-cell") {
    const div = document.createElement("div");
    div.className = className;
    div.innerHTML = text;
    return div;
}

// Faculty Timetable Page logic
async function loadFacultySelectOptions() {
    const select = document.getElementById("faculty-target-select");
    select.innerHTML = "<option value=''>Loading...</option>";

    // Use cached faculties for instant navigation
    let data = getCache("faculties");
    if (!data) {
        data = await requestAPI("/api/faculties");
        if (data) setCache("faculties", data);
    }
    select.innerHTML = "";
    if (data && data.length > 0) {
        data.forEach(item => {
            const opt = document.createElement("option");
            opt.value = item.faculty_id;
            opt.innerText = `${item.faculty_name} (${item.faculty_id})`;
            select.appendChild(opt);
        });
    } else {
        select.innerHTML = "<option value=''>No faculty found</option>";
    }
    renderFacultyGrid();
}

async function renderFacultyGrid() {
    const container = document.getElementById("faculty-grid-container");
    container.innerHTML = "";
    const activeVal = document.getElementById("faculty-target-select").value;
    if (!activeVal) {
        container.innerHTML = "<div class='card'>Please select a faculty member first.</div>";
        return;
    }

    const metadata = await requestAPI("/api/scheduler/metadata");
    if (metadata) {
        state.courseNames = metadata.course_names || {};
        state.facultyNames = metadata.faculty_names || {};
        state.labDetails = metadata.lab_details || {};
        state.departmentNames = metadata.department_names || {};
    }

    if (state.timetableData.length === 0) {
        const generated = await requestAPI("/api/scheduler/generate", "POST", { dry_run: true });
        if (generated && generated.allocations) {
            state.timetableData = generated.allocations;
        }
    }

    drawGridInContainer(container, "faculty", activeVal, metadata);
}

async function downloadFacultyExport(format) {
    const activeVal = document.getElementById("faculty-target-select").value;
    if (!activeVal) return showToast("Please select a faculty member first.", "error");
    const url = `/api/scheduler/export?type=faculty&id=${encodeURIComponent(activeVal)}&format=${encodeURIComponent(format)}`;
    await _secureDownload(url, `timetable_faculty_${activeVal}.${format}`);
}

// Lab Timetable Page logic
async function loadLabSelectOptions() {
    const select = document.getElementById("lab-target-select");
    select.innerHTML = "<option value=''>Loading...</option>";

    // Use cached labs for instant navigation
    let data = getCache("laboratories");
    if (!data) {
        data = await requestAPI("/api/laboratories");
        if (data) setCache("laboratories", data);
    }
    select.innerHTML = "";
    if (data && data.length > 0) {
        data.forEach(item => {
            const opt = document.createElement("option");
            opt.value = item.lab_room_no;
            opt.innerText = `${item.lab_name || item.lab_room_no} (${item.lab_room_no})`;
            select.appendChild(opt);
        });
    } else {
        select.innerHTML = "<option value=''>No labs found</option>";
    }
    renderLabGrid();
}

async function renderLabGrid() {
    const container = document.getElementById("lab-grid-container");
    container.innerHTML = "";
    const activeVal = document.getElementById("lab-target-select").value;
    if (!activeVal) {
        container.innerHTML = "<div class='card'>Please select a laboratory first.</div>";
        return;
    }

    const metadata = await requestAPI("/api/scheduler/metadata");
    if (metadata) {
        state.courseNames = metadata.course_names || {};
        state.facultyNames = metadata.faculty_names || {};
        state.labDetails = metadata.lab_details || {};
        state.departmentNames = metadata.department_names || {};
    }

    if (state.timetableData.length === 0) {
        const generated = await requestAPI("/api/scheduler/generate", "POST", { dry_run: true });
        if (generated && generated.allocations) {
            state.timetableData = generated.allocations;
        }
    }

    drawGridInContainer(container, "lab", activeVal, metadata);
}

async function downloadLabExport(format) {
    const activeVal = document.getElementById("lab-target-select").value;
    if (!activeVal) return showToast("Please select a laboratory first.", "error");
    const url = `/api/scheduler/export?type=lab&id=${encodeURIComponent(activeVal)}&format=${encodeURIComponent(format)}`;
    await _secureDownload(url, `timetable_lab_${activeVal}.${format}`);
}

// Modals controller
function closeModal(modalId) {
    document.getElementById(modalId).classList.add("hidden");
}

async function globalRefresh() {
    const btn = document.getElementById("global-refresh-btn");
    let originalHTML = "";
    if (btn) {
        originalHTML = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="animation: spin 1s linear infinite; margin-right: 0.35rem;"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
            <span>Loading...</span>
        `;
    }
    
    // Invalidate both client and server caches
    invalidateCache();
    await requestAPI("/api/system/clear-cache", "POST").catch(() => null);
    
    await navigateTo(state.currentPage);

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

// Inits
window.onload = () => {
    // Bind modal backdrop click close
    document.querySelectorAll(".modal").forEach(modal => {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                closeModal(modal.id);
            }
        });
    });

    // Apply layout configuration settings
    applySidebarState();
    applyUserThemeSetting(state.theme);
    applyThemeMode(state.themeMode || "light");
    toggleCompactModeSetting(state.compactMode);

    if (state.token) {
        navigateTo("dashboard");
    } else {
        navigateTo("landing");
    }
    loadSocials();
};

async function loadSocials() {
    const socials = await requestAPI("/api/developer/socials");
    if (socials) {
        // Update landing page links
        const githubLink = document.getElementById("dev-github-link");
        const linkedinLink = document.getElementById("dev-linkedin-link");
        if (githubLink && socials.github_url) githubLink.href = socials.github_url;
        if (linkedinLink && socials.linkedin_url) linkedinLink.href = socials.linkedin_url;

        // Update About Developer page links
        const aboutGithub = document.getElementById("about-github-link");
        const aboutLinkedin = document.getElementById("about-linkedin-link");
        if (aboutGithub && socials.github_url) aboutGithub.href = socials.github_url;
        if (aboutLinkedin && socials.linkedin_url) aboutLinkedin.href = socials.linkedin_url;
    }
}

function downloadResume() {
    window.location.href = "/api/developer/resume";
}

async function executePasswordReset(form) {
    const username = form.username.value;
    const old_password = form.old_password.value;
    const new_password = form.new_password.value;

    const payload = { username, new_password };
    if (old_password) {
        payload.old_password = old_password;
    }

    const res = await requestAPI("/api/auth/reset-password", "POST", payload);
    if (res) {
        showToast("Password updated successfully!");
        form.reset();
    }
}

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    const eyeOpen = btn.querySelector(".eye-open");
    const eyeClosed = btn.querySelector(".eye-closed");
    if (input.type === "password") {
        input.type = "text";
        eyeOpen.style.display = "none";
        eyeClosed.style.display = "block";
    } else {
        input.type = "password";
        eyeOpen.style.display = "block";
        eyeClosed.style.display = "none";
    }
}

async function submitContactForm(form) {
    const btn = document.getElementById("contact-submit-btn");
    const originalText = btn ? btn.innerText : "Send Message";
    if (btn) {
        btn.disabled = true;
        btn.innerText = "Sending...";
    }

    const payload = {
        name: form.name.value,
        email: form.email.value,
        phone: form.phone.value,
        message: form.message.value
    };

    try {
        const response = await fetch("https://formsubmit.co/ajax/diva132006@gmail.com", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            showToast("Message sent successfully!");
            form.reset();
        } else {
            showToast("Failed to send message via form. Trying alternative...", "warning");
            window.open(`mailto:diva132006@gmail.com?subject=UniSched Query from ${encodeURIComponent(payload.name)}&body=Name: ${encodeURIComponent(payload.name)}%0D%0AEmail: ${encodeURIComponent(payload.email)}%0D%0APhone: ${encodeURIComponent(payload.phone)}%0D%0AMessage: ${encodeURIComponent(payload.message)}`);
        }
    } catch (e) {
        showToast("Error sending message. Opening mail app...", "warning");
        window.open(`mailto:diva132006@gmail.com?subject=UniSched Query from ${encodeURIComponent(payload.name)}&body=Name: ${encodeURIComponent(payload.name)}%0D%0AEmail: ${encodeURIComponent(payload.email)}%0D%0APhone: ${encodeURIComponent(payload.phone)}%0D%0AMessage: ${encodeURIComponent(payload.message)}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerText = originalText;
        }
    }
}
