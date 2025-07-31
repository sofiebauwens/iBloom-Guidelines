"""
Minimal Clinical AI Module for Bloom App
Works without sentence-transformers to avoid dependency conflicts
"""

import json
import os
from pathlib import Path
from typing import Dict, List

class SimpleClinicalKnowledgeBase:
    def __init__(self):
        self.guidelines = {}
        self.loaded = False
    
    def init_app(self, app):
        """Initialize with Flask app"""
        print("🧠 Loading minimal clinical AI...")
        
        # Load guidelines from JSON files
        if hasattr(app, 'instance_path'):
            guidelines_dir = Path(app.instance_path) / 'guidelines'
        else:
            guidelines_dir = Path('instance/guidelines')
        
        self.load_guidelines(guidelines_dir)
        
        # Store in app
        if hasattr(app, 'extensions'):
            app.extensions = getattr(app, 'extensions', {})
            app.extensions['clinical_kb'] = self
        
        self.loaded = True
        print("✅ Minimal clinical AI initialized")
    
    def load_guidelines(self, guidelines_dir: Path):
        """Load guidelines from JSON files"""
        if not guidelines_dir.exists():
            print(f"📁 Guidelines directory not found: {guidelines_dir}")
            return
        
        json_files = list(guidelines_dir.glob('*.json'))
        for json_file in json_files:
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    self.guidelines[data['topic']] = data
                print(f"📚 Loaded: {data['topic']}")
            except Exception as e:
                print(f"⚠️  Could not load {json_file}: {e}")
    
    def query_guidelines(self, query: str, n_results: int = 3) -> List[Dict]:
        """Simple keyword-based guideline matching"""
        if not self.guidelines:
            return []
        
        query_lower = query.lower()
        relevant_guidelines = []
        
        for topic, guideline_data in self.guidelines.items():
            for guideline in guideline_data['guidelines']:
                content = guideline['content'].lower()
                
                # Simple keyword matching
                keywords = ['burnout', 'stress', 'fatigue', 'depression', 'anxiety', 'work', 'workplace']
                matches = sum(1 for keyword in keywords if keyword in query_lower and keyword in content)
                
                if matches > 0:
                    relevant_guidelines.append({
                        'content': guideline['content'],
                        'metadata': {
                            'source': guideline_data['source'],
                            'topic': topic,
                            'section': guideline['section'],
                            'evidence_level': guideline['evidence_level']
                        },
                        'relevance_score': matches / len(keywords)
                    })
        
        # Sort by relevance and return top results
        relevant_guidelines.sort(key=lambda x: x['relevance_score'], reverse=True)
        return relevant_guidelines[:n_results]
    
    def get_clinical_context(self, user_responses: Dict, burnout_score: float) -> str:
        """Build clinical context for analysis"""
        if burnout_score >= 7:
            query = "severe burnout high stress overwhelming fatigue treatment"
        elif burnout_score >= 4:
            query = "moderate burnout workplace stress prevention intervention"
        else:
            query = "burnout prevention workplace wellness"
        
        guidelines = self.query_guidelines(query, n_results=3)
        
        if not guidelines:
            return ""
        
        context_parts = []
        for guideline in guidelines:
            meta = guideline['metadata']
            context_parts.append(
                f"Source: {meta['source']} ({meta['evidence_level']})\n"
                f"Topic: {meta['topic']} - {meta['section']}\n"
                f"Content: {guideline['content']}\n"
                "---"
            )
        
        return "\n".join(context_parts)

# Global instance
clinical_kb = SimpleClinicalKnowledgeBase()

def init_clinical_ai(app):
    """Initialize clinical AI with Flask app"""
    try:
        clinical_kb.init_app(app)
        print("🌟 Clinical AI system initialized")
        return clinical_kb
    except Exception as e:
        print(f"⚠️  Warning: Clinical AI initialization failed: {e}")
        return None

def get_clinical_ai():
    """Get clinical AI instance - simplified version"""
    return clinical_kb if clinical_kb.loaded else None
