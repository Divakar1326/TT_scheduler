import psycopg2

regions = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "ap-south-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-central-1",
    "sa-east-1",
    "ca-central-1",
    "eu-north-1",
    "me-central-1"
]

pwd = "DIVAKAR1326"

for region in regions:
    host = f"aws-0-{region}.pooler.supabase.com"
    dsn = f"postgresql://postgres.nzwqjlechhsjgbptxyzl:{pwd}@{host}:6543/postgres"
    print(f"Testing region: {region} ({host}) ...")
    try:
        conn = psycopg2.connect(dsn, connect_timeout=4)
        print(f"SUCCESS CONNECTED in region: {region}!")
        conn.close()
        break
    except Exception as e:
        err_msg = str(e)
        if "password authentication failed" in err_msg or "Authentication failed" in err_msg:
            print(f"FOUND TENANT in region: {region} (but password failed)")
        elif "not found" in err_msg:
            # tenant not found
            pass
        else:
            print(f"Other error in {region}: {err_msg}")
