"""
Clinical AI Module for Bloom App
Integrates evidence-based clinical guidelines into AI responses
"""

import os
import json
import fitz  # PyMuPDF
import openai
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import chromadb
from flask import current_app
import numpy as np

@dataclass
class ClinicalGuideline:
    source: str
    topic: str
    content: str
    evidence_level: str
    page_number: int
    citation: str

class ClinicalKnowledgeBase:
    def __init__(self, app=None):
        self.encoder = None
        self.client = None
        self.collection = None
        self.app = app

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app

        # Initialize sentence transformer
        print("🧠 Loading clinical AI models...")
        try:
            self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
            print("✅ Language model loaded")
        except Exception as e:
            print(f"⚠️  Warning: Could not load language model: {e}")
            return

        # Initialize ChromaDB
        try:
            if hasattr(app, 'instance_path'):
                persist_directory = os.path.join(app.instance_path, 'clinical_db')
            else:
                persist_directory = os.path.join(os.getcwd(), 'instance', 'clinical_db')

            os.makedirs(persist_directory, exist_ok=True)

            self.client = chromadb.PersistentClient(path=persist_directory)

            # Get or create collection
            try:
                self.collection = self.client.get_collection("clinical_guidelines")
                print("📚 Loaded existing clinical guidelines database")
            except:
                self.collection = self.client.create_collection("clinical_guidelines")
                print("🆕 Created new clinical guidelines database")

            # Store reference in app
            if hasattr(app, 'extensions'):
                app.extensions = getattr(app, 'extensions', {})
                app.extensions['clinical_kb'] = self

            print("✅ Clinical knowledge base initialized")

        except Exception as e:
            print(f"❌ Error initializing ChromaDB: {e}")
            print("Clinical AI will be disabled")

    def process_pdf_guidelines(self, pdf_path: str, source_name: str) -> int:
        """Process PDF and extract clinical guidelines"""
        print(f"📖 Processing {source_name} from {pdf_path}")

        guidelines_added = 0

        try:
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()

                # Skip pages with minimal content
                if len(text.strip()) < 100:
                    continue

                # Extract meaningful sections (you can customize this)
                sections = self._extract_clinical_sections(text, source_name)

                for section in sections:
                    guideline = ClinicalGuideline(
                        source=source_name,
                        topic=section['topic'],
                        content=section['content'],
                        evidence_level=section.get('evidence_level', 'Not specified'),
                        page_number=page_num + 1,
                        citation=f"{source_name}, Page {page_num + 1}"
                    )

                    self._add_guideline_to_db(guideline)
                    guidelines_added += 1

            doc.close()
            print(f"✅ Added {guidelines_added} guidelines from {source_name}")

        except Exception as e:
            print(f"❌ Error processing {pdf_path}: {e}")

        return guidelines_added

    def _extract_clinical_sections(self, text: str, source: str) -> List[Dict]:
        """Extract meaningful clinical sections from text"""
        sections = []

        # Split by paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]

        for paragraph in paragraphs:
            # Look for clinical content indicators
            if self._is_clinical_content(paragraph):
                topic = self._extract_topic(paragraph, source)
                evidence_level = self._extract_evidence_level(paragraph)

                sections.append({
                    'topic': topic,
                    'content': paragraph,
                    'evidence_level': evidence_level
                })

        return sections

    def _is_clinical_content(self, text: str) -> bool:
        """Determine if text contains clinical information"""
        clinical_indicators = [
            'burnout', 'stress', 'depression', 'anxiety', 'mental health',
            'treatment', 'therapy', 'intervention', 'diagnosis', 'symptoms',
            'occupational', 'workplace', 'employees', 'fatigue', 'prevention',
            'systematic review', 'clinical trial', 'evidence', 'recommendations'
        ]

        text_lower = text.lower()
        return any(indicator in text_lower for indicator in clinical_indicators)

    def _extract_topic(self, text: str, source: str) -> str:
        """Extract topic from text"""
        # Look for headings or key phrases
        lines = text.split('\n')
        first_line = lines[0].strip()

        # If first line looks like a heading, use it
        if len(first_line) < 100 and not first_line.endswith('.'):
            return first_line

        # Otherwise, generate from content
        if 'burnout' in text.lower():
            return 'Workplace Burnout'
        elif 'stress' in text.lower():
            return 'Occupational Stress'
        elif 'mental health' in text.lower():
            return 'Mental Health'
        elif 'training' in text.lower():
            return 'Training Interventions'
        else:
            return f'Clinical Guidelines - {source}'

    def _extract_evidence_level(self, text: str) -> str:
        """Extract evidence level from text"""
        text_lower = text.lower()

        if 'systematic review' in text_lower or 'meta-analysis' in text_lower:
            return 'Level I Evidence'
        elif 'randomized controlled trial' in text_lower or 'rct' in text_lower:
            return 'Level II Evidence'
        elif 'cochrane' in text_lower:
            return 'Level I Evidence'
        elif 'consensus' in text_lower or 'expert' in text_lower:
            return 'Expert Consensus'
        else:
            return 'Clinical Guidelines'

    def _add_guideline_to_db(self, guideline: ClinicalGuideline):
        """Add guideline to vector database"""
        try:
            # Create embedding
            embedding = self.encoder.encode(guideline.content)

            # Create unique ID
            guideline_id = f"{guideline.source}_{guideline.page_number}_{hash(guideline.content)}"

            # Add to collection
            self.collection.add(
                embeddings=[embedding.tolist()],
                documents=[guideline.content],
                metadatas=[{
                    'source': guideline.source,
                    'topic': guideline.topic,
                    'evidence_level': guideline.evidence_level,
                    'page_number': guideline.page_number,
                    'citation': guideline.citation
                }],
                ids=[guideline_id]
            )
        except Exception as e:
            print(f"Warning: Could not add guideline: {e}")

    def query_guidelines(self, query: str, n_results: int = 3) -> List[Dict]:
        """Query guidelines relevant to the question"""
        if not self.collection:
            return []

        try:
            # Create query embedding
            query_embedding = self.encoder.encode(query)

            # Search collection
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=n_results
            )

            guidelines = []
            for i in range(len(results['documents'][0])):
                guidelines.append({
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'relevance_score': 1 - results['distances'][0][i]
                })

            return guidelines

        except Exception as e:
            print(f"Error querying guidelines: {e}")
            return []

    def get_clinical_context(self, user_responses: Dict, burnout_score: float) -> str:
        """Build clinical context based on user responses and burnout score"""
        # Create query from user responses
        query_parts = []

        if burnout_score > 7:
            query_parts.append("severe burnout high stress overwhelming fatigue")
        elif burnout_score > 4:
            query_parts.append("moderate burnout workplace stress")
        else:
            query_parts.append("burnout prevention workplace wellbeing")

        # Add specific concerns from responses
        for response in user_responses.values():
            if isinstance(response, str) and response:
                query_parts.append(response)

        query = " ".join(query_parts)

        # Get relevant guidelines
        guidelines = self.query_guidelines(query, n_results=3)

        if not guidelines:
            return ""

        # Build context
        context_parts = []
        for guideline in guidelines:
            meta = guideline['metadata']
            context_parts.append(
                f"Source: {meta['source']} ({meta['evidence_level']})\n"
                f"Topic: {meta['topic']}\n"
                f"Content: {guideline['content'][:500]}...\n"
                f"Citation: {meta['citation']}\n"
                "---"
            )

        return "\n".join(context_parts)

class ClinicalAIAssistant:
    def __init__(self, knowledge_base: ClinicalKnowledgeBase):
        self.kb = knowledge_base

        # Initialize OpenAI client if API key is available
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key and api_key != 'your-openai-api-key-here':
            try:
                self.client = openai.OpenAI(api_key=api_key)
                self.openai_available = True
                print("✅ OpenAI client initialized")
            except Exception as e:
                print(f"⚠️  Warning: OpenAI client failed to initialize: {e}")
                self.client = None
                self.openai_available = False
        else:
            print("⚠️  OpenAI API key not configured. Clinical analysis will use fallback methods.")
            self.client = None
            self.openai_available = False

    def generate_clinical_analysis(self, user_responses: Dict, burnout_score: float) -> Dict:
        """Generate evidence-based analysis using clinical guidelines"""

        # Get clinical context
        clinical_context = self.kb.get_clinical_context(user_responses, burnout_score)

        if not self.openai_available:
            # Use fallback analysis when OpenAI is not available
            return self._generate_fallback_analysis(user_responses, burnout_score, clinical_context)

        # Build prompt with clinical guidelines
        prompt = self._build_clinical_prompt(user_responses, burnout_score, clinical_context)

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a clinical AI assistant specializing in workplace mental health and burnout prevention. 
                        Base your responses strictly on provided evidence-based clinical guidelines. 
                        Always cite sources and indicate evidence levels. 
                        Recommend seeking professional help when appropriate."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=1000
            )

            ai_analysis = response.choices[0].message.content

            # Extract structured information
            structured_analysis = self._parse_ai_analysis(ai_analysis)

            return {
                'analysis': ai_analysis,
                'structured': structured_analysis,
                'clinical_sources': self._extract_sources_used(clinical_context),
                'confidence': self._calculate_confidence(clinical_context)
            }

        except Exception as e:
            print(f"Error generating clinical analysis: {e}")
            return self._generate_fallback_analysis(user_responses, burnout_score, clinical_context)

    def _generate_fallback_analysis(self, user_responses: Dict, burnout_score: float, clinical_context: str) -> Dict:
        """Generate analysis without OpenAI using clinical guidelines"""

        # Create rule-based analysis based on clinical guidelines
        analysis_parts = []
        recommendations = []
        risk_factors = []

        # Analyze burnout score
        if burnout_score >= 7:
            analysis_parts.append("High burnout risk detected based on clinical assessment criteria.")
            recommendations.extend([
                "Consider workplace interventions as recommended in clinical guidelines",
                "Evaluate need for professional mental health support",
                "Implement job modification strategies"
            ])
            risk_factors.append("Severe workplace stress indicators")

        elif burnout_score >= 4:
            analysis_parts.append("Moderate burnout risk identified.")
            recommendations.extend([
                "Implement preventive measures as outlined in clinical guidelines",
                "Focus on work-life balance improvement",
                "Consider supervisor training interventions"
            ])
            risk_factors.append("Moderate stress levels")

        else:
            analysis_parts.append("Low burnout risk. Focus on prevention strategies.")
            recommendations.extend([
                "Maintain current wellbeing practices",
                "Continue monitoring stress levels",
                "Participate in workplace wellness programs"
            ])

        # Add clinical context insights
        if clinical_context:
            analysis_parts.append("Analysis based on evidence-based clinical guidelines including workplace mental health research.")

        analysis = " ".join(analysis_parts)

        return {
            'analysis': analysis,
            'structured': {
                'risk_factors': risk_factors,
                'recommendations': recommendations,
                'interventions': recommendations[:3],  # First 3 as interventions
                'professional_help': burnout_score >= 7
            },
            'clinical_sources': self._extract_sources_used(clinical_context),
            'confidence': self._calculate_confidence(clinical_context)
        }

    def _build_clinical_prompt(self, responses: Dict, score: float, context: str) -> str:
        """Build prompt with clinical context"""
        return f"""
Based on the following evidence-based clinical guidelines, analyze this workplace burnout assessment:

CLINICAL GUIDELINES CONTEXT:
{context}

USER ASSESSMENT DATA:
Burnout Score: {score}/10
User Responses: {json.dumps(responses, indent=2)}

Please provide:
1. Clinical assessment based on provided guidelines
2. Evidence-based recommendations with citations
3. Risk level evaluation
4. Specific interventions supported by the evidence
5. When to seek professional help

Focus on evidence from the provided clinical sources. Cite specific guidelines used.
"""

    def _parse_ai_analysis(self, analysis: str) -> Dict:
        """Parse AI analysis into structured format"""
        # This is a simplified parser - you can make it more sophisticated
        return {
            'risk_factors': self._extract_section(analysis, 'risk'),
            'recommendations': self._extract_section(analysis, 'recommend'),
            'interventions': self._extract_section(analysis, 'intervention'),
            'professional_help': 'seek professional' in analysis.lower()
        }

    def _extract_section(self, text: str, keyword: str) -> List[str]:
        """Extract bullet points or recommendations from text"""
        lines = text.split('\n')
        relevant_lines = []

        for line in lines:
            if keyword.lower() in line.lower() and (line.strip().startswith('-') or line.strip().startswith('•')):
                relevant_lines.append(line.strip())

        return relevant_lines

    def _extract_sources_used(self, context: str) -> List[str]:
        """Extract sources from clinical context"""
        sources = []
        lines = context.split('\n')

        for line in lines:
            if line.startswith('Source:'):
                sources.append(line.replace('Source:', '').strip())

        return sources

    def _calculate_confidence(self, context: str) -> float:
        """Calculate confidence based on available clinical evidence"""
        if not context:
            return 0.0

        # Count evidence sources
        evidence_indicators = ['Level I Evidence', 'Level II Evidence', 'Cochrane', 'systematic review']
        confidence = 0.0

        for indicator in evidence_indicators:
            if indicator in context:
                confidence += 0.25

        return min(confidence, 1.0)

# Global instances
clinical_kb = ClinicalKnowledgeBase()
clinical_ai = None

def init_clinical_ai(app):
    """Initialize clinical AI with Flask app"""
    global clinical_ai

    try:
        clinical_kb.init_app(app)
        clinical_ai = ClinicalAIAssistant(clinical_kb)

        # Load guidelines from PDFs if they exist
        if hasattr(app, 'instance_path'):
            guidelines_dir = os.path.join(app.instance_path, 'guidelines')
        else:
            guidelines_dir = os.path.join(os.getcwd(), 'instance', 'guidelines')

        if os.path.exists(guidelines_dir):
            load_pdf_guidelines(guidelines_dir)
        else:
            print(f"📁 Guidelines directory not found: {guidelines_dir}")
            print("   Create it and add PDF guidelines for enhanced clinical AI")

        print("🌟 Clinical AI system initialized")

    except Exception as e:
        print(f"⚠️  Warning: Clinical AI initialization failed: {e}")
        print("   App will continue without clinical AI features")
        clinical_ai = None

def load_pdf_guidelines(guidelines_dir: str):
    """Load all PDF guidelines from directory"""
    pdf_files = [f for f in os.listdir(guidelines_dir) if f.endswith('.pdf')]

    for pdf_file in pdf_files:
        pdf_path = os.path.join(guidelines_dir, pdf_file)
        source_name = pdf_file.replace('.pdf', '').replace('_', ' ').title()
        clinical_kb.process_pdf_guidelines(pdf_path, source_name)

def get_clinical_ai() -> ClinicalAIAssistant:
    """Get clinical AI instance"""
    return clinical_ai