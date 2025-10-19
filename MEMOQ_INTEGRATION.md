# MemoQ Integration Guide

Complete guide for integrating the Finance RAG Translation Service with MemoQ.

---

## 🎯 Overview

This service provides AI-powered translation for MemoQ with:
- **TM Integration**: Semantic search over 30K finance translations
- **TB Integration**: Live terminology lookups
- **DNT Integration**: Automatic fund name preservation
- **LLM Integration**: GPT-4o for high-quality translations

---

## 🚀 Quick Start

### 1. Start the Service

```bash
python app.py
```

The service will start on `http://localhost:8000`

### 2. Verify Service is Running

Open browser: http://localhost:8000/health

You should see:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "rag_orchestrator": true,
    "vector_index": true,
    "dnt_loader": true
  }
}
```

---

## 📋 MemoQ Configuration

### Option A: Using MemoQ Custom MT Plugin

1. **Open MemoQ** → Settings → Machine Translation
2. **Add New Engine** → Custom REST API
3. **Configure**:
   - Name: `Finance RAG Translator`
   - URL: `http://localhost:8000/translate`
   - Method: `POST`
   - Content-Type: `application/json`

4. **Request Template**:
```json
{
  "source_text": "{source}",
  "source_language": "en",
  "target_language": "es",
  "use_llm": false
}
```

5. **Response Mapping**:
   - Translation field: `target_text`
   - Confidence field: `confidence`

### Option B: Direct API Calls

If MemoQ doesn't support custom MT directly, use a middleware service that:
1. Receives segments from MemoQ
2. Calls your API
3. Returns translations to MemoQ

---

## 🔄 Translation Workflow


---

## 📡 API Reference

### POST /translate

Translate a single segment (MemoQ calls this for each segment).

**Request:**
```json
{
  "source_text": "The Global Innovation Equity Fund returned 8.5%",
  "source_language": "en",
  "target_language": "es",
  "max_tm_results": 3,
  "max_tb_results": 5,
  "use_llm": false
}
```

**Response:**
```json
{
  "source_text": "The Global Innovation Equity Fund returned 8.5%",
  "target_text": "El Global Innovation Equity Fund registró un 8,5%",
  "confidence": 0.95,
  "has_fund_names": true,
  "fund_terms": ["Global Innovation Equity Fund"],
  "tm_matches": 3,
  "tb_matches": 5,
  "processing_time": 0.025,
  "metadata": {
    "used_llm": false,
    "model": "tm_only"
  }
}
```

### GET /health

Check service health.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "rag_orchestrator": true,
    "llm_translator": true,
    "vector_index": true,
    "dnt_loader": true
  }
}
```

### GET /stats

Get system statistics.

**Response:**
```json
{
  "service": "Finance RAG Translation Service",
  "rag_stats": {
    "total_queries": 150,
    "average_processing_time": 0.025,
    "tm_index_stats": {
      "total_entries": 30000
    }
  },
  "llm_available": true,
  "model": "gpt-4o-mini"
}
```

---

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# MemoQ Connection
MEMOQ_BASE_URL=https://memoq.server.com:8081/memoqserverhttpapi/v1
MEMOQ_USERNAME=your_username
MEMOQ_PASSWORD=your_password
MEMOQ_TM_NAME=SV_test_TM_Finance
MEMOQ_TB_NAME=Finance_TB

# OpenAI (Optional - for LLM translation)
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_TEMPERATURE=0

# System Settings
MAX_TM_RESULTS=5
MAX_TB_RESULTS=10
SIMILARITY_THRESHOLD=0.3
```

---

## 🎯 Translation Modes

### Mode 1: TM Fallback (No API Credits)
- Returns best TM match
- Fast: ~0.025s per segment
- Good for similar content
- **Set**: `use_llm: false`

### Mode 2: GPT-4o Translation (Recommended)
- AI-generated translations
- RAG-enhanced context
- Perfect fund name preservation
- **Set**: `use_llm: true`
- **Cost**: ~$0.001 per segment

---

## 🧪 Testing

### Test Single Translation

```bash
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "source_text": "The Global Innovation Equity Fund returned 8.5%",
    "source_language": "en",
    "target_language": "es",
    "use_llm": false
  }'
```

### Test with Python

```python
import requests

response = requests.post(
    "http://localhost:8000/translate",
    json={
        "source_text": "The European Central Bank announced new measures",
        "source_language": "en",
        "target_language": "es"
    }
)

print(response.json()["target_text"])
```

---

## 📊 Performance

- **Processing Time**: 0.025s per segment
- **Throughput**: ~40 segments/second
- **Memory Usage**: ~2GB with 30K TM entries
- **Scalability**: Can handle full MemoQ projects

---

## 🔧 Troubleshooting

### Service Won't Start

**Issue**: Port 8000 already in use

**Solution**:
```bash
# Use different port
python -m uvicorn app:app --port 8080
```

### MemoQ Can't Connect

**Issue**: Connection refused

**Solutions**:
1. Check service is running: `http://localhost:8000/health`
2. Check firewall settings
3. Use `0.0.0.0` instead of `localhost` if on different machine

### Translations Not Good

**Issue**: TM matches not relevant

**Solutions**:
1. Lower `SIMILARITY_THRESHOLD` in `.env`
2. Add more TM entries
3. Enable LLM mode: `use_llm: true`

### Fund Names Not Preserved

**Issue**: Fund names being translated

**Solution**:
- Check `data/SV_Test_Fund_names2.json` contains your fund names
- Verify DNT loader status: `http://localhost:8000/health`

---

## 📞 Support

For issues or questions:
1. Check logs: Service prints detailed logs
2. Test API: Use `python test_api.py`
3. Verify health: `http://localhost:8000/health`

---

## 🎓 Best Practices

1. **Keep Service Running**: Start before opening MemoQ project
2. **Monitor Performance**: Check `/stats` endpoint regularly
3. **Update TM**: Rebuild vector index when TM grows
4. **Test First**: Use `test_api.py` before connecting MemoQ
5. **Use LLM for Quality**: Enable GPT-4o for final translations

---

**Ready for production translation with MemoQ!** 🚀

