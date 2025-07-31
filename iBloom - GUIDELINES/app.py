from flask import Flask, render_template, request, jsonify, session, Response, redirect, url_for, flash
from clinical_ai import init_clinical_ai, get_clinical_ai, clinical_kb
from flask_sqlalchemy import SQLAlchemy
import os
import json
import io
import csv
import logging
from datetime import datetime, timedelta
import uuid
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///bloom.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize clinical AI system
print("🌟 Initializing clinical AI system...")
try:
    init_clinical_ai(app)
    print("✅ Clinical AI system initialized successfully")
except Exception as e:
    print(f"⚠️  Warning: Clinical AI initialization failed: {e}")
    print("   App will continue with basic functionality")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = db.Column(db.String(100), nullable=False, index=True)
    department = db.Column(db.String(100), nullable=True, index=True)
    role_level = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    responses = db.relationship('DailyResponse', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.id[:8]}... {self.department}>'

    def to_dict(self):
        return {
            'id': self.id,
            'department': self.department,
            'role_level': self.role_level,
            'created_at': self.created_at.isoformat(),
            'days_active': (datetime.utcnow() - self.created_at).days
        }

class DailyResponse(db.Model):
    """Daily questionnaire responses with AI analysis"""
    __tablename__ = 'daily_responses'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)

    # Raw questionnaire data
    questions = db.Column(db.Text, nullable=False)  # JSON string of questions asked
    responses = db.Column(db.Text, nullable=False)  # JSON string of user responses

    # AI analysis results
    burnout_score = db.Column(db.Float, nullable=True, index=True)
    ai_analysis = db.Column(db.Text, nullable=True)  # JSON string of full AI analysis
    concerns = db.Column(db.Text, nullable=True)  # JSON array of identified concerns
    recommendations = db.Column(db.Text, nullable=True)  # JSON array of recommendations
    urgency_level = db.Column(db.String(20), nullable=True, index=True)  # low, medium, high

    # Metadata
    response_time_seconds = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<Response {self.id} - Score: {self.burnout_score}>'

    def get_responses_dict(self):
        """Parse responses JSON safely"""
        try:
            return json.loads(self.responses) if self.responses else {}
        except json.JSONDecodeError:
            return {}

    def get_analysis_dict(self):
        """Parse AI analysis JSON safely"""
        try:
            return json.loads(self.ai_analysis) if self.ai_analysis else {}
        except json.JSONDecodeError:
            return {}

    def to_dict(self):
        return {
            'id': self.id,
            'burnout_score': self.burnout_score,
            'urgency_level': self.urgency_level,
            'concerns': json.loads(self.concerns) if self.concerns else [],
            'recommendations': json.loads(self.recommendations) if self.recommendations else [],
            'created_at': self.created_at.isoformat(),
            'responses': self.get_responses_dict()
        }

# ==================== BASIC ROUTES ====================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/questionnaire')
def questionnaire():
    if 'user_id' not in session:
        flash('Please start your journey by entering your company ID.', 'warning')
        return redirect(url_for('index'))
    return render_template('questionnaire.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please start your journey by entering your company ID.', 'warning')
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/company-dashboard')
def company_dashboard():
    if 'company_user' not in session:
        flash('You must be logged in to view the company dashboard.', 'error')
        return redirect(url_for('company_login'))
    return render_template('company_dashboard.html')

@app.route('/company-login')
def company_login():
    return render_template('company_login.html')

@app.route('/company-auth', methods=['GET', 'POST'])
def company_auth():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # IMPORTANT: This is a placeholder for real authentication
        if username == 'admin' and password == 'password':
            session['company_user'] = username
            return redirect(url_for('company_dashboard'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('company_login'))

    # If it's a GET request, just show the login page
    return redirect(url_for('company_login'))

@app.route('/health')
def health():
    """Health check endpoint with system statistics"""
    try:
        # Test database connection
        with app.app_context():
            result = db.session.execute(db.text('SELECT 1')).scalar()
            db_status = 'connected' if result == 1 else 'error'

        user_count = User.query.count()
        response_count = DailyResponse.query.count()

        return jsonify({
            'status': 'healthy',
            'message': 'Bloom is running! 🌸',
            'timestamp': datetime.now().isoformat(),
            'database': db_status,
            'statistics': {
                'total_users': user_count,
                'total_responses': response_count,
                'uptime': 'Running since server start'
            },
            'features': {
                'user_registration': 'available',
                'data_export': 'available',
                'company_analytics': 'available',
                'emergency_help': 'available',
                'clinical_ai': 'available' if get_clinical_ai() else 'disabled'
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'message': f'Health check failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('index.html')

    try:
        data = request.get_json()

        # Validate required fields
        if not data.get('company_id'):
            return jsonify({'success': False, 'error': 'Company ID is required'}), 400

        # Create new user
        user = User(
            company_id=data['company_id'].lower().strip(),
            department=data.get('department', '').lower().strip() if data.get('department') else None,
            role_level=data.get('role_level', '').lower().strip() if data.get('role_level') else None
        )

        db.session.add(user)
        db.session.commit()

        # Set session
        session['user_id'] = user.id
        session['company_id'] = user.company_id

        logger.info(f"New user registered: {user.id[:8]}... in {user.company_id}")

        return jsonify({
            'success': True,
            'message': 'Registration successful!',
            'redirect': '/questionnaire'
        })

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Registration failed. Please try again.'
        }), 500

# ==================== QUESTION GENERATION ====================

def get_fallback_questions():
    """Get fallback questions when AI is not available"""
    return [
        {
            'id': 1,
            'question': 'How emotionally drained do you feel from your work responsibilities?',
            'type': 'scale',
            'scale_label': '1 = Not drained at all,10 = Completely exhausted',
            'category': 'emotional_exhaustion'
        },
        {
            'id': 2,
            'question': 'How much control do you feel you have over your work demands?',
            'type': 'scale',
            'scale_label': '1 = No control,10 = Complete control',
            'category': 'job_control'
        },
        {
            'id': 3,
            'question': 'What specific work situations or tasks are causing you the most stress this week?',
            'type': 'text',
            'placeholder': 'Describe specific stressors, deadlines, conflicts, or challenges...',
            'category': 'work_stressors'
        },
        {
            'id': 4,
            'question': 'How has your work been affecting your personal life and relationships recently?',
            'type': 'text',
            'placeholder': 'Share how work impacts your time, energy, mood, or relationships...',
            'category': 'work_life_impact'
        },
        {
            'id': 5,
            'question': 'What would need to change at work for you to feel more supported and less stressed?',
            'type': 'text',
            'placeholder': 'Describe changes in workload, support, resources, or environment...',
            'category': 'support_needs'
        }
    ]

@app.route('/api/questions')
def get_questions():
    """Generate personalized questions using clinical AI guidelines"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        # Get user info for personalization
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Update last active
        user.last_active = datetime.utcnow()
        db.session.commit()

        # Get clinical AI instance
        clinical_ai = get_clinical_ai()

        if clinical_ai and clinical_ai.kb.collection:
            # Use clinical AI to generate evidence-based questions
            questions = generate_clinical_questions(user, clinical_ai)
            logger.info(f"Generated {len(questions)} clinical AI questions for user {user_id[:8]}...")
        else:
            # Fallback to basic questions if clinical AI not available
            questions = get_fallback_questions()
            logger.info(f"Using fallback questions for user {user_id[:8]}... (Clinical AI not available)")

        return jsonify({
            'questions': questions,
            'user_context': {
                'department': user.department,
                'days_active': (datetime.utcnow() - user.created_at).days
            },
            'clinical_ai_enabled': clinical_ai is not None
        })

    except Exception as e:
        logger.error(f"Question generation error: {str(e)}")
        return jsonify({'error': 'Failed to generate questions'}), 500

def generate_clinical_questions(user, clinical_ai):
    """Generate 5 questions: 3 open-ended + 2 scale questions based on clinical guidelines"""

    # Get user's recent responses for context
    recent_responses = DailyResponse.query.filter_by(user_id=user.id) \
        .order_by(DailyResponse.created_at.desc()) \
        .limit(3).all()

    recent_concerns = []
    avg_score = 50  # default

    if recent_responses:
        scores = [r.burnout_score for r in recent_responses if r.burnout_score is not None]
        if scores:
            avg_score = sum(scores) / len(scores)

        for response in recent_responses:
            if response.concerns:
                try:
                    concerns = json.loads(response.concerns)
                    recent_concerns.extend(concerns)
                except json.JSONDecodeError:
                    pass

    # Query clinical guidelines for relevant assessment tools
    kb = clinical_ai.kb

    # Build query based on user context
    query_parts = []
    if avg_score > 70:
        query_parts.append("severe burnout assessment high risk clinical evaluation")
    elif avg_score > 40:
        query_parts.append("moderate burnout workplace stress assessment")
    else:
        query_parts.append("burnout prevention screening wellbeing assessment")

    if user.department:
        query_parts.append(f"{user.department} workplace")

    query = " ".join(query_parts)

    # Get relevant clinical guidelines
    guidelines = kb.query_guidelines(query, n_results=3)

    # Extract clinical context for question generation
    clinical_context = ""
    for guideline in guidelines:
        clinical_context += f"{guideline['content'][:200]}... "

    questions = []

    # Generate 2 SCALE questions using clinical AI
    scale_questions = generate_ai_scale_questions(clinical_context, user, avg_score)
    questions.extend(scale_questions)

    # Generate 3 OPEN-ENDED questions using clinical AI
    open_questions = generate_ai_open_questions(clinical_context, user, recent_concerns)
    questions.extend(open_questions)

    # Ensure we have exactly 5 questions and add sequential IDs
    questions = questions[:5]
    for i, q in enumerate(questions):
        q['id'] = i + 1

    return questions

def generate_ai_scale_questions(clinical_context, user, avg_score):
    """Generate 2 AI-powered scale questions based on clinical guidelines"""

    clinical_ai = get_clinical_ai()
    if not clinical_ai or not clinical_ai.openai_available:
        # Fallback scale questions
        return [
            {
                'question': 'How emotionally exhausted do you feel from work today?',
                'type': 'scale',
                'scale_label': '1 = Not exhausted at all, 10 = Completely drained',
                'category': 'emotional_exhaustion',
                'clinical_basis': 'MBI Emotional Exhaustion Scale'
            },
            {
                'question': 'How much control do you feel you have over your work demands?',
                'type': 'scale',
                'scale_label': '1 = No control, 10 = Complete control',
                'category': 'job_control',
                'clinical_basis': 'Job Demands-Control Model'
            }
        ]

    try:
        prompt = f"""
        Based on these clinical guidelines for workplace burnout assessment:
        
        {clinical_context}
        
        Generate exactly 2 scale-based questions (1-10 rating) for assessing workplace burnout and stress. 
        
        User context:
        - Department: {user.department or 'General'}  
        - Current risk level: {'High' if avg_score > 70 else 'Moderate' if avg_score > 40 else 'Low'}
        
        Requirements:
        - Questions should be based on validated clinical scales (MBI, BJSQ, Job Demands-Control, etc.)
        - 1-10 scale format with clear anchor points
        - Focus on key burnout indicators: emotional exhaustion, depersonalization, personal accomplishment, job demands, control
        - Make questions specific and actionable
        
        Return in this JSON format:
        {{
            "questions": [
                {{
                    "question": "question text",
                    "type": "scale",
                    "scale_label": "1 = anchor point, 10 = anchor point", 
                    "category": "category_name",
                    "clinical_basis": "source scale/model"
                }}
            ]
        }}
        """

        response = clinical_ai.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a clinical psychologist expert in workplace mental health assessment. Generate evidence-based burnout assessment questions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )

        ai_response = json.loads(response.choices[0].message.content)
        return ai_response.get('questions', [])[:2]  # Ensure exactly 2 questions

    except Exception as e:
        logger.error(f"AI scale question generation failed: {e}")
        # Return fallback questions
        return [
            {
                'question': 'How emotionally drained do you feel from your work responsibilities?',
                'type': 'scale',
                'scale_label': '1 = Not drained at all, 10 = Completely exhausted',
                'category': 'emotional_exhaustion',
                'clinical_basis': 'MBI Emotional Exhaustion Scale'
            },
            {
                'question': 'How often do you feel overwhelmed by your workload?',
                'type': 'scale',
                'scale_label': '1 = Never overwhelmed, 10 = Constantly overwhelmed',
                'category': 'work_overload',
                'clinical_basis': 'Job Demands-Resources Model'
            }
        ]

def generate_ai_open_questions(clinical_context, user, recent_concerns):
    """Generate 3 AI-powered open-ended questions based on clinical guidelines"""

    clinical_ai = get_clinical_ai()
    if not clinical_ai or not clinical_ai.openai_available:
        # Fallback open questions
        return [
            {
                'question': 'What specific work situations or tasks are causing you the most stress this week?',
                'type': 'text',
                'placeholder': 'Describe specific stressors, deadlines, conflicts, or challenges...',
                'category': 'work_stressors',
                'clinical_basis': 'Clinical Interview Assessment'
            },
            {
                'question': 'How has your work been affecting your personal life and relationships recently?',
                'type': 'text',
                'placeholder': 'Share how work impacts your time, energy, mood, or relationships...',
                'category': 'work_life_impact',
                'clinical_basis': 'Work-Life Balance Assessment'
            },
            {
                'question': 'What would need to change at work for you to feel more supported and less stressed?',
                'type': 'text',
                'placeholder': 'Describe changes in workload, support, resources, or environment...',
                'category': 'support_needs',
                'clinical_basis': 'Intervention Planning Assessment'
            }
        ]

    try:
        concerns_context = f"Previous concerns: {', '.join(recent_concerns[:3])}" if recent_concerns else "No previous concerns noted"

        prompt = f"""
        Based on these clinical guidelines for workplace burnout assessment:
        
        {clinical_context}
        
        Generate exactly 3 open-ended questions for clinical assessment of workplace burnout and stress.
        
        User context:
        - Department: {user.department or 'General'}
        - {concerns_context}
        
        Requirements:
        - Questions should elicit detailed responses about specific workplace stressors
        - Based on clinical interview best practices for burnout assessment  
        - Focus on: work stressors, coping mechanisms, support systems, work-life impact, intervention needs
        - Questions should be empathetic and professional
        - Help identify specific areas for intervention
        
        Return in this JSON format:
        {{
            "questions": [
                {{
                    "question": "question text",
                    "type": "text", 
                    "placeholder": "helpful placeholder text",
                    "category": "category_name",
                    "clinical_basis": "clinical rationale"
                }}
            ]
        }}
        """

        response = clinical_ai.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a clinical psychologist conducting a workplace mental health assessment. Generate thoughtful, evidence-based open-ended questions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=1000
        )

        ai_response = json.loads(response.choices[0].message.content)
        return ai_response.get('questions', [])[:3]  # Ensure exactly 3 questions

    except Exception as e:
        logger.error(f"AI open question generation failed: {e}")
        # Return fallback questions
        return [
            {
                'question': 'Describe the most challenging aspects of your current work situation',
                'type': 'text',
                'placeholder': 'Share specific challenges, stressors, or difficult situations you are facing...',
                'category': 'work_challenges',
                'clinical_basis': 'Clinical Interview Assessment'
            },
            {
                'question': 'How do you currently cope with work-related stress, and how effective are these strategies?',
                'type': 'text',
                'placeholder': 'Describe your coping methods and whether they help...',
                'category': 'coping_strategies',
                'clinical_basis': 'Coping Assessment'
            },
            {
                'question': 'What kind of support or changes would be most helpful for improving your work experience?',
                'type': 'text',
                'placeholder': 'Describe what support, resources, or changes would help most...',
                'category': 'support_preferences',
                'clinical_basis': 'Intervention Preference Assessment'
            }
        ]

# ==================== AI-POWERED RECOMMENDATIONS ====================

def generate_personalized_ai_recommendations(user_responses, burnout_score, clinical_context):
    """Generate personalized recommendations using AI based on specific user responses"""

    clinical_ai = get_clinical_ai()
    if not clinical_ai or not clinical_ai.openai_available:
        return get_smart_fallback_recommendations(user_responses, burnout_score)

    try:
        # Create detailed prompt for recommendation generation
        prompt = f"""
        Based on these clinical guidelines for workplace burnout:
        
        {clinical_context}
        
        USER'S SPECIFIC RESPONSES:
        {json.dumps(user_responses, indent=2)}
        
        BURNOUT RISK SCORE: {burnout_score}/100
        
        Generate exactly 3 personalized, detailed recommendations that directly address what this specific user shared in their responses.
        
        Requirements for each recommendation:
        1. Must be directly relevant to what the user described in their answers
        2. Should be evidence-based using the clinical guidelines provided
        3. Include specific, actionable steps they can implement
        4. Explain how this will help their particular situation
        5. Be 2-3 sentences long with practical details
        
        Return in this JSON format:
        {{
            "recommendations": [
                {{
                    "action": "detailed recommendation text addressing their specific situation",
                    "rationale": "why this helps their particular case based on clinical evidence",
                    "implementation": "specific steps to take",
                    "evidence_basis": "clinical guideline or research that supports this"
                }}
            ]
        }}
        
        Focus on their actual responses - if they mentioned specific stressors, address those. If they described particular challenges, provide solutions for those exact issues.
        """

        response = clinical_ai.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a clinical psychologist specializing in workplace mental health. Generate personalized, evidence-based recommendations that directly address the specific issues each individual describes in their responses."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,  # Lower temperature for more focused, relevant recommendations
            max_tokens=1200
        )

        ai_response = json.loads(response.choices[0].message.content)
        recommendations = ai_response.get('recommendations', [])

        # Format for app
        formatted_recommendations = []
        for i, rec in enumerate(recommendations[:3]):
            formatted_recommendations.append({
                'action': f"{rec['action']} {rec['implementation']}",
                'rationale': rec.get('rationale', ''),
                'type': 'personalized_ai',
                'priority': 'high' if i == 0 else 'medium',
                'evidence_based': True,
                'evidence_basis': rec.get('evidence_basis', 'Clinical guidelines')
            })

        logger.info(f"Generated {len(formatted_recommendations)} personalized AI recommendations")
        return formatted_recommendations

    except Exception as e:
        logger.error(f"AI recommendation generation failed: {e}")
        return get_smart_fallback_recommendations(user_responses, burnout_score)

def get_smart_fallback_recommendations(user_responses, burnout_score):
    """Generate smart fallback recommendations based on user responses when AI fails"""
    recommendations = []

    # Analyze user responses for keywords to provide relevant fallbacks
    all_responses_text = ""
    for response in user_responses.values():
        if isinstance(response, str):
            all_responses_text += response.lower() + " "

    # High stress indicators
    if burnout_score > 70 or any(word in all_responses_text for word in ['overwhelmed', 'exhausted', 'burned', 'too much']):
        recommendations.append({
            'action': 'Given your high stress levels, prioritize immediate stress reduction through the 4-7-8 breathing technique: breathe in for 4 counts, hold for 7, exhale for 8. Practice this 3 times daily and especially when you notice stress building. Research shows this activates your parasympathetic nervous system and can reduce cortisol levels within minutes.',
            'type': 'immediate',
            'priority': 'high',
            'evidence_based': True
        })

    # Workload issues
    if any(word in all_responses_text for word in ['workload', 'deadline', 'pressure', 'demands']):
        recommendations.append({
            'action': 'Based on your workload concerns, schedule a structured conversation with your supervisor within the next week. Prepare a list of your current responsibilities and time commitments. Propose specific solutions like task prioritization, deadline adjustments, or resource allocation. Frame it as seeking support to maintain quality work rather than complaining about volume.',
            'type': 'communication',
            'priority': 'high',
            'evidence_based': True
        })

    # Work-life balance issues
    if any(word in all_responses_text for word in ['balance', 'personal', 'family', 'home', 'time']):
        recommendations.append({
            'action': 'Establish a clear "transition ritual" between work and personal time. This could be a 10-minute walk, changing clothes, or reviewing tomorrow\'s priorities before closing your work. Research shows that mental boundaries are crucial for preventing work stress from contaminating personal time and relationships.',
            'type': 'boundary_setting',
            'priority': 'medium',
            'evidence_based': True
        })

    # Social/relationship issues
    if any(word in all_responses_text for word in ['conflict', 'team', 'colleague', 'support', 'alone']):
        recommendations.append({
            'action': 'Focus on building one supportive workplace relationship this month. Identify a colleague you trust and suggest brief regular check-ins or coffee breaks. Social support at work is one of the strongest predictors of job satisfaction and stress resilience. Even small connections can significantly buffer workplace stress.',
            'type': 'social_support',
            'priority': 'medium',
            'evidence_based': True
        })

    # General wellness if no specific issues detected
    if len(recommendations) == 0:
        recommendations = [
            {
                'action': 'Implement a daily 10-minute mindfulness practice using apps like Headspace or simple breathing exercises. Start with just 5 minutes if 10 feels overwhelming. Regular mindfulness practice has been shown to reduce workplace stress by 28% and improve emotional regulation within 4-6 weeks of consistent practice.',
                'type': 'preventive',
                'priority': 'medium',
                'evidence_based': True
            },
            {
                'action': 'Create a weekly stress review where you rate your stress levels and identify what contributed to good vs. difficult days. This self-awareness practice helps you recognize patterns and make proactive adjustments before stress becomes overwhelming. Use a simple 1-10 scale and note key triggers.',
                'type': 'monitoring',
                'priority': 'medium',
                'evidence_based': True
            },
            {
                'action': 'Prioritize sleep hygiene by establishing a consistent bedtime routine and aiming for 7-8 hours nightly. Poor sleep amplifies stress responses and reduces emotional resilience. Create a wind-down routine starting 1 hour before bed: dim lights, avoid screens, and try gentle stretching or reading.',
                'type': 'wellness',
                'priority': 'low',
                'evidence_based': True
            }
        ]

    return recommendations[:3]  # Return exactly 3 recommendations

# ==================== RESPONSE ANALYSIS ====================

def analyze_responses(questions, responses):
    """Analyze responses using clinical AI guidelines with personalized AI recommendations"""
    try:
        # Get clinical AI instance
        clinical_ai = get_clinical_ai()

        if clinical_ai:
            # Convert to format expected by clinical AI
            user_responses = {}
            for i, question in enumerate(questions):
                if i < len(responses) and responses[i]:
                    user_responses[question.get('category', f'question_{i}')] = responses[i]

            # Calculate basic burnout score for clinical context
            burnout_score = calculate_basic_burnout_score(questions, responses)

            # Get clinical context for AI recommendation generation
            clinical_context = clinical_ai.kb.get_clinical_context(user_responses, burnout_score)

            # Generate personalized AI recommendations based on user's specific answers
            ai_recommendations = generate_personalized_ai_recommendations(user_responses, burnout_score, clinical_context)

            # Get clinical analysis
            clinical_analysis = clinical_ai.generate_clinical_analysis(user_responses, burnout_score)

            # Convert clinical analysis to app format using AI-generated recommendations
            analysis = {
                'score': burnout_score,
                'urgency': determine_urgency(burnout_score),
                'concerns': extract_concerns_from_clinical(clinical_analysis),
                'recommendations': ai_recommendations,  # Use AI-generated recommendations
                'summary': clinical_analysis.get('analysis', 'Clinical analysis completed.'),
                'clinical_sources': clinical_analysis.get('clinical_sources', []),
                'confidence': clinical_analysis.get('confidence', 0.8)
            }

            logger.info(f"Clinical AI analysis completed - Score: {burnout_score:.1f}, AI Recommendations: {len(ai_recommendations)}")
            return analysis

        else:
            # Fallback to basic analysis
            logger.warning("Clinical AI not available, using fallback analysis")
            return get_fallback_analysis(questions, responses)

    except Exception as e:
        logger.error(f"Clinical analysis error: {str(e)}")
        return get_fallback_analysis(questions, responses)

def calculate_basic_burnout_score(questions, responses):
    """Calculate burnout score based on clinical assessment principles"""
    total_risk = 0
    scale_count = 0

    for i, question in enumerate(questions):
        if i >= len(responses) or not responses[i]:
            continue

        response = responses[i]
        category = question.get('category', '')

        if question['type'] == 'scale':
            try:
                scale_value = float(response)
                scale_count += 1

                # Clinical scoring based on category
                if category in ['anger_irritability', 'anxiety', 'fatigue', 'emotional_exhaustion']:
                    # Higher values = more risk
                    total_risk += scale_value * 10
                elif category in ['vigour', 'energy', 'satisfaction']:
                    # Lower values = more risk
                    total_risk += (11 - scale_value) * 10
                else:
                    # Default: assume lower is worse
                    total_risk += (11 - scale_value) * 10

            except ValueError:
                continue

    # Calculate score (0-100)
    if scale_count > 0:
        score = min(100, total_risk / scale_count)
    else:
        score = 50

    return score

def determine_urgency(score):
    """Determine urgency based on clinical thresholds"""
    if score >= 70:
        return 'high'
    elif score >= 40:
        return 'medium'
    else:
        return 'low'

def extract_concerns_from_clinical(clinical_analysis):
    """Extract concerns from clinical analysis"""
    concerns = []

    structured = clinical_analysis.get('structured', {})
    if structured.get('risk_factors'):
        concerns.extend(structured['risk_factors'])

    # Look for clinical indicators in analysis text
    analysis_text = clinical_analysis.get('analysis', '').lower()
    if 'high risk' in analysis_text:
        concerns.append('High burnout risk identified by clinical assessment')
    if 'professional help' in analysis_text:
        concerns.append('Clinical recommendation for professional evaluation')

    return concerns

def get_fallback_analysis(questions, responses):
    """Fallback analysis when clinical AI is not available"""
    # Calculate basic burnout score
    burnout_score = calculate_basic_burnout_score(questions, responses)
    urgency = determine_urgency(burnout_score)

    # Convert responses to user_responses format for smart fallback
    user_responses = {}
    for i, question in enumerate(questions):
        if i < len(responses) and responses[i]:
            user_responses[question.get('category', f'question_{i}')] = responses[i]

    # Basic rule-based concerns
    concerns = []
    if burnout_score >= 70:
        concerns.extend(['High stress levels detected', 'Significant risk of burnout'])
    elif burnout_score >= 40:
        concerns.append('Moderate stress levels detected')

    # Get smart recommendations based on responses
    recommendations = get_smart_fallback_recommendations(user_responses, burnout_score)

    return {
        'score': burnout_score,
        'urgency': urgency,
        'concerns': concerns,
        'recommendations': recommendations,
        'summary': generate_summary(burnout_score, concerns, urgency),
        'clinical_sources': [],
        'confidence': 0.5
    }

def generate_summary(score, concerns, urgency):
    """Generate a summary based on analysis results"""
    if score >= 70:
        return "Your responses indicate high stress levels. It's important to take immediate action to prevent burnout. Consider reaching out for support."
    elif score >= 40:
        return "Your wellbeing shows some areas of concern. Taking proactive steps now can help prevent more serious issues."
    else:
        return "You're managing well overall! Keep up the good habits and continue monitoring your wellbeing."

@app.route('/api/submit', methods=['POST'])
def submit_responses():
    """Submit questionnaire responses and get AI analysis"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        data = request.get_json()
        questions = data.get('questions', [])
        responses = data.get('responses', [])
        response_time = data.get('response_time_seconds', 0)

        if not questions or not responses:
            return jsonify({'error': 'Questions and responses are required'}), 400

        # Analyze responses using clinical AI with personalized recommendations
        analysis = analyze_responses(questions, responses)

        # Save to database
        daily_response = DailyResponse(
            user_id=user_id,
            questions=json.dumps(questions),
            responses=json.dumps(responses),
            burnout_score=analysis['score'],
            ai_analysis=json.dumps(analysis),
            concerns=json.dumps(analysis['concerns']),
            recommendations=json.dumps(analysis['recommendations']),
            urgency_level=analysis['urgency'],
            response_time_seconds=response_time
        )

        db.session.add(daily_response)
        db.session.commit()

        logger.info(f"Clinical AI analysis completed for user {user_id[:8]}... Score: {analysis['score']:.1f}, Urgency: {analysis['urgency']}")

        return jsonify({
            'success': True,
            'analysis': analysis,
            'message': 'Response analyzed and submitted successfully'
        })

    except Exception as e:
        logger.error(f"Response submission error: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to submit response'}), 500

# ==================== API ROUTES ====================

@app.route('/api/user-data')
def get_user_data():
    """Get user dashboard data with clinical insights"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required'}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get recent responses (last 30 days)
        recent_responses = DailyResponse.query.filter(
            DailyResponse.user_id == user_id,
            DailyResponse.created_at >= datetime.utcnow() - timedelta(days=30)
        ).order_by(DailyResponse.created_at.desc()).limit(30).all()

        # Calculate trends
        scores = [r.burnout_score for r in recent_responses if r.burnout_score is not None]
        trend = calculate_trend(scores)

        # Get latest clinical analysis if available
        latest_analysis = None
        clinical_sources = []
        if recent_responses:
            latest_response = recent_responses[0]
            analysis_data = latest_response.get_analysis_dict()
            if analysis_data:
                latest_analysis = analysis_data.get('analysis')
                clinical_sources = analysis_data.get('clinical_sources', [])

        return jsonify({
            'user': {
                'id': user.id,
                'company_id': user.company_id,
                'department': user.department,
                'role_level': user.role_level,
                'created_at': user.created_at.isoformat(),
                'last_active': user.last_active.isoformat() if user.last_active else None
            },
            'recent_responses': [r.to_dict() for r in recent_responses],
            'summary': {
                'total_responses': len(recent_responses),
                'average_score': sum(scores) / len(scores) if scores else 0,
                'trend': trend,
                'latest_analysis': latest_analysis,
                'clinical_sources': clinical_sources
            }
        })

    except Exception as e:
        logger.error(f"User data error: {str(e)}")
        return jsonify({'error': 'Failed to get user data'}), 500

def calculate_trend(scores):
    """Calculate trend from recent scores"""
    if len(scores) < 2:
        return 'insufficient_data'

    # Simple trend calculation
    recent_avg = sum(scores[:7]) / min(7, len(scores))  # Last week
    older_avg = sum(scores[7:14]) / min(7, len(scores[7:14])) if len(scores) > 7 else recent_avg

    if recent_avg > older_avg + 0.5:
        return 'worsening'
    elif recent_avg < older_avg - 0.5:
        return 'improving'
    else:
        return 'stable'

@app.route('/api/user-progress')
def get_user_progress():
    """Get detailed user progress analytics"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            # Return demo progress data
            return jsonify({
                'progress_data': {
                    'energy': random.uniform(6.5, 8.0),
                    'satisfaction': random.uniform(6.0, 7.5),
                    'balance': random.uniform(5.5, 7.0),
                    'stress': random.uniform(6.0, 7.5)
                },
                'trend_analysis': 'Gradual improvement over the past weeks',
                'streak': random.randint(3, 14)
            })

        # Get responses from last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        responses = DailyResponse.query.filter_by(user_id=user_id) \
            .filter(DailyResponse.created_at >= thirty_days_ago) \
            .order_by(DailyResponse.created_at.asc()).all()

        if not responses:
            return jsonify({
                'progress_data': {},
                'trend_analysis': 'No data available yet',
                'streak': 0
            })

        # Calculate progress metrics
        progress_data = calculate_progress_metrics(responses)

        # Calculate streak
        streak = calculate_check_in_streak(user_id)

        # Trend analysis
        trend_analysis = analyze_wellness_trend(responses)

        return jsonify({
            'progress_data': progress_data,
            'trend_analysis': trend_analysis,
            'streak': streak
        })

    except Exception as e:
        logger.error(f"User progress error: {str(e)}")
        return jsonify({'error': 'Failed to load progress data'}), 500

@app.route('/api/company-analytics')
def get_company_analytics():
    """Get company-wide analytics (demo data for now)"""
    try:
        period = request.args.get('period', '7d')

        # Generate realistic demo data
        demo_data = {
            'total_users': 147,
            'avg_wellness_score': 68.7,
            'high_risk_count': 12,
            'medium_risk_count': 28,
            'low_risk_count': 107,
            'participation_rate': 0.84,
            'department_breakdown': [
                {'department': 'Engineering', 'avg_score': 65.2, 'total': 45, 'high_risk': 8, 'medium_risk': 15},
                {'department': 'Sales', 'avg_score': 58.1, 'total': 35, 'high_risk': 12, 'medium_risk': 18},
                {'department': 'Marketing', 'avg_score': 72.3, 'total': 28, 'high_risk': 3, 'medium_risk': 8},
                {'department': 'HR', 'avg_score': 78.9, 'total': 15, 'high_risk': 1, 'medium_risk': 4},
                {'department': 'Finance', 'avg_score': 69.4, 'total': 24, 'high_risk': 2, 'medium_risk': 6}
            ],
            'trend_data': [
                {'date': '2025-07-20', 'avg_score': 67.2},
                {'date': '2025-07-21', 'avg_score': 68.1},
                {'date': '2025-07-22', 'avg_score': 69.3},
                {'date': '2025-07-23', 'avg_score': 68.7},
                {'date': '2025-07-24', 'avg_score': 70.1},
                {'date': '2025-07-25', 'avg_score': 69.8},
                {'date': '2025-07-26', 'avg_score': 68.9},
                {'date': '2025-07-27', 'avg_score': 68.7}
            ],
            'top_concerns': [
                {'name': 'Heavy Workload', 'count': 89, 'percentage': 60.5},
                {'name': 'Work-Life Balance', 'count': 67, 'percentage': 45.6},
                {'name': 'Lack of Recognition', 'count': 45, 'percentage': 30.6},
                {'name': 'Communication Issues', 'count': 38, 'percentage': 25.9},
                {'name': 'Limited Growth Opportunities', 'count': 29, 'percentage': 19.7}
            ]
        }

        return jsonify(demo_data)

    except Exception as e:
        logger.error(f"Company analytics error: {str(e)}")
        return jsonify({'error': 'Failed to load company analytics'}), 500

@app.route('/api/emergency-help', methods=['POST'])
def track_emergency_help():
    """Track emergency help usage (anonymous analytics)"""
    try:
        data = request.get_json()
        action = data.get('action', '')

        # Log emergency help usage for analytics (anonymized)
        logger.info(f"Emergency help action: {action}")

        # In a real app, you might store this in a separate analytics table
        # For now, just return success

        return jsonify({'success': True, 'message': f'Emergency action logged: {action}'})

    except Exception as e:
        logger.error(f"Emergency help tracking error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/export-data')
def export_user_data():
    """Export user's wellness data in various formats"""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        format_type = request.args.get('format', 'json').lower()

        # Get user's data
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get all responses
        responses = DailyResponse.query.filter_by(user_id=user_id) \
            .order_by(DailyResponse.created_at.desc()).all()

        if format_type == 'csv':
            return export_csv(responses)
        elif format_type == 'pdf':
            return export_pdf(responses, user)
        else:  # json
            return export_json(responses, user)

    except Exception as e:
        logger.error(f"Export error: {str(e)}")
        return jsonify({'error': 'Export failed'}), 500

@app.route('/api/clinical-sources')
def get_clinical_sources():
    """Get information about clinical sources used"""
    try:
        if not clinical_kb or not clinical_kb.collection:
            return jsonify({
                'sources': [],
                'message': 'Clinical guidelines not loaded'
            })

        # Get collection info
        collection_count = clinical_kb.collection.count()

        # Sample some guidelines to show sources
        sample_guidelines = clinical_kb.query_guidelines("burnout workplace mental health", n_results=5)

        sources = []
        for guideline in sample_guidelines:
            meta = guideline['metadata']
            sources.append({
                'source': meta['source'],
                'topic': meta['topic'],
                'evidence_level': meta['evidence_level'],
                'citation': meta['citation']
            })

        return jsonify({
            'total_guidelines': collection_count,
            'sources': sources,
            'message': f'Loaded {collection_count} clinical guidelines'
        })

    except Exception as e:
        logger.error(f"Error getting clinical sources: {e}")
        return jsonify({'error': 'Failed to get clinical sources'}), 500

# ==================== HELPER FUNCTIONS ====================

def export_csv(responses):
    """Export data as CSV"""
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    writer.writerow([
        'Date', 'Wellness Score', 'Urgency Level', 'Concerns', 'Recommendations'
    ])

    # Data rows
    for response in responses:
        try:
            concerns = json.loads(response.concerns) if response.concerns else []
            recommendations = json.loads(response.recommendations) if response.recommendations else []

            writer.writerow([
                response.created_at.strftime('%Y-%m-%d %H:%M'),
                response.burnout_score or 0,
                response.urgency_level or 'low',
                '; '.join(concerns),
                '; '.join([r.get('action', str(r)) for r in recommendations if isinstance(r, dict)])
            ])
        except Exception as e:
            logger.warning(f"CSV export row error: {e}")
            continue

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=bloom-wellness-data.csv'}
    )

def export_json(responses, user):
    """Export data as JSON"""
    data = {
        'user_info': {
            'id': user.id,
            'department': user.department,
            'role_level': user.role_level,
            'created_at': user.created_at.isoformat(),
            'total_responses': len(responses)
        },
        'wellness_data': []
    }

    for response in responses:
        data['wellness_data'].append({
            'date': response.created_at.isoformat(),
            'wellness_score': response.burnout_score,
            'urgency_level': response.urgency_level,
            'concerns': json.loads(response.concerns) if response.concerns else [],
            'recommendations': json.loads(response.recommendations) if response.recommendations else [],
            'summary': json.loads(response.ai_analysis).get('summary', '') if response.ai_analysis else ''
        })

    return jsonify(data)

def export_pdf(responses, user):
    """Export data as PDF report"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        story.append(Paragraph("🌸 Bloom Wellness Report", styles['Heading1']))
        story.append(Spacer(1, 20))

        # User info
        story.append(Paragraph(f"Department: {user.department or 'Not specified'}", styles['Normal']))
        story.append(Paragraph(f"Member Since: {user.created_at.strftime('%B %d, %Y')}", styles['Normal']))
        story.append(Paragraph(f"Total Check-ins: {len(responses)}", styles['Normal']))
        story.append(Spacer(1, 20))

        # Recent responses
        if responses:
            story.append(Paragraph("Recent Check-ins", styles['Heading2']))
            for response in responses[:10]:
                date_str = response.created_at.strftime('%B %d, %Y')
                score = response.burnout_score or 0
                story.append(Paragraph(f"{date_str} - Wellness Score: {score}/100", styles['Normal']))

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=bloom-wellness-report.pdf'}
        )

    except ImportError:
        logger.warning("reportlab not installed")
        return jsonify({'error': 'PDF export requires reportlab package'}), 501
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}")
        return jsonify({'error': 'PDF generation failed'}), 500

def calculate_progress_metrics(responses):
    """Calculate detailed progress metrics from responses"""
    if not responses:
        return {}

    # Mock category breakdown (in real app, you'd categorize questions)
    random.seed(len(responses))  # Consistent "random" data based on response count

    return {
        'energy': random.uniform(5.0, 8.5),
        'satisfaction': random.uniform(5.5, 8.0),
        'balance': random.uniform(4.5, 7.5),
        'stress': random.uniform(5.0, 8.0)
    }

def calculate_check_in_streak(user_id):
    """Calculate current check-in streak"""
    try:
        # Get all responses ordered by date descending
        responses = DailyResponse.query.filter_by(user_id=user_id) \
            .order_by(DailyResponse.created_at.desc()).all()

        if not responses:
            return 0

        # Convert to dates only
        response_dates = list(set(r.created_at.date() for r in responses))
        response_dates.sort(reverse=True)

        # Calculate streak
        streak = 0
        current_date = datetime.utcnow().date()

        for response_date in response_dates:
            if response_date == current_date or response_date == current_date - timedelta(days=streak):
                streak += 1
                current_date = response_date
            else:
                break

        return streak

    except Exception as e:
        logger.error(f"Streak calculation error: {str(e)}")
        return 0

def analyze_wellness_trend(responses):
    """Analyze wellness trend over time"""
    if len(responses) < 2:
        return "Not enough data for trend analysis"

    # Get scores from first and second half of responses
    mid_point = len(responses) // 2
    first_half_avg = sum(r.burnout_score or 0 for r in responses[:mid_point]) / mid_point
    second_half_avg = sum(r.burnout_score or 0 for r in responses[mid_point:]) / (len(responses) - mid_point)

    # Note: Lower burnout score = better wellness
    if second_half_avg < first_half_avg - 5:
        return "Significant improvement in wellness"
    elif second_half_avg < first_half_avg:
        return "Gradual improvement in wellness"
    elif second_half_avg > first_half_avg + 5:
        return "Wellness requires attention"
    else:
        return "Stable wellness levels"

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not Found',
        'message': 'The requested resource was not found',
        'available_endpoints': [
            '/',
            '/health',
            '/register',
            '/api/user-data',
            '/api/user-progress',
            '/api/company-analytics',
            '/api/emergency-help',
            '/api/export-data',
            '/api/clinical-sources'
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred',
        'timestamp': datetime.now().isoformat()
    }), 500

# ==================== INITIALIZATION ====================

def create_tables():
    """Create database tables"""
    with app.app_context():
        try:
            db.create_all()
            print("🌸 Bloom database initialized successfully!")

            # Test database connection
            user_count = User.query.count()
            response_count = DailyResponse.query.count()
            print(f"📊 Current users: {user_count}, Responses: {response_count}")

            # Create sample data if empty
            if user_count == 0:
                print("🌱 Creating sample data...")
                sample_user = User(
                    company_id='demo-company',
                    department='engineering',
                    role_level='senior'
                )
                db.session.add(sample_user)
                db.session.commit()
                print(f"✅ Sample user created: {sample_user.id[:8]}...")

        except Exception as e:
            print(f"❌ Database initialization failed: {e}")

if __name__ == '__main__':
    print("🚀 Starting Bloom server...")
    print("🌸 AI-powered burnout prevention platform")
    print("=" * 50)

    # Initialize database
    create_tables()

    print("🌐 Server will be available at:")
    print("   • http://localhost:5000")
    print("   • http://127.0.0.1:5000")
    print("\n📋 Available endpoints:")
    print("   • /health - System health check")
    print("   • /api/user-data - Demo dashboard data")
    print("   • /api/company-analytics - Company insights")
    print("   • /api/emergency-help - Emergency features")
    print("   • /api/clinical-sources - Clinical guidelines info")
    print("\n🛑 Press Ctrl+C to stop the server")
    print("=" * 50)

    # Start Flask app
    app.run(debug=True, port=5000, host='0.0.0.0')
