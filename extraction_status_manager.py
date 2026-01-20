"""
Shared extraction status manager module.
This module is imported by both app.py and extraction_agent.py to share extraction status.
"""

# Global extraction status dictionary
extraction_status = {}

def update_status(extraction_id: str, status_data: dict):
    """Update extraction status for a given extraction_id"""
    extraction_status[extraction_id] = status_data

def get_status(extraction_id: str):
    """Get extraction status for a given extraction_id"""
    return extraction_status.get(extraction_id)

def remove_status(extraction_id: str):
    """Remove extraction status for a given extraction_id"""
    if extraction_id in extraction_status:
        del extraction_status[extraction_id]

def clear_all():
    """Clear all extraction statuses"""
    extraction_status.clear()
