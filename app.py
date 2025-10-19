"""
Finance RAG Translation Service - FastAPI
Connects RAG system to MemoQ for AI-powered translation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import asyncio
import logging
import os

from rag_orchestrator import RAGOrchestrator, RAGQuery
from vector_index import TMVectorIndex  # ✅ UPDATED: Using advanced vector index
from non_trans_loader import NonTransLoader
from memoq_client import MemoQConfig

# Optional LLM integration (if OpenAI credits available)
try:
    from llm_translator import LLMTranslator
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Finance RAG Translation Service",
    description="AI-powered translation service with TM, TB, and DNT integration for MemoQ",
    version="1.0.0"
)

# Add CORS middleware (allows MemoQ to call from different origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class TranslationRequest(BaseModel):
    """Translation request from MemoQ"""
    source_text: str = Field(..., description="Source text segment to translate")
    source_language: str = Field(default="en", description="Source language code")
    target_language: str = Field(default="es", description="Target language code")
    context: Optional[str] = Field(default=None, description="Optional context for translation")
    max_tm_results: Optional[int] = Field(default=3, description="Max TM results to retrieve")
    max_tb_results: Optional[int] = Field(default=5, description="Max TB results to retrieve")
    use_llm: Optional[bool] = Field(default=True, description="Use LLM for translation")  # True = GPT-4o, False = TM only

class TranslationResponse(BaseModel):
    """Translation response to MemoQ"""
    source_text: str
    target_text: str
    confidence: float = Field(ge=0.0, le=1.0, description="Translation confidence score")
    has_fund_names: bool
    fund_terms: List[str]
    tm_matches: int
    tb_matches: int
    processing_time: float
    metadata: Dict[str, Any]

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    components: Dict[str, bool]

# Global components (initialized on startup)
orchestrator: Optional[RAGOrchestrator] = None
llm_translator: Optional[LLMTranslator] = None

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    global orchestrator, llm_translator
    
    try:
        logger.info("🚀 Starting Finance RAG Translation Service...")
        
        # Initialize MemoQ config
        memoq_config = MemoQConfig.from_env()
        
        # Initialize vector index (advanced with Sentence Transformers + FAISS)
        logger.info("📊 Loading TM vector index...")
        tm_index = TMVectorIndex("models/tm_vector_index")  # ✅ UPDATED: Using advanced vector index
        tm_index.similarity_threshold = 0.3
        logger.info(f"✅ Vector index loaded: {len(tm_index.tm_entries):,} entries")
        
        # Initialize DNT loader
        logger.info("🚫 Loading Do Not Translate terms...")
        dnt_loader = NonTransLoader("data/SV_Test_Fund_names2.json")
        dnt_loader.load()
        logger.info(f"✅ DNT loaded: {len(dnt_loader.terms)} terms")
        
        # Initialize RAG orchestrator
        orchestrator = RAGOrchestrator(
            memoq_config=memoq_config,
            tm_index=tm_index,
            dnt_loader=dnt_loader
        )
        logger.info("✅ RAG Orchestrator initialized")
        
        # Try to initialize LLM translator (optional)
        if LLM_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            try:
                llm_translator = LLMTranslator()
                logger.info("✅ LLM Translator initialized (GPT-4o ready)")
            except Exception as e:
                logger.warning(f"⚠️  LLM Translator not available: {e}")
                llm_translator = None
        else:
            logger.info("ℹ️  LLM Translator not available (no OpenAI API key)")
        
        logger.info("🎉 Service started successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to start service: {e}")
        raise

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint"""
    return {
        "service": "Finance RAG Translation Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "translate": "POST /translate",
            "health": "GET /health",
            "stats": "GET /stats"
        }
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        components={
            "rag_orchestrator": orchestrator is not None,
            "llm_translator": llm_translator is not None,
            "vector_index": orchestrator is not None and len(orchestrator.tm_index.tm_entries) > 0,
            "dnt_loader": orchestrator is not None and len(orchestrator.dnt_loader.terms) > 0
        }
    )

@app.post("/translate", response_model=TranslationResponse)
async def translate(request: TranslationRequest):
    """
    Main translation endpoint - called by MemoQ for each segment
    
    This endpoint:
    1. Receives a source text segment from MemoQ
    2. Processes through RAG pipeline (TM + TB + DNT)
    3. Generates translation with LLM (if available)
    4. Returns target translation to populate MemoQ target field
    """
    try:
        logger.info(f"📝 Translation request: {request.source_text[:50]}...")
        
        if orchestrator is None:
            raise HTTPException(status_code=503, detail="Service not initialized")
        
        # Create RAG query
        rag_query = RAGQuery(
            source_text=request.source_text,
            source_language=request.source_language,
            target_language=request.target_language,
            context=request.context,
            max_tm_results=request.max_tm_results,
            max_tb_results=request.max_tb_results
        )
        
        # Process through RAG orchestrator
        rag_response = await orchestrator.process_query(rag_query)
        
        # Generate translation
        target_text = ""
        confidence = 0.0
        
        if request.use_llm and llm_translator is not None:
            # Use LLM for translation
            try:
                result = llm_translator.translate_with_rag(rag_response)
                target_text = result.translated_text
                confidence = 0.95  # High confidence with LLM
                logger.info(f"✅ LLM translation: {target_text[:50]}...")
            except Exception as e:
                logger.error(f"❌ LLM translation failed: {e}")
                # Fallback to TM if LLM fails
                if rag_response.tm_results:
                    target_text = rag_response.tm_results[0].target_text
                    confidence = rag_response.tm_results[0].similarity_score
                else:
                    target_text = f"[Translation unavailable: {str(e)}]"
                    confidence = 0.0
        else:
            # Use best TM match if LLM not available
            if rag_response.tm_results:
                target_text = rag_response.tm_results[0].target_text
                confidence = rag_response.tm_results[0].similarity_score
                logger.info(f"✅ TM match (no LLM): {target_text[:50]}...")
            else:
                target_text = f"[No translation available - LLM not configured]"
                confidence = 0.0
        
        # Build response
        response = TranslationResponse(
            source_text=request.source_text,
            target_text=target_text,
            confidence=confidence,
            has_fund_names=rag_response.has_fund_names,
            fund_terms=rag_response.dnt_terms[:5],  # First 5 fund terms
            tm_matches=len(rag_response.tm_results),
            tb_matches=len(rag_response.tb_results),
            processing_time=rag_response.processing_time,
            metadata={
                "rag_query_id": rag_response.metadata.get("query_id"),
                "used_llm": request.use_llm and llm_translator is not None,
                "model": os.getenv("OPENAI_MODEL", "none") if llm_translator else "tm_only"
            }
        )
        
        logger.info(f"✅ Translation completed in {response.processing_time:.3f}s")
        return response
        
    except Exception as e:
        logger.error(f"❌ Translation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    stats = orchestrator.get_stats()
    
    return {
        "service": "Finance RAG Translation Service",
        "rag_stats": stats,
        "llm_available": llm_translator is not None,
        "model": os.getenv("OPENAI_MODEL", "none") if llm_translator else "tm_only"
    }

@app.post("/batch-translate")
async def batch_translate(requests: List[TranslationRequest]):
    """
    Batch translation endpoint for multiple segments
    Useful for translating entire documents
    """
    results = []
    
    for req in requests:
        try:
            result = await translate(req)
            results.append(result)
        except Exception as e:
            logger.error(f"Batch translation failed for segment: {e}")
            results.append(None)
    
    return {
        "total": len(requests),
        "successful": len([r for r in results if r is not None]),
        "failed": len([r for r in results if r is None]),
        "results": results
    }

if __name__ == "__main__":
    import uvicorn
    
    # Run the service
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

