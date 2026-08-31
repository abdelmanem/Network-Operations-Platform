#!/usr/bin/env python3
import os
import sys
from sqlalchemy import create_engine, text

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

db_url = os.getenv("DATABASE_URL", "postgresql://nop_user:nop_password@localhost:5432/nop_dev")

engine = create_engine(db_url)

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, name, transport_types, credential_type, provider_reference FROM credential_profiles ORDER BY created_at DESC LIMIT 5"))
    rows = result.fetchall()
    
    if rows:
        print("Recent credential profiles in database:")
        for row in rows:
            print(f"  ID: {row[0]}")
            print(f"  Name: {row[1]}")
            print(f"  Transport Types: {row[2]}")
            print(f"  Credential Type: {row[3]}")
            print(f"  Provider Ref: {row[4]}")
            print()
    else:
        print("No credential profiles found")
