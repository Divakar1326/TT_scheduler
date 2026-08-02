# Failed Tests Detail

## ❌ test_list_endpoints_return_json_array
- **Node:** `tests/test_api.py::TestAPIResponseFormats::test_list_endpoints_return_json_array`
- **Error:** `/api/faculties returned 500
assert 500 == 200
 +  where 500 = <Response [500]>.status_code`

## ❌ test_concurrent_read_requests
- **Node:** `tests/test_api.py::TestAPIPerformance::test_concurrent_read_requests`
- **Error:** `Some concurrent requests failed: [500, 500, 500, 500, 500]
assert False
 +  where False = all(<generator object TestAPIPerformance.test_concurrent_read_requests.<locals>.<genexpr> at 0x00000177BEF8F9F0>)`

## ❌ test_admin_dashboard_stats_load_non_zero
- **Node:** `tests/test_dashboard.py::TestAdminDashboard::test_admin_dashboard_stats_load_non_zero`
- **Error:** `Faculty count should be non-zero
assert '0' != '0'
 +  where '0' = <built-in method strip of str object at 0x00007FFD832847A8>()
 +    where <built-in method strip of str object at 0x00007FFD832847A8> = '0'.strip`

## ❌ test_api_dashboard_stats_endpoint
- **Node:** `tests/test_dashboard.py::TestAdminDashboard::test_api_dashboard_stats_endpoint`
- **Error:** `Dashboard stats Expected 200/201, got 500: {"error":"int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"}
`

## ❌ test_api_dashboard_stats_counts_positive
- **Node:** `tests/test_dashboard.py::TestAdminDashboard::test_api_dashboard_stats_counts_positive`
- **Error:** `faculty_count should be non-negative
assert -1 >= 0
 +  where -1 = <built-in method get of dict object at 0x00000177C227D4C0>('faculty_count', -1)
 +    where <built-in method get of dict object at 0x00000177C227D4C0> = {'error': "int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"}.get`

## ❌ test_crud_manager_visible
- **Node:** `tests/test_departments.py::TestDepartmentUI::test_crud_manager_visible`
- **Error:** `UI navigation failed, skipping test: Locator expected to be visible
Actual value: hidden 
Call log:
  - Expect "to_be_visible" with timeout 5000ms
  - waiting for locator("#crud-table-body, table, .table-container").first
    14 × locator resolved to <div class="table-container">…</div>
       - unexpected value "hidden"

Aria snapshot:
- banner:
  - heading "University Timetable Automation System" [level=1]
  - button "Dashboard"
  - button "CRUD Entities"
  - button "Timetable Grid"
  - button "Rules Builder"
  - button "Logout"
- complementary:
  - heading "Entities" [level=2]
  - list:
    - listitem:
      - button "Departments"
    - listitem:
      - button "Faculty"
    - listitem:
      - button "Courses"
    - listitem:
      - button "Sections"
    - listitem:
      - button "Rooms"
    - listitem:
      - button "Laboratories"
    - listitem:
      - button "Rules"
- main:
  - heading "Manage departments" [level=2]
  - button "Add New Record"
  - table:
    - rowgroup:
      - row "DEPARTMENT ID DEPARTMENT NAME HOD NAME EMAIL PHONE ACTIONS":
        - columnheader "DEPARTMENT ID"
        - columnheader "DEPARTMENT NAME"
        - columnheader "HOD NAME"
        - columnheader "EMAIL"
        - columnheader "PHONE"
        - columnheader "ACTIONS"
    - rowgroup:
      - row "ISC Intelligent Systems and Cybersecurity Edit Delete":
        - cell "ISC"
        - cell "Intelligent Systems and Cybersecurity"
        - cell
        - cell
        - cell
        - cell "Edit Delete":
          - button "Edit"
          - button "Delete"
      - row "QAD QA Test Department Edit Delete":
        - cell "QAD"
        - cell "QA Test Department"
        - cell
        - cell
        - cell
        - cell "Edit Delete":
          - button "Edit"
          - button "Delete"`

## ❌ test_list_faculties
- **Node:** `tests/test_faculty.py::TestFacultyAPI::test_list_faculties`
- **Error:** `List faculties Expected 200/201, got 500: {"error":"int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"}
`

## ❌ test_faculty_list_has_expected_fields
- **Node:** `tests/test_faculty.py::TestFacultyAPI::test_faculty_list_has_expected_fields`
- **Error:** `0`

## ❌ test_hod_can_read_faculty
- **Node:** `tests/test_faculty.py::TestFacultyAPI::test_hod_can_read_faculty`
- **Error:** `HOD read faculty Expected 200/201, got 500: {"error":"int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"}
`

## ❌ test_faculty_list_search_by_department
- **Node:** `tests/test_faculty.py::TestFacultyAPI::test_faculty_list_search_by_department`
- **Error:** `slice(None, 5, None)`

## ❌ test_generate_returns_allocations
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_generate_returns_allocations`
- **Error:** `Generate schedule Expected 200/201, got 500: {"error":"int() argument must be a string, a bytes-like object or a real number, not 'NoneType'"}
`

## ❌ test_allocations_have_required_fields
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_allocations_have_required_fields`
- **Error:** `Generation failed; skipping field check`

## ❌ test_no_faculty_clashes
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_no_faculty_clashes`
- **Error:** `Generation failed`

## ❌ test_no_section_clashes
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_no_section_clashes`
- **Error:** `Generation failed`

## ❌ test_no_room_clashes
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_no_room_clashes`
- **Error:** `Generation failed`

## ❌ test_no_lab_clashes
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_no_lab_clashes`
- **Error:** `Generation failed`

## ❌ test_practical_sessions_are_consecutive
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_practical_sessions_are_consecutive`
- **Error:** `Generation failed`

## ❌ test_day_range_is_1_to_5
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_day_range_is_1_to_5`
- **Error:** `Generation failed`

## ❌ test_period_range_is_1_to_7
- **Node:** `tests/test_scheduler.py::TestSchedulerGeneration::test_period_range_is_1_to_7`
- **Error:** `Generation failed`

## ❌ test_timetable_grid_renders_after_generation
- **Node:** `tests/test_scheduler.py::TestSchedulerUI::test_timetable_grid_renders_after_generation`
- **Error:** `Timetable grid should have cells after generation
assert 0 > 0
 +  where 0 = len([])`

