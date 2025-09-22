# streamlit_app.py
import streamlit as st
import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from pathlib import Path
import time
import json
from typing import Dict, List, Any

# Page configuration
st.set_page_config(
    page_title="LSETF AI Recruitment Tool",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for enhanced appearance
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .success-box {
        background: linear-gradient(135deg, #E8F5E8 0%, #C8E6C9 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #4CAF50;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    
    .candidate-card {
        background: linear-gradient(135deg, #F8F9FA 0%, #E9ECEF 100%);
        padding: 1.5rem;
        margin: 1rem 0;
        border-radius: 10px;
        border: 1px solid #DEE2E6;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.2s ease;
    }
    
    .candidate-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    
    .metric-card {
        background: linear-gradient(135deg, #FFFFFF 0%, #F8F9FA 100%);
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #E9ECEF;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .skill-tag {
        display: inline-block;
        background: linear-gradient(135deg, #007BFF 0%, #0056B3 100%);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 15px;
        margin: 0.2rem;
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    .program-selector {
        background: linear-gradient(135deg, #6C757D 0%, #495057 100%);
        color: white;
        border-radius: 8px;
        padding: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
BACKEND_URL = "https://lsetf-ai-recruiter-final.onrender.com"

# Initialize session state
if 'processing_results' not in st.session_state:
    st.session_state.processing_results = []
if 'analytics_data' not in st.session_state:
    st.session_state.analytics_data = None

def check_api_health() -> Dict[str, Any]:
    """Check API health and get service info"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=10)
        if response.status_code == 200:
            return {"status": "healthy", "data": response.json()}
        else:
            return {"status": "unhealthy", "error": f"Status code: {response.status_code}"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "error": str(e)}

def get_available_programs() -> Dict[str, Any]:
    """Get available LSETF programs"""
    try:
        response = requests.get(f"{BACKEND_URL}/api/programs", timeout=10)
        if response.status_code == 200:
            return response.json()
        return {"success": False, "programs": {}}
    except:
        return {"success": False, "programs": {}}

def analyze_single_resume(uploaded_file, program_type: str) -> Dict[str, Any]:
    """Send a single resume to the API for analysis"""
    try:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
        params = {"program_type": program_type}
        
        with st.spinner(f"🤖 Analyzing resume with {program_type} optimization..."):
            response = requests.post(
                f"{BACKEND_URL}/api/analyze-candidate",
                files=files,
                params=params,
                timeout=60
            )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "success": False, 
                "error": f"API Error: {response.status_code} - {response.text}"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_score_radar_chart(score_breakdown: Dict[str, float]) -> go.Figure:
    """Create a radar chart for score breakdown"""
    categories = []
    values = []
    
    # Map technical names to display names
    display_names = {
        "skills_match": "Skills Match",
        "skills_diversity": "Skills Diversity", 
        "experience_years": "Experience Years",
        "role_relevance": "Role Relevance",
        "education_level": "Education Level",
        "field_relevance": "Field Relevance",
        "portfolio_indicators": "Portfolio"
    }
    
    for key, value in score_breakdown.items():
        if key in display_names and isinstance(value, (int, float)):
            categories.append(display_names[key])
            values.append(min(value, 1.0))  # Cap at 1.0
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        name='Score',
        line=dict(color='#1E88E5', width=2),
        fillcolor='rgba(30, 136, 229, 0.3)'
    ))
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickmode='linear',
                tick0=0,
                dtick=0.2
            ),
            angularaxis=dict(
                tickfont=dict(size=12)
            )
        ),
        showlegend=False,
        title="Skills Assessment Profile",
        title_x=0.5,
        height=400,
        font=dict(size=11)
    )
    
    return fig

def create_skills_chart(skills_data: List[Dict[str, Any]]) -> go.Figure:
    """Create a skills breakdown chart"""
    if not skills_data:
        return go.Figure().add_annotation(text="No skills data available")
    
    # Group skills by category
    categories = {}
    for skill in skills_data:
        category = skill.get("category", "unknown").replace("_", " ").title()
        confidence = skill.get("confidence", 1.0)
        
        if category not in categories:
            categories[category] = []
        categories[category].append(confidence)
    
    # Calculate average confidence per category
    category_names = []
    avg_confidences = []
    skill_counts = []
    
    for category, confidences in categories.items():
        category_names.append(category)
        avg_confidences.append(sum(confidences) / len(confidences))
        skill_counts.append(len(confidences))
