import psycopg2

passwords = ["DIVAKAR1326", "[DIVAKAR1326]"]

for pwd in passwords:
    dsn = f"postgresql://postgres:{pwd}@db.nzwqjlechhsjgbptxyzl.supabase.co:5432/postgres"
    print(f"Testing direct DSN: {dsn.replace(pwd, '***')}")
    try:
        conn = psycopg2.connect(dsn, connect_timeout=5)
        print(f"SUCCESS! Password is: {pwd}")
        conn.close()
        break
    except Exception as e:
        print(f"Failed: {e}")
