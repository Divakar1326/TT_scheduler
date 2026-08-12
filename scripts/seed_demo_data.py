"""Seeding script to populate local SQLite database with realistic university dataset."""
from scripts.seed_supabase import seed_data

def main():
    seed_data()

if __name__ == "__main__":
    main()
