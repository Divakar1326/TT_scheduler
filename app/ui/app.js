/**
 * Client-side script managing REST API calls, state transitions, grid renders, and CRUD.
 */

// Global State
const state = {
    token: null,          // Always start unauthenticated — login required on every session
    role: null,
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
    settings: { data: null, ts: 0 },
    stats: { data: null, ts: 0 },
    hod_sections_status: { data: null, ts: 0 }
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
    // ─── GETTING STARTED ─────────────────────────────────────────────────────
    {
        title: "1. What is UniSched ERP?",
        category: "Getting Started",
        content: "UniSched ERP is an AI-powered University Timetable Automation System. It solves the academic scheduling problem — assigning courses, faculty, rooms, and time slots to sections — without conflicts. The system models timetabling as a Constraint Satisfaction Problem (CSP) and uses a Backtracking Solver, Local Search Repair Engine, and a multi-provider AI inference engine. It supports two database modes: Supabase PostgreSQL (cloud) for production, and SQLite (local) for offline/development use."
    },
    {
        title: "2. Login & User Roles",
        category: "Getting Started",
        content: "UniSched uses role-based access control with two roles:\n\n• SUPER ADMIN — Full system access. Can create/edit/delete all departments, faculty, courses, rooms, labs, and HOD accounts. Username: admin\n\n• HOD (Head of Department) — Department-scoped access only. Can manage their own department's faculty, courses, sections, rooms, labs, rules, and generate/export timetables. HOD usernames follow the pattern: hod_{department_id_lowercase} (e.g. hod_cse, hod_ise, hod_ece, hod_aids).\n\nTo login: Click 'Login as HOD' or 'Login as Admin' from the landing page. Session ends when you click Logout or close/refresh the browser — you must login again each time."
    },
    {
        title: "3. Default Credentials & Accounts",
        category: "Getting Started",
        content: "Default credentials are set when the system database is first initialized:\n\n┌─────────────────────┬──────────────────────────┬──────────────┐\n│ Role                │ Username                 │ Password     │\n├─────────────────────┼──────────────────────────┼──────────────┤\n│ System Admin        │ admin                    │ adminpassword│\n│ HOD — CSE           │ hod_cse                  │ csepassword  │\n│ HOD — ISC/ISE       │ hod_isc                  │ iscpassword  │\n│ HOD — ECE           │ hod_ece                  │ ecepassword  │\n│ HOD — AIDS          │ hod_aids                 │ aidspassword │\n└─────────────────────┴──────────────────────────┴──────────────┘\n\nNote: When the Admin creates a new department, a HOD account is automatically created. The generated password is shown ONCE on screen — save it immediately. Passwords can be changed from Settings > Change Password."
    },
    {
        title: "4. Changing Your Password",
        category: "Getting Started",
        content: "To change your password:\n1. Login with your current credentials.\n2. Go to Settings (bottom of sidebar).\n3. Scroll to the 'Change Password' section.\n4. Enter your current (old) password, new password, and confirm.\n5. Click 'Update Password'.\n\nRules:\n• You can only change your own password (HODs cannot change other users' passwords).\n• Admin can change any user's password.\n• Passwords are stored securely as salted bcrypt hashes — never stored as plain text.\n• If you forget your password, ask the Admin to reset it from the backend."
    },
    {
        title: "5. Recommended Setup Order (Quick Start)",
        category: "Getting Started",
        content: "Follow this exact sequence for a clean initial setup:\n\n1. Login as Admin\n2. Create Departments (e.g. CSE, ISE, ECE)\n3. Add Rooms (classrooms) for each department\n4. Add Labs for departments that have practical courses\n5. Add Faculty and assign them to departments\n6. Add Courses — set theory hours, lab hours, and link required labs\n7. Add Sections — assign classroom, class teacher, and link courses\n8. (Optional) Define Rules via Rule Builder\n9. Login as HOD → Navigate to Generate Timetable → Select department → Click Generate\n10. View generated timetable → Export as PDF/Excel/CSV\n\nSkipping steps or adding data out of order is the most common cause of solver failures."
    },

    // ─── DEPARTMENTS ─────────────────────────────────────────────────────────
    {
        title: "6. Managing Departments",
        category: "Data Management",
        content: "Path: Sidebar > Departments (Admin only)\n\nCreating a Department:\n• Department Code/ID: Short unique identifier (e.g. CSE, ISC, ECE, AIDS). Case-insensitive.\n• Department Name: Full official name.\n• HOD: Optionally select an existing faculty member as HOD label (cosmetic only — actual HOD login is auto-created).\n\nWhen you create a department:\n• A HOD login account is automatically generated (username: hod_{id_lowercase}).\n• A random secure password is generated and shown ONCE — copy it before closing.\n\nDepartment cards show live counts: faculty, courses, sections, rooms, labs.\n\nDeleting a department: Soft-delete only (data is preserved in DB, not visible in UI). Cannot be undone from the UI."
    },

    // ─── FACULTY ─────────────────────────────────────────────────────────────
    {
        title: "7. Managing Faculty",
        category: "Data Management",
        content: "Path: Sidebar > Faculty\n\nRequired fields: Faculty ID (e.g. F001), Faculty Name, Department.\n\nOptional but important:\n• Max Weekly Hours: Cap on total lectures per week (default 30). Scheduler respects this.\n• Max Daily Hours: Maximum lectures in a single day (default 8).\n• Professor Type: Regular / Adjunct / Visiting — affects scheduling priority.\n• Preferred Days: Comma-separated day numbers (1=Mon … 5=Fri). Soft constraint.\n• Preferred Periods: Comma-separated slot numbers. Soft constraint.\n• Status: ACTIVE faculty are included in scheduling; ON_LEAVE / RETIRED are excluded.\n• Assigned Courses: Multi-select. Links this faculty to courses they can teach.\n\nHOD restriction: HODs can only view/edit faculty in their own department. Admin sees all."
    },

    // ─── COURSES ─────────────────────────────────────────────────────────────
    {
        title: "8. Managing Courses",
        category: "Data Management",
        content: "Path: Sidebar > Courses\n\nRequired: Course Code (e.g. CS301), Course Name, Department, Semester.\n\nKey fields:\n• Theory Hours (L+T): Lecture + Tutorial hours per week. These become individual 1-period scheduled slots.\n• Lab Hours (P): Practical hours per week. The scheduler automatically groups these into consecutive 2-period lab sessions.\n• Has Lab Component: Set to 'Yes' if this course has practicals.\n• Required Laboratory: The specific lab room this course must use (optional — if blank, any available lab is used).\n• Course Color: Visual color used in the timetable grid display.\n• Difficulty Weight (1–5): Higher value = solver tries to schedule this course first.\n• Assigned Faculty: Which faculty can teach this course.\n• Assigned Sections: Which sections study this course.\n\nImportant: If Lab Hours > 0, always set 'Has Lab' to Yes and link a Required Lab if applicable."
    },

    // ─── SECTIONS ────────────────────────────────────────────────────────────
    {
        title: "9. Managing Sections",
        category: "Data Management",
        content: "Path: Sidebar > Sections\n\nA Section represents a group of students (a class batch).\n\nRequired: Section ID (e.g. CSE-A, 3ISC-B), Section Name, Semester, Department.\n\nKey fields:\n• Capacity: Maximum student seats in this section's classroom.\n• Strength: Actual enrolled students. Must not exceed room capacity or solver will flag conflicts.\n• Assigned Classroom: The room where this section normally sits.\n• Class Teacher: The mentor/homeroom faculty for this section.\n• Assigned Courses: All courses this section attends.\n\nSection detail cards show: timetable grid, lab schedules, and generation status.\n\nHOD restriction: HODs only see/edit their own department's sections."
    },

    // ─── ROOMS & LABS ─────────────────────────────────────────────────────────
    {
        title: "10. Managing Rooms (Classrooms)",
        category: "Data Management",
        content: "Path: Sidebar > Rooms\n\nRequired: Room Number (unique ID, e.g. R101, A-203), Seating Capacity.\n\nKey fields:\n• Department Allocation: Which department primarily uses this room (used for scoping).\n• Room Type: PROJECTOR / SMART / LAB — informational tag.\n• Availability Pattern: Leave as 'All Slots' for full availability, or enter a JSON pattern to restrict specific days/periods.\n\nImportant: Room capacity must be ≥ section strength, otherwise the validator will report a capacity violation."
    },
    {
        title: "11. Managing Laboratories",
        category: "Data Management",
        content: "Path: Sidebar > Laboratories\n\nRequired: Lab Room Code (unique ID, e.g. LAB-CS1), Lab Name, Workstation Capacity.\n\nKey fields:\n• Department Allocation: Which department owns this lab.\n• Lab Incharge: Faculty member responsible for this lab.\n• Equipment Profile: Free-text description of hardware/software (e.g. 'NVIDIA GPUs, Python 3.11, Cisco Packet Tracer').\n• Availability Pattern: Default 'All Slots' means available all periods.\n\nLab sessions are ALWAYS scheduled as consecutive 2-period blocks (e.g. Period 1–2, Period 3–4) to allow meaningful practical time. The solver enforces this automatically."
    },

    // ─── RULES ───────────────────────────────────────────────────────────────
    {
        title: "12. Rule Builder — Overview",
        category: "Constraint Management",
        content: "Path: Sidebar > Rules\n\nRules define scheduling constraints. There are two types:\n\n• HARD rules: Must never be violated. Example: 'Dr. Sharma cannot teach on Saturday.' If violated, the solver backtracks.\n• SOFT rules: Preferred but not mandatory. Example: 'Dr. Rekha prefers morning slots.' Violations are penalized in the quality score but don't block generation.\n\nRules are versioned — every save creates a new version. You can view history, toggle rules on/off, and roll back versions. Department-scoped rules only apply to that department's timetable.\n\nTwo methods to create rules:\n1. Structured Rule Builder (form-based)\n2. AI Rule Builder (natural language input)"
    },
    {
        title: "13. Rule Builder — Structured Form",
        category: "Constraint Management",
        content: "The Structured Rule Builder provides a form interface to create rules without writing JSON.\n\nRule ID: A unique slug identifier (e.g. no-fri-lectures). Use lowercase-with-dashes.\nRule Name: Human-readable label.\nRule Type: HARD or SOFT.\nPriority: Higher number = higher enforcement priority (1–10).\nParameter: The JSON constraint definition. Examples:\n\nFaculty unavailability:\n{\"constraint\": \"faculty_unavailable\", \"faculty_id\": \"F001\", \"day\": 5}\n\nRoom restriction:\n{\"constraint\": \"room_fixed\", \"section_id\": \"CSE-A\", \"room_no\": \"R201\"}\n\nMax consecutive lectures:\n{\"constraint\": \"max_consecutive\", \"faculty_id\": \"F003\", \"max\": 2}\n\nThe system validates entities exist before saving and checks for duplicates and contradictions."
    },
    {
        title: "14. Rule Builder — AI Natural Language",
        category: "Constraint Management",
        content: "The AI Rule Builder translates plain English descriptions into structured JSON rules.\n\nHow to use:\n1. Go to Rules > AI Rule Builder tab.\n2. Type your rule in plain English. Examples:\n   - 'Dr. Rekha cannot teach on Fridays'\n   - 'The Database lab must be scheduled before Period 4'\n   - 'Section CSE-A should not have more than 3 consecutive classes'\n   - 'Prof. Kumar prefers morning sessions from Period 1 to 3'\n3. Click 'Translate with AI'.\n4. Review the generated JSON in the preview panel.\n5. Edit if needed, then click 'Save Rule'.\n\nAI Provider Fallback Chain:\nOpenRouter → Groq → Cerebras → Gemini\n\nIf one provider is down or rate-limited, the system automatically tries the next. The current provider is shown in Settings > AI Engine Status.\n\nSafety: AI output is always validated against the rule schema before saving. Invalid JSON or unknown constraint types are rejected."
    },

    // ─── TIMETABLE GENERATION ─────────────────────────────────────────────────
    {
        title: "15. Generating a Timetable",
        category: "Scheduler Engine",
        content: "Path: Sidebar > Generate Timetable\n\nSteps:\n1. Select a Department from the dropdown (HODs see only their own).\n2. Optionally select a specific Section to generate for just one group.\n3. Click 'Generate Timetable'.\n4. Watch the real-time progress stream:\n   • Stage 1–3: DB connection, academic year, departments loaded\n   • Stage 4–7: Sections, courses, faculty, rooms & labs loaded\n   • Stage 8–11: Sessions built, candidates generated\n   • Stage 12–14: CSP solver running, labs scheduled\n   • Stage 15–16: Results saved, complete\n5. When complete: Hard Score %, Soft Penalty, and total sessions scheduled are shown.\n\nA Hard Score of 100% means zero hard constraint violations. Soft penalty indicates preference satisfaction quality."
    },
    {
        title: "16. Understanding the CSP Solver",
        category: "Scheduler Engine",
        content: "The scheduler uses a Backtracking Constraint Satisfaction Problem (CSP) solver.\n\nHow it works:\n1. Sections are ranked by difficulty (courses with more constraints go first).\n2. For each session, a list of valid candidates (day + period + room/lab) is generated.\n3. Each candidate is checked against all active HARD rules.\n4. If a candidate is valid, it's assigned. If not, the solver backtracks and tries the next.\n5. For lab sessions: Two consecutive periods in the same lab are always scheduled together.\n6. After the primary pass, a Local Search Repair Engine resolves remaining conflicts.\n\nSoft constraints (preferences) are scored as a penalty. The solver reports both scores:\n• Hard Score: % of sessions with zero hard violations (target: 100%)\n• Soft Penalty: Lower = better quality (target: 0)"
    },
    {
        title: "17. What Happens If Generation Fails or Partially Succeeds?",
        category: "Scheduler Engine",
        content: "Common failure modes:\n\n• 'No sections found' — The selected department has no sections. Create sections first.\n• 'No courses assigned' — Sections exist but no courses are linked. Assign courses to sections.\n• 'No faculty available' — All faculty are ON_LEAVE or none are assigned to the department's courses.\n• Hard Score < 100% — Some sessions could not be placed without violating a hard constraint. Solutions:\n   - Relax/disable overly restrictive rules.\n   - Add more room capacity.\n   - Reduce max daily/weekly hour limits.\n   - Add more rooms or labs.\n• Duplicate run error — A generation is already in progress. Wait for it to complete.\n\nAfter partial generation, use the Repair function (Validate page) to attempt auto-repair of conflicts."
    },
    {
        title: "18. Using the Repair Engine",
        category: "Scheduler Engine",
        content: "Path: Timetables > Verify Constraints > Repair\n\nThe Repair Engine attempts to fix remaining hard constraint violations after generation.\n\nHow it works:\n1. The engine identifies all sessions with violations (room conflicts, faculty double-booking, capacity issues).\n2. It attempts to swap, move, or reassign sessions to valid slots.\n3. Repaired sessions are merged back into the timetable.\n4. Statistics show: sessions repaired, remaining conflicts.\n\nWhen to use:\n• After generation if Hard Score < 100%.\n• After manual data changes (e.g. a new room was added) to re-optimize.\n\nNote: Repair does not change the solver's logic — it operates on the final result only."
    },

    // ─── VIEWING TIMETABLES ───────────────────────────────────────────────────
    {
        title: "19. Viewing Timetables",
        category: "Timetable Views",
        content: "UniSched provides four timetable views:\n\n1. Section Timetable (Timetables page): Shows the weekly schedule for a selected section/class batch. Each cell shows: Course name, Faculty name, Room number. Lab sessions appear as merged 2-period blocks.\n\n2. Faculty Timetable (Faculty View page): Shows all classes a selected faculty member teaches across the week. Useful for checking a professor's workload.\n\n3. Lab Timetable (Lab View page): Shows which course/section is using a selected laboratory at each time slot.\n\n4. Department-wide view: Export type 'department' generates a combined CSV/Excel for all sections in a department.\n\nAll views update immediately after a new timetable is generated."
    },
    {
        title: "20. Exporting Timetables",
        category: "Timetable Views",
        content: "All timetable views support three export formats:\n\n• Print / PDF: Opens an HTML print layout optimized for A4 printing. Use your browser's Print function (Ctrl+P / Cmd+P) and select 'Save as PDF'.\n\n• Excel (.xls): Downloads a formatted spreadsheet with color-coded cells and a proper timetable grid layout.\n\n• CSV: Downloads a raw comma-separated file suitable for import into other tools.\n\nExport types available:\n• section — Timetable for one section\n• faculty — Schedule for one faculty member\n• lab — Occupancy schedule for one lab\n• department — All sections in a department (CSV only)\n\nAccess Control: HODs can only export their own department's data. Attempting to export another department's timetable will be rejected."
    },
    {
        title: "21. Validation & Constraint Checking",
        category: "Timetable Views",
        content: "Path: Timetables > Verify Constraints\n\nThe Validator checks the generated timetable for:\n\nHard Constraint Checks:\n• Faculty double-booking (same faculty in two places at once)\n• Room double-booking (same room used by two sections simultaneously)\n• Lab double-booking (same lab used by two sections simultaneously)\n• Capacity violations (section strength > room capacity)\n• Lab continuity (lab sessions must be consecutive 2-period blocks)\n• Unscheduled sessions (sessions that couldn't be placed)\n\nSoft Constraint Checks:\n• Faculty preference violations (teaching outside preferred days/periods)\n• Max consecutive lecture violations\n• Workload distribution imbalance\n\nResults show each violation with its type, affected entities, and severity. Use this to diagnose why a timetable has a low Hard Score."
    },

    // ─── DASHBOARD ───────────────────────────────────────────────────────────
    {
        title: "22. Dashboard Overview",
        category: "Navigation",
        content: "The Dashboard is the first page after login.\n\nAdmin Dashboard shows:\n• Total Departments, Faculty, Courses, Rooms, Labs, Rules (system-wide)\n• Section Status table: which sections have timetables generated\n• Quick navigation to all management modules\n\nHOD Dashboard shows:\n• Department-scoped counts: Faculty, Courses, Rooms, Labs, Sections, Students, Rules\n• Section status with class teacher details and generation status\n• Quick-access buttons for common actions\n\nAll counts update in real-time. Click 'Refresh' to force a data reload from the database."
    },

    // ─── SETTINGS ────────────────────────────────────────────────────────────
    {
        title: "23. Settings & Personalization",
        category: "Navigation",
        content: "Path: Sidebar > Settings\n\nTheme Color: Choose from Orange (default), Blue, Green, Purple, or Red accent colors.\n\nTheme Mode: Light or Dark mode.\n\nDisplay Density: Normal or Compact (reduces padding for larger data tables).\n\nDatabase Status: Shows live connection status to Supabase PostgreSQL (production) or SQLite (local). Displays last sync timestamp and connection pool details.\n\nAI Engine Status: Shows which AI provider is currently active (OpenRouter / Groq / Cerebras / Gemini), the model in use, last successful request timestamp, and average response time.\n\nChange Password: Allows updating your own login password (requires current password).\n\nAll theme/display preferences are saved in browser local storage and persist across sessions (even after logout)."
    },

    // ─── SYSTEM ARCHITECTURE ──────────────────────────────────────────────────
    {
        title: "24. System Architecture",
        category: "Technical Reference",
        content: "UniSched ERP Architecture:\n\nFrontend: Single-page HTML/CSS/JS application (no framework). State managed in a global object. TTL-based client-side cache for fast navigation.\n\nBackend: Python Flask REST API. Blueprints: auth, crud, scheduler, rules, hod.\n\nDatabase (Dual-mode):\n• Production: Supabase PostgreSQL (cloud) — SUPABASE_URL + SUPABASE_KEY + DATABASE_URL\n• Development: SQLite local file — database/timetable.db\n\nScheduler Engine: Backtracking CSP solver → Local Search Repair Engine.\n\nAI Engine: Unified AIService with provider fallback chain: OpenRouter → Groq → Cerebras → Gemini.\n\nAuthentication: In-memory session token store (UUID tokens). Role-based access control (SUPER_ADMIN / HOD). Department-scoped data isolation enforced server-side.\n\nExports: TimetableExporter generates CSV, Excel (.xls), and HTML print layouts."
    },
    {
        title: "25. Database Schema Overview",
        category: "Technical Reference",
        content: "Key tables:\n\n• department — Stores department details\n• faculty — Faculty members with availability and preferences\n• courses — Course definitions with LTP credits\n• sections — Student batches with classroom and teacher assignments\n• rooms — Classroom infrastructure\n• labs — Laboratory rooms\n• faculty_course — M:N mapping (which faculty teaches which courses)\n• section_course — M:N mapping (which section attends which course)\n• course_lab — M:N mapping (which course uses which lab)\n• rules — Version-controlled scheduling constraint definitions\n• scheduler_run — Execution metadata (status, timestamps, department)\n• schedule — Generated timetable assignments (section × course × day × period × room/lab)\n• users — Authentication accounts (HOD + Admin)\n• academic_year — Academic year and semester configuration\n\nRelationship hierarchy: Department → (Faculty, Courses, Sections, Rooms, Labs) → Schedule"
    },
    {
        title: "26. AI Provider Configuration",
        category: "Technical Reference",
        content: "The AI engine supports four providers with automatic failover:\n\nPriority chain (default): OpenRouter → Groq → Cerebras → Gemini\n\nConfigure in .env file:\n• AI_PROVIDER=gemini (sets the preferred primary provider)\n• OPENROUTER_API_KEY, OPENROUTER_MODEL\n• GROQ_API_KEY, GROQ_MODEL\n• CEREBRAS_API_KEY, CEREBRAS_MODEL\n• GEMINI_API_KEY, GEMINI_MODEL\n\nThe provider listed in AI_PROVIDER is tried first. If it fails (timeout, rate limit, error), the system automatically tries the next provider in the chain. This makes AI rule translation resilient to individual provider outages.\n\nCurrent provider status is visible in Settings > AI Engine Status. API keys are never sent to the browser — all AI calls happen server-side only."
    },
    {
        title: "27. Environment Variables Reference",
        category: "Technical Reference",
        content: "Required environment variables (set in .env file):\n\nAPP_ENV — production or development\nPORT — HTTP port (default 8000)\nJWT_SECRET — Secret key for session security (use a strong random string)\n\nSupabase (Production):\nSUPABASE_URL — Your Supabase project URL\nSUPABASE_KEY — Supabase publishable/anon key\nSUPABASE_SERVICE_ROLE_KEY — Service-role key (backend only, never sent to browser)\nDATABASE_URL — PostgreSQL connection URL\n\nLocal Development:\nLOCAL_MODE=true — Use SQLite instead of Supabase\nDATABASE_PATH — Path to SQLite file (default: database/timetable.db)\n\nAI Providers:\nOPENROUTER_API_KEY, OPENROUTER_MODEL\nGROQ_API_KEY, GROQ_MODEL\nCEREBRAS_API_KEY, CEREBRAS_MODEL\nGEMINI_API_KEY, GEMINI_MODEL\nAI_PROVIDER — Primary provider name\n\nLogging:\nLOG_LEVEL — DEBUG / INFO / WARNING / ERROR"
    },

    // ─── TROUBLESHOOTING ──────────────────────────────────────────────────────
    {
        title: "28. Troubleshooting — Common Errors",
        category: "Troubleshooting",
        content: "Error: 'Duplicate ID' when creating entities\n→ UniSched is case-insensitive for IDs. 'CSE' and 'cse' are the same. Choose a different ID.\n\nError: 'Faculty not found' in rules\n→ The faculty_id in the rule JSON does not exist in the database. Check the exact ID.\n\nError: 'No timetable generated yet'\n→ Run Generate Timetable first. The timetable view requires at least one successful generation.\n\nError: 'Access denied' on API call\n→ Your session has no permission for this data. Logout and login again with the correct account.\n\nError: 'AI rule translation failed'\n→ All AI providers are offline or rate-limited. Check your API keys in .env and try again later.\n\nError: Server returns 500 with request_id\n→ An internal error occurred. Note the request_id and check the server logs at logs/timetable_app.log."
    },
    {
        title: "29. Troubleshooting — Scheduler Issues",
        category: "Troubleshooting",
        content: "Solver produces Hard Score < 100%:\n→ Check that all sections have assigned courses, all courses have assigned faculty, and all sections have an assigned classroom.\n→ Check that room capacity ≥ section strength for all sections.\n→ Disable or relax overly restrictive HARD rules.\n→ Add more rooms or labs if resources are genuinely insufficient.\n→ Run the Repair Engine to fix remaining conflicts automatically.\n\nGeneration completes instantly with 0 sessions:\n→ The selected department has no sections, or sections have no courses linked.\n\nGeneration hangs indefinitely:\n→ If the progress stream stops, the solver may be stuck in a constraint deadlock. Refresh the page and try with fewer hard rules.\n\nDuplicate run ID error:\n→ A previous generation is still running or crashed mid-way. Wait 30 seconds and try again."
    },
    {
        title: "30. Troubleshooting — Login Issues",
        category: "Troubleshooting",
        content: "Cannot login — 'Invalid credentials':\n→ Double-check the username (case-sensitive: use lowercase like hod_cse, not HOD_CSE).\n→ If you changed the password and forgot it, ask the System Admin to reset it.\n→ Default passwords follow the pattern: {department_id_lowercase}password (e.g. csepassword for hod_cse).\n\nForgot Admin password:\n→ There is no self-service reset for Admin. Access the server directly and run:\n   python -c \"from werkzeug.security import generate_password_hash; print(generate_password_hash('newpassword'))\"\n   Then update the users table directly in the database.\n\nLogged out immediately after login:\n→ The server may have restarted, invalidating all sessions. This is expected — login again.\n\nLogin button does nothing:\n→ Check that the backend server is running (python -m app.api.app). Check browser console for errors."
    },

    // ─── DATA INTEGRITY ───────────────────────────────────────────────────────
    {
        title: "31. Data Integrity & Best Practices",
        category: "Best Practices",
        content: "Before generating timetables, verify:\n\n✓ Every section has at least one course assigned.\n✓ Every course has at least one faculty assigned.\n✓ Every section has an assigned classroom.\n✓ Classroom capacity ≥ section strength for all sections.\n✓ Lab-required courses have a required lab specified.\n✓ Faculty status is ACTIVE for all intended teaching staff.\n✓ No circular dependency in rules (e.g. two HARD rules that contradict each other).\n\nBest Practices:\n• Use meaningful IDs: 'F001', 'CS301', 'CSE-A' rather than generic names.\n• Set course colors so the timetable grid is visually distinct and easy to read.\n• Add SOFT rules for faculty preferences before HARD rules — HARD rules are absolute.\n• Always verify constraints after generation before exporting to stakeholders.\n• Export both Excel and PDF for distribution — PDF for notice boards, Excel for further processing."
    },
    {
        title: "32. Keyboard Shortcuts & Navigation Tips",
        category: "Best Practices",
        content: "Navigation:\n• Click any sidebar item to navigate.\n• Press Escape to close any open modal/dialog.\n• Click outside a modal to close it.\n\nSearch:\n• Help page: Use the search bar to filter help topics by keyword.\n• CRUD tables: Use the column filter dropdowns at the top of data tables.\n\nExport shortcuts:\n• From any timetable view: Click Print/PDF, Excel, or CSV buttons.\n• PDF export: Browser print dialog opens — choose 'Save as PDF' as the printer.\n\nPerformance:\n• First load after login may be slightly slower as the system warms the data cache.\n• Subsequent navigation is instant due to the TTL cache.\n• Click the Refresh button (circular arrow) in the header to force-reload from the database.\n\nSidebar:\n• Click the ← collapse button to hide the sidebar for more screen space.\n• Click → to expand it again."
    },
    {
        title: "33. Security & Access Control Summary",
        category: "Technical Reference",
        content: "UniSched enforces security at multiple layers:\n\nAuthentication:\n• Login required on every session — no persistent auto-login.\n• Session tokens are UUID-based, generated at login, and cleared on logout or server restart.\n• Passwords are bcrypt-hashed in the database — never stored in plaintext.\n\nAuthorization (server-enforced):\n• HOD users can ONLY read/write data belonging to their own department — enforced server-side.\n• HOD cannot generate timetables for other departments — department_id is locked to session.\n• HOD cannot export other departments' timetables — export endpoint verifies ownership.\n• Password reset requires authentication — unauthenticated resets are rejected.\n\nData exposure:\n• AI provider API keys are NEVER sent to the browser.\n• Supabase service-role key is NEVER sent to the browser.\n• Error messages in production are generic — technical details go only to server logs.\n• File exports use secure fetch with Authorization header — token is not exposed in URLs."
    },
    {
        title: "34. Supabase RLS (Row-Level Security)",
        category: "Technical Reference",
        content: "UniSched includes a Supabase RLS policy file: SUPABASE_RLS_POLICIES.sql\n\nFor production deployment, apply this file to your Supabase project:\n1. Open your Supabase project dashboard.\n2. Go to SQL Editor.\n3. Paste and run the contents of SUPABASE_RLS_POLICIES.sql.\n\nThis enables Row-Level Security on all tables, ensuring:\n• Anonymous/unauthenticated requests cannot read any data.\n• Only the backend service-role key has full access.\n• The publishable (anon) key is restricted to the minimum necessary operations.\n\nNote: RLS must be applied before going live. Without it, anyone with your SUPABASE_URL and SUPABASE_KEY could read all data directly."
    },
    {
        title: "35. Frequently Asked Questions",
        category: "Troubleshooting",
        content: "Q: Can I have the same faculty in multiple departments?\nA: No. Each faculty member belongs to one department. Use 'Visiting' professor type for cross-department faculty and assign them to courses manually.\n\nQ: Can a room be shared between departments?\nA: Yes. Leave 'Department Allocation' blank to make a room globally available, or assign it to a specific department.\n\nQ: What is the maximum timetable grid size?\nA: Default: 5 days × 8 periods (40 slots). This is configurable in the academic year settings.\n\nQ: Can I run multiple simultaneous timetable generations?\nA: No. Only one generation per department at a time is allowed. Concurrent requests return a conflict message.\n\nQ: How do I undo a generated timetable?\nA: Generate a new timetable — it overwrites the previous one for that department. There is no soft-undo.\n\nQ: Is the timetable stored in the cloud?\nA: Yes, in production mode (Supabase). In local mode (SQLite), it's stored in database/timetable.db.\n\nQ: How do I add a new semester?\nA: Update the Academic Year settings in the database (currently backend-only configuration)."
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
    let stats = getCache("stats");
    if (!stats) {
        stats = await requestAPI("/api/dashboard/stats");
        if (stats) {
            setCache("stats", stats);
        }
    }

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
                valSpan.style.fontWeight = "700";
            } else if (statusVal === "N/A" || !statusVal || statusVal.includes("NOT VALIDATED") || statusVal.includes("PENDING")) {
                valSpan.innerText = "N/A";
                valSpan.style.color = "var(--text-muted)";
                valSpan.style.fontWeight = "500";
            } else {
                valSpan.innerText = "ERROR";
                valSpan.style.color = "var(--color-danger)";
                valSpan.style.fontWeight = "700";
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
    invalidateCache("stats");
    invalidateCache("hod_sections_status");
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
    // Always require login — clear any leftover auth tokens from previous sessions
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_role");
    state.token = null;
    state.role = null;

    // Bind modal backdrop click close
    document.querySelectorAll(".modal").forEach(modal => {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                closeModal(modal.id);
            }
        });
    });

    // Apply layout configuration settings (UI prefs persist across sessions)
    applySidebarState();
    applyUserThemeSetting(state.theme);
    applyThemeMode(state.themeMode || "light");
    toggleCompactModeSetting(state.compactMode);

    // Always start at landing/login page
    navigateTo("landing");
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
