/**
 * Client-side script managing REST API calls, state transitions, grid renders, and CRUD.
 */

// Global State
const state = {
    token: localStorage.getItem("auth_token") || null,
    role: localStorage.getItem("auth_role") || null,
    currentPage: "landing",
    selectedDept: "ISC",
    timetableData: [],
    crudEntity: "faculties", // Current CRUD entity being managed
    crudData: [],
    ruleTab: "structured",
    timetableSubPage: "generate"
};

// Config APIs
const API_BASE = "";

// Entity Specific Form Schemas
const CRUD_SCHEMAS = {
    departments: {
        title: "Departments",
        idField: "department_id",
        fields: [
            { name: "department_id", label: "Department ID", type: "text", required: true },
            { name: "department_name", label: "Department Name", type: "text", required: true },
            { name: "hod", label: "HOD Name", type: "text" },
            { name: "email", label: "Email", type: "email" },
            { name: "phone", label: "Phone", type: "text" }
        ]
    },
    faculties: {
        title: "Faculty",
        idField: "faculty_id",
        fields: [
            { name: "faculty_id", label: "Faculty ID", type: "text", required: true },
            { name: "faculty_name", label: "Faculty Name", type: "text", required: true },
            { name: "email", label: "Email", type: "email" },
            { name: "phone", label: "Phone", type: "text" },
            { name: "designation", label: "Designation", type: "text" },
            { name: "department_id", label: "Department", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" },
            { name: "max_hours_week", label: "Maximum Weekly Hours", type: "number", required: true, default: 30 },
            { name: "max_hours_daily", label: "Maximum Daily Hours", type: "number", required: true, default: 8 },
            { name: "status", label: "Status", type: "select", options: ["ACTIVE", "ON_LEAVE", "TRANSFERRED", "RETIRED"] }
        ]
    },
    courses: {
        title: "Courses",
        idField: "course_id",
        fields: [
            { name: "course_id", label: "Course ID", type: "text", required: true },
            { name: "course_name", label: "Course Name", type: "text", required: true },
            { name: "semester", label: "Semester", type: "number", required: true },
            { name: "c", label: "Credits", type: "number", required: true },
            { name: "l", label: "Lecture (L)", type: "number", required: true },
            { name: "t", label: "Tutorial (T)", type: "number", required: true },
            { name: "p", label: "Practical (P)", type: "number", required: true },
            { name: "has_lab", label: "Has Lab", type: "select", options: [ {value: 0, text: "No"}, {value: 1, text: "Yes"} ] },
            { name: "difficulty", label: "Difficulty", type: "number", min: 1, max: 5 },
            { name: "weekly_hours", label: "Weekly Hours", type: "number", required: true }
        ]
    },
    rooms: {
        title: "Rooms",
        idField: "room_no",
        fields: [
            { name: "room_no", label: "Room Number", type: "text", required: true },
            { name: "capacity", label: "Capacity", type: "number", required: true },
            { name: "building", label: "Building", type: "text" },
            { name: "floor", label: "Floor", type: "number" },
            { name: "department_id", label: "Department", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" }
        ]
    },
    laboratories: {
        title: "Laboratories",
        idField: "lab_room_no",
        fields: [
            { name: "lab_room_no", label: "Lab Number", type: "text", required: true },
            { name: "lab_name", label: "Lab Name", type: "text", required: true },
            { name: "capacity", label: "Capacity", type: "number", required: true },
            { name: "department_id", label: "Department", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" },
            { name: "supported_courses", label: "Supported Courses", type: "text" }
        ]
    },
    sections: {
        title: "Sections",
        idField: "section_id",
        fields: [
            { name: "section_id", label: "Section ID", type: "text", required: true },
            { name: "section_name", label: "Section Name", type: "text", required: true },
            { name: "semester", label: "Semester", type: "number", required: true },
            { name: "capacity", label: "Strength (Capacity)", type: "number", required: true },
            { name: "department_id", label: "Department", type: "select", optionsUrl: "/api/departments", optionValue: "department_id", optionText: "department_name" },
            { name: "classroom", label: "Classroom", type: "select", optionsUrl: "/api/rooms", optionValue: "room_no", optionText: "room_no" },
            { name: "class_teacher", label: "Class Teacher", type: "select", optionsUrl: "/api/faculties", optionValue: "faculty_id", optionText: "faculty_name" }
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
            { name: "enabled", label: "Enabled", type: "select", options: [ {value: 1, text: "Active"}, {value: 0, text: "Disabled"} ] },
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

// REST Client requests wrapper
async function requestAPI(url, method = "GET", body = null) {
    try {
        const options = { method, headers: getHeaders() };
        if (body) {
            options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        if (response.status === 401 || response.status === 403) {
            showToast("Unauthorized. Please login again.", "error");
            logout();
            return null;
        }
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Request failed.");
        }
        return data;
    } catch (err) {
        showToast(err.message, "error");
        return null;
    }
}

// Navigation View Controller
function navigateTo(pageId) {
    state.currentPage = pageId;
    
    // Hide all views
    document.querySelectorAll(".view-section").forEach(sec => sec.classList.add("hidden"));
    
    // Determine view to show based on login state
    if (!state.token) {
        document.getElementById("view-landing").classList.remove("hidden");
        document.getElementById("nav-logout-btn").classList.add("hidden");
        document.getElementById("nav-dashboard-btn").classList.add("hidden");
        document.getElementById("nav-crud-btn").classList.add("hidden");
        document.getElementById("nav-timetable-btn").classList.add("hidden");
        document.getElementById("nav-rules-btn").classList.add("hidden");
        return;
    }
    
    document.getElementById("nav-logout-btn").classList.remove("hidden");
    document.getElementById("nav-dashboard-btn").classList.remove("hidden");
    document.getElementById("nav-crud-btn").classList.remove("hidden");
    document.getElementById("nav-timetable-btn").classList.remove("hidden");
    document.getElementById("nav-rules-btn").classList.remove("hidden");
    
    if (pageId === "dashboard") {
        if (state.role === "SUPER_ADMIN") {
            document.getElementById("view-admin-dashboard").classList.remove("hidden");
            loadAdminDashboard();
        } else {
            document.getElementById("view-hod-dashboard").classList.remove("hidden");
            loadHODDashboard();
        }
    } else if (pageId === "crud") {
        document.getElementById("view-crud-manager").classList.remove("hidden");
        loadCRUDEntityList();
    } else if (pageId === "timetable") {
        document.getElementById("view-timetable-planner").classList.remove("hidden");
        switchTimetableSubPage(state.timetableSubPage);
    } else if (pageId === "rules") {
        document.getElementById("view-rule-builder").classList.remove("hidden");
        loadRulesList();
    }
}

// User Actions: Logins & Logouts
async function login(username, password) {
    const data = await requestAPI("/api/auth/login", "POST", { username, password });
    if (data && data.token) {
        state.token = data.token;
        state.role = data.role;
        localStorage.setItem("auth_token", data.token);
        localStorage.setItem("auth_role", data.role);
        showToast("Logged in successfully!");
        navigateTo("dashboard");
    }
}

function logout() {
    state.token = null;
    state.role = null;
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_role");
    navigateTo("landing");
}

// Dashboard Initializations
async function loadAdminDashboard() {
    const stats = await requestAPI("/api/dashboard/stats");
    if (stats) {
        document.getElementById("stat-admin-depts").innerText = stats.department_count || 0;
        document.getElementById("stat-admin-faculty").innerText = stats.faculty_count || 0;
        document.getElementById("stat-admin-courses").innerText = stats.course_count || 0;
        document.getElementById("stat-admin-rooms").innerText = stats.room_count || 0;
        document.getElementById("stat-admin-rules").innerText = stats.rule_count || 0;
        document.getElementById("stat-admin-students").innerText = stats.student_count || 0;
        document.getElementById("stat-admin-teachers").innerText = stats.class_teacher_count || 0;
    }
}

async function loadHODDashboard() {
    const stats = await requestAPI("/api/dashboard/stats");
    if (stats) {
        document.getElementById("stat-hod-faculty").innerText = stats.faculty_count || 0;
        document.getElementById("stat-hod-courses").innerText = stats.course_count || 0;
        document.getElementById("stat-hod-rooms").innerText = stats.room_count || 0;
        document.getElementById("stat-hod-sections").innerText = stats.section_count || 0;
        document.getElementById("stat-hod-students").innerText = stats.student_count || 0;
        document.getElementById("stat-hod-teachers").innerText = stats.class_teacher_count || 0;
    }
    
    // Load section statuses table
    const sections = await requestAPI("/api/hod/sections-status");
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
                <td><span style="color: ${sec.status === 'Generated' ? 'var(--color-green-btn)' : '#ef4444'}; font-weight: 500;">${sec.status}</span></td>
                <td>
                    <button class="btn btn-secondary" onclick="viewSectionTimetableDirect('${sec.section_id}')">View</button>
                    <button class="btn btn-secondary" onclick="downloadSectionExportDirect('${sec.section_id}', 'html')">PDF</button>
                    <button class="btn btn-secondary" onclick="downloadSectionExportDirect('${sec.section_id}', 'csv')">Excel</button>
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
    state.timetableSubPage = "view";
    navigateTo("timetable");
    setTimeout(async () => {
        document.getElementById("timetable-type-select").value = "section";
        await updateTimetableIdOptions();
        const idSelect = document.getElementById("timetable-id-select");
        idSelect.value = secId;
        renderTimetableGrid();
    }, 200);
}

function downloadSectionExportDirect(secId, format) {
    const token = state.token;
    window.open(`/api/scheduler/export?type=section&id=${secId}&format=${format}&Authorization=Bearer ${token}`);
}

// CRUD Management Module
function changeCRUDEntity(entity) {
    state.crudEntity = entity;
    loadCRUDEntityList();
}

async function loadCRUDEntityList() {
    let endpoint = `/api/${state.crudEntity}`;
    const data = await requestAPI(endpoint);
    if (data) {
        state.crudData = data;
        renderCRUDTable();
    }
}

function renderCRUDTable() {
    const headersDiv = document.getElementById("crud-table-headers");
    const bodyDiv = document.getElementById("crud-table-body");
    
    headersDiv.innerHTML = "";
    bodyDiv.innerHTML = "";
    
    document.getElementById("crud-entity-title").innerText = state.crudEntity;
    
    const schema = CRUD_SCHEMAS[state.crudEntity];
    if (!schema) return;
    
    if (state.crudData.length === 0) {
        bodyDiv.innerHTML = `<tr><td colspan="${schema.fields.length + 1}">No records found.</td></tr>`;
        return;
    }
    
    // Header Row
    const headerRow = document.createElement("tr");
    schema.fields.forEach(f => {
        const th = document.createElement("th");
        th.innerText = f.label.toUpperCase();
        headerRow.appendChild(th);
    });
    const actionsTh = document.createElement("th");
    actionsTh.innerText = "ACTIONS";
    headerRow.appendChild(actionsTh);
    headersDiv.appendChild(headerRow);
    
    // Body Rows
    state.crudData.forEach(row => {
        const tr = document.createElement("tr");
        schema.fields.forEach(f => {
            const td = document.createElement("td");
            let val = row[f.name];
            if (val === undefined || val === null) val = "";
            if (f.name === "has_lab") {
                val = val ? "Yes" : "No";
            } else if (f.name === "enabled") {
                val = val ? "Active" : "Disabled";
            }
            td.innerText = val;
            tr.appendChild(td);
        });
        
        const actionsTd = document.createElement("td");
        if (state.role === "SUPER_ADMIN") {
            actionsTd.innerHTML = `
                <button class="btn btn-secondary" onclick="openEditModal('${row[schema.idField]}')">Edit</button>
                <button class="btn btn-secondary" style="background:#ef4444;color:white;" onclick="deleteCRUDEntity('${row[schema.idField]}')">Delete</button>
            `;
        } else {
            actionsTd.innerText = "None";
        }
        tr.appendChild(actionsTd);
        bodyDiv.appendChild(tr);
    });
}

async function openAddModal() {
    const form = document.getElementById("crud-entity-form");
    form.reset();
    delete form.dataset.editId;
    
    document.getElementById("crud-modal-title").innerText = `Add New ${CRUD_SCHEMAS[state.crudEntity].title}`;
    await renderFormFields();
    openModal("crud-modal");
}

async function openEditModal(idVal) {
    const form = document.getElementById("crud-entity-form");
    form.reset();
    form.dataset.editId = idVal;
    
    document.getElementById("crud-modal-title").innerText = `Edit ${CRUD_SCHEMAS[state.crudEntity].title}`;
    await renderFormFields();
    
    const record = state.crudData.find(r => r[CRUD_SCHEMAS[state.crudEntity].idField].toString() === idVal.toString());
    if (record) {
        CRUD_SCHEMAS[state.crudEntity].fields.forEach(f => {
            const el = form.querySelector(`[name="${f.name}"]`);
            if (el) {
                if (el.type === "checkbox") {
                    el.checked = !!record[f.name];
                } else {
                    el.value = record[f.name] !== undefined && record[f.name] !== null ? record[f.name] : "";
                }
            }
        });
    }
    openModal("crud-modal");
}

async function renderFormFields() {
    const container = document.getElementById("crud-form-fields-container");
    container.innerHTML = "";
    const schema = CRUD_SCHEMAS[state.crudEntity];
    if (!schema) return;
    
    for (const f of schema.fields) {
        const formGroup = document.createElement("div");
        formGroup.className = "form-group";
        
        const label = document.createElement("label");
        label.innerText = f.label;
        formGroup.appendChild(label);
        
        let input;
        if (f.type === "select") {
            input = document.createElement("select");
            input.name = f.name;
            if (f.required) input.required = true;
            
            if (f.options) {
                f.options.forEach(opt => {
                    const option = document.createElement("option");
                    if (typeof opt === "object") {
                        option.value = opt.value;
                        option.innerText = opt.text;
                    } else {
                        option.value = opt;
                        option.innerText = opt;
                    }
                    input.appendChild(option);
                });
            } else if (f.optionsUrl) {
                const data = await requestAPI(f.optionsUrl);
                if (data) {
                    const emptyOption = document.createElement("option");
                    emptyOption.value = "";
                    emptyOption.innerText = "-- Select Option --";
                    input.appendChild(emptyOption);
                    data.forEach(item => {
                        const option = document.createElement("option");
                        option.value = item[f.optionValue];
                        option.innerText = item[f.optionText] || item[f.optionValue];
                        input.appendChild(option);
                    });
                }
            }
        } else if (f.type === "textarea") {
            input = document.createElement("textarea");
            input.name = f.name;
            input.rows = 4;
            if (f.required) input.required = true;
        } else {
            input = document.createElement("input");
            input.name = f.name;
            input.type = f.type;
            if (f.required) input.required = true;
            if (f.min !== undefined) input.min = f.min;
            if (f.max !== undefined) input.max = f.max;
            if (f.default !== undefined) input.value = f.default;
        }
        
        const form = document.getElementById("crud-entity-form");
        if (form.dataset.editId && f.name === schema.idField) {
            input.disabled = true;
            const hidden = document.createElement("input");
            hidden.type = "hidden";
            hidden.name = f.name;
            hidden.value = form.dataset.editId;
            formGroup.appendChild(hidden);
        }
        
        formGroup.appendChild(input);
        container.appendChild(formGroup);
    }
}

async function deleteCRUDEntity(idVal) {
    if (!confirm("Are you sure you want to delete this entity?")) return;
    const data = await requestAPI(`/api/${state.crudEntity}/${idVal}`, "DELETE");
    if (data) {
        showToast("Deleted successfully.");
        loadCRUDEntityList();
    }
}

async function saveEntitySubmit(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);
    const payload = {};
    formData.forEach((val, key) => {
        payload[key] = val;
    });
    
    // Convert numbers and booleans
    const schema = CRUD_SCHEMAS[state.crudEntity];
    schema.fields.forEach(f => {
        if (payload[f.name] !== undefined) {
            if (f.type === "number") {
                payload[f.name] = parseInt(payload[f.name]) || 0;
            }
            if (f.name === "has_lab" || f.name === "enabled") {
                payload[f.name] = parseInt(payload[f.name]) || 0;
            }
        }
    });
    
    const isEdit = form.dataset.editId;
    let res;
    if (isEdit) {
        res = await requestAPI(`/api/${state.crudEntity}/${isEdit}`, "PUT", payload);
    } else {
        res = await requestAPI(`/api/${state.crudEntity}`, "POST", payload);
    }
    
    if (res) {
        showToast("Saved successfully.");
        closeModal("crud-modal");
        loadCRUDEntityList();
    }
}

// Timetable Sub-Page Switcher
function switchTimetableSubPage(subPage) {
    state.timetableSubPage = subPage;
    document.querySelectorAll(".timetable-sub-page").forEach(el => el.classList.add("hidden"));
    document.getElementById(`timetable-sub-${subPage}`).classList.remove("hidden");
    
    // Active sidebar class
    document.querySelectorAll(".timetable-menu button").forEach(btn => {
        if (btn.getAttribute("onclick").includes(subPage)) {
            btn.parentElement.classList.add("active");
        } else {
            btn.parentElement.classList.remove("active");
        }
    });
    
    if (subPage === "dashboard") {
        loadTimetableDashboard();
    } else if (subPage === "generate") {
        loadGenerateSections();
    } else if (subPage === "view") {
        updateTimetableIdOptions();
    }
}

async function loadTimetableDashboard() {
    const stats = await requestAPI("/api/dashboard/stats");
    if (stats) {
        document.getElementById("tt-stat-faculty").innerText = stats.faculty_count || 0;
        document.getElementById("tt-stat-courses").innerText = stats.course_count || 0;
        document.getElementById("tt-stat-rooms").innerText = stats.room_count || 0;
        document.getElementById("tt-stat-labs").innerText = stats.lab_count || 0;
        document.getElementById("tt-stat-sections").innerText = stats.section_count || 0;
        document.getElementById("tt-stat-runs").innerText = stats.generated_timetables_count || 0;
        document.getElementById("tt-stat-latest-time").innerText = stats.latest_generation_time || "N/A";
    }
}

async function loadGenerateSections() {
    const sections = await requestAPI("/api/sections");
    const select = document.getElementById("generate-section-select");
    select.innerHTML = "";
    if (sections) {
        sections.forEach(sec => {
            const opt = document.createElement("option");
            opt.value = sec.section_id;
            opt.innerText = `${sec.section_name} (${sec.section_id})`;
            select.appendChild(opt);
        });
    }
}

function toggleGenerateScope() {
    const scope = document.getElementById("generate-scope-select").value;
    const group = document.getElementById("generate-section-group");
    if (scope === "section") {
        group.classList.remove("hidden");
    } else {
        group.classList.add("hidden");
    }
}

async function executeGeneration() {
    const scope = document.getElementById("generate-scope-select").value;
    const secId = document.getElementById("generate-section-select").value;
    
    let payload = {};
    if (scope === "section") {
        if (!secId) return showToast("Please select a section.", "error");
        payload["section_id"] = secId;
    }
    
    showToast("Generating timetable, please wait...");
    const data = await requestAPI("/api/scheduler/generate", "POST", payload);
    
    const resultsCard = document.getElementById("generation-results-card");
    resultsCard.classList.remove("hidden");
    
    if (data) {
        showToast("Timetable generated successfully!");
        document.getElementById("gen-status-val").innerText = "SUCCESS";
        document.getElementById("gen-time-val").innerText = `${data.stats.execution_time.toFixed(4)} seconds`;
        state.timetableData = data.allocations;
        switchTimetableSubPage('view');
    } else {
        document.getElementById("gen-status-val").innerText = "FAILED";
        document.getElementById("gen-time-val").innerText = "N/A";
        document.getElementById("gen-validation-val").innerText = "N/A";
    }
}

async function executeValidation() {
    showToast("Diagnosing schedule...");
    const data = await requestAPI("/api/scheduler/validate", "POST");
    const rep = document.getElementById("tt-validation-report");
    if (data) {
        rep.innerHTML = `
            <strong>Status:</strong> ${data.is_valid ? '<span style="color:var(--color-green-btn); font-weight:bold;">VALID</span>' : '<span style="color:#ef4444; font-weight:bold;">CONFLICTS DETECTED</span>'}<br><br>
            <strong>Hard Constraint Errors:</strong> ${data.errors.length ? `<ul style="margin-left: 1.5rem; color:#ef4444;">${data.errors.map(e => `<li>${e}</li>`).join('')}</ul>` : '<span style="color:var(--color-green-btn)">None</span>'}<br>
            <strong>Soft Preference Warnings:</strong> ${data.warnings.length ? `<ul style="margin-left: 1.5rem; color:var(--color-orange-header);">${data.warnings.map(w => `<li>${w}</li>`).join('')}</ul>` : 'None'}
        `;
    } else {
        rep.innerHTML = `<span style="color:#ef4444;">Failed to execute validation report.</span>`;
    }
}

async function executeRepair() {
    showToast("Executing local search repair...");
    const data = await requestAPI("/api/scheduler/repair", "POST");
    const rep = document.getElementById("tt-repair-report");
    if (data) {
        showToast("Repair process completed!");
        state.timetableData = data.repaired_schedule;
        rep.innerHTML = `
            <strong>Status:</strong> <span style="color:var(--color-green-btn); font-weight:bold;">REPAIRED</span><br><br>
            <strong>Iterations Run:</strong> ${data.stats.iterations_run || 0}<br>
            <strong>Repairs Applied:</strong> ${data.stats.repairs_applied || 0}<br>
            <strong>Remaining Clashes:</strong> ${data.remaining_conflicts || 0}<br>
            <strong>Execution Time:</strong> ${data.stats.execution_time ? data.stats.execution_time.toFixed(4) : 0} seconds
        `;
    } else {
        rep.innerHTML = `<span style="color:#ef4444;">Failed to execute repair engine.</span>`;
    }
}

// AI Rules Module & Structured Builder
function switchRuleTab(tabId) {
    state.ruleTab = tabId;
    document.querySelectorAll(".rule-tab-content").forEach(el => el.classList.add("hidden"));
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    
    document.getElementById(`tab-${tabId}`).classList.remove("hidden");
    event.target.classList.add("active");
}

async function parseNaturalRule() {
    const text = document.getElementById("natural-rule-text").value.trim();
    if (!text) return showToast("Please enter rule text.", "error");
    
    const data = await requestAPI("/api/rules/parse-natural", "POST", { rule_text: text });
    if (data) {
        document.getElementById("rule-preview-json").innerText = JSON.stringify(data, null, 2);
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
    } catch(e) {
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
            course_id: form.course_id.value || undefined,
            avoid_days: form.avoid_days.value ? [parseInt(form.avoid_days.value)] : undefined,
            avoid_periods: form.avoid_periods.value ? [parseInt(form.avoid_periods.value)] : undefined
        }
    };
    
    const res = await requestAPI("/api/rules/save", "POST", payload);
    if (res) {
        showToast("Structured Rule saved successfully.");
        loadRulesList();
    }
}

async function loadRulesList() {
    const rules = await requestAPI("/api/rules");
    if (rules) {
        const tbody = document.getElementById("rules-list-body");
        tbody.innerHTML = "";
        rules.forEach(r => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${r.rule_id}</td>
                <td>${r.rule_name}</td>
                <td>${r.type}</td>
                <td>${r.priority}</td>
                <td>${r.enabled ? 'Active' : 'Disabled'}</td>
                <td>
                    <button class="btn btn-secondary" onclick="viewRuleVersions('${r.rule_id}')">Versions</button>
                    <button class="btn btn-secondary" onclick="toggleRule('${r.rule_id}', ${r.version || 1}, ${r.enabled ? 0 : 1})">${r.enabled ? 'Disable' : 'Enable'}</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
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
            li.style.padding = "0.5rem";
            li.style.borderBottom = "1px solid var(--border-color)";
            li.innerHTML = `
                <strong>Ver ${v.version}</strong> (${v.created_at}) - ${v.enabled ? 'Active' : 'Disabled'}
                <pre style="font-size:0.8rem;background:var(--bg-light);padding:0.25rem;">${v.parameter}</pre>
            `;
            list.appendChild(li);
        });
        openModal("versions-modal");
    }
}

// Exporter Download triggers
function downloadExport(format) {
    const category = document.getElementById("timetable-type-select").value;
    const selectTarget = document.getElementById("timetable-id-select");
    const idVal = selectTarget.value;
    if (!idVal) return showToast("Please select a target first.", "error");
    
    const token = state.token;
    window.open(`/api/scheduler/export?type=${category}&id=${idVal}&format=${format}&Authorization=Bearer ${token}`);
}

async function updateTimetableIdOptions() {
    const category = document.getElementById("timetable-type-select").value;
    const selectTarget = document.getElementById("timetable-id-select");
    selectTarget.innerHTML = "<option value=''>Loading...</option>";
    
    let endpoint = "";
    if (category === "section") endpoint = "/api/sections";
    else if (category === "faculty") endpoint = "/api/faculties";
    else if (category === "lab") endpoint = "/api/laboratories";
    
    const data = await requestAPI(endpoint);
    selectTarget.innerHTML = "";
    if (data && data.length > 0) {
        data.forEach(item => {
            const opt = document.createElement("option");
            if (category === "section") {
                opt.value = item.section_id;
                opt.innerText = `${item.section_name} (${item.section_id})`;
            } else if (category === "faculty") {
                opt.value = item.faculty_id;
                opt.innerText = `${item.faculty_name} (${item.faculty_id})`;
            } else if (category === "lab") {
                opt.value = item.lab_room_no;
                opt.innerText = `${item.lab_name || item.lab_room_no} (${item.lab_room_no})`;
            }
            selectTarget.appendChild(opt);
        });
    } else {
        selectTarget.innerHTML = "<option value=''>No targets found</option>";
    }
    renderTimetableGrid();
}

// Renders structured grid coordinates representation
function renderTimetableGrid() {
    const container = document.getElementById("timetable-grid-container");
    container.innerHTML = "";
    
    container.appendChild(createGridCell("Day / Period", "grid-header"));
    for (let p = 1; p <= 7; p++) {
        container.appendChild(createGridCell(`Period ${p}`, "grid-header"));
    }
    
    const dayNames = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday"};
    
    const category = document.getElementById("timetable-type-select").value;
    const selectTarget = document.getElementById("timetable-id-select");
    const activeFilterVal = selectTarget.value;
    
    for (let day = 1; day <= 5; day++) {
        container.appendChild(createGridCell(dayNames[day], "grid-header"));
        
        for (let period = 1; period <= 7; period++) {
            let match = null;
            if (activeFilterVal) {
                match = state.timetableData.find(a => {
                    if (a.day_id !== day || a.period_no !== period) return false;
                    if (category === "section") return a.section_id === activeFilterVal;
                    if (category === "faculty") return a.faculty_id === activeFilterVal;
                    if (category === "lab") return a.lab_room_no === activeFilterVal;
                    return false;
                });
            }
            
            if (match) {
                const room = match.room_no || match.lab_room_no || "Unassigned";
                if (category === "section") {
                    container.appendChild(createGridCell(`${match.course_id}<br><strong>${match.faculty_id}</strong><br>[${room}]`));
                } else if (category === "faculty") {
                    container.appendChild(createGridCell(`${match.course_id}<br><strong>${match.section_id}</strong><br>[${room}]`));
                } else if (category === "lab") {
                    container.appendChild(createGridCell(`${match.course_id}<br><strong>${match.section_id}</strong><br>(${match.faculty_id})`));
                }
            } else {
                container.appendChild(createGridCell(""));
            }
        }
    }
}

function createGridCell(text, className = "grid-cell") {
    const div = document.createElement("div");
    div.className = className;
    div.innerHTML = text;
    return div;
}

// Modals controller
function openModal(modalId) {
    document.getElementById(modalId).classList.remove("hidden");
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add("hidden");
}

// Inits
window.onload = () => {
    document.getElementById("nav-dashboard-btn").onclick = () => navigateTo("dashboard");
    document.getElementById("nav-crud-btn").onclick = () => navigateTo("crud");
    document.getElementById("nav-timetable-btn").onclick = () => navigateTo("timetable");
    document.getElementById("nav-rules-btn").onclick = () => navigateTo("rules");
    document.getElementById("nav-logout-btn").onclick = logout;
    
    if (state.token) {
        navigateTo("dashboard");
    } else {
        navigateTo("landing");
    }
};
