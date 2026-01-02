# Fix Google Cloud Vision API Access

## Current Issue
**Error:** `access_denied: Account restricted`

The Vision API is failing because of authentication/authorization issues.

## Root Cause
1. **Missing Service Account Key File**: The required JSON credentials file `gcp-creds.json` is not found
2. **Account Restrictions**: Your Google Cloud account may have restrictions or billing issues

## Solution Steps

### Step 1: Check Your Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project: `contract-extractor-479305`
3. Check if Vision API is enabled:
   - Go to **APIs & Services** > **Enabled APIs & services**
   - Search for "Cloud Vision API"
   - If not enabled, click **+ ENABLE APIS AND SERVICES** and enable it

### Step 2: Check Billing

1. Go to **Billing** in Google Cloud Console
2. Ensure you have:
   - ✅ Active billing account
   - ✅ Valid payment method
   - ✅ No billing alerts or issues
3. Vision API requires billing enabled (has free tier: 1000 units/month)

### Step 3: Create/Download Service Account Key

1. Go to **IAM & Admin** > **Service Accounts**
2. Find or create a service account with these roles:
   - `Cloud Vision API User`
   - `Storage Object Admin` (for GCS access)
3. Click on the service account
4. Go to **Keys** tab
5. Click **Add Key** > **Create new key**
6. Choose **JSON** format
7. Download the JSON file
8. **Rename it to:** `gcp-creds.json`
9. **Place it in:** `c:\Users\Admin\Account_payable\`

### Step 4: Enable Vision API with the Updated Configuration

Once you have the JSON file, update the code to use Vision API:

```python
# In test_invoice_extraction.py, change:
agent = ExtractionAgent(api_key=api_key, use_gcs_vision=False)

# To:
agent = ExtractionAgent(api_key=api_key, use_gcs_vision=True)
```

```python
# In app.py, change both occurrences from:
use_gcs_vision=False

# To:
use_gcs_vision=True
```

### Step 5: Test Vision API

Run this test to verify Vision API is working:

```bash
python -c "from google.cloud import vision; from google.oauth2 import service_account; creds = service_account.Credentials.from_service_account_file('gcp-creds.json'); client = vision.ImageAnnotatorClient(credentials=creds); print('✓ Vision API working!')"
```

## Quick Alternative: Use Environment Variable

Instead of hardcoding the path, set an environment variable:

```bash
# Windows PowerShell
$env:GOOGLE_APPLICATION_CREDENTIALS="c:\Users\Admin\Account_payable\gcp-creds.json"

# Or add to system environment variables permanently
```

## Verify It's Working

Once fixed, the construction invoices should extract properly:

```bash
python test_invoice_extraction.py
```

You should see:
- ✅ Document Type: INVOICE (Confidence: HIGH)
- ✅ Invoice ID: [extracted]
- ✅ Vendor: [extracted]
- ✅ Amount: [extracted]

## Troubleshooting

### Error: "Account restricted"
- Check if your Google Cloud account is suspended
- Verify billing is active
- Check if you've exceeded free tier limits

### Error: "Permission denied"
- Ensure service account has `Cloud Vision API User` role
- Ensure service account has `Storage Object Admin` role (for GCS buckets)

### Error: "Bucket not found"
- Check if the GCS bucket `data-pdf-extractor` exists
- Create it if missing:
  1. Go to Cloud Storage in Google Cloud Console
  2. Create bucket named `data-pdf-extractor`
  3. Set location and storage class
  4. Grant service account access

## Cost Information

**Google Cloud Vision API Pricing:**
- First 1,000 units/month: **FREE**
- 1,001 - 5,000,000 units: $1.50 per 1,000 units
- Each page = 1 unit

For 22 invoices, you'll use only 22 units (well within free tier).

## Need Help?

Contact your Google Cloud administrator or check:
- [Vision API Documentation](https://cloud.google.com/vision/docs)
- [Service Account Setup](https://cloud.google.com/iam/docs/creating-managing-service-accounts)

