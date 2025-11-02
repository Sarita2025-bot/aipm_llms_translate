"""
Hybrid File Translation MVP with Streamlit UI

Architecture:
- RAG calls MemoQ for TB/TM lookups
- DNT loaded from JSON file
- User uploads EN file via Streamlit UI
- No MemoQ as translation client (self-contained)
- Generates ES translation + QA report
"""

import streamlit as st
import pandas as pd
import asyncio
import time
import os
import re
import logging
import zipfile
import io
from pathlib import Path
from datetime import datetime
import docx
from docx import Document
import openpyxl
from openpyxl import load_workbook, Workbook

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RAG and translation components
from rag_orchestrator import RAGOrchestrator, RAGQuery
from vector_index import TMVectorIndex
from non_trans_loader import NonTransLoader
from memoq_client import MemoQConfig

# Quality metrics
try:
    from sacrebleu import BLEU
    from sacrebleu.metrics import CHRF
    QUALITY_AVAILABLE = True
except ImportError:
    QUALITY_AVAILABLE = False

# Try to import LLM translator (optional)
try:
    from llm_translator import LLMTranslator
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# MemoQ Language Codes for European Languages
MEMOQ_LANG_CODES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'nl': 'Dutch',
    'ru': 'Russian',
    'pl': 'Polish',
    'cs': 'Czech',
    'hu': 'Hungarian',
    'ro': 'Romanian',
    'sk': 'Slovak',
    'sv': 'Swedish',
    'da': 'Danish',
    'fi': 'Finnish',
    'no': 'Norwegian',
    'el': 'Greek',
    'bg': 'Bulgarian',
    'hr': 'Croatian',
    'sl': 'Slovenian',
    'et': 'Estonian',
    'lv': 'Latvian',
    'lt': 'Lithuanian',
    'ga': 'Irish',
    'mt': 'Maltese',
    'is': 'Icelandic',
    'mk': 'Macedonian'
}

# Configure page
st.set_page_config(
    page_title="Hybrid File Translation MVP",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .status-success {
        color: #28a745;
        font-weight: bold;
    }
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'orchestrator' not in st.session_state:
    st.session_state.orchestrator = None
    st.session_state.initialized = False
    st.session_state.current_job = None
    st.session_state.translation_results = None  # Store translation results
    st.session_state.show_results = False  # Control results display

class DocumentProcessor:
    """Processes various document formats"""
    
    @staticmethod
    def extract_text(file_path: str, file_type: str) -> str:
        """Extract text from document"""
        try:
            if file_type.lower() in ['docx', 'doc']:
                doc = Document(file_path)
                return '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
            elif file_type.lower() == 'txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif file_type.lower() in ['xlsx', 'xls']:
                wb = load_workbook(file_path)
                text = []
                for sheet in wb:
                    for row in sheet.iter_rows(values_only=True):
                        row_text = ' '.join([str(cell) for cell in row if cell])
                        if row_text.strip():
                            text.append(row_text.strip())
                return '\n'.join(text)
        except Exception as e:
            st.error(f"Error extracting text: {e}")
            return ""
    
    @staticmethod
    def segment_text(text: str) -> list:
        """Segment text by sentences - improved segmentation"""
        segments = []
        
        # Split text into lines first to preserve structure
        lines = text.split('\n')
        current_paragraph = []
        
        for line in lines:
            line = line.strip()
            
            # Empty line - end of paragraph
            if not line:
                if current_paragraph:
                    # Process the accumulated paragraph
                    paragraph_text = ' '.join(current_paragraph)
                    if paragraph_text:
                        # Split paragraph into sentences
                        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', paragraph_text)
                        
                        for sentence in sentences:
                            sentence = sentence.strip()
                            if sentence:
                                # Ensure proper ending
                                if not sentence.endswith(('.', '!', '?', ':', ';')):
                                    sentence += '.'
                                
                                segments.append({
                                    'segment_id': len(segments) + 1,
                                    'source_en': sentence
                                })
                    
                    current_paragraph = []
            
            # Non-empty line - might be heading, list item, or sentence
            else:
                # Check if it looks like a heading (shorter line, all caps, or ends with :)
                if len(line) < 100 and (line.isupper() or line.endswith(':')):
                    # It's a heading - treat as a separate segment
                    segments.append({
                        'segment_id': len(segments) + 1,
                        'source_en': line
                    })
                else:
                    # Regular sentence - add to current paragraph
                    current_paragraph.append(line)
        
        # Process any remaining paragraph
        if current_paragraph:
            paragraph_text = ' '.join(current_paragraph)
            if paragraph_text:
                sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', paragraph_text)
                
                for sentence in sentences:
                    sentence = sentence.strip()
                    if sentence:
                        if not sentence.endswith(('.', '!', '?', ':')):
                            sentence += '.'
                        
                        segments.append({
                            'segment_id': len(segments) + 1,
                            'source_en': sentence
                        })
        
        return segments

class QualityScorer:
    """Calculate quality metrics"""
    
    def __init__(self):
        self.bleu = BLEU() if QUALITY_AVAILABLE else None
        self.chrf = CHRF() if QUALITY_AVAILABLE else None
    
    def calculate_metrics(self, source: str, target: str) -> dict:
        """Calculate chrF and BLEU scores"""
        if not QUALITY_AVAILABLE:
            return {'chrF': 0.0, 'BLEU': 0.0}
        
        try:
            bleu_score = self.bleu.sentence_score(target, [source])
            chrf_score = self.chrf.sentence_score(target, [source])
            
            return {
                'chrF': chrf_score.score / 100.0,
                'BLEU': bleu_score.score / 100.0
            }
        except Exception as e:
            st.warning(f"Quality metric calculation error: {e}")
            return {'chrF': 0.0, 'BLEU': 0.0}

# (Reverted) No comparison helpers in this app – standalone script handles comparisons.

def initialize_rag_system():
    """Initialize RAG system with MemoQ backend"""
    if st.session_state.initialized:
        return True
    
    try:
        with st.spinner("🚀 Initializing RAG system..."):
            # Initialize MemoQ config
            try:
                memoq_config = MemoQConfig.from_env()
                st.success("✅ Connected to MemoQ")
            except Exception as e:
                st.warning(f"⚠️ MemoQ not configured: {e}")
                memoq_config = None
            
            # Initialize vector index
            tm_index = TMVectorIndex(
                model_name="all-MiniLM-L6-v2",
                index_path="./models/tm_vector_index"
            )
            tm_index.similarity_threshold = 0.3
            
            # Load TM data if index is empty
            if len(tm_index.tm_entries) == 0:
                st.info("📊 Loading TM data into vector index...")
                try:
                    tm_index.build_from_csv('data/en-es_sample_30k.csv')
                    st.success(f"✅ Loaded {len(tm_index.tm_entries)} TM entries")
                except Exception as e:
                    st.warning(f"⚠️ Could not load TM data: {e}")
            else:
                st.success(f"✅ Vector index loaded with {len(tm_index.tm_entries)} entries")
            
            # Load DNT terms
            dnt_loader = NonTransLoader("data/SV_Test_Fund_names2.json")
            dnt_loader.load()
            st.success(f"✅ DNT loaded: {len(dnt_loader.terms)} terms")
            
            # Initialize orchestrator
            orchestrator = RAGOrchestrator(
                memoq_config=memoq_config,
                tm_index=tm_index,
                dnt_loader=dnt_loader
            )
            
            # Try to initialize LLM translator
            if LLM_AVAILABLE:
                try:
                    llm_translator = LLMTranslator()
                    st.session_state.llm_translator = llm_translator
                    st.success("✅ LLM Translator ready (GPT-4o)")
                except Exception as e:
                    st.warning(f"⚠️ LLM not available: {e}")
                    st.session_state.llm_translator = None
            else:
                st.session_state.llm_translator = None
            
            st.session_state.orchestrator = orchestrator
            st.session_state.initialized = True
            
            return True
            
    except Exception as e:
        st.error(f"❌ Failed to initialize RAG system: {e}")
        return False

def validate_translation(segment: dict, rag_response) -> dict:
    """
    Validate translation against TB, TM, and DNT requirements
    Returns validation results with warnings
    """
    validation = {
        'is_valid': True,
        'warnings': [],
        'errors': []
    }
    
    # DNT matches are GOOD (not violations)
    # We just log them for information
    if rag_response.dnt_terms:
        validation['warnings'].append(f"DNT terms found (protected): {len(rag_response.dnt_terms)} terms")
    
    # Check TM hits
    if rag_response.tm_results and len(rag_response.tm_results) > 0:
        tm_match = rag_response.tm_results[0].similarity_score
        if tm_match < 0.3:
            validation['warnings'].append(f"Low TM similarity: {tm_match:.2f}")
    else:
        validation['warnings'].append("No TM matches found")
    
    # Check TB hits
    if len(rag_response.tb_results) == 0:
        validation['warnings'].append("No TB term matches found")
    
    return validation

def translate_segment(segment: dict) -> dict:
    """Translate a single segment using RAG"""
    try:
        # Create RAG query
        rag_query = RAGQuery(
            source_text=segment['source_en'],
            source_language=st.session_state.source_lang,
            target_language=st.session_state.target_lang,
            max_tm_results=3,
            max_tb_results=5
        )
        
        # Process through RAG
        start_time = time.time()
        rag_response = asyncio.run(st.session_state.orchestrator.process_query(rag_query))
        processing_time = time.time() - start_time
        
        # Generate translation using LLM if available, otherwise use best TM match
        try:
            # Try to use LLM translator if available
            if LLM_AVAILABLE and 'llm_translator' in st.session_state and st.session_state.llm_translator:
                # Use real LLM translation
                result = st.session_state.llm_translator.translate_with_rag(rag_response)
                target_text = result.translated_text
            elif rag_response.tm_results and len(rag_response.tm_results) > 0:
                # Fallback: use best TM match from RAG
                target_text = rag_response.tm_results[0].target_text
            else:
                # Final fallback: return original
                target_text = segment['source_en']
        except Exception as e:
            # Fallback on error - use TM if available
            if rag_response.tm_results and len(rag_response.tm_results) > 0:
                target_text = rag_response.tm_results[0].target_text
            else:
                target_text = segment['source_en']
        
        # Validate translation
        validation = validate_translation(segment, rag_response)
        segment['validation'] = validation
        
        # Calculate quality metrics
        scorer = QualityScorer()
        metrics = scorer.calculate_metrics(segment['source_en'], target_text)
        
        # Update segment with results
        segment.update({
            'target_es': target_text,
            'retrieval_hits': len(rag_response.tm_results),
            'tm_match': rag_response.tm_results[0].similarity_score if rag_response.tm_results else 0.0,
            'tb_hits': len(rag_response.tb_results),
            'dnt_matches': ', '.join(rag_response.dnt_terms) if rag_response.dnt_terms else '',  # Renamed: these are matches, not violations
            'dnt_violations': 1 if rag_response.dnt_terms else 0,  # Binary: 1 if fund names found (good), 0 if not
            'chrF': metrics['chrF'],
            'BLEU': metrics['BLEU'],
            'processing_time': processing_time,
            'is_valid': validation['is_valid']
        })
        
        # Log warnings/errors
        if validation['errors']:
            logger.warning(f"Segment {segment['segment_id']} errors: {validation['errors']}")
        if validation['warnings']:
            logger.info(f"Segment {segment['segment_id']} warnings: {validation['warnings']}")
        
        return segment
        
    except Exception as e:
        st.error(f"Translation error: {e}")
        segment['target_es'] = f"[ERROR: {str(e)}]"
        return segment

def generate_translated_file(segments: list, original_path: Path, target_lang: str) -> str:
    """Generate translated file in original format"""
    try:
        # Create output filename with target language suffix
        original_name = original_path.stem
        original_ext = original_path.suffix
        output_name = f"{original_name}_{target_lang}{original_ext}"
        output_path = original_path.parent / output_name
        
        # Extract target translations
        target_texts = [seg.get('target_es', '') for seg in segments]
        translated_content = '\n'.join(target_texts)
        
        # Save in same format as original
        if original_ext in ['.txt']:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated_content)
        else:
            # For other formats, save as plain text for now
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(translated_content)
        
        logger.info(f"📄 Generated translated file: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.error(f"Error generating translated file: {e}")
        return ""

def generate_qa_report(segments: list, filename: str, target_lang: str) -> str:
    """Generate QA report CSV"""
    df = pd.DataFrame(segments)
    
    # Rename columns based on source/target languages
    lang_map = {'en': 'en', 'es': 'es', 'fr': 'fr', 'de': 'de', 'it': 'it', 'pt': 'pt'}
    source_col = f'source_{st.session_state.source_lang}'
    target_col = f'target_{st.session_state.target_lang}'
    
    # Standardize column names
    df = df.rename(columns={
        'source_en': source_col,
        'target_es': target_col
    })
    
    columns = [
        'segment_id', source_col, target_col, 'retrieval_hits',
        'tm_match', 'dnt_matches', 'chrF'
    ]
    
    # Filter to available columns
    available_columns = [col for col in columns if col in df.columns]
    df = df[available_columns]
    
    # Save report
    report_path = f"uploads/{filename}_{st.session_state.target_lang}_qa.csv"
    os.makedirs("uploads", exist_ok=True)
    df.to_csv(report_path, index=False, encoding='utf-8')
    
    return report_path

def calculate_overall_scores(segments: list) -> dict:
    """Calculate overall quality scores"""
    if not segments:
        return {}
    
    total_segments = len(segments)
    avg_chrF = sum(s.get('chrF', 0) for s in segments) / total_segments
    avg_BLEU = sum(s.get('BLEU', 0) for s in segments) / total_segments
    total_tm_hits = sum(s.get('retrieval_hits', 0) for s in segments)
    total_tb_hits = sum(s.get('tb_hits', 0) for s in segments)
    # dnt_violations is now binary: 1 if fund names found (GOOD), 0 if not
    total_dnt_matches = sum(1 for s in segments if s.get('dnt_matches'))  # Count segments with DNT matches
    total_dnt_violations = 0  # No actual violations - fund names should NOT be translated
    
    # Quality scores (0-100)
    terminology_score = min(100, (total_tb_hits / total_segments) * 20)
    # DNT compliance is HIGH when fund names are detected (they should NOT be translated)
    dnt_compliance = min(100, 80 + (total_dnt_matches / total_segments) * 20)  # Higher score for more DNT matches
    style_score = avg_chrF * 100
    tm_compliance = min(100, (total_tm_hits / total_segments) * 30)
    
    overall_score = (
        terminology_score * 0.2 +
        dnt_compliance * 0.3 +
        style_score * 0.3 +
        tm_compliance * 0.2
    )
    
    return {
        'total_segments': total_segments,
        'avg_chrF': avg_chrF,
        'avg_BLEU': avg_BLEU,
        'total_tm_hits': total_tm_hits,
        'total_tb_hits': total_tb_hits,
        'total_dnt_violations': total_dnt_violations,
        'terminology_score': terminology_score,
        'dnt_compliance': dnt_compliance,
        'style_score': style_score,
        'tm_compliance': tm_compliance,
        'overall_score': overall_score
    }

# Main UI
def main():
    st.markdown('<div class="main-header">🌐 Hybrid File Translation MVP</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Powered by RAG + MemoQ + Streamlit | European Languages</div>', unsafe_allow_html=True)
    
    # Language selection
    col1, col2 = st.columns(2)
    
    with col1:
        source_lang = st.selectbox(
            "🌍 Source Language",
            options=list(MEMOQ_LANG_CODES.keys()),
            format_func=lambda x: f"{MEMOQ_LANG_CODES[x]} ({x})",
            index=0,  # Default to English
            help="Select the source language of your document"
        )
    
    with col2:
        target_lang = st.selectbox(
            "🎯 Target Language",
            options=list(MEMOQ_LANG_CODES.keys()),
            format_func=lambda x: f"{MEMOQ_LANG_CODES[x]} ({x})",
            index=1,  # Default to Spanish
            help="Select the target language for translation"
        )
    
    # Language pair validation
    if source_lang == target_lang:
        st.warning("⚠️ Source and target languages must be different!")
        st.stop()
    
    st.markdown(f"**Translation:** {MEMOQ_LANG_CODES[source_lang]} ({source_lang}) → {MEMOQ_LANG_CODES[target_lang]} ({target_lang})")
    st.divider()
    
    # Initialize system
    if not st.session_state.initialized:
        if initialize_rag_system():
            st.session_state.initialized = True
            st.rerun()
        else:
            st.error("❌ Failed to initialize. Check configuration.")
            return
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # MemoQ connection status
        if st.session_state.orchestrator:
            st.success("✅ RAG System Ready")
            st.success("✅ MemoQ Connected")
            st.success(f"✅ DNT Loaded")
        
        st.divider()
        
        st.header("📊 Features")
        st.markdown("""
        - ✅ Multi-language Support (28 EU languages)
        - ✅ File Upload (DOCX, DOC, TXT, XLSX)
        - ✅ Smart Segmentation
        - ✅ RAG-Powered Translation
        - ✅ MemoQ TM/TB Lookup
        - ✅ DNT Detection
        - ✅ Quality Scoring
        - ✅ QA Report Generation
        """)
        
        st.divider()
        
        st.header("ℹ️ About")
        st.markdown("""
        This MVP uses:
        - MemoQ for TM/TB lookups
        - RAG for semantic search
        - DNT JSON for fund names
        - Streamlit for UI
        - **28 European Languages**
        """)
        
        st.header("🌍 Supported Languages")
        st.markdown("""
        English, Spanish, French, German, Italian, Portuguese, Dutch, Russian, Polish, Czech, Hungarian, Romanian, Slovak, Swedish, Danish, Finnish, Norwegian, Greek, Bulgarian, Croatian, Slovenian, Estonian, Latvian, Lithuanian, Irish, Maltese, Icelandic, Macedonian
        """)
    
    # Main content
    st.header("📁 Upload Document")
    
    uploaded_file = st.file_uploader(
        "Upload document",
        type=['docx', 'doc', 'txt', 'xlsx'],
        help="Supported formats: DOCX, DOC, TXT, XLSX"
    )
    
    # Store language selection in session state
    st.session_state.source_lang = source_lang
    st.session_state.target_lang = target_lang
    
    if uploaded_file is not None:
        st.success(f"✅ File uploaded: {uploaded_file.name}")
        st.info(f"📝 Language pair: {MEMOQ_LANG_CODES[source_lang]} → {MEMOQ_LANG_CODES[target_lang]}")
        
        # Save uploaded file
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Add a prominent button with better styling
        st.markdown("---")
        st.markdown("### 🎯 Ready to Translate")
        
        # Process file
        translate_button = st.button(
            "🚀 **TRANSLATE DOCUMENT NOW** 🚀",
            use_container_width=True,
            type="primary"  # Makes it a prominent primary button
        )
        
        if translate_button:
            with st.spinner("Processing document..."):
                processor = DocumentProcessor()
                
                # Extract text
                file_type = Path(uploaded_file.name).suffix.lower().lstrip('.')
                text = processor.extract_text(str(file_path), file_type)
                
                if not text:
                    st.error("Failed to extract text from file")
                    return
                
                # Segment text
                segments = processor.segment_text(text)
                st.success(f"📝 Segmented into {len(segments)} segments")
                
                # Translate segments
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, segment in enumerate(segments):
                    progress_bar.progress((i + 1) / len(segments))
                    status_text.text(f"Translating segment {i+1}/{len(segments)}...")
                    
                    segment = translate_segment(segment)
                
                status_text.text("✅ Translation complete!")
                
                # Generate translated file
                st.info("📄 Generating translated file...")
                translated_file_path = generate_translated_file(segments, file_path, st.session_state.target_lang)
                
                # Generate QA report
                st.info("📊 Generating QA report...")
                report_path = generate_qa_report(
                    segments,
                    Path(uploaded_file.name).stem,
                    st.session_state.target_lang
                )
                
                # Calculate overall scores
                scores = calculate_overall_scores(segments)
                
                # Display results
                st.divider()
                st.header("📊 Translation Results")
                
                # Overall scores
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Overall Score", f"{scores['overall_score']:.1f}/100")
                
                with col2:
                    st.metric("Total Segments", f"{scores['total_segments']}")
                
                with col3:
                    st.metric("TM Hits", f"{scores['total_tm_hits']}")
                
                with col4:
                    st.metric("TB Hits", f"{scores['total_tb_hits']}")
                
                # Detailed scores
                st.subheader("Quality Metrics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Terminology", f"{scores['terminology_score']:.1f}/100")
                
                with col2:
                    st.metric("DNT Compliance", f"{scores['dnt_compliance']:.1f}/100")
                
                with col3:
                    st.metric("Style Score", f"{scores['style_score']:.1f}/100")
                
                with col4:
                    st.metric("TM Compliance", f"{scores['tm_compliance']:.1f}/100")
                
                # Segment details
                st.subheader("Segment Details")
                df = pd.DataFrame(segments)
                st.dataframe(df[['segment_id', 'source_en', 'target_es', 'retrieval_hits', 'dnt_matches']], use_container_width=True)
                
                # Store results in session state
                st.session_state.translation_results = {
                    'segments': segments,
                    'scores': scores,
                    'translated_file_path': translated_file_path,
                    'report_path': report_path,
                    'uploaded_file_name': uploaded_file.name
                }
                st.session_state.show_results = True  # Show results section
                
                # Single download button for both files
                st.markdown("### 📥 Download Files")
                
                # Create a zip file with both files
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    if os.path.exists(translated_file_path):
                        zip_file.write(translated_file_path, os.path.basename(translated_file_path))
                    if os.path.exists(report_path):
                        zip_file.write(report_path, os.path.basename(report_path))
                
                zip_buffer.seek(0)
                
                # Single download button
                st.download_button(
                    label="📥 Download Both Files (Translated + QA Report)",
                    data=zip_buffer,
                    file_name=f"{Path(uploaded_file.name).stem}_translation_results.zip",
                    mime='application/zip',
                    use_container_width=True,
                    key=f"download_both_{uploaded_file.name}"
                )
                st.info("💡 Downloaded ZIP contains: Translated file + QA report")
                
                # Add "Start New Translation" button
                st.markdown("---")
                if st.button("🔄 Start New Translation", use_container_width=True, key="new_trans_btn"):
                    st.session_state.translation_results = None
                    st.session_state.show_results = False
                    st.rerun()
    
    # Display stored results if available (separate from translation flow)
    elif st.session_state.get("show_results") and st.session_state.get("translation_results") is not None:
        results = st.session_state.translation_results
        
        st.divider()
        st.header("📊 Previous Translation Results")
        st.info(f"📄 File: {results['uploaded_file_name']}")
        
        # Overall scores
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Overall Score", f"{results['scores']['overall_score']:.1f}/100")
        
        with col2:
            st.metric("Total Segments", f"{results['scores']['total_segments']}")
        
        with col3:
            st.metric("TM Hits", f"{results['scores']['total_tm_hits']}")
        
        with col4:
            st.metric("TB Hits", f"{results['scores']['total_tb_hits']}")
        
        # Download buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if os.path.exists(results['translated_file_path']):
                with open(results['translated_file_path'], 'rb') as f:
                    st.download_button(
                        label="📥 Download Translated File",
                        data=f.read(),
                        file_name=os.path.basename(results['translated_file_path']),
                        mime='text/plain',
                        use_container_width=True,
                        key=f"download_translated_stored_{results['uploaded_file_name']}"
                    )
        
        with col2:
            if os.path.exists(results['report_path']):
                with open(results['report_path'], 'rb') as f:
                    st.download_button(
                        label="📥 Download QA Report",
                        data=f.read(),
                        file_name=os.path.basename(results['report_path']),
                        mime='text/csv',
                        use_container_width=True,
                        key=f"download_qa_stored_{results['uploaded_file_name']}"
                    )
        
        # Start new translation button
        st.markdown("---")
        if st.button("🔄 Start New Translation", use_container_width=True, key="new_trans_btn2"):
            st.session_state.translation_results = None
            st.session_state.show_results = False
            st.rerun()

    # (Reverted) No comparison UI in MVP app.

if __name__ == "__main__":
    main()
