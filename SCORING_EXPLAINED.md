# 📊 Translation Quality Scoring Explained

## 🎯 **Scoring System**

The translation quality score is based on **4 components** with a weighted average:

### **1. Terminology Score** (20% weight)
```python
terminology_score = (TB hits / total segments) * 20
```
- How well you used glossary terms
- More TB hits = higher score
- **Max: 20 points**

### **2. DNT Compliance** (30% weight) - **Most Important!**
```python
dnt_compliance = 100 - (DNT violations / total segments) * 50
```
- How well you preserved non-translatable terms (fund names)
- Each violation = -50 points per segment
- **Most penalized** - can drop score significantly
- **Max: 30 points**

### **3. Style Score** (30% weight)
```python
style_score = avg_chrF * 100
```
- Translation fluency and style quality
- Based on chrF (character-level F-score) metric
- Measures how natural the translation reads
- **Max: 30 points**

### **4. TM Compliance** (20% weight)
```python
tm_compliance = (TM hits / total segments) * 30
```
- How well you matched existing translations
- More TM matches = more consistency
- **Max: 20 points**

## 🧮 **Overall Score Calculation:**

```python
overall_score = (
    terminology_score * 0.2 +      # 20% weight
    dnt_compliance * 0.3 +          # 30% weight ⭐ MOST IMPORTANT
    style_score * 0.3 +             # 30% weight ⭐ MOST IMPORTANT
    tm_compliance * 0.2             # 20% weight
)
```

## 📈 **Per-Segment Metrics:**

### **chrF Score:**
- Character-level F-score (similarity metric)
- Calculated by `sacrebleu` library
- Range: 0-100 (normalized to 0-1)
- Measures character-level accuracy



## 🎯 **What Makes a Good Score:**

### **High Score (80-100):**
- ✅ High DNT compliance (no fund name violations)
- ✅ Good style (high chrF)
- ✅ Many TM/TB hits
- ✅ Consistent terminology

### **Low Score (<50):**
- ❌ DNT violations (translated fund names)
- ❌ Poor style (low chrF)
- ❌ Few TM/TB hits
- ❌ Inconsistent terminology

## 📋 **Example Scoring:**

### **Scenario: 44 segments, 0 TB hits, 0 TM hits**
```
terminology_score: (0/44) * 20 = 0 points
dnt_compliance: 100 - (0/44) * 50 = 100 points
style_score: 100 (assuming good chrF)
tm_compliance: (0/44) * 30 = 0 points

overall_score = 0*0.2 + 100*0.3 + 100*0.3 + 0*0.2 = 60 points
```

But with **DNT violations**, the score drops:
```
dnt_compliance: 100 - (5/44) * 50 = 94.3 points
overall_score = 0*0.2 + 94.3*0.3 + 100*0.3 + 0*0.2 = 58.3 points
```

## 🔍 **Key Metrics:**

| Metric | Calculation | Weight | Max Points |
|--------|-------------|--------|------------|
| **Terminology** | (TB hits / segments) * 20 | 20% | 20 |
| **DNT Compliance** | 100 - (violations / segments) * 50 | 30% | 30 |
| **Style** | chrF * 100 | 30% | 30 |
| **TM Compliance** | (TM hits / segments) * 30 | 20% | 20 |
| **Overall** | Weighted sum | 100% | 100 |

## 💡 **Why chrF & BLEU?**

- **chrF**: Character-level similarity (catches word order, accents)
- **BLEU**: N-gram precision (catches fluency, word choice)

Both are **industry-standard** translation quality metrics!
