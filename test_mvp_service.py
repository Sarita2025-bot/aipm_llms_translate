"""
MVP Translation Service Test Script
Tests the complete file translation workflow
"""

import requests
import time
import os
from pathlib import Path

def test_mvp_service():
    """Test the MVP translation service"""
    print("🧪 Testing MVP File Translation Service")
    print("=" * 60)
    
    # Service URL
    base_url = "http://localhost:8001"
    
    # Test file
    test_file = "sample_document.txt"
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        return
    
    print(f"📁 Test file: {test_file}")
    print()
    
    # 1. Health check
    print("1️⃣ Health Check")
    print("-" * 40)
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            health = response.json()
            print("✅ Service is healthy")
            print(f"   Components: {health['components']}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to service: {e}")
        print("   Make sure to run: python mvp_translation_service.py")
        return
    
    print()
    
    # 2. Upload file
    print("2️⃣ File Upload")
    print("-" * 40)
    try:
        with open(test_file, 'rb') as f:
            files = {'file': (test_file, f, 'text/plain')}
            response = requests.post(f"{base_url}/upload", files=files)
        
        if response.status_code == 200:
            job = response.json()
            job_id = job['job_id']
            print(f"✅ File uploaded successfully")
            print(f"   Job ID: {job_id}")
            print(f"   Status: {job['status']}")
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return
    except Exception as e:
        print(f"❌ Upload error: {e}")
        return
    
    print()
    
    # 3. Monitor job progress
    print("3️⃣ Job Processing")
    print("-" * 40)
    max_wait = 60  # Maximum wait time in seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{base_url}/jobs/{job_id}")
            if response.status_code == 200:
                job = response.json()
                print(f"   Status: {job['status']}")
                print(f"   Progress: {job['segments_processed']}/{job['total_segments']}")
                
                if job['status'] == 'completed':
                    print("✅ Job completed successfully!")
                    print(f"   Translated file: {job['translated_file']}")
                    print(f"   QA report: {job['qa_report']}")
                    break
                elif job['status'] == 'failed':
                    print(f"❌ Job failed: {job.get('error_message', 'Unknown error')}")
                    return
            else:
                print(f"❌ Job status check failed: {response.status_code}")
                return
                
        except Exception as e:
            print(f"❌ Job monitoring error: {e}")
            return
        
        time.sleep(2)  # Wait 2 seconds before next check
    
    else:
        print("⏰ Job processing timeout")
        return
    
    print()
    
    # 4. Check generated files
    print("4️⃣ Generated Files")
    print("-" * 40)
    
    uploads_dir = Path("uploads")
    if uploads_dir.exists():
        files = list(uploads_dir.glob("*"))
        print(f"✅ Found {len(files)} files in uploads directory:")
        for file in files:
            print(f"   - {file.name} ({file.stat().st_size} bytes)")
    else:
        print("❌ Uploads directory not found")
    
    print()
    print("=" * 60)
    print("✅ MVP SERVICE TEST COMPLETE")
    print("=" * 60)
    
    print()
    print("📋 Next Steps:")
    print("1. Check the uploads/ directory for generated files")
    print("2. Review the QA report CSV for translation metrics")
    print("3. Test with different file formats (DOCX, XLSX)")
    print("4. Integrate with actual LLM for real translations")

if __name__ == "__main__":
    test_mvp_service()
