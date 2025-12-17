"""
Document Type Classifier
Detects whether a document is a Lease, NDA, or Contract.
"""

import json
from typing import Dict, Any, Optional
from openai import OpenAI


def classify_document_type(document_text: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Classify the document type (Lease, NDA, or Contract).
    
    Args:
        document_text: The text content of the document
        api_key: OpenAI API key (optional, will use env var if not provided)
        
    Returns:
        Dictionary with document_type, confidence, and reasoning
    """
    client = OpenAI(api_key=api_key)
    model = "gpt-4o-mini"
    
    # Truncate text if too long (keep first 3000 characters for classification)
    text_sample = document_text[:3000] if len(document_text) > 3000 else document_text
    
    prompt = f"""Analyze the following document and classify it as one of these three types:
1. LEASE - A lease agreement for property, equipment, or assets
2. NDA - A Non-Disclosure Agreement (also known as Confidentiality Agreement)
3. CONTRACT - A general contract or agreement (service agreement, employment contract, etc.)

DOCUMENT TEXT (sample):
{text_sample}

Based on the document content, classify it as LEASE, NDA, or CONTRACT.

Return your response in JSON format:
{{
    "document_type": "LEASE" | "NDA" | "CONTRACT",
    "confidence": "HIGH" | "MEDIUM" | "LOW",
    "reasoning": "Brief explanation of why this classification was chosen"
}}

IMPORTANT:
- Return ONLY valid JSON, no markdown, no explanations
- Be specific: if it's clearly a lease agreement, classify as LEASE
- If it's clearly an NDA/Confidentiality Agreement, classify as NDA
- If it's a general contract or agreement, classify as CONTRACT
- Use HIGH confidence if the document type is very clear, MEDIUM if somewhat clear, LOW if uncertain
"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a document classification expert. Classify documents as LEASE, NDA, or CONTRACT based on their content."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,  # Low temperature for consistency
            response_format={"type": "json_object"}
        )
        
        response_content = response.choices[0].message.content
        classification = json.loads(response_content) if isinstance(response_content, str) else response_content
        
        # Normalize document type
        doc_type = classification.get("document_type", "CONTRACT").upper()
        if doc_type not in ["LEASE", "NDA", "CONTRACT"]:
            doc_type = "CONTRACT"  # Default fallback
        
        return {
            "document_type": doc_type,
            "confidence": classification.get("confidence", "MEDIUM"),
            "reasoning": classification.get("reasoning", "Document analyzed and classified")
        }
    except Exception as e:
        # Fallback classification based on keywords
        return _fallback_classification(document_text)
    

def _fallback_classification(document_text: str) -> Dict[str, Any]:
    """
    Fallback classification using keyword matching if API call fails.
    
    Args:
        document_text: The text content of the document
        
    Returns:
        Dictionary with document_type, confidence, and reasoning
    """
    text_lower = document_text.lower()
    
    # NDA keywords
    nda_keywords = [
        "non-disclosure", "nondisclosure", "confidentiality agreement", 
        "confidential information", "proprietary information", "trade secret"
    ]
    nda_score = sum(1 for keyword in nda_keywords if keyword in text_lower)
    
    # Lease keywords
    lease_keywords = [
        "lease agreement", "lessor", "lessee", "rental agreement", 
        "lease term", "monthly rent", "security deposit", "premises"
    ]
    lease_score = sum(1 for keyword in lease_keywords if keyword in text_lower)
    
    # Determine type
    if nda_score > lease_score and nda_score > 0:
        return {
            "document_type": "NDA",
            "confidence": "MEDIUM",
            "reasoning": "Classified based on confidentiality and non-disclosure keywords found in document"
        }
    elif lease_score > nda_score and lease_score > 0:
        return {
            "document_type": "LEASE",
            "confidence": "MEDIUM",
            "reasoning": "Classified based on lease and rental keywords found in document"
        }
    else:
        return {
            "document_type": "CONTRACT",
            "confidence": "LOW",
            "reasoning": "Classified as general contract (no specific lease or NDA keywords found)"
        }

