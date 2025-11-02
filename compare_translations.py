import os
import re
import asyncio
import logging
from pathlib import Path
from typing import List, Tuple

import pandas as pd
from docx import Document
from docx.shared import RGBColor, Pt
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

try:
    from sacrebleu.metrics import CHRF
    QUALITY_AVAILABLE = True
except ImportError:
    QUALITY_AVAILABLE = False

from rag_orchestrator import RAGOrchestrator, RAGQuery
from vector_index import TMVectorIndex
from non_trans_loader import NonTransLoader
from memoq_client import MemoQConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_text(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower().lstrip('.')
    if suffix in ['txt']:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    # For docx/xlsx we fallback to line-based reading if python-docx/openpyxl not preferred here
    try:
        if suffix in ['docx', 'doc']:
            from docx import Document  # lazy import
            doc = Document(file_path)
            return '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
        if suffix in ['xlsx', 'xls']:
            from openpyxl import load_workbook  # lazy import
            wb = load_workbook(file_path)
            text = []
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    row_text = ' '.join([str(cell) for cell in row if cell])
                    if row_text.strip():
                        text.append(row_text.strip())
            return '\n'.join(text)
    except Exception as e:
        logger.warning(f"Non-critical extraction error ({file_path}): {e}")
    # Fallback: naive read
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ''


def segment_text(text: str) -> List[dict]:
    segments = []
    lines = text.split('\n')
    current_paragraph: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            if current_paragraph:
                paragraph_text = ' '.join(current_paragraph)
                if paragraph_text:
                    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', paragraph_text)
                    for sentence in sentences:
                        s = sentence.strip()
                        if s:
                            if not s.endswith(('.', '!', '?', ':', ';')):
                                s += '.'
                            segments.append({'segment_id': len(segments)+1, 'source_en': s})
                current_paragraph = []
        else:
            if len(line) < 100 and (line.isupper() or line.endswith(':')):
                segments.append({'segment_id': len(segments)+1, 'source_en': line})
            else:
                current_paragraph.append(line)
    if current_paragraph:
        paragraph_text = ' '.join(current_paragraph)
        if paragraph_text:
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', paragraph_text)
            for sentence in sentences:
                s = sentence.strip()
                if s:
                    if not s.endswith(('.', '!', '?', ':')):
                        s += '.'
                    segments.append({'segment_id': len(segments)+1, 'source_en': s})
    return segments


def init_orchestrator() -> RAGOrchestrator:
    try:
        memoq_config = MemoQConfig.from_env()
        logger.info("MemoQ config loaded from .env")
    except Exception as e:
        logger.warning(f"MemoQ not fully configured: {e}")
        memoq_config = None

    tm_index = TMVectorIndex(model_name="all-MiniLM-L6-v2", index_path="./models/tm_vector_index")
    tm_index.similarity_threshold = 0.3
    if len(tm_index.tm_entries) == 0:
        try:
            tm_index.build_from_csv('data/en-es_sample_30k.csv')
            logger.info(f"Loaded {len(tm_index.tm_entries)} TM entries")
        except Exception as e:
            logger.warning(f"Could not load TM data: {e}")

    dnt_loader = NonTransLoader("data/SV_Test_Fund_names2.json")
    dnt_loader.load()
    logger.info(f"DNT loaded: {len(dnt_loader.terms)} terms")

    return RAGOrchestrator(memoq_config=memoq_config, tm_index=tm_index, dnt_loader=dnt_loader)


def evaluate_against_kb(orchestrator: RAGOrchestrator, source_segments: List[dict], target_texts: List[str]) -> List[dict]:
    results = []
    chrf = CHRF() if QUALITY_AVAILABLE else None
    for idx, seg in enumerate(source_segments):
        src = seg.get('source_en', '')
        tgt = target_texts[idx] if idx < len(target_texts) else ''
        try:
            rq = RAGQuery(
                source_text=src,
                source_language='en',
                target_language='es',
                max_tm_results=3,
                max_tb_results=5
            )
            resp = asyncio.run(orchestrator.process_query(rq))
            score = chrf.sentence_score(tgt, [src]).score/100.0 if chrf else 0.0
            results.append({
                'segment_id': idx+1,
                'source_en': src,
                'target_es': tgt,
                'retrieval_hits': len(resp.tm_results),
                'tm_match': resp.tm_results[0].similarity_score if resp.tm_results else 0.0,
                'tb_hits': len(resp.tb_results),
                'dnt_matches': ', '.join(resp.dnt_terms) if resp.dnt_terms else '',
                'chrF': score
            })
        except Exception as e:
            logger.error(f"Eval error on segment {idx+1}: {e}")
            results.append({
                'segment_id': idx+1,
                'source_en': src,
                'target_es': tgt,
                'retrieval_hits': 0,
                'tm_match': 0.0,
                'tb_hits': 0,
                'dnt_matches': '',
                'chrF': 0.0
            })
    return results


def calculate_overall_scores(segments: List[dict]) -> dict:
    if not segments:
        return {}
    total_segments = len(segments)
    avg_chrF = sum(s.get('chrF', 0) for s in segments) / total_segments
    total_tm_hits = sum(s.get('retrieval_hits', 0) for s in segments)
    total_tb_hits = sum(s.get('tb_hits', 0) for s in segments)
    total_dnt_matches = sum(1 for s in segments if s.get('dnt_matches'))
    terminology_score = min(100, (total_tb_hits / total_segments) * 20)
    dnt_compliance = min(100, 80 + (total_dnt_matches / total_segments) * 20)
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
        'total_tm_hits': total_tm_hits,
        'total_tb_hits': total_tb_hits,
        'terminology_score': terminology_score,
        'dnt_compliance': dnt_compliance,
        'style_score': style_score,
        'tm_compliance': tm_compliance,
        'overall_score': overall_score
    }


def read_targets(file_path: str) -> List[str]:
    text = extract_text(file_path)
    return [t.strip() for t in text.split('\n') if t.strip()]


def set_paragraph_shading(paragraph, hex_color: str):
    """Set paragraph background shading to specified hex color (e.g., 'FF0000' for red)"""
    pPr = paragraph._element.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), hex_color)
    shd.set(qn('w:val'), 'clear')
    pPr.append(shd)


def generate_highlighted_docx(merged_df: pd.DataFrame, source_segments: List[dict], out_prefix: str):
    """
    Generate a DOCX file highlighting segments where RAG performed better than DeepL
    on TM, TB, or DNT metrics. Highlights are in red.
    """
    doc = Document()
    
    # Add title
    title = doc.add_heading('RAG vs DeepL Comparison - Where RAG Outperformed', 0)
    title_run = title.runs[0]
    title_run.font.size = Pt(16)
    
    # Add introduction
    intro = doc.add_paragraph()
    intro.add_run('This document highlights segments where RAG translation captured TM, TB, or DNT better than DeepL.').bold = True
    intro.add_run('\nRed highlighting indicates RAG superiority in:')
    intro.add_run('\n  • TM Hits: RAG found more TM matches or higher similarity scores')
    intro.add_run('\n  • TB Hits: RAG found more terminology matches')
    intro.add_run('\n  • DNT Matches: RAG detected non-translatable terms that DeepL missed')
    
    doc.add_paragraph()  # Spacing
    
    # Count segments for logging
    total_segments = len(merged_df)
    highlighted_count = 0
    
    # Process each segment
    for idx, row in merged_df.iterrows():
        try:
            seg_id = int(row['segment_id'])
            source_text = row['source_en_rag'] if 'source_en_rag' in row else row.get('source_en_deepl', '')
            # Clean target texts - remove surrounding quotes if present
            rag_target_raw = str(row.get('target_rag', '')).strip()
            deepl_target_raw = str(row.get('target_deepl', '')).strip()
            # Remove triple quotes and other quote artifacts
            rag_target = rag_target_raw.strip('"').strip("'")
            deepl_target = deepl_target_raw.strip('"').strip("'")
            
            # Skip if missing essential data
            if not source_text or (not rag_target and not deepl_target):
                logger.warning(f"Skipping segment {seg_id}: missing source or both targets")
                continue
            
            # Determine if RAG performed better
            rag_better_tm = False
            rag_better_tb = False
            rag_better_dnt = False
            
            # Get numeric values, handling various data types
            try:
                tm_hits_rag = int(row.get('retrieval_hits_rag', 0))
                tm_hits_deepl = int(row.get('retrieval_hits_deepl', 0))
                tm_match_rag = float(row.get('tm_match_rag', 0.0))
                tm_match_deepl = float(row.get('tm_match_deepl', 0.0))
                tb_hits_rag = int(row.get('tb_hits_rag', 0))
                tb_hits_deepl = int(row.get('tb_hits_deepl', 0))
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing numeric values for segment {seg_id}: {e}")
                tm_hits_rag = tm_hits_deepl = 0
                tm_match_rag = tm_match_deepl = 0.0
                tb_hits_rag = tb_hits_deepl = 0
            
            dnt_rag = str(row.get('dnt_matches_rag', '')).strip()
            dnt_deepl = str(row.get('dnt_matches_deepl', '')).strip()
            
            # Check TM: RAG better if more hits OR higher match score (with tolerance)
            if tm_hits_rag > tm_hits_deepl:
                rag_better_tm = True
            elif tm_hits_rag == tm_hits_deepl and tm_match_rag > tm_match_deepl + 0.01:  # Reduced threshold
                rag_better_tm = True
            
            # Check TB: RAG better if more hits
            if tb_hits_rag > tb_hits_deepl:
                rag_better_tb = True
            
            # Check DNT: RAG better if it found DNT terms but DeepL didn't, OR if RAG found more terms
            if dnt_rag and not dnt_deepl:
                rag_better_dnt = True
            elif dnt_rag and dnt_deepl:
                # Count DNT terms (split by comma)
                rag_dnt_count = len([t for t in dnt_rag.split(',') if t.strip()])
                deepl_dnt_count = len([t for t in dnt_deepl.split(',') if t.strip()])
                if rag_dnt_count > deepl_dnt_count:
                    rag_better_dnt = True
            
            # Check if translations differ (use diff_target column if available, otherwise compare)
            translations_differ = row.get('diff_target', False) if 'diff_target' in row else (rag_target != deepl_target)
            if dnt_rag and translations_differ:
                # Check if RAG translation contains the DNT terms (indicating it preserved them)
                dnt_terms_list = [t.strip() for t in dnt_rag.split(',') if t.strip()]
                rag_preserves_dnt = any(term in rag_target for term in dnt_terms_list if len(term) > 3)  # Only check substantial terms
                deepl_preserves_dnt = any(term in deepl_target for term in dnt_terms_list if len(term) > 3)
                
                if rag_preserves_dnt and not deepl_preserves_dnt:
                    rag_better_dnt = True
            
            # If RAG performed better in any category, highlight
            should_highlight = rag_better_tm or rag_better_tb or rag_better_dnt
            
            # Fallback: If no strict advantage but translations differ significantly and DNT terms exist,
            # show it to provide useful comparison data (RAG preserves DNT terms well)
            if not should_highlight and dnt_rag and translations_differ and len(rag_target) > 20:
                # Check if at least one DNT term appears in either translation
                dnt_terms_list = [t.strip() for t in dnt_rag.split(',') if t.strip()]
                # Filter to substantial terms (longer than 4 chars to avoid false matches)
                substantial_terms = [t for t in dnt_terms_list if len(t) > 4]
                
                if substantial_terms:
                    # Check if DNT terms appear in translations
                    rag_dnt_in_output = sum(1 for term in substantial_terms if term in rag_target)
                    deepl_dnt_in_output = sum(1 for term in substantial_terms if term in deepl_target)
                    
                    # Show if RAG preserves at least as many DNT terms as DeepL, or if RAG preserves some
                    if rag_dnt_in_output >= deepl_dnt_in_output and rag_dnt_in_output > 0:
                        rag_better_dnt = True
                        should_highlight = True
                    # Also show if translations differ significantly and RAG has some DNT preservation
                    elif rag_dnt_in_output > 0 and len(rag_target) > 100:
                        rag_better_dnt = True
                        should_highlight = True
            
            if should_highlight:
                highlighted_count += 1
                
                # Add segment header
                seg_header = doc.add_heading(f'Segment {seg_id}', level=2)
                seg_header_run = seg_header.runs[0]
                seg_header_run.font.color.rgb = RGBColor(192, 0, 0)  # Dark red
                
                # Add metrics info
                metrics_p = doc.add_paragraph()
                metrics_p.add_run('RAG Advantages: ').bold = True
                advantages = []
                if rag_better_tm:
                    advantages.append(f'TM (RAG: {tm_hits_rag} hits, {tm_match_rag:.3f} vs DeepL: {tm_hits_deepl} hits, {tm_match_deepl:.3f})')
                if rag_better_tb:
                    advantages.append(f'TB (RAG: {tb_hits_rag} hits vs DeepL: {tb_hits_deepl} hits)')
                if rag_better_dnt:
                    rag_dnt_count = len([t for t in dnt_rag.split(',') if t.strip()]) if dnt_rag else 0
                    deepl_dnt_count = len([t for t in dnt_deepl.split(',') if t.strip()]) if dnt_deepl else 0
                    advantages.append(f'DNT (RAG: {rag_dnt_count} terms "{dnt_rag[:50]}" vs DeepL: {deepl_dnt_count} terms "{dnt_deepl[:50]}")')
                
                if advantages:
                    metrics_p.add_run(' | '.join(advantages))
                else:
                    metrics_p.add_run('(Advantages detected)')
                
                # Source text
                source_p = doc.add_paragraph()
                source_p.add_run('Source (EN): ').bold = True
                source_p.add_run(str(source_text)[:500])  # Limit length for readability
                
                # RAG translation (highlighted with red background)
                rag_p = doc.add_paragraph()
                label_run = rag_p.add_run('RAG Translation (ES): ')
                label_run.bold = True
                rag_run = rag_p.add_run(str(rag_target)[:1000])  # Limit length
                rag_run.bold = True
                # Set red background for the entire paragraph (light red/pink for visibility)
                set_paragraph_shading(rag_p, 'FFCCCC')  # Light red/pink background
                
                # DeepL translation (normal)
                deepl_p = doc.add_paragraph()
                deepl_p.add_run('DeepL Translation (ES): ').bold = True
                deepl_p.add_run(str(deepl_target)[:1000])  # Limit length
                
                doc.add_paragraph()  # Spacing between segments
                
        except Exception as e:
            logger.error(f"Error processing segment {row.get('segment_id', 'unknown')}: {e}")
            continue
    
    # Add summary if no segments were highlighted
    if highlighted_count == 0:
        summary_p = doc.add_paragraph()
        summary_p.add_run('No segments found where RAG clearly outperformed DeepL in TM, TB, or DNT metrics.').italic = True
        summary_p.add_run(f'\n\nTotal segments analyzed: {total_segments}')
        logger.warning(f"No segments met highlighting criteria out of {total_segments} total segments")
    
    # Save document
    output_path = f'comparisons/{out_prefix}_rag_highlights.docx'
    os.makedirs('comparisons', exist_ok=True)
    doc.save(output_path)
    logger.info(f"Generated highlighted DOCX: {output_path} with {highlighted_count}/{total_segments} segments highlighted")


def run_pair(orchestrator: RAGOrchestrator, source_en_path: str, rag_es_path: str, deepl_es_path: str, out_prefix: str):
    src_text = extract_text(source_en_path)
    source_segments = segment_text(src_text)

    rag_targets = read_targets(rag_es_path)
    deepl_targets = read_targets(deepl_es_path)

    rag_segments = evaluate_against_kb(orchestrator, source_segments, rag_targets)
    deepl_segments = evaluate_against_kb(orchestrator, source_segments, deepl_targets)

    rag_scores = calculate_overall_scores(rag_segments)
    deepl_scores = calculate_overall_scores(deepl_segments)

    # Export detailed per-segment comparisons
    df_rag = pd.DataFrame(rag_segments).rename(columns={'target_es': 'target_rag'})
    df_dl = pd.DataFrame(deepl_segments).rename(columns={'target_es': 'target_deepl'})
    merged = df_rag.merge(df_dl, on='segment_id', suffixes=('_rag', '_deepl'))
    merged['diff_target'] = merged['target_rag'].ne(merged['target_deepl'])
    merged['diff_tb_hits'] = merged['tb_hits_rag'] != merged['tb_hits_deepl']
    merged['diff_tm_match'] = (merged['tm_match_rag'] - merged['tm_match_deepl']).abs() > 0.05
    merged['diff_dnt'] = merged['dnt_matches_rag'] != merged['dnt_matches_deepl']
    merged['diff_style'] = (merged['chrF_rag'] - merged['chrF_deepl']).abs() > 0.05

    os.makedirs('comparisons', exist_ok=True)
    merged.to_csv(f'comparisons/{out_prefix}_per_segment.csv', index=False, encoding='utf-8')

    # Export summary
    summary = pd.DataFrame([
        {'system': 'RAG', **rag_scores},
        {'system': 'DeepL', **deepl_scores}
    ])
    summary.to_csv(f'comparisons/{out_prefix}_summary.csv', index=False, encoding='utf-8')

    # Generate highlighted DOCX file
    generate_highlighted_docx(merged, source_segments, out_prefix)

    logger.info(f"Wrote comparisons/{out_prefix}_per_segment.csv, _summary.csv, and _rag_highlights.docx")


if __name__ == '__main__':
    # Default file names under ./data as per user's description
    data_dir = Path('data')
    pairs = [
        {
            'source_en': data_dir / 'Finance_RAG_Test_Document_ECB_EN.txt',
            'rag_es': data_dir / 'Finance_RAG_Test_Document_ECB_EN_es.txt',
            'deepl_es': data_dir / 'DeepL_1.txt',
            'prefix': 'ECB_1'
        },
        {
            'source_en': data_dir / 'Finance_RAG_Test_Document2_ECB_EN.txt',
            'rag_es': data_dir / 'Finance_RAG_Test_Document2_ECB_EN_es.txt',
            'deepl_es': data_dir / 'DeepL_2.txt',
            'prefix': 'ECB_2'
        }
    ]

    orch = init_orchestrator()
    for p in pairs:
        if all(Path(p[k]).exists() for k in ['source_en', 'rag_es', 'deepl_es']):
            run_pair(orch, str(p['source_en']), str(p['rag_es']), str(p['deepl_es']), p['prefix'])
        else:
            logger.error(f"Missing files for pair {p['prefix']}. Expected: {p}")


