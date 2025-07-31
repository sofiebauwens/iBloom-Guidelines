#!/usr/bin/env python3
"""
Setup script for Bloom Clinical Guidelines System
Run this script to initialize your clinical AI with PDF guidelines
"""

import os
import shutil
from pathlib import Path
from clinical_ai import ClinicalKnowledgeBase, load_pdf_guidelines

def setup_guidelines_directory():
    """Create guidelines directory and copy PDFs"""
    print("🗂️  Setting up guidelines directory...")

    # Create instance directory structure
    instance_dir = Path('instance')
    guidelines_dir = instance_dir / 'guidelines'

    instance_dir.mkdir(exist_ok=True)
    guidelines_dir.mkdir(exist_ok=True)

    print(f"✅ Created directories: {guidelines_dir}")

    # Instructions for user to add their PDFs
    print("\n📚 NEXT STEPS:")
    print("1. Copy your PDF guidelines to the following directory:")
    print(f"   {guidelines_dir.absolute()}")
    print("\n2. Your PDFs should include:")
    print("   • Burnout clinical guidelines (from your paste.txt)")
    print("   • Cochrane systematic reviews")
    print("   • DynaMed occupational medicine guidelines")
    print("   • Any other evidence-based clinical sources")

    return guidelines_dir

def create_sample_guideline_from_paste():
    """Create a sample guideline file from the burnout content you provided"""
    print("📝 Creating sample guideline from your burnout content...")

    # Your burnout content from paste.txt
    burnout_content = """
Burnout Clinical Guidelines

ESSENTIALS
Burnout is not an illness but a syndrome. It should not be medicalized.
The three key features of burnout are:
- Intense, overwhelming fatigue
- Cynical relationship to work  
- Diminished professional self-esteem

Depression and burnout overlap. Burnout may be a precipitating factor in the development depression. 
Depression is actively treated as in other cases. Fatigue may be the symptom of a somatic disease.

EPIDEMIOLOGY
Burnout does not appear overnight. Instead, it develops gradually through the interaction of one's 
personality, work and work community. Burnout is not the same as work stress. Stress is created when 
a person tries to adapt to his or her workload, and it is not entirely negative. Burnout develops when 
mere adaptation does not suffice, normalization is not achieved, and the state of stress is prolonged.

DIFFERENTIAL DIAGNOSIS
Common psychiatric differential diagnoses:
- Severe depression (especially when feelings of worthlessness or guilt are associated)
- Alcohol and drug abuse problem (for example, recurring short absence from work)
- Atypical depression (for example, getting emotionally hurt at workplace triggers strong fluctuations in mood)
- Stress disorders (a distinct external triggering factor must be identified)
- Generalized anxiety disorder (worry over one's performance, constant restlessness)
- Fear of social situations (fatigue in social situations)
- Somatization disorder (several somatic symptoms)
- Personality disorder (functioning may vary, but problems have continued throughout adulthood)
- Adjustment disorders (identifiable external stress factor that impairs functioning unexpectedly)

TREATMENT
Speaking about "treatment" may cause unnecessary medicalization of the problem. It would be better to talk 
about rehabilitation or empowerment to manage one's own affairs. Job modification is among the most 
important means in this.

The amount and perceived loading of work tasks can be influenced by interventions directed at the work 
place and well-being at work. Interventions targeting the work place may often decrease the time required 
for return to work.

Part of the rehabilitation consists of an individual assessment of what has caused the burnout, where it 
has led to and how the situation can be resolved.

If burnout is manifested as a part of depression or an adjustment disorder, the need of treatment and 
sick leave are determined on terms generally applicable in these disorders, albeit the role of job 
modification is more important.

Severe fatigue impairing functional capacity e.g. in association with an adjustment disorder requires 
a sick leave of 2–3 weeks.

A severe state of depression often requires even longer sick leave because it takes longer to regain 
functional capacity than it does for symptoms to disappear.

If the patient has burnout without a psychiatric or somatic illness and he/she needs time off work, 
the solution is not a sick leave but a reduction of work burden or other arrangements of work tasks.

PREVENTION
Burnout can be prevented by:
- Making clear the difference between work and leisure time
- The ability to say "no", i.e. bold prioritization of tasks
- The ability to plan one's work in advance
- Taking care of one's physical condition
- Admitting one's own limits
- Good relationships at home
- Working relationships at work
- An open work climate
- Consistent career development
- A supportive employer
- Clear definitions of work assignments
- Perception of one's job as meaningful
- Inclusion of field-level workers in work development activities
- Maintenance of expertise

Work supervision may prevent burnout of at least health care and teaching personnel.
"""

    # Save as text file in guidelines directory
    guidelines_dir = Path('instance/guidelines')
    sample_file = guidelines_dir / 'burnout_clinical_guidelines.txt'

    with open(sample_file, 'w', encoding='utf-8') as f:
        f.write(burnout_content)

    print(f"✅ Created sample guideline: {sample_file}")
    return sample_file

def test_clinical_system():
    """Test the clinical AI system"""
    print("🧪 Testing clinical AI system...")

    # Check if we have the minimum requirements
    try:
        import sentence_transformers
        import chromadb
        print("✅ Required packages installed")
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        return False

    # Check if OpenAI API key is set
    import os
    from dotenv import load_dotenv

    # Load environment variables
    load_dotenv()

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key or api_key == 'your-openai-api-key-here':
        print("⚠️  OpenAI API key not configured. Clinical AI will work but without OpenAI analysis.")
        print("   Add your API key to .env file to enable full functionality.")
        return True  # Still considered successful for basic setup

    print("✅ OpenAI API key configured")

    # Test basic clinical knowledge base functionality (without requiring the full app)
    try:
        from clinical_ai import ClinicalKnowledgeBase
        kb = ClinicalKnowledgeBase()
        print("✅ Clinical knowledge base can be initialized")
        return True
    except Exception as e:
        print(f"❌ Error initializing clinical knowledge base: {e}")
        return False

def setup_environment():
    """Setup environment variables"""
    print("🔧 Checking environment setup...")

    env_file = Path('.env')
    if not env_file.exists():
        print("⚠️  .env file not found. Creating template...")

        env_template = """# Bloom App Environment Variables
FLASK_SECRET_KEY=your-secret-key-here-change-this
OPENAI_API_KEY=your-openai-api-key-here
FLASK_ENV=development

# Database (optional - defaults to SQLite)
# DATABASE_URL=sqlite:///bloom.db

# Clinical AI Settings
CLINICAL_AI_ENABLED=true
CLINICAL_DB_PATH=instance/clinical_db
"""

        with open(env_file, 'w') as f:
            f.write(env_template)

        print(f"✅ Created .env template at {env_file.absolute()}")
        print("⚠️  IMPORTANT: Edit .env file and add your OpenAI API key!")
        return False
    else:
        print("✅ .env file exists")

        # Check for OpenAI API key
        with open(env_file) as f:
            env_content = f.read()

        if 'OPENAI_API_KEY=your-openai-api-key-here' in env_content:
            print("⚠️  Please update your OpenAI API key in .env file")
            return False

        print("✅ Environment appears configured")
        return True

def main():
    """Main setup function"""
    print("🌸 Bloom Clinical AI Setup")
    print("=" * 50)

    # Install dependencies first
    print("📦 Installing required dependencies...")
    try:
        import subprocess
        import sys

        packages = [
            "sentence-transformers",
            "chromadb",
            "PyMuPDF",
            "numpy",
            "scikit-learn",
            "python-dotenv"
        ]

        for package in packages:
            print(f"  Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

        print("✅ Dependencies installed successfully")

    except Exception as e:
        print(f"⚠️  Warning: Could not install some dependencies: {e}")
        print("Please install manually: pip install sentence-transformers chromadb PyMuPDF numpy scikit-learn python-dotenv")

    # Check environment
    env_ready = setup_environment()

    # Setup directories
    guidelines_dir = setup_guidelines_directory()

    # Create sample guideline
    create_sample_guideline_from_paste()

    print("\n🚀 Testing system...")

    # Test the system
    success = test_clinical_system()

    if success:
        print("\n✅ Setup completed successfully!")
        print("\n🎯 Next steps:")
        print("1. Edit .env file and add your OpenAI API key")
        print("2. Add your PDF guidelines to:", guidelines_dir.absolute())
        print("3. Run: python app.py")
        print("4. Visit: http://localhost:5000")
        print("5. Test the clinical AI features!")

        if not env_ready:
            print("\n⚠️  IMPORTANT: Don't forget to configure your .env file!")
    else:
        print("\n⚠️  Setup completed with warnings.")
        print("Please check the issues above and try again.")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure you have Python 3.8+ installed")
        print("2. Install missing packages manually if needed")
        print("3. Check your .env file configuration")

if __name__ == '__main__':
    main()