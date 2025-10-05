#!/usr/bin/env python3
"""Check digest_state table structure and content"""

import sqlite3

conn = sqlite3.connect('news.db')

print('=== digest_state table schema ===')
cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='digest_state'")
result = cursor.fetchone()
if result:
    print(result[0])
else:
    print('Table not found')

print('\n=== Row count ===')
cursor = conn.execute('SELECT COUNT(*) FROM digest_state')
print(f'Total rows: {cursor.fetchone()[0]}')

print('\n=== Sample data (first 2 rows) ===')
cursor = conn.execute('SELECT * FROM digest_state LIMIT 2')
for row in cursor.fetchall():
    print(row)

print('\n=== All dates in digest_state ===')
cursor = conn.execute('SELECT DISTINCT digest_date FROM digest_state ORDER BY digest_date DESC')
for row in cursor.fetchall():
    print(f'Date: {row[0]}')

conn.close()
