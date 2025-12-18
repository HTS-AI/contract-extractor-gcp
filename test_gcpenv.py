"""
SECURITY-SAFE TEST
------------------
✔ Checks if .env loads correctly
✔ Verifies GCP_CREDENTIALS_JSON is set
✔ Does NOT read or print secret value
✔ Does NOT call GCP
"""

import os
from dotenv import load_dotenv

print("=" * 80)
print("Testing .env access for GCP_CREDENTIALS_JSON (SAFE CHECK)")
print("=" * 80)

# Load .env
load_dotenv()

# Check presence ONLY
env_var_name = "GCP_CREDENTIALS_JSON"

if env_var_name in os.environ:
    print(f"✅ Environment variable '{env_var_name}' is accessible")
    print("🔐 Value is NOT read or printed (secret-safe)")
else:
    print(f"❌ Environment variable '{env_var_name}' is NOT set")

print("=" * 80)
print("Test completed")
print("=" * 80)
