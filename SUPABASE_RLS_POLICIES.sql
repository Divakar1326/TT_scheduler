-- ====================================================================
-- SUPABASE ROW LEVEL SECURITY (RLS) & ACCESS CONTROL POLICIES
-- ====================================================================

-- 1. Enable RLS on all core tables
ALTER TABLE department ENABLE ROW LEVEL SECURITY;
ALTER TABLE faculty ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE labs ENABLE ROW LEVEL SECURITY;
ALTER TABLE rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_teacher ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduler_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedule ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Helper function to check if the current user is a Super Admin
CREATE OR REPLACE FUNCTION is_super_admin()
RETURNS BOOLEAN AS $$
BEGIN
  -- Resolves to true if user is logged in and role is SUPER_ADMIN
  RETURN EXISTS (
    SELECT 1 FROM users
    WHERE username = current_setting('request.jwt.claim.sub', true)
      AND role = 'SUPER_ADMIN'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Helper function to get the current user's department ID
CREATE OR REPLACE FUNCTION get_user_department()
RETURNS TEXT AS $$
DECLARE
  dept_id TEXT;
BEGIN
  SELECT department_id INTO dept_id
  FROM users
  WHERE username = current_setting('request.jwt.claim.sub', true);
  RETURN dept_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- ====================================================================
-- POLICY DEFINITIONS
-- ====================================================================

----------------------------------------------------------------------
-- DEPARTMENT TABLE POLICIES
----------------------------------------------------------------------
-- Anonymous: Read Only
CREATE POLICY anon_select_department ON department
  FOR SELECT TO anon USING (is_deleted = 0);

-- Admin: Full Access
CREATE POLICY admin_all_department ON department
  FOR ALL TO authenticated USING (is_super_admin()) WITH CHECK (is_super_admin());

-- HOD: Read/Write restricted to own department
CREATE POLICY hod_access_department ON department
  FOR ALL TO authenticated
  USING (LOWER(department_id) = LOWER(get_user_department()))
  WITH CHECK (LOWER(department_id) = LOWER(get_user_department()));


----------------------------------------------------------------------
-- FACULTY TABLE POLICIES
----------------------------------------------------------------------
-- Anonymous: Read Only
CREATE POLICY anon_select_faculty ON faculty
  FOR SELECT TO anon USING (is_deleted = 0);

-- Admin: Full Access
CREATE POLICY admin_all_faculty ON faculty
  FOR ALL TO authenticated USING (is_super_admin()) WITH CHECK (is_super_admin());

-- HOD: Read/Write restricted to own department
CREATE POLICY hod_access_faculty ON faculty
  FOR ALL TO authenticated
  USING (LOWER(department_id) = LOWER(get_user_department()))
  WITH CHECK (LOWER(department_id) = LOWER(get_user_department()));


----------------------------------------------------------------------
-- COURSES TABLE POLICIES
----------------------------------------------------------------------
-- Anonymous: Read Only
CREATE POLICY anon_select_courses ON courses
  FOR SELECT TO anon USING (is_deleted = 0);

-- Admin: Full Access
CREATE POLICY admin_all_courses ON courses
  FOR ALL TO authenticated USING (is_super_admin()) WITH CHECK (is_super_admin());

-- HOD: Read/Write restricted to own department
CREATE POLICY hod_access_courses ON courses
  FOR ALL TO authenticated
  USING (LOWER(department_id) = LOWER(get_user_department()))
  WITH CHECK (LOWER(department_id) = LOWER(get_user_department()));


----------------------------------------------------------------------
-- SECTIONS TABLE POLICIES
----------------------------------------------------------------------
-- Anonymous: Read Only
CREATE POLICY anon_select_sections ON sections
  FOR SELECT TO anon USING (is_deleted = 0);

-- Admin: Full Access
CREATE POLICY admin_all_sections ON sections
  FOR ALL TO authenticated USING (is_super_admin()) WITH CHECK (is_super_admin());

-- HOD: Read/Write restricted to own department
CREATE POLICY hod_access_sections ON sections
  FOR ALL TO authenticated
  USING (LOWER(department_id) = LOWER(get_user_department()))
  WITH CHECK (LOWER(department_id) = LOWER(get_user_department()));


----------------------------------------------------------------------
-- ROOMS & LABS POLICIES
----------------------------------------------------------------------
-- Anonymous: Read Only
CREATE POLICY anon_select_rooms ON rooms FOR SELECT TO anon USING (is_deleted = 0);
CREATE POLICY anon_select_labs ON labs FOR SELECT TO anon USING (is_deleted = 0);

-- Admin: Full Access
CREATE POLICY admin_all_rooms ON rooms FOR ALL TO authenticated USING (is_super_admin()) WITH CHECK (is_super_admin());
CREATE POLICY admin_all_labs ON labs FOR ALL TO authenticated USING (is_super_admin()) WITH CHECK (is_super_admin());

-- HOD: Read/Write restricted to own department
CREATE POLICY hod_access_rooms ON rooms FOR ALL TO authenticated
  USING (LOWER(department_id) = LOWER(get_user_department())) WITH CHECK (LOWER(department_id) = LOWER(get_user_department()));
CREATE POLICY hod_access_labs ON labs FOR ALL TO authenticated
  USING (LOWER(department_id) = LOWER(get_user_department())) WITH CHECK (LOWER(department_id) = LOWER(get_user_department()));


----------------------------------------------------------------------
-- SCHEDULE & RUNS POLICIES
----------------------------------------------------------------------
-- Anonymous: Read Only
CREATE POLICY anon_select_schedule ON schedule FOR SELECT TO anon USING (true);
CREATE POLICY anon_select_run ON scheduler_run FOR SELECT TO anon USING (true);

-- Admin: Full Access
CREATE POLICY admin_all_schedule ON schedule FOR ALL TO authenticated USING (is_super_admin()) WITH CHECK (is_super_admin());
CREATE POLICY admin_all_run ON scheduler_run FOR ALL TO authenticated USING (is_super_admin()) WITH CHECK (is_super_admin());

-- HOD: Read/Write/Delete restricted to own department
CREATE POLICY hod_access_schedule ON schedule FOR ALL TO authenticated
  USING (LOWER(department_id) = LOWER(get_user_department())) WITH CHECK (LOWER(department_id) = LOWER(get_user_department()));
CREATE POLICY hod_access_run ON scheduler_run FOR ALL TO authenticated
  USING (LOWER(department_id) = LOWER(get_user_department())) WITH CHECK (LOWER(department_id) = LOWER(get_user_department()));
