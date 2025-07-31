#!/usr/bin/env python3
"""
Minimal Setup for Bloom Clinical AI
Works without sentence-transformers to avoid conda conflicts
"""

import os
import json
from pathlib import Path

def create_directories():
    """Create necessary directories"""
    print("📁 Creating directories...")

    # Create instance directory
    instance_dir = Path('instance')
    guidelines_dir = instance_dir / 'guidelines'

    instance_dir.mkdir(exist_ok=True)
    guidelines_dir.mkdir(exist_ok=True)

    print(f"✅ Created: {instance_dir}")
    print(f"✅ Created: {guidelines_dir}")

    return guidelines_dir

def create_env_file():
    """Create .env file if it doesn't exist"""
    print("🔧 Setting up environment file...")

    env_file = Path('.env')
    if env_file.exists():
        print("✅ .env file already exists")

        # Check if OpenAI API key is configured
        with open(env_file) as f:
            content = f.read()
            if 'OPENAI_API_KEY=your-openai-api-key-here' in content:
                print("⚠️  Please update your OpenAI API key in .env file")
                return False
            elif 'OPENAI_API_KEY=' in content:
                print("✅ OpenAI API key appears to be configured")
                return True
        return True

    env_content = """# Bloom App Environment Variables
FLASK_SECRET_KEY=your-secret-key-change-this-in-production
OPENAI_API_KEY=your-openai-api-key-here
FLASK_ENV=development

# Database (optional - defaults to SQLite)
DATABASE_URL=sqlite:///bloom.db

# Clinical AI Settings
CLINICAL_AI_ENABLED=true
"""

    with open(env_file, 'w', encoding='utf-8') as f:
        f.write(env_content)

    print(f"✅ Created .env file: {env_file.absolute()}")
    print("⚠️  IMPORTANT: Edit .env and add your OpenAI API key!")
    return False

def create_clinical_guidelines():
    """Create sample clinical guidelines without complex processing"""
    print("📝 Creating clinical guidelines...")

    guidelines_dir = Path('instance/guidelines')

    # Create burnout guidelines
    burnout_file = guidelines_dir / 'burnout_guidelines.json'
    burnout_data = {
        "source": "Clinical Practice Guidelines",
        "topic": "Workplace Burnout",
        "guidelines": [
            {
                "section": "Definition",
                "content": "Burnout is not an illness but a syndrome with three key features: intense overwhelming fatigue, cynical relationship to work, and diminished professional self-esteem.",
                "evidence_level": "Expert Consensus"
            },
            {
                "section": "Differential Diagnosis",
                "content": "Common differential diagnoses include severe depression (feelings of worthlessness/guilt), alcohol/drug abuse, atypical depression, stress disorders, generalized anxiety, social anxiety.",
                "evidence_level": "Clinical Guidelines"
            },
            {
                "section": "Treatment",
                "content": "Focus on rehabilitation rather than medicalization. Key interventions: job modification (most important), workplace interventions, individual assessment. Severe fatigue may require 2-3 weeks sick leave.",
                "evidence_level": "Clinical Guidelines"
            },
            {
                "section": "Prevention",
                "content": "Clear work-leisure boundaries, ability to prioritize and say no, advance work planning, physical health maintenance, recognizing personal limits, strong relationships, positive work climate.",
                "evidence_level": "Evidence-Based"
            }
        ]
    }

    with open(burnout_file, 'w', encoding='utf-8') as f:
        json.dump(burnout_data, f, indent=2)

    print(f"✅ Created: {burnout_file}")

    # Create occupational health guidelines
    occ_health_file = guidelines_dir / 'occupational_health_guidelines.json'
    occ_health_data = {
        "source": "Occupational Medicine Guidelines",
        "topic": "Workplace Mental Health",
        "guidelines": [
            {
                "section": "Risk Assessment",
                "content": "Assess workplace stress factors, workload, management support, job control, and social support. High stress with low control increases burnout risk.",
                "evidence_level": "Level II Evidence"
            },
            {
                "section": "Interventions",
                "content": "Primary prevention: modify work environment. Secondary: early identification and support. Tertiary: treatment and rehabilitation. Workplace interventions more effective than individual-only approaches.",
                "evidence_level": "Systematic Review"
            },
            {
                "section": "Return to Work",
                "content": "Gradual return with modified duties. Supervisor training on mental health support. Regular follow-up assessments. Address workplace factors that contributed to burnout.",
                "evidence_level": "Clinical Guidelines"
            }
        ]
    }

    with open(occ_health_file, 'w', encoding='utf-8') as f:
        json.dump(occ_health_data, f, indent=2)

    print(f"✅ Created: {occ_health_file}")

def create_minimal_clinical_ai():
    """Create a simple clinical AI module that works without sentence-transformers"""
    print("🧠 Creating minimal clinical AI module...")

    minimal_ai_content = '''"""
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
                f"Source: {meta['source']} ({meta['evidence_level']})\\n"
                f"Topic: {meta['topic']} - {meta['section']}\\n"
                f"Content: {guideline['content']}\\n"
                "---"
            )
        
        return "\\n".join(context_parts)

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
'''

    with open('clinical_ai_minimal.py', 'w', encoding='utf-8') as f:
        f.write(minimal_ai_content)

    print("✅ Created minimal clinical AI module")

def test_basic_imports():
    """Test basic imports that we need"""
    print("🧪 Testing basic imports...")

    # Test core Python modules first
    core_modules = ['json', 'os', 'pathlib']
    for module in core_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} - CRITICAL ERROR")
            return False

    # Test optional modules with better error handling
    optional_modules = [
        ('flask', 'Flask'),
        ('openai', 'OpenAI'),
        ('dotenv', 'python-dotenv')
    ]

    all_optional_good = True
    for module_name, display_name in optional_modules:
        try:
            if module_name == 'dotenv':
                # Special case for python-dotenv
                import dotenv
                print(f"  ✅ {display_name}")
            else:
                module = __import__(module_name)
                print(f"  ✅ {display_name}")
        except ImportError as e:
            print(f"  ⚠️  {display_name} - {e}")
            all_optional_good = False
        except Exception as e:
            print(f"  ⚠️  {display_name} - Warning: {e}")
            # Don't fail for other types of errors

    # Even if some optional modules failed, we can continue
    print(f"  📋 Core modules: ✅")
    if not all_optional_good:
        print(f"  📋 Some optional modules had issues, but continuing...")

    return True  # Always return True since we can work around missing optional modules

def main():
    """Main setup function"""
    print("🌸 Bloom Clinical AI - Minimal Setup")
    print("(Avoids sentence-transformers dependency conflicts)")
    print("=" * 60)

    # Test basic imports - but continue even if some fail
    print("Testing your Python environment...")
    test_basic_imports()

    print("\n📁 Setting up project structure...")
    # Create directories
    guidelines_dir = create_directories()

    print("\n🔧 Configuring environment...")
    # Create environment file
    env_configured = create_env_file()

    print("\n📚 Creating clinical guidelines...")
    # Create clinical guidelines
    create_clinical_guidelines()

    print("\n🧠 Creating minimal AI module...")
    # Create minimal AI module
    create_minimal_clinical_ai()

    print("\n" + "=" * 60)
    print("✅ Setup completed successfully!")

    print("\n🎯 Next Steps:")
    print("1. Edit .env file and add your OpenAI API key")
    print("2. Update your app.py to use: from clinical_ai_minimal import init_clinical_ai")
    print("3. Copy any PDF guidelines to:", guidelines_dir.absolute())
    print("4. Run: python app.py")
    print("5. Visit: http://localhost:5000")

    if not env_configured:
        print("\n⚠️  IMPORTANT: Configure your OpenAI API key in .env file")

    print("\n📋 This minimal version:")
    print("  • Uses simple keyword matching instead of AI embeddings")
    print("  • Works with your existing conda environment")
    print("  • Provides clinical guidelines without complex dependencies")
    print("  • Can be upgraded later when dependency issues are resolved")

    print("\n🚀 Try running: python app.py")

if __name__ == '__main__':
    main()
