import pandas as pd

# Update the CSV Template
csv_path = 'data/human_review_template.csv'
df = pd.read_csv(csv_path)

# Add new columns if they don't exist
if 'reviewer_name_and_contact' not in df.columns:
    df.insert(0, 'reviewer_name_and_contact', '')  # Put at the front
if 'score_rationale_and_comments' not in df.columns:
    df['score_rationale_and_comments'] = ''

df.to_csv(csv_path, index=False)

# Update the Markdown Guide
guide_path = 'docs/human_review_guide.md'
with open(guide_path, 'r', encoding='utf-8') as f:
    guide_content = f.read()

# Prepend the new instructions
new_instructions = '''# Human Review Guide for Phase 7 (InfraSecBench)

**Research Paper:** *Valid but Vulnerable: The Security-by-Default Paradox in LLM-Generated Infrastructure*

Thank you for volunteering! To ensure the academic rigor and credibility of this research, we need to verify our human reviewers. 

### Instructions before starting:
1. **Identify Yourself:** In the eviewer_name_and_contact column of the CSV, please provide your Name and a link to your LinkedIn profile (or a professional email address). This will only be used to validate to reviewers/publishers that our human baseline was conducted by real, qualified professionals.
2. **Provide Rationale:** Human bias is natural. For each scenario you score, please leave a brief explanation in the score_rationale_and_comments column explaining *why* you chose those numbers.

'''

# Replace the old header with the new one
if "Thank you for volunteering!" not in guide_content:
    guide_content = guide_content.replace('# Human Review Guide for Phase 7\n\n', new_instructions)
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)

print("Template and Guide successfully updated.")
