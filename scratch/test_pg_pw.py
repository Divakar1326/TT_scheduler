import psycopg2

passwords = ["DIVAKAR1326", "[DIVAKAR1326]"]
host = "aws-0-ap-south-1.pooler.supabase.com"
port = 6543

for pwd in passwords:
    dsn = f"postgresql://postgres.nzwqjlechhsjgbptxyzl:{pwd}@{host}:{port}/postgres"
    print(f"Testing DSN: {dsn.replace(pwd, '***')}")
    try:
        conn = psycopg2.connect(dsn, connect_timeout=5)
        print(f"SUCCESS with port {port}! password: {pwd}")
        conn.close()
        break
    except Exception as e:
        print(f"Failed: {e}")
