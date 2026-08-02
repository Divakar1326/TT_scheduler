"""Unit tests for connection manager and repository layer."""
import os
import unittest
import sqlite3
from app.repository.connection import DatabaseConnectionManager, TransactionContext
from app.repository.entity_repositories import DepartmentRepository, FacultyRepository

class TestRepositoryLayer(unittest.TestCase):
    
    def setUp(self):
        self.db_path = "test_timetable.db"
        # If database exists, delete it first
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            
        # Initialize schema
        conn = sqlite3.connect(self.db_path)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        schema_path = os.path.join(base_dir, "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()
        conn.close()

        # Initialize repositories with test database path
        self.dept_repo = DepartmentRepository(db_path=self.db_path)
        self.faculty_repo = FacultyRepository(db_path=self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except OSError:
                pass

    def test_generic_crud_operations(self):
        # 1. Insert
        self.dept_repo.insert_dept("CS", "Computer Science")
        dept = self.dept_repo.find_by_id("CS")
        self.assertIsNotNone(dept)
        self.assertEqual(dept["department_name"], "Computer Science")

        # 2. Update
        updated = self.dept_repo.update("department", {"department_id": "CS"}, {"department_name": "Computing"})
        self.assertEqual(updated, 1)
        dept = self.dept_repo.find_by_id("CS")
        self.assertEqual(dept["department_name"], "Computing")

        # 3. Find All
        all_depts = self.dept_repo.find_all("department")
        self.assertEqual(len(all_depts), 1)

        # 4. Delete
        deleted = self.dept_repo.delete("department", {"department_id": "CS"})
        self.assertEqual(deleted, 1)
        dept = self.dept_repo.find_by_id("CS")
        self.assertIsNone(dept)

    def test_transaction_commit(self):
        with TransactionContext(db_path=self.db_path):
            self.dept_repo.insert_dept("MATH", "Mathematics")
            self.faculty_repo.insert_faculty("F_MATH1", "Dr. Gauss", 20, "gauss@math.org")
            
        # Verify both inserted records are committed and visible
        dept = self.dept_repo.find_by_id("MATH")
        faculty = self.faculty_repo.find_by_id("F_MATH1")
        self.assertIsNotNone(dept)
        self.assertIsNotNone(faculty)

    def test_transaction_rollback_on_error(self):
        try:
            with TransactionContext(db_path=self.db_path):
                self.dept_repo.insert_dept("PHY", "Physics")
                # Intentionally cause an error (foreign key violation or database constraint)
                # By inserting duplicate primary key or raising manual error
                raise ValueError("Simulated transaction exception")
        except ValueError:
            pass

        # Verify that "PHY" department was rolled back and is not in the DB
        dept = self.dept_repo.find_by_id("PHY")
        self.assertIsNone(dept)
        
    def test_connection_sharing_in_transaction(self):
        with TransactionContext(db_path=self.db_path):
            conn1, should_close1 = DatabaseConnectionManager.get_connection(self.db_path)
            conn2, should_close2 = DatabaseConnectionManager.get_connection(self.db_path)
            # The connections returned within the same transaction must be the same instance
            self.assertIs(conn1, conn2)
            self.assertFalse(should_close1)
            self.assertFalse(should_close2)
            
        # Outside transaction, connection should be new
        conn3, should_close3 = DatabaseConnectionManager.get_connection(self.db_path)
        self.assertTrue(should_close3)
        conn3.close()


if __name__ == "__main__":
    unittest.main()
