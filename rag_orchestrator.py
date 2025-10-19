"""
RAG Orchestrator for Finance Translation
Coordinates TM (dense retrieval), TB (live lookup), and DNT (fund names)

Dense Hybrid RAG Architecture:
- TM: Global pre-built vector store (Sentence Transformers + FAISS)
- TB: Live per-call MemoQ API lookups
- DNT: Local pattern matching
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

from memoq_client import MemoQClient, MemoQConfig
from vector_index import TMVectorIndex  # ✅ UPDATED: Using advanced vector index
from non_trans_loader import NonTransLoader

logger = logging.getLogger(__name__)

@dataclass
class RAGQuery:
    """Input query for RAG system"""
    source_text: str
    source_language: str = "en"
    target_language: str = "es"
    context: Optional[str] = None
    max_tm_results: int = 5
    max_tb_results: int = 10

@dataclass
class TMResult:
    """Translation Memory result"""
    source_text: str
    target_text: str
    similarity_score: float
    entry_id: Optional[str] = None
    metadata: Optional[Dict] = None

@dataclass
class TBResult:
    """Term Base result"""
    source_term: str
    target_term: str
    is_preferred: bool = False
    is_forbidden: bool = False
    definition: Optional[str] = None
    context: Optional[str] = None
    reliability: Optional[int] = None

@dataclass
class RAGResponse:
    """Complete RAG response"""
    query: RAGQuery
    tm_results: List[TMResult]
    tb_results: List[TBResult]
    dnt_terms: List[str]
    has_fund_names: bool
    processing_time: float
    metadata: Dict[str, Any]

class RAGOrchestrator:
    """
    Main RAG orchestrator that coordinates all components:
    - TM: Dense retrieval from vector index (Sentence Transformers + FAISS)
    - TB: Live lookup from MemoQ API
    - DNT: Fund name detection and preservation
    
    Dense Hybrid RAG Approach:
    - Global TM Store: Pre-built vector index loaded once
    - Live TB Lookup: Per-call API queries for fresh terminology
    - DNT Detection: Local pattern matching
    """
    
    def __init__(self, 
                 memoq_config: MemoQConfig,
                 tm_index: TMVectorIndex,  # ✅ UPDATED: Using advanced vector index
                 dnt_loader: NonTransLoader,
                 tm_guid: Optional[str] = None,
                 tb_guid: Optional[str] = None):
        """
        Initialize RAG orchestrator
        
        Args:
            memoq_config: MemoQ server configuration
            tm_index: Vector index for TM dense retrieval (Sentence Transformers + FAISS)
            dnt_loader: Do Not Translate terms loader
            tm_guid: Optional TM GUID for fuzzy matches
            tb_guid: Optional TB GUID for terminology lookup
        """
        self.memoq_config = memoq_config
        self.tm_index = tm_index
        self.dnt_loader = dnt_loader
        self.tm_guid = tm_guid
        self.tb_guid = tb_guid
        
        # Initialize MemoQ client
        self.memoq_client = MemoQClient(memoq_config)
        
        # Statistics
        self.query_count = 0
        self.total_processing_time = 0.0
        
        logger.info("RAG Orchestrator initialized with advanced vector index")
    
    async def process_query(self, query: RAGQuery) -> RAGResponse:
        """
        Process a translation query through the complete RAG pipeline
        
        Dense Hybrid RAG Flow:
        1. TM: Dense semantic search in pre-built vector index
        2. TB: Live API lookup for fresh terminology
        3. DNT: Pattern matching for fund names
        
        Args:
            query: The translation query
            
        Returns:
            Complete RAG response with TM, TB, and DNT results
        """
        start_time = time.time()
        self.query_count += 1
        
        logger.info(f"Processing RAG query {self.query_count}: {query.source_text[:50]}...")
        
        try:
            # Run all components in parallel for speed
            # This is the "hybrid" part - combining different retrieval methods
            tasks = [
                self._process_tm_dense(query),  # Dense semantic search
                self._process_tb_live(query),   # Live API lookup
                self._process_dnt_check(query)  # Pattern matching
            ]
            
            # Wait for all tasks to complete
            tm_results, tb_results, dnt_data = await asyncio.gather(*tasks)
            
            processing_time = time.time() - start_time
            self.total_processing_time += processing_time
            
            # Prepare metadata
            metadata = {
                'query_id': self.query_count,
                'timestamp': datetime.now().isoformat(),
                'tm_results_count': len(tm_results),
                'tb_results_count': len(tb_results),
                'dnt_terms_count': len(dnt_data['terms']),
                'has_fund_names': dnt_data['has_funds'],
                'processing_time': processing_time,
                'retrieval_method': 'dense_hybrid_rag'  # ✅ Track the method
            }
            
            response = RAGResponse(
                query=query,
                tm_results=tm_results,
                tb_results=tb_results,
                dnt_terms=dnt_data['terms'],
                has_fund_names=dnt_data['has_funds'],
                processing_time=processing_time,
                metadata=metadata
            )
            
            logger.info(f"RAG query {self.query_count} completed in {processing_time:.3f}s")
            return response
            
        except Exception as e:
            logger.error(f"RAG query {self.query_count} failed: {e}")
            processing_time = time.time() - start_time
            
            return RAGResponse(
                query=query,
                tm_results=[],
                tb_results=[],
                dnt_terms=[],
                has_fund_names=False,
                processing_time=processing_time,
                metadata={'error': str(e), 'query_id': self.query_count}
            )
    
    async def _process_tm_dense(self, query: RAGQuery) -> List[TMResult]:
        """
        Process TM dense retrieval using vector index
        
        Uses Sentence Transformers + FAISS for semantic search
        - Finds semantically similar translations (not just word matches)
        - Handles paraphrases and synonyms
        - Better for finance domain terminology
        """
        def _search_tm():
            try:
                # Dense semantic search in pre-built vector index
                results = self.tm_index.search(query.source_text, k=query.max_tm_results)
                
                tm_results = []
                for entry, score in results:
                    tm_result = TMResult(
                        source_text=entry['source_text'],
                        target_text=entry['target_text'],
                        similarity_score=score,
                        entry_id=entry.get('entry_id'),
                        metadata={
                            'source_lang': entry.get('source_language'), 
                            'target_lang': entry.get('target_language'),
                            'retrieval_method': 'dense_semantic_search'  # ✅ Track method
                        }
                    )
                    tm_results.append(tm_result)
                
                logger.debug(f"TM dense retrieval found {len(tm_results)} semantic matches")
                return tm_results
                
            except Exception as e:
                logger.error(f"TM dense retrieval failed: {e}")
                return []
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _search_tm)
    
    async def _process_tb_live(self, query: RAGQuery) -> List[TBResult]:
        """
        Process TB live lookup from MemoQ API
        
        Live per-call API lookup ensures:
        - Always fresh terminology
        - Up-to-date policy flags (preferred/forbidden)
        - No stale cached data
        """
        def _search_tb():
            try:
                if not self.tb_guid:
                    logger.warning("No TB GUID configured for live lookup")
                    return []
                
                # Live API lookup for fresh terminology
                results = self.memoq_client.tb_lookup_terms(
                    tb_guid=self.tb_guid,
                    source_text=query.source_text,
                    source_lang=query.source_language,
                    target_lang=query.target_language,
                    max_results=query.max_tb_results
                )
                
                tb_results = []
                for item in results:
                    tb_result = TBResult(
                        source_term=item.get('SourceText', ''),
                        target_term=item.get('TargetText', ''),
                        is_preferred=item.get('IsPreferred', False),
                        is_forbidden=item.get('IsForbidden', False),
                        definition=item.get('Definition'),
                        context=item.get('Context'),
                        reliability=item.get('Reliability')
                    )
                    tb_results.append(tb_result)
                
                logger.debug(f"TB live lookup found {len(tb_results)} fresh terminology entries")
                return tb_results
                
            except Exception as e:
                logger.error(f"TB live lookup failed: {e}")
                return []
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _search_tb)
    
    async def _process_dnt_check(self, query: RAGQuery) -> Dict[str, Any]:
        """Process Do Not Translate check (local pattern matching)"""
        def _check_dnt():
            try:
                has_funds = self.dnt_loader.is_non_translatable(query.source_text)
                fund_terms = self.dnt_loader.get_non_translatable_terms(query.source_text)
                
                logger.debug(f"DNT check: {len(fund_terms)} fund terms found")
                return {
                    'has_funds': has_funds,
                    'terms': fund_terms
                }
                
            except Exception as e:
                logger.error(f"DNT check failed: {e}")
                return {'has_funds': False, 'terms': []}
        
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check_dnt)
    
    def format_llm_prompt(self, response: RAGResponse) -> str:
        """
        Format RAG response into structured LLM prompt
        
        Args:
            response: RAG response to format
            
        Returns:
            Formatted prompt for LLM translation
        """
        prompt_parts = []
        
        # Section 1: Non-translatable terms (fund names)
        if response.has_fund_names:
            prompt_parts.append("=== DO NOT TRANSLATE TERMS ===")
            prompt_parts.append("The following fund names MUST NOT be translated:")
            for term in response.dnt_terms[:5]:  # Show first 5 terms
                prompt_parts.append(f"  • {term}")
            prompt_parts.append("")
        
        # Section 2: Glossary terms (TB results)
        if response.tb_results:
            prompt_parts.append("=== GLOSSARY TERMS ===")
            
            # Separate preferred, forbidden, and neutral terms
            preferred_terms = [t for t in response.tb_results if t.is_preferred]
            forbidden_terms = [t for t in response.tb_results if t.is_forbidden]
            neutral_terms = [t for t in response.tb_results if not t.is_preferred and not t.is_forbidden]
            
            if preferred_terms:
                prompt_parts.append("PREFERRED TERMS (use these):")
                for term in preferred_terms:
                    prompt_parts.append(f"  • {term.source_term} → {term.target_term}")
                    if term.definition:
                        prompt_parts.append(f"    Definition: {term.definition}")
            
            if forbidden_terms:
                prompt_parts.append("FORBIDDEN TERMS (avoid these):")
                for term in forbidden_terms:
                    prompt_parts.append(f"  • {term.source_term} → {term.target_term}")
                    if term.definition:
                        prompt_parts.append(f"    Definition: {term.definition}")
            
            if neutral_terms:
                prompt_parts.append("TERMINOLOGY:")
                for term in neutral_terms:
                    prompt_parts.append(f"  • {term.source_term} → {term.target_term}")
                    if term.definition:
                        prompt_parts.append(f"    Definition: {term.definition}")
        
        # Section 3: Translation examples (TM results)
        if response.tm_results:
            prompt_parts.append("\n=== TRANSLATION EXAMPLES (use as style guidance) ===")
            for i, tm_result in enumerate(response.tm_results[:3], 1):
                prompt_parts.append(f"{i}. {tm_result.source_text}")
                prompt_parts.append(f"   → {tm_result.target_text}")
                prompt_parts.append(f"   (similarity: {tm_result.similarity_score:.3f})")
        
        # Section 4: Translation task
        prompt_parts.append(f"\n=== TRANSLATION TASK ===")
        prompt_parts.append(f"Translate this sentence: \"{response.query.source_text}\"")
        prompt_parts.append(f"From {response.query.source_language} to {response.query.target_language}")
        prompt_parts.append("")
        prompt_parts.append("Instructions:")
        
        if response.has_fund_names:
            prompt_parts.append("• DO NOT translate the fund names listed above")
        
        prompt_parts.append("• Use glossary terms strictly (preferred terms are mandatory)")
        prompt_parts.append("• Use TM examples as style guidance")
        prompt_parts.append("• Maintain consistency with existing translations")
        prompt_parts.append("• Avoid forbidden terms")
        
        return "\n".join(prompt_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics"""
        avg_processing_time = (
            self.total_processing_time / self.query_count 
            if self.query_count > 0 else 0
        )
        
        return {
            'total_queries': self.query_count,
            'average_processing_time': avg_processing_time,
            'total_processing_time': self.total_processing_time,
            'tm_index_stats': self.tm_index.get_stats(),
            'dnt_terms_count': len(self.dnt_loader.terms) if hasattr(self.dnt_loader, 'terms') else 0,
            'retrieval_method': 'dense_hybrid_rag'  # ✅ Track method
        }

# Example usage and testing
async def main():
    """Example usage of RAG orchestrator"""
    from dotenv import load_dotenv
    import os
    
    load_dotenv()
    
    # Initialize components
    memoq_config = MemoQConfig.from_env()
    tm_index = TMVectorIndex("models/tm_vector_index")  # ✅ UPDATED: Using advanced vector index
    dnt_loader = NonTransLoader("data/SV_Test_Fund_names2.json")
    dnt_loader.load()
    
    # Initialize orchestrator
    tm_index.similarity_threshold = 0.3  # Lower threshold for better results
    orchestrator = RAGOrchestrator(
        memoq_config=memoq_config,
        tm_index=tm_index,
        dnt_loader=dnt_loader
    )
    
    # Example query
    query = RAGQuery(
        source_text="The Global Innovation Equity Fund returned 8.5% in the first quarter",
        max_tm_results=3,
        max_tb_results=5
    )
    
    # Process query
    response = await orchestrator.process_query(query)
    
    # Show results
    print("🔍 RAG Query Results:")
    print(f"Query: {response.query.source_text}")
    print(f"TM Results: {len(response.tm_results)}")
    print(f"TB Results: {len(response.tb_results)}")
    print(f"Fund Names: {response.dnt_terms}")
    print(f"Processing Time: {response.processing_time:.3f}s")
    
    # Format for LLM
    prompt = orchestrator.format_llm_prompt(response)
    print("\n📝 LLM Prompt:")
    print("=" * 60)
    print(prompt)
    
    # Get stats
    stats = orchestrator.get_stats()
    print(f"\n📊 Stats: {stats}")

if __name__ == "__main__":
    asyncio.run(main())
