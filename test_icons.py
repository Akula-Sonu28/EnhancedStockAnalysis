"""Test icon set to verify correct arrow directions"""
import pandas as pd
import xlsxwriter

# Create test data
data = {
    'Stock': ['HIGH_PROFIT', 'MEDIUM_PROFIT', 'SMALL_PROFIT', 'SMALL_LOSS', 'MEDIUM_LOSS', 'HIGH_LOSS'],
    'MY_PROFIT_%': [0.15, 0.08, 0.02, -0.02, -0.08, -0.15]  # 15%, 8%, 2%, -2%, -8%, -15%
}

df = pd.DataFrame(data)

# Create Excel file
with pd.ExcelWriter('test_icons.xlsx', engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name='Test', index=False)
    workbook = writer.book
    worksheet = writer.sheets['Test']
    
    # Apply icon set - Method 1: With explicit icons
    worksheet.conditional_format('B2:B7', {
        'type': 'icon_set',
        'icon_style': '3_arrows',
        'icons': [
            {'criteria': '>=', 'type': 'number', 'value': 0.05},   # Green up
            {'criteria': '>=', 'type': 'number', 'value': -0.05},  # Yellow
            {'criteria': '<', 'type': 'number', 'value': -0.05}    # Red down
        ]
    })
    
    # Format as percentage
    percent_format = workbook.add_format({'num_format': '0.00%'})
    worksheet.set_column('B:B', 15, percent_format)

print("✅ Test file created: test_icons.xlsx")
print("\nExpected results:")
print("HIGH_PROFIT (15%):  GREEN ↑")
print("MEDIUM_PROFIT (8%): GREEN ↑")
print("SMALL_PROFIT (2%):  YELLOW →")
print("SMALL_LOSS (-2%):   YELLOW →")
print("MEDIUM_LOSS (-8%):  RED ↓")
print("HIGH_LOSS (-15%):   RED ↓")
print("\nPlease open test_icons.xlsx and verify the arrows match!")
