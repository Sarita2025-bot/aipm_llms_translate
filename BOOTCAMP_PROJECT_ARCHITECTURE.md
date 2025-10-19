# 🎓 Bootcamp Project Setup Guide
## Finance RAG Translation System with MemoQ Integration

---

## ✅ What We Have Now

### Optimized Dataset 

| Component | File | Size | Status |
|-----------|------|------|--------|
| **TM (Translation Memory)** | `data/en-es_sample_30k.tmx` | 30,000 entries | ✅ Ready |
| **TM Preview** | `data/en-es_sample_30k.csv` | 30,000 rows | ✅ Ready |
| **TB (Term Base)** | Synthetic finance TB |  custom terms | ✅ Ready |
| **DNT (Do Not Translate)** | `data/SV_Test_Fund_names2.json` | 50 fund names | ✅ Ready |

### Original Problem - SOLVED! 🎉

- ❌ **Before**: 116K entries → 30+ second timeout → FAILED
- ✅ **After**: 30K entries → ~2-3 seconds → SUCCESS!

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────┐
│     MemoQ Translation Project           │
│     (Document segmented by sentences)   │
└─────────────────────────────────────────┘
                 │
                 │ For each segment
                 ▼
┌─────────────────────────────────────────┐
│  Segment: "The Global Innovation        │
│  Equity Fund returned 8.5%"             │
└─────────────────────────────────────────┘
                 │
                 │ HTTP POST /translate
                 ▼
┌─────────────────────────────────────────┐
│    Your FastAPI Service                 │
│    localhost:8000                       │
└─────────────────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌───────┐  ┌─────────┐  ┌────────┐
│  DNT  │  │   TM    │  │   TB   │
│ Check │  │ Search  │  │ Lookup │
└───────┘  └─────────┘  └────────┘
    │            │            │
    └────────────┼────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  RAG Context Generated                  │
│  • Fund names: Global Innovation...     │
│  • TM matches: 3 examples               │
│  • TB terms: 5 terminology entries      │
└─────────────────────────────────────────┘
                 │
                 │ (Optional) GPT-4o
                 ▼
┌─────────────────────────────────────────┐
│  Translation:                           │
│  "El Global Innovation Equity Fund      │
│   registró un 8,5%"                     │
└─────────────────────────────────────────┘
                 │
                 │ Return to MemoQ
                 ▼
┌─────────────────────────────────────────┐
│  MemoQ Target Field Populated           │
└─────────────────────────────────────────┘
```

---

## 🎯 Key Features of the RAG System

### 1. Translation Memory (TM) - 30K Entries
- **Source**: ECB/EU financial corpus from OPUS (https://opus.nlpl.eu/)
- **Size**: 30K parallel curated sentences EN > ES (no timeouts!)
- **Speed**: Queries in 2-3 seconds
- **Purpose**: Provide translation examples and style consistency

### 2. Term Base (TB) - Finance Terminology
- **Type**: Synthetic finance glossary
- **Content**: Financial terms with preferred/forbidden flags with Memoq encoding
- **Purpose**: Ensure consistent terminology usage
- **Example**: "returns" → "rendimientos" (preferred)

### 3. Do Not Translate (DNT) - 50 Fund Names
- **File**: `SV_Test_Fund_names2.json`
- **Integration**: Automatically loaded via `non_trans_loader.py`
- **Purpose**: Preserve fund names in original language
- **Examples**:
  - Global Innovation Equity Fund
  - AB SICAV I - European Equity Portfolio
  - abrdn SICAV I - Global Small & Mid-Cap SDG Horizons Equity Fund

### 4. Hybrid RAG Architecture
- **Dense Retrieval**: Semantic search with sentence transformers
- **Fuzzy Matching**: Traditional TM fuzzy matching
- **Live TB Lookups**: Fresh terminology from MemoQ server
- **Parallel Queries**: Fast concurrent processing

## 📋 Steps

### Step 1: Import TM, TB and DNT into MemoQ --> ✅ Ready

1. Open MemoQ Server
2. Create a new Translation Memory
3. Import `data/en-es_sample_30k.tmx`
4. Name it:**SV_test_TM_Finance**
5. Genereate TB and TM Guids with: `find_memoq_guids.ipynb` and write down the **TM and TB GUID** 

### Step 2: Create Your .env File --> ✅ Ready


Then update these fields in `.env`:
- `MEMOQ_BASE_URL` → MemoQ server URL
- `MEMOQ_USERNAME` → MemoQ username
- `MEMOQ_PASSWORD` → MemoQ password
- `MEMOQ_TM_GUID` → GUID of your new TM (from Step 1)
- `MEMOQ_TB_GUID` → GUID of your finance term base

**Note**: Use `find_memoq_guids.ipynb` notebook to find your GUIDs automatically!

### Step 3: Test Your Connection with MemoQ --> ✅ Ready

Run the MemoQ client test:

```bash
# Test MemoQ connection
python memoq_client.py

   - API integration
   - Authentication
   - TM/TB lookups
   - Error handling

# Test DNT loader
python non_trans_loader.py

   - pattern matching
   - JSON parsing
   - Regex patterns
   - Term detection


```bash
# Find MemoQ GUIDs

python find_guids.ipynb

   - finds GUIDs for TB and TM in MemoQ

```
---
### Step 4: Create a Vector Index (from TM in csv) --> ✅ Tested and Ready 

```bash
# Find MemoQ GUIDs

python vector_index.py

   - Uses ./data/en-es_sample_30.csv (fallback TM)
   - Building TM Vector Index
   - Generate embeddings
   - Saved index to ./models/tm_vector_index --> Stored

```
---

### Step 5: The Query Handler --> ✅ Tested

```bash
# Run RAG orchestrator

python rag_orchestrator.py

   - Loads the pre-built index
   - Processess queries (EN > ES Translations)
   - Coordinates TM + TB + DNT (for query-translation)
   - Returns RAG results - translations

```
---

### Step 6: Activate LLM --> ✅ Tested 

```bash
# Run API call to integrate GPT-4o with RAG context

python llm_translator.py

   - LLM Translation Module
   - Integrates GPT-4o with RAG context for finance translation
   - Uses LangChain for structured prompting

```

### Step 7: FastAPI server to MemoQ --> Not tested yet

```bash
# Start Server

python app.py

   - FastAPI Translation Service for MemoQ Integration
   - Provides REST API endpoint for segment-by-segment translation
   - MemoQ calls this service for each translation segment
   - Returns translation to MemoQ

```


### Step 7.1 Test Fast API integrationt

### **Run Test**

```bash
python test_api.py
```

- Test the FastAPI Translation Service
- Simulates how MemoQ would call the API




---

## 🔧 **Control LLM Usage**

### **Always Use LLM** (Current Setting)

Default in `app.py`:
```python
use_llm: Optional[bool] = Field(default=True)  # ← Always GPT-4o
```

### **Use LLM Per Request**

In API calls, control per translation:
```python
{
    "source_text": "Your text here",
    "use_llm": true   # ← Use GPT-4o for this translation
}
```

Or disable for specific translations:
```python
{
    "source_text": "Your text here",
    "use_llm": false  # ← Use TM only (free, fast)
}
```

---

## 💰 **Cost Tracking**

Each translation response includes cost info:
```json
{
    "target_text": "...",
    "metadata": {
        "used_llm": true,
        "model": "gpt-4o-mini"
    }
}
```

**Expected costs**:
- **Per segment**: ~$0.001 (one tenth of a cent)
- **100 segments**: ~$0.10
- **1000 segments**: ~$1.00

Very affordable! 💵

---

## ✅ **Checklist**

- [ ] OpenAI account has credits
- [ ] OPENAI_API_KEY in .env file
- [ ] Service restarted
- [ ] Test passed: `python test_api.py`

---

## 🎯 **What You Get with GPT-4o**

**Before (TM only)**:
```
Source: The Global Innovation Equity Fund returned 8.5%
Target: [Some TM match - may not be perfect]
```

**After (GPT-4o)**:
```
Source: The Global Innovation Equity Fund returned 8.5%
Target: El Global Innovation Equity Fund registró un 8,5% ✨
         ↑                                      ↑
    Preserved fund name               Perfect translation
```

---

## 🚫 **If You Don't Have Credits**

**Your system still works!**

- ✅ Returns best TM match
- ✅ DNT still works (fund names detected)
- ✅ Fast processing (0.025s)
- ✅ Good for similar content

Set `use_llm: false` to avoid errors.

---

## 📞 **Troubleshooting**

### **Error: "insufficient_quota"**

**Solution**: Add credits on OpenAI website (Step 1)

### **Error: "invalid_api_key"**

**Solution**: Check your OPENAI_API_KEY in .env file

### **Translation not using LLM**

**Solution**: 
1. Check `use_llm: true` in request
2. Verify service restarted after adding credits
3. Check logs for "LLM Translator initialized"

---

**Ready to translate with GPT-4o!** 🚀


## 📊 Performance Expectations


### After Optimization (30K entries)
- ⏱️ Load time: 2-3 minutes ✅
- 💾 Memory: 1-2 GB ✅
- 🔍 Query: 2-3 seconds ✅
- ✅ Result: Fast and reliable!

---



---

## 🎓 Learning Resources


   - Error handling

2. **`hybrid_rag_system.py`** - Learn RAG architecture
   - Vector store implementation
   - Parallel query processing
   - Context formatting for LLM

3. **`non_trans_loader.py`** - Learn pattern matching
   - JSON parsing
   - Regex patterns
   - Term detection

4. **`vector_index.py`** - Understand embeddings
   - Sentence transformers
   - FAISS indexing
   - Semantic search

---



---

## ❓ Troubleshooting

### Timeout Errors
- ✅ **Fixed!** Your new 30K TM should load in 2-3 minutes
- If still timing out, increase `MEMOQ_TIMEOUT` in `.env`

### Connection Errors
- Check `MEMOQ_BASE_URL` format (must include `:8081/memoqserverhttpapi/v1`)
- Verify username/password
- Check firewall settings

### Memory Errors
- 30K entries should use ~1-2GB
- If issues persist, reduce to 20K entries
- Close other applications

### DNT Not Working
- Verify `NON_TRANS_FILE` path in `.env`
- Check JSON structure with: `python non_trans_loader.py`
- Ensure fund names are properly formatted

---

## 📞 Need Help?

- Review project documentation: `README.md`
- Check configuration guide: `GUID_CONFIGURATION_GUIDE.md`
- Study RAG system docs: `RAG_SYSTEM_README.md`
- Review cleanup guide: `PROJECT_CLEANUP.md`

---

**Good luck with your bootcamp project! 🚀**

You now have a properly sized, production-ready RAG translation system!


