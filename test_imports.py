"""
Test script to verify all imports work correctly.
Run this from your project root: python test_imports.py
"""

import sys
print("Testing imports...")

try:
    print("1. Importing database...")
    from app.database import Base, engine, init_db
    print("   ✓ Database imported")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

try:
    print("2. Importing models...")
    from app import models
    print("   ✓ Models imported")
    print(f"   Models found: {[name for name in dir(models) if not name.startswith('_')]}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

try:
    print("3. Checking Base.registry...")
    print(f"   Registered models: {[cls.__name__ for cls in Base.registry.mappers]}")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

try:
    print("4. Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("   ✓ Tables created")
except Exception as e:
    print(f"   ✗ Error: {e}")
    sys.exit(1)

print("\n✓ All imports successful!")