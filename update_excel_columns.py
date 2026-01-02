"""
Script to update the contract_extractions.xlsx file with new column order.
Run this script when the Excel file is NOT open.
"""

import pandas as pd
from pathlib import Path

def update_excel_file():
    """Update the Excel file with new column order and datetime formatting."""
    excel_file = "contract_extractions.xlsx"
    
    # Check if file exists
    if not Path(excel_file).exists():
        print(f"Error: {excel_file} not found!")
        return False
    
    try:
        # Read the existing Excel file
        print(f"Reading {excel_file}...")
        df = pd.read_excel(excel_file)
        
        print(f"Current columns: {list(df.columns)}")
        print(f"Number of rows: {len(df)}")
        
        # Define new column order (Extracted At first)
        new_order = [
            'Extracted At',
            'Document Name',
            'Document Type',
            'Party Names',
            'Start Date',
            'Due Date',
            'Amount',
            'Currency',
            'Frequency',
            'Account Type (Head)',
            'ID',
            'Risk Score'
        ]
        
        # Reorder columns
        print("\nReordering columns...")
        df = df[new_order]
        
        # Convert 'Extracted At' to datetime format
        print("Converting 'Extracted At' to datetime format...")
        # Handle both Excel serial numbers and ISO datetime strings
        df['Extracted At'] = pd.to_datetime(df['Extracted At'], errors='coerce', origin='1899-12-30')
        
        # Save back to Excel with proper datetime formatting
        print(f"\nSaving to {excel_file}...")
        with pd.ExcelWriter(excel_file, engine='openpyxl', datetime_format='YYYY-MM-DD HH:MM:SS') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            
            # Get the worksheet and set column width for 'Extracted At' column
            worksheet = writer.sheets['Sheet1']
            worksheet.column_dimensions['A'].width = 20  # Column A = 'Extracted At'
        
        print("\n✅ Excel file updated successfully!")
        print(f"\nNew column order: {list(df.columns)}")
        print(f"\nFirst few rows:")
        print(df.head())
        
        return True
        
    except PermissionError:
        print(f"\n❌ Error: {excel_file} is currently open!")
        print("Please close the Excel file and run this script again.")
        return False
    except Exception as e:
        print(f"\n❌ Error updating Excel file: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Contract Extractions Excel Column Reorder Script")
    print("=" * 60)
    print()
    update_excel_file()
    print()
    print("=" * 60)

