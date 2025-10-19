"""
Vector Index Builder for TM Dense Retrieval
Creates FAISS index from TM CSV/TMX data for semantic search

Features:
- GPU acceleration for faster embedding generation
- Automatic device detection (GPU/CPU)
- Optimized batch sizes for different hardware
- Better semantic understanding with Sentence Transformers
"""

import pandas as pd
import numpy as np
import faiss
import pickle
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import logging

# Try to import torch for GPU detection
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

class TMVectorIndex:
    """
    Vector index for Translation Memory dense retrieval
    Uses FAISS for fast semantic search over TM entries
    
    GPU-Optimized Features:
    - Automatic GPU detection
    - Dynamic batch sizing based on hardware
    - Fast embedding generation with GPU acceleration
    """
    
    def __init__(self, 
                 model_name: str = "all-MiniLM-L6-v2",
                 index_path: str = "models/tm_vector_index",
                 similarity_threshold: float = 0.7):
        """
        Initialize TM vector index with GPU support
        
        Args:
            model_name: Sentence transformer model for embeddings
            index_path: Path to save/load FAISS index
            similarity_threshold: Minimum similarity for matches
        """
        self.model_name = model_name
        self.index_path = Path(index_path)
        self.similarity_threshold = similarity_threshold
        
        # Detect GPU availability
        self.device = self._detect_device()
        
        # Initialize sentence transformer
        logger.info(f"Loading sentence transformer: {model_name}")
        logger.info(f"🔧 Using device: {self.device}")
        self.encoder = SentenceTransformer(model_name, device=self.device)
        self.embedding_dim = self.encoder.get_sentence_embedding_dimension()
        
        # Initialize FAISS index
        self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine similarity
        self.tm_entries: List[Dict] = []
        self.metadata: List[Dict] = []
        
        # Load existing index if available
        self._load_index()
        
        logger.info(f"TM Vector Index initialized with {len(self.tm_entries)} entries")
    
    def _detect_device(self) -> str:
        """
        Detect available device (GPU/CPU)
        
        Returns:
            'cuda' if GPU available, 'cpu' otherwise
        """
        if TORCH_AVAILABLE and torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"✅ GPU detected: {gpu_name}")
            return 'cuda'
        else:
            logger.info("ℹ️  No GPU detected, using CPU")
            return 'cpu'
    
    def _get_batch_size(self) -> int:
        """
        Get optimal batch size based on device
        
        Returns:
            Batch size (larger for GPU, smaller for CPU)
        """
        if self.device == 'cuda':
            return 64  # GPU can handle larger batches
        else:
            return 8   # CPU needs smaller batches
    
    def _load_index(self):
        """Load existing index from disk"""
        try:
            if self.index_path.exists():
                # Load FAISS index
                index_file = self.index_path / "index.faiss"
                if index_file.exists():
                    self.index = faiss.read_index(str(index_file))
                
                # Load metadata
                metadata_file = self.index_path / "metadata.pkl"
                if metadata_file.exists():
                    with open(metadata_file, 'rb') as f:
                        data = pickle.load(f)
                        self.tm_entries = data.get('tm_entries', [])
                        self.metadata = data.get('metadata', [])
                
                logger.info(f"✅ Loaded existing index with {len(self.tm_entries)} entries")
        except Exception as e:
            logger.warning(f"Could not load existing index: {e}")
    
    def _save_index(self):
        """Save index to disk"""
        try:
            self.index_path.mkdir(parents=True, exist_ok=True)
            
            # Save FAISS index
            index_file = self.index_path / "index.faiss"
            faiss.write_index(self.index, str(index_file))
            
            # Save metadata
            metadata_file = self.index_path / "metadata.pkl"
            with open(metadata_file, 'wb') as f:
                pickle.dump({
                    'tm_entries': self.tm_entries,
                    'metadata': self.metadata,
                    'model_name': self.model_name,
                    'embedding_dim': self.embedding_dim,
                    'similarity_threshold': self.similarity_threshold
                }, f)
            
            logger.info(f"💾 Saved index with {len(self.tm_entries)} entries to {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to save index: {e}")
    
    def build_from_csv(self, csv_file: str, source_col: str = 'source', target_col: str = 'target'):
        """
        Build vector index from CSV file
        
        Args:
            csv_file: Path to CSV file with TM data
            source_col: Column name for source text
            target_col: Column name for target text
        """
        logger.info(f"🏗️  Building vector index from CSV: {csv_file}")
        logger.info(f"📊 Device: {self.device}, Batch size: {self._get_batch_size()}")
        
        try:
            # Load CSV data
            df = pd.read_csv(csv_file)
            logger.info(f"📂 Loaded {len(df):,} translation pairs from CSV")
            
            # Prepare TM entries
            tm_entries = []
            for _, row in df.iterrows():
                entry = {
                    'source_text': str(row[source_col]).strip(),
                    'target_text': str(row[target_col]).strip(),
                    'source_language': 'en',
                    'target_language': 'es',
                    'entry_id': len(tm_entries)
                }
                
                # Only add non-empty entries
                if entry['source_text'] and entry['target_text'] and entry['source_text'] != 'nan':
                    tm_entries.append(entry)
            
            logger.info(f"✅ Prepared {len(tm_entries):,} valid TM entries")
            
            # Build index
            self.add_entries(tm_entries)
            
        except Exception as e:
            logger.error(f"Failed to build index from CSV: {e}")
            raise
    
    def add_entries(self, entries: List[Dict]):
        """
        Add TM entries to vector index with GPU acceleration
        
        Args:
            entries: List of TM entry dictionaries
        """
        if not entries:
            return
        
        logger.info(f"➕ Adding {len(entries):,} entries to vector index")
        logger.info(f"⚡ Using {self.device} with batch size {self._get_batch_size()}")
        
        # Prepare texts for embedding (combine source and target)
        texts = []
        for entry in entries:
            # Create combined text for better semantic matching
            combined_text = f"{entry['source_text']} | {entry['target_text']}"
            texts.append(combined_text)
        
        # Generate embeddings with GPU support
        logger.info("🧮 Generating embeddings...")
        batch_size = self._get_batch_size()
        
        embeddings = self.encoder.encode(
            texts, 
            show_progress_bar=True, 
            batch_size=batch_size,
            device=self.device  # Use GPU if available
        )
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        
        # Add to FAISS index
        start_id = len(self.tm_entries)
        self.index.add(embeddings.astype('float32'))
        
        # Store entries and metadata
        for i, (entry, embedding) in enumerate(zip(entries, embeddings)):
            self.tm_entries.append(entry)
            self.metadata.append({
                'entry_id': start_id + i,
                'source_length': len(entry['source_text']),
                'target_length': len(entry['target_text']),
                'embedding_norm': float(np.linalg.norm(embedding))
            })
        
        logger.info(f"✅ Successfully added {len(entries):,} entries. Total: {len(self.tm_entries):,}")
        
        # Save index
        self._save_index()
    
    def search(self, query: str, k: int = 5) -> List[Tuple[Dict, float]]:
        """
        Search for similar TM entries using semantic similarity
        
        Args:
            query: Search query text
            k: Number of results to return
            
        Returns:
            List of (entry, similarity_score) tuples
        """
        if len(self.tm_entries) == 0:
            logger.warning("Vector index is empty")
            return []
        
        try:
            # Encode query with GPU support
            query_embedding = self.encoder.encode([query], device=self.device)
            faiss.normalize_L2(query_embedding)
            
            # Search
            scores, indices = self.index.search(query_embedding.astype('float32'), k)
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:  # FAISS returns -1 for empty slots
                    continue
                
                if score >= self.similarity_threshold:
                    entry = self.tm_entries[idx]
                    results.append((entry, float(score)))
            
            logger.debug(f"🔍 Found {len(results)} similar entries for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def export_test_results_to_markdown(self, 
                                       test_queries: List[str], 
                                       output_file: str = "vector_index_test_results.md",
                                       k: int = 5):
        """
        Export test query results to markdown file
        
        Args:
            test_queries: List of test queries to run
            output_file: Output markdown file path
            k: Number of results per query
        """
        logger.info(f"📝 Exporting test results to {output_file}")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            # Write header
            f.write("# Vector Index Test Results\n\n")
            f.write(f"**Model:** {self.model_name}\n\n")
            f.write(f"**Device:** {self.device}\n\n")
            f.write(f"**Total Entries:** {len(self.tm_entries):,}\n\n")
            f.write(f"**Similarity Threshold:** {self.similarity_threshold}\n\n")
            f.write(f"**Embedding Dimension:** {self.embedding_dim}\n\n")
            f.write("---\n\n")
            
            # Run each test query
            for i, query in enumerate(test_queries, 1):
                f.write(f"## Test Query {i}\n\n")
                f.write(f"**Query:** `{query}`\n\n")
                
                # Search
                results = self.search(query, k=k)
                
                if results:
                    f.write(f"**Found {len(results)} results:**\n\n")
                    
                    for j, (entry, score) in enumerate(results, 1):
                        # Format score as percentage
                        score_pct = score * 100
                        
                        f.write(f"### Result {j} (Similarity: {score_pct:.1f}%)\n\n")
                        f.write(f"**Source:** {entry['source_text']}\n\n")
                        f.write(f"**Target:** {entry['target_text']}\n\n")
                        f.write(f"**Entry ID:** {entry.get('entry_id', 'N/A')}\n\n")
                        f.write("---\n\n")
                else:
                    f.write("**No results found** (below similarity threshold)\n\n")
                    f.write("---\n\n")
            
            # Write footer with stats
            f.write("## Statistics\n\n")
            stats = self.get_stats()
            f.write(f"- **Total Entries:** {stats['total_entries']:,}\n")
            f.write(f"- **Average Source Length:** {stats['average_source_length']:.1f} chars\n")
            f.write(f"- **Average Target Length:** {stats['average_target_length']:.1f} chars\n")
            f.write(f"- **Device Used:** {stats['device']}\n")
        
        logger.info(f"✅ Results exported to {output_file}")
        print(f"\n📄 Results saved to: {output_file}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'total_entries': len(self.tm_entries),
            'embedding_dimension': self.embedding_dim,
            'model_name': self.model_name,
            'similarity_threshold': self.similarity_threshold,
            'device': self.device,
            'index_size': self.index.ntotal if hasattr(self.index, 'ntotal') else 0,
            'average_source_length': np.mean([len(e['source_text']) for e in self.tm_entries]) if self.tm_entries else 0,
            'average_target_length': np.mean([len(e['target_text']) for e in self.tm_entries]) if self.tm_entries else 0
        }

def main():
    """Build vector index from CSV data and export test results"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build TM vector index with GPU support')
    parser.add_argument('--csv', default='data/en-es_sample_30k.csv', help='CSV file path')
    parser.add_argument('--model', default='all-MiniLM-L6-v2', help='Sentence transformer model')
    parser.add_argument('--output', default='models/tm_vector_index', help='Output directory')
    parser.add_argument('--threshold', type=float, default=0.7, help='Similarity threshold')
    parser.add_argument('--export', action='store_true', help='Export test results to markdown')
    parser.add_argument('--export-file', default='vector_index_test_results.md', help='Output markdown file')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Build index
    print("🏗️  Building TM Vector Index with GPU Support...")
    print("=" * 60)
    
    index = TMVectorIndex(
        model_name=args.model,
        index_path=args.output,
        similarity_threshold=args.threshold
    )
    
    index.build_from_csv(args.csv)
    
    # Show stats
    stats = index.get_stats()
    print("\n📊 Index Statistics:")
    print("=" * 60)
    print(f"Total entries: {stats['total_entries']:,}")
    print(f"Model: {stats['model_name']}")
    print(f"Embedding dimension: {stats['embedding_dimension']}")
    print(f"Device: {stats['device']}")
    print(f"Similarity threshold: {stats['similarity_threshold']}")
    print(f"Avg source length: {stats['average_source_length']:.1f} chars")
    print(f"Avg target length: {stats['average_target_length']:.1f} chars")
    
    # Test queries
    test_queries = [
        "The European Central Bank announced new policy measures",
        "Investment funds showed strong performance in Q1",
        "Foreign exchange reserves increased significantly"
    ]
    
    # Test search
    print("\n🔍 Testing semantic search...")
    print("=" * 60)
    
    for query in test_queries:
        results = index.search(query, k=3)
        print(f"\n📝 Query: {query}")
        if results:
            for i, (entry, score) in enumerate(results, 1):
                print(f"  {i}. {entry['source_text'][:80]}...")
                print(f"     → {entry['target_text'][:80]}...")
                print(f"     Similarity: {score:.3f}")
        else:
            print("  No results found")
    
    # Export to markdown if requested
    if args.export:
        print("\n📝 Exporting results to markdown...")
        index.export_test_results_to_markdown(
            test_queries=test_queries,
            output_file=args.export_file
        )

if __name__ == "__main__":
    main()
