"""
Clean up old vector index files before building new one
"""
import shutil
from pathlib import Path

def cleanup_old_index():
    index_path = Path("models/tm_vector_index")
    
    if index_path.exists():
        print(f"🗑️  Removing old index: {index_path}")
        shutil.rmtree(index_path)
        print("✅ Old index removed!")
    else:
        print("ℹ️  No old index found")
    
    # Create fresh directory
    index_path.mkdir(parents=True, exist_ok=True)
    print("✅ Fresh directory created!")

if __name__ == "__main__":
    cleanup_old_index()