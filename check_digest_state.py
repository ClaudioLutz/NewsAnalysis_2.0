import sqlite3

conn = sqlite3.connect('news.db')
conn.row_factory = sqlite3.Row

print("Digest states for 2025-10-04:")
print("-" * 80)
cur = conn.execute("""
    SELECT topic, article_count, created_at, updated_at 
    FROM digest_state 
    WHERE digest_date = '2025-10-04'
    ORDER BY topic
""")

for row in cur.fetchall():
    print(f"Topic: {row['topic']}")
    print(f"  Articles: {row['article_count']}")
    print(f"  Created: {row['created_at']}")
    print(f"  Updated: {row['updated_at']}")
    print()

conn.close()
