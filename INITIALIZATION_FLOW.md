# 🔄 Initialization Flow: hybrid_mvp_app.py

## ✅ **What Gets Imported (Lines 31-34):**
```python
from rag_orchestrator import RAGOrchestrator, RAGQuery
from vector_index import TMVectorIndex
from non_trans_loader import NonTransLoader
from memoq_client import MemoQConfig
```

## 📊 **Initialization Order in `initialize_rag_system()`:**

### **Step 1: MemoQ Client** (Lines 265-270) 📞
```python
memoq_config = MemoQConfig.from_env()  # Load from .env file
```
- **File**: `memoq_client.py`
- **Order**: 1️⃣ FIRST
- **Purpose**: MemoQ server connection config
- **Timing**: Sequential

### **Step 2: Vector Index** (Lines 273-288) 📚
```python
tm_index = TMVectorIndex(
    model_name="all-MiniLM-L6-v2",  # Hugging Face model
    index_path="./models/tm_vector_index"
)
# Load TM data if empty
if len(tm_index.tm_entries) == 0:
    tm_index.build_from_csv('data/en-es_sample_30k.csv')
```
- **File**: `vector_index.py`
- **Order**: 2️⃣ SECOND
- **Purpose**: Semantic search (Sentence Transformers + FAISS)
- **Timing**: Sequential
- **Model**: Hugging Face `all-MiniLM-L6-v2` ✅

### **Step 3: DNT Loader** (Lines 291-293) 🚫
```python
dnt_loader = NonTransLoader("data/SV_Test_Fund_names2.json")
dnt_loader.load()
```
- **File**: `non_trans_loader.py`
- **Order**: 3️⃣ THIRD
- **Purpose**: Load non-translatable terms (fund names)
- **Timing**: Sequential

### **Step 4: RAG Orchestrator** (Lines 296-300) 🤖
```python
orchestrator = RAGOrchestrator(
    memoq_config=memoq_config,
    tm_index=tm_index,
    dnt_loader=dnt_loader
)
```
- **File**: `rag_orchestrator.py`
- **Order**: 4️⃣ FOURTH
- **Purpose**: Coordinates all components
- **Timing**: Sequential
- **Creates**: MemoQClient inside (Line 100 in rag_orchestrator.py)

### **Step 5: LLM Translator** (Lines 303-312) 🌟
```python
if LLM_AVAILABLE:
    llm_translator = LLMTranslator()  # GPT-4o
```
- **File**: `llm_translator.py`
- **Order**: 5️⃣ FIFTH
- **Purpose**: OpenAI GPT-4o translation
- **Timing**: Sequential

## 🔄 **Initialization Flow Diagram:**

```
hybrid_mvp_app.py START
        ↓
1️⃣ MemoQConfig.from_env()
        ↓ (uses .env file)
2️⃣ TMVectorIndex() 
        ↓ (Hugging Face model)
3️⃣ NonTransLoader.load()
        ↓ (JSON file)
4️⃣ RAGOrchestrator()
        ↓ (Creates MemoQClient inside)
5️⃣ LLMTranslator() (optional)
        ↓
✅ ALL SYSTEMS INITIALIZED
```

## ⚙️ **Order: SEQUENTIAL (One After Another)**

### **Why Sequential?**
- Each component depends on the previous one
- MemoQ config needed before RAG orchestrator
- Vector index needed before RAG
- DNT needed before RAG
- RAG orchestrator needs all three

### **Not Parallel/Simultaneous Because:**
1. **Dependencies**: RAG needs vector index and DNT ready
2. **Data**: Vector index needs TM data loaded first
3. **Error Handling**: Each step can fail and needs handling
4. **Streamlit**: Shows progress messages sequentially

## 📋 **Detailed Sequence:**

### **At App Startup (First Load):**

1. **User opens app** → Streamlit loads `hybrid_mvp_app.py`
2. **Import statements** (Lines 31-34):
   - Loads `rag_orchestrator.py` module
   - Loads `vector_index.py` module
   - Loads `non_trans_loader.py` module
   - Loads `memoq_client.py` module
3. **Call `initialize_rag_system()`** when UI renders
4. **Sequential initialization**:
   - MemoQ config (1 sec)
   - Vector index + TM data (5-10 sec)
   - DNT loader (1 sec)
   - RAG orchestrator (1 sec)
   - LLM translator (2 sec)
5. **Total**: ~10-15 seconds

## 🔍 **What Each File Does:**

### **memoq_client.py**
- MemoQConfig class (credentials)
- MemoQClient class (API calls)
- ✅ Used in RAG orchestrator

### **vector_index.py**
- TMVectorIndex class
- Sentence Transformer (Hugging Face) ✅
- FAISS vector search
- ✅ Used in RAG orchestrator

### **non_trans_loader.py**
- NonTransLoader class
- Loads fund names from JSON
- ✅ Used in RAG orchestrator

### **rag_orchestrator.py**
- RAGOrchestrator class
- Coordinates all components
- ✅ Uses memoq_client, vector_index, dnt_loader
- ✅ Uses Hugging Face for semantic search ✅

### **llm_translator.py**
- LLMTranslator class
- GPT-4o integration
- ✅ Used for final translation



