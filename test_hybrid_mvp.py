"""
Test script for Hybrid MVP Streamlit app
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def main():
    print("🌐 Testing Hybrid File Translation MVP")
    print("=" * 60)
    
    # Check if app exists
    if not Path("hybrid_mvp_app.py").exists():
        print("❌ hybrid_mvp_app.py not found!")
        return
    
    print("✅ App file found")
    
    # Check Streamlit installation
    try:
        import streamlit
        print("✅ Streamlit installed")
    except ImportError:
        print("❌ Streamlit not installed")
        return
    
    # Check required files
    required_files = [
        "rag_orchestrator.py",
        "vector_index.py", 
        "non_trans_loader.py",
        "memoq_client.py",
        "data/SV_Test_Fund_names2.json"
    ]
    
    missing = [f for f in required_files if not Path(f).exists()]
    
    if missing:
        print(f"⚠️  Missing files: {', '.join(missing)}")
    else:
        print("✅ All required files found")
    
    print()
    print("🚀 Starting Streamlit app...")
    print()
    print("=" * 60)
    print("📱 Open your browser at: http://localhost:8501")
    print("=" * 60)
    print()
    print("💡 To stop the server, press Ctrl+C")
    print()
    
    try:
        # Start Streamlit
        subprocess.run([sys.executable, "-m", "streamlit", "run", "hybrid_mvp_app.py"])
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
