"""
Test script to verify Google Cloud Vision API connectivity and functionality.
Run: python test_vision_api.py
"""

import os
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_credentials():
    """Test if GCP credentials are properly configured."""
    print("\n" + "="*60)
    print("TEST 1: Checking GCP Credentials")
    print("="*60)
    
    # Check for credentials JSON in environment
    gcp_creds = os.getenv("GCP_CREDENTIALS_JSON")
    gcp_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if gcp_creds:
        print("✅ GCP_CREDENTIALS_JSON found in environment")
        try:
            creds_data = json.loads(gcp_creds)
            print(f"   Project ID: {creds_data.get('project_id', 'N/A')}")
            print(f"   Client Email: {creds_data.get('client_email', 'N/A')[:50]}...")
            return True
        except json.JSONDecodeError:
            print("❌ GCP_CREDENTIALS_JSON is not valid JSON")
            return False
    elif gcp_file and os.path.exists(gcp_file):
        print(f"✅ GOOGLE_APPLICATION_CREDENTIALS file found: {gcp_file}")
        return True
    else:
        print("❌ No GCP credentials found!")
        print("   Set either GCP_CREDENTIALS_JSON or GOOGLE_APPLICATION_CREDENTIALS")
        return False


def test_vision_client():
    """Test if Vision API client can be created."""
    print("\n" + "="*60)
    print("TEST 2: Creating Vision API Client")
    print("="*60)
    
    try:
        from google.cloud import vision
        from google.oauth2 import service_account
        
        # Try to create credentials
        gcp_creds = os.getenv("GCP_CREDENTIALS_JSON")
        if gcp_creds:
            creds_data = json.loads(gcp_creds)
            credentials = service_account.Credentials.from_service_account_info(creds_data)
            client = vision.ImageAnnotatorClient(credentials=credentials)
        else:
            client = vision.ImageAnnotatorClient()
        
        print("✅ Vision API client created successfully")
        return client
    except ImportError:
        print("❌ google-cloud-vision package not installed")
        print("   Run: pip install google-cloud-vision")
        return None
    except Exception as e:
        print(f"❌ Failed to create Vision client: {e}")
        return None


def test_storage_client():
    """Test if Storage client can be created."""
    print("\n" + "="*60)
    print("TEST 3: Creating Storage Client")
    print("="*60)
    
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        
        gcp_creds = os.getenv("GCP_CREDENTIALS_JSON")
        if gcp_creds:
            creds_data = json.loads(gcp_creds)
            credentials = service_account.Credentials.from_service_account_info(creds_data)
            client = storage.Client(credentials=credentials, project=creds_data.get('project_id'))
        else:
            client = storage.Client()
        
        print("✅ Storage client created successfully")
        return client
    except ImportError:
        print("❌ google-cloud-storage package not installed")
        print("   Run: pip install google-cloud-storage")
        return None
    except Exception as e:
        print(f"❌ Failed to create Storage client: {e}")
        return None


def test_bucket_access(storage_client):
    """Test if we can access the GCS bucket."""
    print("\n" + "="*60)
    print("TEST 4: Testing GCS Bucket Access")
    print("="*60)
    
    bucket_name = "data-pdf-extractor"
    
    try:
        bucket = storage_client.bucket(bucket_name)
        # Try to check if bucket exists by listing a few blobs
        blobs = list(bucket.list_blobs(max_results=3))
        print(f"✅ Successfully accessed bucket: gs://{bucket_name}")
        print(f"   Found {len(blobs)} objects (showing max 3)")
        for blob in blobs:
            print(f"   - {blob.name}")
        return True
    except Exception as e:
        print(f"❌ Failed to access bucket '{bucket_name}': {e}")
        return False


def test_vision_simple_request(vision_client):
    """Test a simple Vision API request with a public image."""
    print("\n" + "="*60)
    print("TEST 5: Testing Vision API with Simple Request")
    print("="*60)
    
    try:
        from google.cloud import vision
        
        # Use a simple test - detect labels on a public image
        image = vision.Image()
        image.source.image_uri = "gs://cloud-samples-data/vision/label/wakeupcat.jpg"
        
        print("   Sending request to Vision API...")
        response = vision_client.label_detection(image=image, max_results=5)
        
        if response.error.message:
            print(f"❌ Vision API returned error: {response.error.message}")
            return False
        
        labels = response.label_annotations
        print(f"✅ Vision API responded successfully!")
        print(f"   Detected {len(labels)} labels in test image:")
        for label in labels[:5]:
            print(f"   - {label.description} (confidence: {label.score:.2%})")
        return True
        
    except Exception as e:
        print(f"❌ Vision API request failed: {e}")
        return False


def test_async_batch_capability(vision_client):
    """Test if async batch annotation is available (used for PDF OCR)."""
    print("\n" + "="*60)
    print("TEST 6: Testing Async Batch Annotation Capability")
    print("="*60)
    
    try:
        # Just check if the method exists and is callable
        if hasattr(vision_client, 'async_batch_annotate_files'):
            print("✅ async_batch_annotate_files method is available")
            print("   This is used for PDF/multi-page document OCR")
            return True
        else:
            print("❌ async_batch_annotate_files method not found")
            return False
    except Exception as e:
        print(f"❌ Error checking async capability: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("GOOGLE CLOUD VISION API TEST")
    print("="*60)
    
    results = {}
    
    # Test 1: Credentials
    results['credentials'] = test_credentials()
    if not results['credentials']:
        print("\n⚠️  Cannot proceed without valid credentials")
        sys.exit(1)
    
    # Test 2: Vision Client
    vision_client = test_vision_client()
    results['vision_client'] = vision_client is not None
    
    # Test 3: Storage Client
    storage_client = test_storage_client()
    results['storage_client'] = storage_client is not None
    
    # Test 4: Bucket Access
    if storage_client:
        results['bucket_access'] = test_bucket_access(storage_client)
    else:
        results['bucket_access'] = False
        print("\n⚠️  Skipping bucket test - no storage client")
    
    # Test 5: Vision API Request
    if vision_client:
        results['vision_request'] = test_vision_simple_request(vision_client)
    else:
        results['vision_request'] = False
        print("\n⚠️  Skipping Vision request test - no vision client")
    
    # Test 6: Async Batch Capability
    if vision_client:
        results['async_batch'] = test_async_batch_capability(vision_client)
    else:
        results['async_batch'] = False
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Vision API is working correctly!")
    else:
        print("⚠️  SOME TESTS FAILED - Check the errors above")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
