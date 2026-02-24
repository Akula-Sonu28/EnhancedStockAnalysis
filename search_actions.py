"""
Search for all possible action_recommendation values in the system
"""
import re

# Read the source file
with open('analyze_top200_stocks_enhanced.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all assignments to action_recommendation or action_type
patterns = [
    r'action_recommendation[\'"\]]\s*=\s*[\'"]([^\'"]+)[\'"]',
    r'action_type\s*=\s*[\'"]([^\'"]+)[\'"]',
    r'action_type\s*=\s*f[\'"]([^\'"]+)[\'"]',
]

all_actions = set()
for pattern in patterns:
    matches = re.findall(pattern, content)
    all_actions.update(matches)

print("ALL POSSIBLE ACTION VALUES:\n")
for action in sorted(all_actions):
    print(f"  • {action}")

print(f"\nTotal unique actions: {len(all_actions)}")
