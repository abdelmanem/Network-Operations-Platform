#!/usr/bin/env python3
"""
Clean up credential profiles with missing or empty transport_types.
"""
import os
from backend.app.persistence.discovery_repositories import CredentialProfileRepository
from backend.app.persistence import get_session

# Get database session
Session = get_session()
session = Session()

try:
    repo = CredentialProfileRepository(session)
    # Get all profiles
    profiles = session.query(repo.model).all()
    
    print("Checking credential profiles:")
    for profile in profiles:
        print(f"  - {profile.name}")
        print(f"    ID: {profile.id}")
        print(f"    Transport Types: {profile.transport_types}")
        print(f"    Credential Type: {profile.credential_type}")
        print()
finally:
    session.close()
