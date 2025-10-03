import os
import sqlite3
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Get a sample summary
conn = sqlite3.connect('news.db')
conn.row_factory = sqlite3.Row
cur = conn.execute('SELECT summary FROM summaries WHERE summary IS NOT NULL LIMIT 1')
row = cur.fetchone()
summary = row['summary'] if row else None
conn.close()

if not summary:
    print("No summary found!")
    exit(1)

print(f"Testing with summary (first 200 chars):\n{summary[:200]}...\n")

# Test GPT call using Responses API
client = OpenAI()
instructions = """Extract 2-4 key bullet points from the following article summary. 
Each point should contain one concrete piece of information.
Return only the bullet points, one per line, starting with a dash (-)."""

response = client.responses.create(
    model=os.getenv("MODEL_MINI", "gpt-5-mini"),
    instructions=instructions,
    input=[{"role": "user", "content": f"Article summary:\n{summary}"}],
    max_output_tokens=500,
    reasoning={"effort": "low"}  # Reduce reasoning effort to get more output
)

print(f"Full response: {response}")
print(f"Model used: {response.model}")
print(f"Output text: '{response.output_text}'")
print(f"Output text length: {len(response.output_text) if response.output_text else 0}")

content = (response.output_text or "").strip()
print(f"\nGPT Response:\n{content}\n")

# Test parsing
lines = content.strip().split('\n')
key_points = []
for line in lines:
    line = line.strip()
    if not line:
        continue
    # Remove bullet markers
    if line.startswith('- ') or line.startswith('* '):
        line = line[2:]
    elif line.startswith('• '):
        line = line[2:]
    # Remove numbering
    import re
    line = re.sub(r'^\d+\.\s*', '', line)
    
    if line:
        key_points.append(line)

print(f"Parsed {len(key_points)} key points:")
for i, point in enumerate(key_points, 1):
    print(f"{i}. {point}")
