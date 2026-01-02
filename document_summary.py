"""
Document Summary Generator
Analyzes extracted contract data and generates a summary of what's present and missing.
Uses the new simplified JSON structure.
"""

from typing import Dict, Any, List, Tuple


def generate_paragraph_summary(extracted_data: Dict[str, Any], summary: Dict[str, Any]) -> str:
    """
    Generate a paragraph-style summary of approximately 100 words.
    
    Args:
        extracted_data: The extracted contract data dictionary
        summary: The detailed summary dictionary
        
    Returns:
        A paragraph string summarizing the document
    """
    sentences = []
    
    # Start with document identification
    document_type = extracted_data.get("document_type", "document")
    document_type_display = {
        "LEASE": "lease agreement",
        "NDA": "non-disclosure agreement (NDA)",
        "CONTRACT": "service contract"
    }.get(document_type.upper(), document_type.lower())
    
    sentences.append(f"This document is a {document_type_display}.")
    
    # Parties information
    party_names = extracted_data.get("party_names", {})
    party_1 = party_names.get("party_1", "")
    party_2 = party_names.get("party_2", "")
    
    if party_1 and party_2:
        sentences.append(f"The {document_type_display} involves two parties: {party_1} and {party_2}.")
    elif party_1:
        sentences.append(f"The {document_type_display} involves {party_1} as the primary party.")
    elif party_2:
        sentences.append(f"The {document_type_display} involves {party_2} as the primary party.")
    
    # Dates
    date_info = []
    if extracted_data.get("start_date"):
        date_info.append(f"start date of {extracted_data['start_date']}")
    if extracted_data.get("due_date"):
        date_info.append(f"due date of {extracted_data['due_date']}")
    
    if date_info:
        sentences.append(f"The document has a {', and '.join(date_info)}.")
    
    # Payment information
    amount = extracted_data.get("amount")
    frequency = extracted_data.get("frequency")
    per_period_amount = extracted_data.get("per_period_amount")
    per_month_amount = extracted_data.get("per_month_amount")
    period_name = extracted_data.get("period_name", "period")
    
    if amount:
        if frequency:
            sentences.append(f"Payment terms specify a total amount of {amount} with {frequency} frequency.")
            if per_period_amount:
                sentences.append(f"The amount per {period_name} is {per_period_amount}.")
                if per_month_amount and period_name != "month":
                    sentences.append(f"This is equivalent to {per_month_amount} per month.")
        else:
            sentences.append(f"Payment terms specify an amount of {amount}.")
    elif frequency:
        sentences.append(f"Payment frequency is set to {frequency}.")
    
    # Account type
    account_type = extracted_data.get("account_type")
    if account_type:
        sentences.append(f"The account type for this document is {account_type}.")
    
    # Completeness
    completeness = summary["overview"]["completeness_score"]
    if completeness >= 80:
        sentences.append(f"The document is highly complete ({completeness}% of expected fields present), containing most essential elements.")
    elif completeness >= 60:
        sentences.append(f"The document is moderately complete ({completeness}% of expected fields present), with several key elements identified.")
    else:
        sentences.append(f"The document has low completeness ({completeness}% of expected fields present), with many important elements missing.")
    
    # Missing critical items
    critical_missing = summary["missing_items"]["critical"]
    if critical_missing:
        missing_text = ", ".join(critical_missing[:3])
        if len(critical_missing) > 3:
            missing_text += f", and {len(critical_missing) - 3} other critical item(s)"
        sentences.append(f"Critical missing elements include {missing_text}, which should be addressed before execution.")
    
    # Risk assessment
    risk_data = extracted_data.get("risk_score")
    if risk_data and isinstance(risk_data, dict):
        risk_score = risk_data.get("score", 0)
        if risk_score > 70:
            sentences.append(f"The document has a high risk score of {risk_score}/100, requiring careful review.")
        elif risk_score > 50:
            sentences.append(f"The document has a moderate risk score of {risk_score}/100.")
        elif risk_score > 0:
            sentences.append(f"The document has a low risk score of {risk_score}/100.")
    
    # Combine sentences into paragraph
    paragraph = " ".join(sentences)
    
    # Trim to approximately 100 words if needed
    words = paragraph.split()
    if len(words) > 110:
        # Keep first ~100 words
        paragraph = " ".join(words[:100])
        # Ensure it ends properly
        if not paragraph.endswith('.'):
            paragraph += "..."
    
    return paragraph


def generate_document_summary(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a comprehensive summary of what's present and missing in the contract.
    Uses the new simplified JSON structure.
    
    Args:
        extracted_data: The extracted contract data dictionary
        
    Returns:
        Dictionary containing summary information with present and missing items
    """
    summary = {
        "overview": {
            "document_type": extracted_data.get("document_type"),
            "completeness_score": 0,
            "total_fields": 0,
            "filled_fields": 0
        },
        "present_items": {
            "basic_info": [],
            "parties": [],
            "dates": [],
            "financial": [],
            "other": []
        },
        "missing_items": {
            "critical": [],
            "important": [],
            "optional": []
        },
        "recommendations": []
    }
    
    # Track all fields
    total_fields = 0
    filled_fields = 0
    
    # Document Type
    document_type = extracted_data.get("document_type")
    if document_type:
        summary["present_items"]["basic_info"].append(("Document Type", document_type))
        filled_fields += 1
    else:
        summary["missing_items"]["critical"].append("Document Type")
    total_fields += 1
    
    # Parties
    party_names = extracted_data.get("party_names", {})
    party_1 = party_names.get("party_1", "")
    party_2 = party_names.get("party_2", "")
    additional_parties = party_names.get("additional_parties", [])
    
    if party_1:
        summary["present_items"]["parties"].append(("Party 1", party_1))
        filled_fields += 1
    else:
        summary["missing_items"]["critical"].append("Party 1 Name")
    total_fields += 1
    
    if party_2:
        summary["present_items"]["parties"].append(("Party 2", party_2))
        filled_fields += 1
    else:
        summary["missing_items"]["critical"].append("Party 2 Name")
    total_fields += 1
    
    if additional_parties and len(additional_parties) > 0:
        summary["present_items"]["parties"].append(("Additional Parties", f"{len(additional_parties)} additional party/parties"))
        filled_fields += 1
    total_fields += 1
    
    # Dates
    if extracted_data.get("start_date"):
        summary["present_items"]["dates"].append(("Start Date", extracted_data["start_date"]))
        filled_fields += 1
    else:
        summary["missing_items"]["critical"].append("Start Date")
    total_fields += 1
    
    if extracted_data.get("due_date"):
        summary["present_items"]["dates"].append(("Due Date", extracted_data["due_date"]))
        filled_fields += 1
    else:
        summary["missing_items"]["important"].append("Due Date")
    total_fields += 1
    
    # Financial Information
    amount = extracted_data.get("amount")
    if amount:
        summary["present_items"]["financial"].append(("Amount", amount))
        filled_fields += 1
    else:
        summary["missing_items"]["important"].append("Amount")
    total_fields += 1
    
    frequency = extracted_data.get("frequency")
    if frequency:
        summary["present_items"]["financial"].append(("Frequency", frequency))
        filled_fields += 1
    else:
        summary["missing_items"]["optional"].append("Frequency")
    total_fields += 1
    
    # Per-period amount (calculated)
    per_period_amount = extracted_data.get("per_period_amount")
    per_month_amount = extracted_data.get("per_month_amount")
    period_name = extracted_data.get("period_name", "period")
    if per_period_amount:
        summary["present_items"]["financial"].append((f"Per {period_name.capitalize()}", per_period_amount))
        if per_month_amount and period_name != "month":
            summary["present_items"]["financial"].append(("Per Month (equivalent)", per_month_amount))
        filled_fields += 1
    total_fields += 1
    
    # Account Type
    account_type = extracted_data.get("account_type")
    if account_type:
        summary["present_items"]["financial"].append(("Account Type", account_type))
        filled_fields += 1
    else:
        summary["missing_items"]["optional"].append("Account Type")
    total_fields += 1
    
    # Document IDs
    document_ids = extracted_data.get("document_ids", {})
    id_count = 0
    if document_ids.get("invoice_id"):
        summary["present_items"]["other"].append(("Invoice ID", document_ids["invoice_id"]))
        id_count += 1
    if document_ids.get("contract_id"):
        summary["present_items"]["other"].append(("Contract ID", document_ids["contract_id"]))
        id_count += 1
    if document_ids.get("reference_id"):
        summary["present_items"]["other"].append(("Reference ID", document_ids["reference_id"]))
        id_count += 1
    if document_ids.get("agreement_id"):
        summary["present_items"]["other"].append(("Agreement ID", document_ids["agreement_id"]))
        id_count += 1
    if document_ids.get("document_number"):
        summary["present_items"]["other"].append(("Document Number", document_ids["document_number"]))
        id_count += 1
    if document_ids.get("other_ids"):
        for idx, other_id in enumerate(document_ids["other_ids"], 1):
            summary["present_items"]["other"].append((f"Other ID {idx}", str(other_id)))
            id_count += 1
    if id_count > 0:
        filled_fields += 1
    total_fields += 1
    
    # Risk Score
    risk_data = extracted_data.get("risk_score")
    if risk_data and isinstance(risk_data, dict):
        risk_score = risk_data.get("score", 0)
        risk_level = risk_data.get("level", "Unknown")
        summary["present_items"]["other"].append(("Risk Score", f"{risk_score}/100 ({risk_level} Risk)"))
        filled_fields += 1
    else:
        summary["missing_items"]["optional"].append("Risk Score")
    total_fields += 1
    
    # Calculate completeness score
    if total_fields > 0:
        completeness_score = int((filled_fields / total_fields) * 100)
    else:
        completeness_score = 0
    
    summary["overview"]["completeness_score"] = completeness_score
    summary["overview"]["total_fields"] = total_fields
    summary["overview"]["filled_fields"] = filled_fields
    
    # Generate recommendations
    recommendations = []
    
    if len(summary["missing_items"]["critical"]) > 0:
        recommendations.append({
            "priority": "HIGH",
            "message": f"Critical items missing: {', '.join(summary['missing_items']['critical'])}. These should be addressed before signing.",
            "items": summary["missing_items"]["critical"]
        })
    
    if len(summary["missing_items"]["important"]) > 0:
        recommendations.append({
            "priority": "MEDIUM",
            "message": f"Important items missing: {', '.join(summary['missing_items']['important'])}. Consider adding these for clarity.",
            "items": summary["missing_items"]["important"]
        })
    
    if completeness_score < 50:
        recommendations.append({
            "priority": "HIGH",
            "message": f"Document completeness is low ({completeness_score}%). Many fields are missing. Review the document carefully.",
            "items": []
        })
    elif completeness_score < 70:
        recommendations.append({
            "priority": "MEDIUM",
            "message": f"Document completeness is moderate ({completeness_score}%). Some important information may be missing.",
            "items": []
        })
    
    # Check for risk factors
    if risk_data and isinstance(risk_data, dict):
        risk_score = risk_data.get("score", 0)
        if risk_score > 70:
            recommendations.append({
                "priority": "HIGH",
                "message": f"High risk score detected ({risk_score}/100). Review risk factors carefully before proceeding.",
                "items": []
            })
    
    summary["recommendations"] = recommendations
    
    # Generate paragraph summary
    summary["paragraph_summary"] = generate_paragraph_summary(extracted_data, summary)
    
    return summary
