













"""
Test the FastAPI Translation Service
Simulates how MemoQ would call the API
"""

import requests
import json
import time

# Wait for service to start
print("⏳ Waiting for service to start...")
time.sleep(5)

# Service URL
BASE_URL = "http://localhost:8000"

print("🧪 Testing Finance RAG Translation API")
print("=" * 60)

# Test 1: Health check
print("\n1️⃣ Health Check")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        health = response.json()
        print(f"✅ Service is healthy")
        print(f"   Components:")
        for component, status in health['components'].items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {component}: {status}")
    else:
        print(f"❌ Health check failed: {response.status_code}")
except Exception as e:
    print(f"❌ Cannot connect to service: {e}")
    print("   Make sure the service is running: python app.py")
    exit(1)

# Test 2: Simple translation request
print("\n2️⃣ Translation Request (Fund Name Segment)")
print("-" * 60)

translation_request = {
    "source_text": "The Global Innovation Equity Fund returned 8.5% in the first quarter",
    "source_language": "en",
    "target_language": "es",
    "max_tm_results": 3,
    "max_tb_results": 5,
    "use_llm": True  # ← Set to True to use GPT-4o (requires OpenAI credits)
}

try:
    response = requests.post(
        f"{BASE_URL}/translate",
        json=translation_request,
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Translation successful")
        print(f"\n   Source: {result['source_text']}")
        print(f"   Target: {result['target_text']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Fund names detected: {result['has_fund_names']}")
        if result['fund_terms']:
            print(f"   Fund terms: {', '.join(result['fund_terms'][:3])}")
        print(f"   TM matches: {result['tm_matches']}")
        print(f"   TB matches: {result['tb_matches']}")
        print(f"   Processing time: {result['processing_time']:.3f}s")
    else:
        print(f"❌ Translation failed: {response.status_code}")
        print(f"   {response.text}")
        
except Exception as e:
    print(f"❌ Request failed: {e}")

# Test 3: Another segment (ECB example)
print("\n3️⃣ Translation Request (ECB Segment)")
print("-" * 60)

translation_request2 = {
    "source_text": "The European Central Bank announced new monetary policy measures",
    "source_language": "en",
    "target_language": "es",
    "use_llm": True  # ← Using GPT-4o
}

try:
    response = requests.post(
        f"{BASE_URL}/translate",
        json=translation_request2,
        timeout=30
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Translation successful")
        print(f"\n   Source: {result['source_text']}")
        print(f"   Target: {result['target_text']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   TM matches: {result['tm_matches']}")
        print(f"   Processing time: {result['processing_time']:.3f}s")
    else:
        print(f"❌ Translation failed: {response.status_code}")
        
except Exception as e:
    print(f"❌ Request failed: {e}")

# Test 4: Get stats
print("\n4️⃣ System Statistics")
print("-" * 60)
try:
    response = requests.get(f"{BASE_URL}/stats")
    if response.status_code == 200:
        stats = response.json()
        print(f"✅ Stats retrieved")
        print(f"   Total queries: {stats['rag_stats']['total_queries']}")
        print(f"   Avg processing time: {stats['rag_stats']['average_processing_time']:.3f}s")
        print(f"   TM index size: {stats['rag_stats']['tm_index_stats']['total_entries']:,}")
        print(f"   LLM available: {stats['llm_available']}")
        print(f"   Model: {stats['model']}")
    else:
        print(f"❌ Stats failed: {response.status_code}")
except Exception as e:
    print(f"❌ Request failed: {e}")

print("\n" + "=" * 60)
print("✅ API TESTING COMPLETE")
print("=" * 60)
print("\n📋 MemoQ Integration Steps:")
print("1. Configure MemoQ to use custom MT engine")
print("2. Set endpoint: http://localhost:8000/translate")
print("3. MemoQ will send each segment to this endpoint")
print("4. Service returns translation for target field")
print("\n💡 To use with LLM:")
print("   - Add OpenAI credits")
print("   - Set use_llm: true in requests")
print("=" * 60)

