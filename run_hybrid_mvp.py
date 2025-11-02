"""
Quick start script for Hybrid MVP
"""

import subprocess
import sys
import os

def main():
    print("🌐 Starting Hybrid File Translation MVP")
    print("=" * 60)
    
    # Check if streamlit is installed
    try:
        import streamlit
        print("✅ Streamlit installed")
    except ImportError:
        print("❌ Streamlit not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit"])
    
    # Check if required files exist
    required_files = [
        "hybrid_mvp_app.py",
        "rag_orchestrator.py",
        "vector_index.py",
        "non_trans_loader.py",
        "memoq_client.py"
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing files: {', '.join(missing_files)}")
        return
    
    print("✅ All required files found")
    
    # Start streamlit
    print("\n🚀 Starting Streamlit...")
    print("📱 Open your browser at: http://localhost:8501")
    print("\nPress Ctrl+C to stop the server\n")
    
    try:
        subprocess.run(["streamlit", "run", "hybrid_mvp_app.py"])
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Error starting server: {e}")

if __name__ == "__main__":
    main()
