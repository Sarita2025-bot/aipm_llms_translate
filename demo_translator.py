"""
Demo Translator (No API Required)
Simulates GPT-4o translations for bootcamp demos
Shows the complete RAG pipeline without API costs
"""

import asyncio
from simple_vector_index import SimpleTMVectorIndex
from non_trans_loader import NonTransLoader
from memoq_client import MemoQConfig
from rag_orchestrator import RAGOrchestrator, RAGQuery

async def demo_translation():
    """Demo the complete RAG system without LLM API"""
    
    print("🏦 Finance RAG Translation Demo")
    print("=" * 60)
    
    # Initialize components
    memoq_config = MemoQConfig.from_env()
    tm_index = SimpleTMVectorIndex("models/tm_vector_index")
    tm_index.similarity_threshold = 0.3
    dnt_loader = NonTransLoader("data/SV_Test_Fund_names2.json")
    dnt_loader.load()
    
    # Initialize RAG orchestrator
    orchestrator = RAGOrchestrator(
        memoq_config=memoq_config,
        tm_index=tm_index,
        dnt_loader=dnt_loader
    )
    
    # Test queries
    test_queries = [
        "The Global Innovation Equity Fund returned 8.5% in the first quarter",
        "AB SICAV I - European Equity Portfolio showed strong performance in Q2",
        "The European Central Bank announced new monetary policy measures"
    ]
    
    for i, query_text in enumerate(test_queries, 1):
        print(f"\n{'='*60}")
        print(f"Demo {i}/3")
        print('='*60)
        
        # Create query
        query = RAGQuery(
            source_text=query_text,
            max_tm_results=3,
            max_tb_results=5
        )
        
        # Get RAG context
        print(f"📝 Source: {query_text}")
        rag_response = await orchestrator.process_query(query)
        
        # Show RAG context
        print(f"\n🔍 RAG Context Generated:")
        print(f"   • Fund names detected: {len(rag_response.dnt_terms)}")
        if rag_response.dnt_terms[:3]:
            print(f"     → {', '.join(list(set([t for t in rag_response.dnt_terms if len(t.split()) > 2]))[:2])}")
        print(f"   • TM examples found: {len(rag_response.tm_results)}")
        print(f"   • TB terms found: {len(rag_response.tb_results)}")
        print(f"   • Processing time: {rag_response.processing_time:.3f}s")
        
        # Show formatted prompt
        prompt = orchestrator.format_llm_prompt(rag_response)
        print(f"\n📄 LLM Prompt Preview:")
        print("-" * 60)
        # Show first 500 chars of prompt
        print(prompt[:500] + "..." if len(prompt) > 500 else prompt)
        print("-" * 60)
        
        # Simulated translation (would come from GPT-4o)
        print(f"\n🤖 [GPT-4o would generate translation here]")
        print(f"💡 Demo: Your RAG system provides perfect context for:")
        print(f"   ✅ Fund name preservation")
        print(f"   ✅ Terminology consistency")
        print(f"   ✅ Style matching from TM examples")
    
    print(f"\n{'='*60}")
    print("✅ RAG SYSTEM DEMO COMPLETE")
    print("=" * 60)
    print("\n📊 System Status:")
    stats = orchestrator.get_stats()
    print(f"   • Total queries: {stats['total_queries']}")
    print(f"   • Avg processing time: {stats['average_processing_time']:.3f}s")
    print(f"   • TM index size: {stats['tm_index_stats']['total_entries']:,} entries")
    print(f"   • DNT terms loaded: {stats['dnt_terms_count']}")
    print("\n💡 To add LLM translation:")
    print("   1. Add OpenAI credits at platform.openai.com/billing")
    print("   2. Run: python llm_translator.py")

if __name__ == "__main__":
    asyncio.run(demo_translation())

