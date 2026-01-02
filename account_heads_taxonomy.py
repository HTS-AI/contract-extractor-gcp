"""
Account Heads Taxonomy
Comprehensive list of account head categories for invoice classification
"""

# Standard Chart of Accounts - Expense Categories
EXPENSE_ACCOUNT_HEADS = {
    # Operating Expenses
    "RENT_LEASE": "Rent & Lease Expense",
    "UTILITIES": "Utilities Expense",
    "OFFICE_SUPPLIES": "Office Supplies & Consumables",
    "REPAIRS_MAINTENANCE": "Repairs & Maintenance",
    "INSURANCE": "Insurance Expense",
    "TELECOMMUNICATIONS": "Telecommunications & Internet",
    
    # Professional Services
    "LEGAL_FEES": "Legal & Professional Fees",
    "CONSULTING": "Consulting & Advisory Services",
    "ACCOUNTING_AUDIT": "Accounting & Audit Fees",
    "IT_SERVICES": "IT & Technical Services",
    
    # Technology & Software
    "SOFTWARE_SUBSCRIPTIONS": "Software Subscriptions & Licenses",
    "IT_EQUIPMENT": "IT Equipment & Hardware",
    "CLOUD_SERVICES": "Cloud & Hosting Services",
    
    # Construction & Manufacturing
    "CONSTRUCTION": "Construction Expense",
    "RAW_MATERIALS": "Raw Materials & Components",
    "EQUIPMENT_RENTAL": "Equipment Rental",
    "LABOR_CONTRACTORS": "Labor & Contractor Charges",
    
    # Sales & Marketing
    "ADVERTISING": "Advertising & Marketing",
    "PROMOTIONAL": "Promotional Materials",
    "DIGITAL_MARKETING": "Digital Marketing & SEO",
    
    # HR & Employee
    "TRAINING": "Training & Development",
    "RECRUITMENT": "Recruitment & Hiring",
    "EMPLOYEE_BENEFITS": "Employee Benefits & Welfare",
    "PAYROLL_SERVICES": "Payroll Processing Services",
    
    # Travel & Transport
    "TRAVEL": "Travel & Accommodation",
    "VEHICLE": "Vehicle Maintenance & Fuel",
    "LOGISTICS_SHIPPING": "Logistics & Shipping",
    "COURIER": "Courier & Delivery Services",
    
    # Administrative
    "BANK_CHARGES": "Bank Fees & Charges",
    "PRINTING_STATIONERY": "Printing & Stationery",
    "SECURITY": "Security Services",
    "CLEANING_HOUSEKEEPING": "Cleaning & Housekeeping",
    
    # Other
    "MISCELLANEOUS": "Miscellaneous Expense",
    "GENERAL_EXPENSE": "General Expense",
}

# Revenue Categories
REVENUE_ACCOUNT_HEADS = {
    "SERVICE_REVENUE": "Service Revenue",
    "PRODUCT_SALES": "Product Sales Revenue",
    "CONSULTING_REVENUE": "Consulting Revenue",
    "RENTAL_INCOME": "Rental Income",
    "LICENSE_FEES": "License & Subscription Fees",
    "COMMISSION_INCOME": "Commission Income",
}

# Asset Purchase Categories
ASSET_ACCOUNT_HEADS = {
    "FIXED_ASSETS": "Fixed Asset Purchase",
    "EQUIPMENT_PURCHASE": "Equipment Purchase",
    "FURNITURE_FIXTURES": "Furniture & Fixtures",
    "VEHICLES": "Vehicle Purchase",
}

# All account heads combined
ALL_ACCOUNT_HEADS = {
    **EXPENSE_ACCOUNT_HEADS,
    **REVENUE_ACCOUNT_HEADS,
    **ASSET_ACCOUNT_HEADS
}

# Keywords for classification
ACCOUNT_HEAD_KEYWORDS = {
    "RENT_LEASE": ["rent", "lease", "rental", "premises", "office space", "property lease"],
    "UTILITIES": ["electricity", "water", "gas", "utility", "power", "energy", "sewage"],
    "OFFICE_SUPPLIES": ["office supplies", "stationery", "paper", "pens", "supplies", "consumables"],
    "REPAIRS_MAINTENANCE": ["repair", "maintenance", "servicing", "upkeep", "fix"],
    "INSURANCE": ["insurance", "premium", "policy", "coverage"],
    "TELECOMMUNICATIONS": ["telephone", "mobile", "internet", "broadband", "telecom", "wifi", "data plan"],
    
    "LEGAL_FEES": ["legal", "attorney", "lawyer", "advocate", "legal services"],
    "CONSULTING": ["consulting", "advisory", "consultant", "business advisory"],
    "ACCOUNTING_AUDIT": ["accounting", "audit", "bookkeeping", "tax filing", "financial audit"],
    "IT_SERVICES": ["IT services", "technical support", "system integration", "network setup"],
    
    "SOFTWARE_SUBSCRIPTIONS": ["software", "license", "subscription", "saas", "monthly plan", "annual license"],
    "IT_EQUIPMENT": ["computer", "laptop", "server", "hardware", "IT equipment", "workstation"],
    "CLOUD_SERVICES": ["cloud", "hosting", "aws", "azure", "cloud storage", "server hosting"],
    
    "CONSTRUCTION": ["construction", "building", "civil work", "fabrication", "installation"],
    "RAW_MATERIALS": ["raw material", "materials", "components", "parts", "supplies"],
    "EQUIPMENT_RENTAL": ["equipment rental", "machinery rental", "tool rental", "rental of equipment"],
    "LABOR_CONTRACTORS": ["labor", "contractor", "manpower", "workers", "labor charges"],
    
    "ADVERTISING": ["advertising", "advertisement", "ad campaign", "media", "billboard"],
    "PROMOTIONAL": ["promotional", "branding", "merchandise", "giveaway"],
    "DIGITAL_MARKETING": ["digital marketing", "seo", "social media", "google ads", "facebook ads"],
    
    "TRAINING": ["training", "workshop", "seminar", "course", "certification", "skill development"],
    "RECRUITMENT": ["recruitment", "hiring", "staffing", "headhunting", "placement"],
    "EMPLOYEE_BENEFITS": ["employee benefits", "health insurance", "welfare", "perks"],
    "PAYROLL_SERVICES": ["payroll", "salary processing", "payroll services"],
    
    "TRAVEL": ["travel", "flight", "hotel", "accommodation", "airfare", "lodging"],
    "VEHICLE": ["vehicle", "fuel", "petrol", "diesel", "car maintenance", "vehicle service"],
    "LOGISTICS_SHIPPING": ["logistics", "shipping", "freight", "cargo", "transportation"],
    "COURIER": ["courier", "delivery", "express", "parcel"],
    
    "BANK_CHARGES": ["bank charges", "bank fees", "transaction charges", "service charges"],
    "PRINTING_STATIONERY": ["printing", "photocopying", "binding", "lamination"],
    "SECURITY": ["security", "guard", "surveillance", "cctv", "security services"],
    "CLEANING_HOUSEKEEPING": ["cleaning", "housekeeping", "janitorial", "sanitation"],
}


def get_account_head_list():
    """Get formatted list of all account heads for AI classification."""
    result = []
    for key, name in ALL_ACCOUNT_HEADS.items():
        result.append(f"- {name}")
    return "\n".join(result)


def get_account_head_by_key(key):
    """Get account head name by key."""
    return ALL_ACCOUNT_HEADS.get(key, "General Expense")

