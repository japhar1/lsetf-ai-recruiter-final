from flask import Flask, request, jsonify
from flask_cors import CORS
import tempfile
import shutil
import uuid
import time
import re
import json
from pathlib import Path
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)

# Configuration
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'hackathon-secret-2024')
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 
        'https://lsetf-plp-ai-recruiter-tool.streamlit.app').split(',')

app.config.from_object(Config)

CORS(app, origins=Config.ALLOWED_ORIGINS)

# LSETF Program Configurations
LSETF_PROGRAMS = {
    "software_development": {
        "name": "Software Development Track",
        "description": "Full-stack web and mobile development",
        "required_skills": ["python", "javascript", "sql", "git"],
        "preferred_skills": ["react", "node.js", "django", "flask"]
    },
    "data_science": {
        "name": "Data Science & Analytics Track",
        "description": "Data analysis, machine learning, and business intelligence", 
        "required_skills": ["python", "sql", "pandas", "numpy"],
        "preferred_skills": ["scikit-learn", "matplotlib", "jupyter", "tableau"]
    }
}

# Skills database
SKILLS_DATABASE = {
    "programming": ["python", "javascript", "java", "html", "css", "sql", "php", "c++", "c#", "typescript"],
    "web": ["react", "angular", "vue", "node.js", "django", "flask", "bootstrap", "jquery"],
    "database": ["mysql", "postgresql", "mongodb", "sqlite", "redis", "elasticsearch"],
    "cloud": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform"],
    "data_science": ["pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "jupyter", "matplotlib", "tableau"]
}

ALL_SKILLS = []
for category, skills in SKILLS_DATABASE.items():
    ALL_SKILLS.extend(skills)

# Copy your working functions here:
def parse_file_safe(file_path):
    """Safely parse file with fallback options"""
    try:
        file_extension = file_path.suffix.lower()
        
        if file_extension == '.pdf':
            # Try multiple PDF parsing methods
            text = ""
            
            # Method 1: Try pdfplumber (may fail due to cryptography issue)
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                if text.strip():
                    return text.strip()
            except Exception as e:
                logger.warning(f"pdfplumber failed: {e}")
            
            # Method 2: Try PyPDF2 as fallback
            try:
                import PyPDF2
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                if text.strip():
                    return text.strip()
            except Exception as e:
                logger.warning(f"PyPDF2 failed: {e}")
            
            # Method 3: Basic text extraction attempt
            return "PDF parsing failed due to dependency issues. Please try with DOCX format."
        
        elif file_extension in ['.docx', '.doc']:
            try:
                import docx2txt
                text = docx2txt.process(file_path)
                return text.strip() if text else "No text extracted from document"
            except Exception as e:
                return f"DOCX parsing failed: {str(e)}"
        
        else:
            return f"Unsupported file format: {file_extension}"
    
    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        return f"File parsing error: {str(e)}"
    pass

def extract_skills_enhanced(text):
    """Enhanced skills extraction with better matching"""
    found_skills = []
    text_lower = text.lower()
    
    # Remove extra whitespace and normalize text
    text_normalized = ' '.join(text_lower.split())
    
    logger.info(f"Analyzing text of length: {len(text_normalized)}")
    logger.info(f"Text preview: {text_normalized[:200]}...")
    
    skills_found_debug = []
    
    for skill in ALL_SKILLS:
        skill_lower = skill.lower()
        
        # Multiple matching strategies
        found = False
        match_type = ""
        
        # Strategy 1: Exact word boundary match
        pattern = r'\b' + re.escape(skill_lower) + r'\b'
        if re.search(pattern, text_normalized):
            found = True
            match_type = "exact_boundary"
        
        # Strategy 2: Partial match for compound terms
        elif skill_lower in text_normalized:
            # Check if it's not part of a larger word (for simple skills)
            if len(skill_lower) > 3:  # Only for longer skills
                found = True
                match_type = "partial"
        
        # Strategy 3: Handle common variations
        variations = {
            'javascript': ['js', 'java script'],
            'python': ['py'],
            'c++': ['cpp', 'c plus plus', 'cplusplus'],
            'c#': ['c sharp', 'csharp'],
            'node.js': ['nodejs', 'node js'],
            'react': ['reactjs', 'react.js'],
            'angular': ['angularjs'],
            'vue': ['vuejs', 'vue.js']
        }
        
        if skill_lower in variations:
            for variation in variations[skill_lower]:
                if variation in text_normalized:
                    found = True
                    match_type = "variation"
                    break
        
        if found:
            # Find which category this skill belongs to
            category = "unknown"
            for cat, skills_list in SKILLS_DATABASE.items():
                if skill in skills_list:
                    category = cat
                    break
            
            skill_info = {
                "skill": skill,
                "category": category,
                "confidence": 1.0 if match_type == "exact_boundary" else 0.8,
                "match_type": match_type
            }
            
            found_skills.append(skill_info)
            skills_found_debug.append(f"{skill} ({match_type})")
    
    logger.info(f"Skills found: {skills_found_debug}")
    return found_skills  
    pass

def extract_experience_enhanced(text):
    """Enhanced experience extraction"""
    patterns = [
        r'(\d+)\+?\s*years?\s*(?:of\s*)?(?:work\s*)?experience',
        r'experience\s*:?\s*(\d+)\+?\s*years?',
        r'(\d+)\+?\s*yrs?\s*(?:of\s*)?(?:work\s*)?experience',
        r'(\d+)\+?\s*years?\s*(?:in|with|of)\s+',
        r'over\s+(\d+)\s*years?',
        r'more\s+than\s+(\d+)\s*years?',
        r'(\d+)\s*years?\s*working',
        r'worked\s*(?:for\s*)?(\d+)\s*years?'
    ]
    
    text_lower = text.lower()
    max_years = 0
    matches_found = []
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            try:
                years = int(str(match).replace('+', ''))
                if 0 < years <= 50:  # Reasonable range
                    max_years = max(max_years, years)
                    matches_found.append(f"{years} years")
            except ValueError:
                continue
    
    logger.info(f"Experience matches found: {matches_found}")
    return max_years
    pass

def extract_education_enhanced(text):
    """Enhanced education extraction with better patterns"""
    education_keywords = [
        r'\b(?:bachelor|b\.?sc|b\.?a|b\.?tech|b\.?eng|undergraduate)\b',
        r'\b(?:master|m\.?sc|m\.?a|m\.?tech|mba|graduate)\b',
        r'\b(?:phd|ph\.?d|doctorate|doctoral)\b',
        r'\b(?:diploma|certificate|certification)\b',
        r'\b(?:degree|qualification)\b',
        r'\b(?:university|college|institute|school)\b',
        r'\b(?:ond|hnd)\b'  # Nigerian qualifications
    ]
    
    sentences = re.split(r'[.!?\n\r]', text)
    education_entries = []
    
    for sentence in sentences:
        sentence_clean = sentence.strip()
        if len(sentence_clean) < 10:  # Skip very short sentences
            continue
            
        sentence_lower = sentence_clean.lower()
        
        # Check if sentence contains education keywords
        for pattern in education_keywords:
            if re.search(pattern, sentence_lower):
                education_entries.append(sentence_clean)
                logger.info(f"Education match found: {sentence_clean[:100]}...")
                break
    
    # Remove duplicates while preserving order
    unique_education = []
    for edu in education_entries:
        if edu not in unique_education:
            unique_education.append(edu)
    
    return unique_education[:5]  # Return max 5 entries
    pass

def calculate_score_enhanced(skills, experience_years, education):
    """Enhanced scoring with debug info"""
    # Skills scoring (50% of total) - increased weight
    skills_count = len(skills)
    skills_score = min(skills_count / 6.0, 1.0)  # Reduced threshold for max score
    
    # Experience scoring (30% of total)
    experience_score = min(experience_years / 4.0, 1.0)  # Max at 4 years instead of 5
    
    # Education scoring (20% of total)
    education_count = len(education)
    education_score = min(education_count / 2.0, 1.0)  # Max at 2 education entries
    
    # Calculate weighted total
    total_score = (
        skills_score * 0.5 +
        experience_score * 0.3 +
        education_score * 0.2
    )
    
    logger.info(f"Scoring debug: skills={skills_count} (score: {skills_score:.2f}), experience={experience_years} (score: {experience_score:.2f}), education={education_count} (score: {education_score:.2f})")
    
    return {
        "total_score": round(total_score, 3),
        "skills_score": round(skills_score, 3),
        "experience_score": round(experience_score, 3),
        "education_score": round(education_score, 3)
    }
    pass

@app.route('/')
def home():
    return jsonify({
        "service": "LSETF AI Recruitment API",
        "status": "ready",
        "version": "hackathon",
        "programs": list(LSETF_PROGRAMS.keys())
    })

@app.route('/api/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "hackathon"
    })

@app.route('/api/programs')
def list_programs():
    return jsonify({
        "success": True,
        "programs": LSETF_PROGRAMS
    })

@app.route('/api/analyze-candidate', methods=['POST'])
def analyze_candidate():
    start_time = time.time()
    temp_path = None
    
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No file provided"}), 400
        
        file = request.files['file']
        program_type = request.form.get('program_type', 'software_development')
        
        if program_type not in LSETF_PROGRAMS:
            program_type = 'software_development'
        
        filename = secure_filename(file.filename)
        file_extension = Path(filename).suffix
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            file.save(temp_file.name)
            temp_path = Path(temp_file.name)
        
        # Process file
        raw_text = parse_file_safe(temp_path)
        skills = extract_skills_enhanced(raw_text)
        experience_years = extract_experience_enhanced(raw_text)
        education = extract_education_enhanced(raw_text)
        scores = calculate_score_enhanced(skills, experience_years, education)
        
        processing_time = time.time() - start_time
        
        return jsonify({
            "success": True,
            "candidate_id": str(uuid.uuid4()),
            "filename": filename,
            "program_type": program_type,
            "score": scores["total_score"],
            "score_breakdown": scores,
            "processing_time": round(processing_time, 2),
            "extracted_data": {
                "skills": skills,
                "experience_years": experience_years,
                "education": education
            },
            "recommendations": ["Analysis completed successfully"],
            "program_info": LSETF_PROGRAMS[program_type]
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
    finally:
        if temp_path:
            try:
                temp_path.unlink()
            except:
                pass

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=Config.DEBUG)