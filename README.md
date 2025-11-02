# Finance RAG Translation System

AI-powered translation system combining RAG (Retrieval-Augmented Generation) with Translation Memory (TM), Termbase (TB), and Do-Not-Translate (DNT) rules for high-quality financial document translation.

## 🎯 Overview

This system provides English-to-Spanish translation for financial documents using a hybrid approach that combines:
- **Translation Memory (TM)**: Dense vector retrieval using Sentence Transformers + FAISS
- **Termbase (TB)**: Live terminology lookup from MemoQ API
- **DNT Rules**: Fund name and entity preservation
- **LLM Translation**: GPT-4o for final translation with RAG context

## ✨ Key Features

- **Hybrid MVP Web Application**: Streamlined interface for document translation
- **RAG vs DeepL Comparison Tool**: Analyze translation quality metrics
- **Advanced Vector Search**: Fast semantic TM retrieval with CPU/GPU support
- **Quality Scoring**: Multi-dimensional evaluation (Terminology, DNT Compliance, Style, TM Match)
- **Fund Name Preservation**: Automatic detection and preservation of financial entities
- **Batch Processing**: Handle multiple documents efficiently

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key (for GPT-4o)
- MemoQ server credentials (for TB lookup)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Sarita2025-bot/aipm_llms_translate.git
cd aipm_llms_translate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file with:
```
OPENAI_API_KEY=your_api_key_here
MEMOQ_SERVER_URL=your_memoq_server_url
MEMOQ_USERNAME=your_username
MEMOQ_PASSWORD=your_password
```

4. Prepare data files:
- Place TM data in `data/en-es_sample_30k.csv`
- Place DNT rules in `data/SV_Test_Fund_names2.json`

### Running the Application

**Option 1: Hybrid MVP Web Application**
```bash
python run_hybrid_mvp.py
```
Then open http://localhost:8501 in your browser.

**Option 2: Direct Python Script**
```bash
python hybrid_mvp_app.py
```

## 📊 Comparison Tool

Compare RAG translations against DeepL to analyze quality metrics:

```bash
python compare_translations.py
```

This generates:
- `comparisons/*_per_segment.csv` - Detailed segment-by-segment comparison
- `comparisons/*_summary.csv` - Overall quality scores
- `comparisons/*_rag_highlights.docx` - Visual comparison document highlighting RAG advantages

### Metrics Analyzed

- **TM Hits**: Number and quality of translation memory matches
- **TB Hits**: Terminology coverage from termbase
- **DNT Matches**: Fund names and entities correctly preserved
- **chrF Score**: Character n-gram F-score for translation quality
- **Overall Score**: Weighted combination of all metrics

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Input (EN)                      │
└─────────────────────┬───────────────────────────────────┘
                      │
         ┌────────────▼────────────┐
         │   RAG Orchestrator      │
         └────────┬────────────────┘
                  │
     ┌────────────┼────────────┐
     │            │            │
┌────▼─────┐ ┌───▼────┐  ┌───▼─────┐
│ TM Index │ │   TB   │  │   DNT   │
│ (Vector) │ │ (Live) │  │ (Local) │
└────┬─────┘ └───┬────┘  └───┬─────┘
     │           │           │
     └───────────┼───────────┘
                 │
         ┌───────▼───────┐
         │ LLM Translator│
         │   (GPT-4o)    │
         └───────┬───────┘
                 │
         ┌───────▼───────┐
         │  Translation  │
         │     (ES)      │
         └───────────────┘
```

## 📁 Project Structure

```
aipm_llms_translate/
├── hybrid_mvp_app.py          # Main Streamlit web application
├── run_hybrid_mvp.py          # Application runner script
├── rag_orchestrator.py        # Core RAG coordination logic
├── llm_translator.py          # OpenAI GPT-4o integration
├── vector_index.py            # TM vector search (FAISS)
├── non_trans_loader.py        # DNT rules loader
├── memoq_client.py            # MemoQ API client
├── compare_translations.py    # RAG vs DeepL comparison tool
├── test_hybrid_mvp.py         # Unit tests
├── requirements.txt           # Python dependencies
├── data/                      # Training data and resources
│   ├── en-es_sample_30k.csv  # TM pairs
│   └── SV_Test_Fund_names2.json  # DNT rules
└── models/                    # Vector index models (gitignored)
```

## 🧪 Testing

Run the test suite:
```bash
pytest test_hybrid_mvp.py -v
```

Run service tests:
```bash
python test_mvp_service.py
```

## 📈 Quality Scoring

The system uses a multi-dimensional scoring approach:

| Metric | Weight | Description |
|--------|--------|-------------|
| **Terminology Score** | 20% | TB term coverage |
| **DNT Compliance** | 30% | Fund name preservation |
| **Style Score** | 30% | Translation quality (chrF) |
| **TM Compliance** | 20% | TM match utilization |

**Overall Score** = Weighted average of all metrics (0-100)

See `SCORING_EXPLAINED.md` for detailed methodology.

## 🔧 Configuration

### Vector Index Settings
- **Model**: `all-MiniLM-L6-v2` (384-dim embeddings)
- **Similarity Threshold**: 0.3
- **Max Results**: 3 TM matches per query

### LLM Settings
- **Model**: GPT-4o
- **Temperature**: 0 (deterministic)
- **Max Tokens**: 2000

### Translation Memory
- **Format**: CSV with `source` and `target` columns
- **Size**: 30,000 EN-ES pairs
- **Domain**: Financial documents

## 📚 Documentation

- **HYBRID_MVP_READY.md** - Complete MVP feature documentation
- **SCORING_EXPLAINED.md** - Detailed scoring methodology
- **env_template.txt** - Environment variable template

## 🤝 Contributing

This is a bootcamp project. For questions or suggestions, please open an issue.

## 📝 License

This project is part of an AI Product Management bootcamp final project.

## 🙏 Acknowledgments

- OpenAI for GPT-4o
- Sentence Transformers for embedding models
- FAISS for efficient vector search
- MemoQ for translation management integration

---

**Version**: 1.0.0  
**Last Updated**: November 2024  
**Author**: Sarita2025-bot

