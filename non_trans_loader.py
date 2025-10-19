"""
Do Not Translate (DNT) Loader for Fund Names
Loads fund names that should NOT be translated
"""

import json
import re
from typing import List, Set, Dict, Any

class NonTransLoader:
    """Loads non-translatable fund names from JSON"""
    
    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.terms: Set[str] = set()
        self.loaded = False
        
    def load(self) -> None:
        """Load fund names from JSON file"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract fund names from the JSON structure
            rules = self._extract_fund_names(data)
            
            for rule in rules:
                if rule and isinstance(rule, str):
                    rule = rule.strip()
                    if rule:
                        self.terms.add(rule)
                        # Also add individual words
                        words = re.findall(r'\b[A-Za-z][A-Za-z0-9]*\b', rule)
                        for word in words:
                            if len(word) > 2:
                                self.terms.add(word)
            
            self.loaded = True
            print(f"✅ Loaded {len(self.terms)} non-translatable terms")
            
        except Exception as e:
            print(f"❌ Failed to load: {e}")
            self.loaded = False
    
    def _extract_fund_names(self, data: Dict[str, Any]) -> List[str]:
        """Extract fund names from JSON structure"""
        rules = []
        
        def find_rules(obj):
            if isinstance(obj, dict):
                if "nonTransRule" in obj:
                    for rule_obj in obj["nonTransRule"]:
                        if isinstance(rule_obj, dict) and "_text" in rule_obj:
                            rules.append(rule_obj["_text"])
                        elif isinstance(rule_obj, str):
                            rules.append(rule_obj)
                
                for value in obj.values():
                    find_rules(value)
                    
            elif isinstance(obj, list):
                for item in obj:
                    find_rules(item)
        
        find_rules(data)
        return rules
    
    def is_non_translatable(self, text: str) -> bool:
        """Check if text contains fund names"""
        if not self.loaded:
            self.load()
        
        if not self.terms:
            return False
        
        text_lower = text.lower()
        
        for term in self.terms:
            if term.lower() in text_lower:
                return True
        
        return False
    
    def get_non_translatable_terms(self, text: str) -> List[str]:
        """Get list of fund names found in text"""
        if not self.loaded:
            self.load()
        
        found_terms = []
        text_lower = text.lower()
        
        for term in self.terms:
            if term.lower() in text_lower:
                found_terms.append(term)
        
        return found_terms

# Test function
if __name__ == "__main__":
    loader = NonTransLoader("./data/SV_Test_Fund_names2.json")
    loader.load()
    
    # Test examples
    test_texts = [
        "The Global Innovation Equity Fund returned 8.5%",
        "This is a regular sentence",
        "AB SICAV I - European Equity Portfolio performance"
    ]
    
    print("\n🧪 Testing fund name detection:")
    for text in test_texts:
        is_dnt = loader.is_non_translatable(text)
        found_terms = loader.get_non_translatable_terms(text)
        status = "🚫 FUND NAME" if is_dnt else "✅ OK"
        print(f"{status}: {text}")
        if found_terms:
            print(f"   Found: {found_terms}")
        print()