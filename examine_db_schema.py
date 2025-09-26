#!/usr/bin/env python3
"""
Examine Database Schema Script
Investigates database constraints and triggers that prevent state transitions
"""

import sqlite3

def main():
    db_path = 'news.db'
    conn = sqlite3.connect(db_path)
    
    print('=== Database Schema - Items Table ===')
    cursor = conn.execute("PRAGMA table_info(items)")
    for row in cursor.fetchall():
        col_id, name, type_, not_null, default_val, pk = row
        nullable = "NOT NULL" if not_null else "nullable"
        default = f"default={default_val}" if default_val else "no default"
        print(f'{name} | {type_} | {nullable} | {default}')

    print('\n=== Database Triggers ===')
    cursor = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'")
    triggers = cursor.fetchall()
    if triggers:
        for name, sql in triggers:
            print(f'Trigger: {name}')
            print(f'{sql}\n')
    else:
        print('No triggers found')

    print('\n=== Database Constraints (Items Table Definition) ===') 
    cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='items'")
    table_def = cursor.fetchone()
    if table_def:
        print(table_def[0])
    
    print('\n=== Check Constraints ===')
    cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    for row in cursor.fetchall():
        if row[0] and 'CHECK' in row[0]:
            print("Found CHECK constraint:")
            print(row[0])

    conn.close()

if __name__ == "__main__":
    main()
