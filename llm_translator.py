"""
LLM Translation Module
Integrates GPT-4o with RAG context for finance translation
Uses LangChain for structured prompting
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv

from rag_orchestrator import RAGResponse

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class TranslationResult:
    """LLM translation result"""
    source_text: str
    translated_text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    metadata: Dict[str, Any]

class LLMTranslator:
    """
    LLM translator using GPT-4o with RAG context
    Integrates with RAG orchestrator for context-aware translation
    """
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 model: str = "gpt-4o",
                 temperature: float = 0):
        """
        Initialize LLM translator
        
        Args:
            api_key: OpenAI API key (reads from env if not provided)
            model: Model name (gpt-4o, gpt-4o-mini, etc.)
            temperature: 0 for deterministic, higher for creative
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        self.temperature = temperature
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY in .env")
        
        # Initialize LangChain ChatOpenAI
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=self.temperature
        )
        
        # Create prompt template
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            ("human", "{rag_context}\n\nProvide ONLY the translation, nothing else.")
        ])
        
        # Pricing (per 1M tokens)
        self.pricing = {
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00}
        }
        
        logger.info(f"LLM Translator initialized with model: {self.model}")
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the translator"""
        return """You are a precise financial translator. Translate ONLY the text provided, word by word.

TRANSLATION RULES:
1. Translate exactly what is given - do NOT add, omit, or modify content
2. Preserve ALL numbers, percentages, dates exactly
3. Keep fund names as shown in "DO NOT TRANSLATE" section
4. Use glossary terms when available
5. Return ONLY the Spanish translation, nothing else

DO NOT:
- Make up content not in the source
- Add explanations or notes
- Summarize or paraphrase
- Change the meaning
- Be creative - be ACCURATE"""
    
    def translate_with_rag(self, rag_response: RAGResponse) -> TranslationResult:
        """
        Translate using RAG context
        
        Args:
            rag_response: RAG response with TM/TB/DNT context
            
        Returns:
            Translation result with metadata
        """
        logger.info(f"Translating with RAG context: {rag_response.query.source_text[:50]}...")
        
        try:
            # Format RAG context (this comes from RAG orchestrator)
            rag_context = self._format_rag_context(rag_response)
            
            # Create chain
            chain = self.prompt_template | self.llm
            
            # Invoke LLM
            response = chain.invoke({"rag_context": rag_context})
            
            # Extract translation
            translated_text = response.content.strip()
            
            # Calculate cost
            input_tokens = response.response_metadata.get('token_usage', {}).get('prompt_tokens', 0)
            output_tokens = response.response_metadata.get('token_usage', {}).get('completion_tokens', 0)
            total_tokens = response.response_metadata.get('token_usage', {}).get('total_tokens', 0)
            
            cost_usd = self._calculate_cost(input_tokens, output_tokens)
            
            result = TranslationResult(
                source_text=rag_response.query.source_text,
                translated_text=translated_text,
                model=self.model,
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                metadata={
                    'has_fund_names': rag_response.has_fund_names,
                    'fund_terms': rag_response.dnt_terms,
                    'tm_results_count': len(rag_response.tm_results),
                    'tb_results_count': len(rag_response.tb_results),
                    'rag_processing_time': rag_response.processing_time
                }
            )
            
            logger.info(f"Translation completed. Tokens: {total_tokens}, Cost: ${cost_usd:.4f}")
            return result
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            raise
    
    def _format_rag_context(self, rag_response: RAGResponse) -> str:
        """Format RAG response into structured context"""
        context_parts = []
        
        # Section 1: Non-translatable terms (fund names)
        if rag_response.has_fund_names:
            context_parts.append("=== DO NOT TRANSLATE ===")
            context_parts.append("These fund names MUST stay in original language:")
            # Only show unique, longer terms (avoid showing individual words)
            unique_terms = set()
            for term in rag_response.dnt_terms:
                if len(term.split()) > 2:  # Only multi-word fund names
                    unique_terms.add(term)
            
            for term in list(unique_terms)[:5]:
                context_parts.append(f"  • {term}")
            context_parts.append("")
        
        # Section 2: Glossary terms from TB
        if rag_response.tb_results:
            context_parts.append("=== GLOSSARY TERMS ===")
            preferred = [t for t in rag_response.tb_results if t.is_preferred]
            forbidden = [t for t in rag_response.tb_results if t.is_forbidden]
            
            if preferred:
                context_parts.append("PREFERRED (mandatory):")
                for term in preferred:
                    context_parts.append(f"  • {term.source_term} → {term.target_term}")
            
            if forbidden:
                context_parts.append("FORBIDDEN (do not use):")
                for term in forbidden:
                    context_parts.append(f"  • {term.source_term} ✗ {term.target_term}")
            context_parts.append("")
        
        # Section 3: Translation examples from TM
        if rag_response.tm_results:
            context_parts.append("=== STYLE EXAMPLES ===")
            for i, tm in enumerate(rag_response.tm_results[:2], 1):
                context_parts.append(f"{i}. {tm.source_text}")
                context_parts.append(f"   → {tm.target_text}")
            context_parts.append("")
        
        # Section 4: Translation task
        context_parts.append("=== TRANSLATE ===")
        context_parts.append(f'"{rag_response.query.source_text}"')
        context_parts.append(f"From: {rag_response.query.source_language}")
        context_parts.append(f"To: {rag_response.query.target_language}")
        
        return "\n".join(context_parts)
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost in USD"""
        pricing = self.pricing.get(self.model, self.pricing["gpt-4o"])
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost
    
    def translate_simple(self, text: str, source_lang: str = "en", target_lang: str = "es") -> str:
        """
        Simple translation without RAG context (for testing)
        
        Args:
            text: Text to translate
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Translated text
        """
        messages = [
            SystemMessage(content="You are a financial translator. Translate accurately and professionally."),
            HumanMessage(content=f"Translate from {source_lang} to {target_lang}: {text}")
        ]
        
        response = self.llm.invoke(messages)
        return response.content.strip()

# Example usage and testing
async def main():
    """Example usage of LLM translator with RAG"""
    from vector_index import TMVectorIndex
    from non_trans_loader import NonTransLoader
    from memoq_client import MemoQConfig
    from rag_orchestrator import RAGOrchestrator, RAGQuery
    
    print("🤖 Testing LLM Translator with RAG")
    print("=" * 60)
    
    # Initialize components
    memoq_config = MemoQConfig.from_env()
    tm_index = TMVectorIndex(
        model_name="all-MiniLM-L6-v2",
        index_path="models/tm_vector_index"
    )
    tm_index.similarity_threshold = 0.3
    dnt_loader = NonTransLoader("data/SV_Test_Fund_names2.json")
    dnt_loader.load()
    
    # Initialize RAG orchestrator
    orchestrator = RAGOrchestrator(
        memoq_config=memoq_config,
        tm_index=tm_index,
        dnt_loader=dnt_loader
    )
    
    # Initialize LLM translator
    translator = LLMTranslator()
    
    # Test query with fund name
    query = RAGQuery(
        source_text="The Global Innovation Equity Fund returned 8.5% in the first quarter",
        max_tm_results=3,
        max_tb_results=5
    )
    
    # Get RAG context
    print("📊 Getting RAG context...")
    rag_response = await orchestrator.process_query(query)
    
    print(f"✅ RAG context ready:")
    print(f"   TM results: {len(rag_response.tm_results)}")
    print(f"   TB results: {len(rag_response.tb_results)}")
    print(f"   Fund names: {rag_response.dnt_terms[:3]}")
    
    # Translate with LLM
    print("\n🤖 Translating with GPT-4o...")
    result = translator.translate_with_rag(rag_response)
    
    # Show results
    print("\n" + "=" * 60)
    print("TRANSLATION RESULT")
    print("=" * 60)
    print(f"Source: {result.source_text}")
    print(f"Target: {result.translated_text}")
    print(f"\nModel: {result.model}")
    print(f"Tokens: {result.total_tokens} (input: {result.prompt_tokens}, output: {result.completion_tokens})")
    print(f"Cost: ${result.cost_usd:.4f}")
    print(f"Fund names preserved: {result.metadata['has_fund_names']}")
    print("=" * 60)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

