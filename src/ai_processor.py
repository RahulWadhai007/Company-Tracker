import os
import logging
from pydantic import BaseModel, Field
from typing import Optional, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ApplicationExtraction(BaseModel):
    """Extraction schema for parsing job application emails."""
    company: str
    role: str
    status: Literal['Applied', 'Assessment', 'Interview', 'Rejected', 'Offer']
    deadline: Optional[str]
    action_required: bool
    link: Optional[str]

def get_job_info_from_email(email_body: str) -> dict:
    """
    Passes email text to Gemini to extract structured job application information.
    Handles rate-limit fallback for the free tier.
    """
    
    # Try to extract the Gemini API Key, default logic if it's missing (helps UX).
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("No GOOGLE_API_KEY found, returning fallback mock extraction.")
        return _fallback_extraction()
        
    try:
        # Using Gemini 3 Flash Preview
        model = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            temperature=0.0,
            max_retries=2
        )
        
        # Enforce JSON structured output using Pydantic
        structured_llm = model.with_structured_output(ApplicationExtraction)
        
        prompt = PromptTemplate.from_template(
            """You are a precise job application data extraction engine.
            Extract the company name, job role, current pipeline status, any deadlines (strictly format as YYYY-MM-DD HH:MM:SS, output null if none), 
            a true/false boolean if the user needs to take any action, and link to an assessment or interview. 
            
            Valid Statuses: 'Applied', 'Assessment', 'Interview', 'Rejected', 'Offer'
            
            Email Text:
            {email_body}
            """
        )
        
        chain = prompt | structured_llm
        result = chain.invoke({"email_body": email_body})
        
        # Return as a simple dictionary
        if isinstance(result, ApplicationExtraction):
            return result.model_dump()
        return dict(result)

    except Exception as e:
        logger.error(f"Error extracting information via Gemini (possible 429 or auth issue): {e}")
        return _fallback_extraction()

def _fallback_extraction() -> dict:
    """Deterministic fallback if Gemini 429 limits hit."""
    return {
        "company": "Parse Error / Rate Limit Hit",
        "role": "Unknown",
        "status": "Applied",
        "deadline": None,
        "action_required": False,
        "link": None
    }

if __name__ == "__main__":
    test_text = "Hi Rahul! Your assessment for the AI Intern role at OpenAI is due in 48 hours. Please complete it here: https://hackerrank.com/openai"
    res = get_job_info_from_email(test_text)
    print("Extracted output:")
    print(res)
