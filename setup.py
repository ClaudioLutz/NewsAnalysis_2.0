#!/usr/bin/env python3
"""
Quick setup script for the AI News Analysis System.

This script helps initialize the system by:
1. Creating necessary directories
2. Initializing the database
3. Loading feed configurations
4. Verifying the installation
"""

import os
import sys
from pathlib import Path

def create_directories():
    """Create necessary directories for the system."""
    directories = [
        "data",
        "out",
        "out/digests", 
        "logs",
        "fixtures",
        "fixtures/sample_feeds",
        "tests"
    ]
    
    for dir_name in directories:
        Path(dir_name).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {dir_name}")

def init_database():
    """Initialize the database."""
    print("\n🗄️  Initializing database...")
    try:
        from scripts.init_db import init_database
        init_database()
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False
    return True

def load_feeds():
    """Load feed configurations."""
    print("\n📰 Loading feed configurations...")
    try:
        from scripts.load_feeds import load_feeds_from_config
        load_feeds_from_config()
        print("✓ Feed configurations loaded successfully")
    except Exception as e:
        print(f"❌ Feed loading failed: {e}")
        return False
    return True

def verify_installation():
    """Verify that all components can be imported."""
    print("\n🔍 Verifying installation...")
    
    try:
        from news_pipeline import (
            NewsCollector, AIFilter, ContentScraper, 
            ArticleSummarizer, MetaAnalyzer
        )
        print("✓ Core pipeline components imported successfully")
        
        # Test basic functionality
        db_path = os.getenv("DB_PATH", "./news.db")
        collector = NewsCollector(db_path)
        filter_obj = AIFilter(db_path)
        
        print("✓ Components initialized successfully")
        return True
        
    except Exception as e:
        print(f"❌ Component verification failed: {e}")
        return False

def main():
    """Main setup function."""
    print("🚀 AI News Analysis System Setup")
    print("=" * 40)
    
    # Create directories
    create_directories()
    
    # Initialize database
    if not init_database():
        print("\n❌ Setup failed at database initialization")
        sys.exit(1)
    
    # Load feeds
    if not load_feeds():
        print("\n❌ Setup failed at feed loading")
        sys.exit(1)
    
    # Verify installation
    if not verify_installation():
        print("\n❌ Setup failed at verification")
        sys.exit(1)
    
    print("\n✅ Setup completed successfully!")
    print("\nNext steps:")
    print("1. Copy .env.example to .env and add your OpenAI API key")
    print("2. Run: python news_analyzer.py --help")
    print("3. Test with: python news_analyzer.py --stats")

if __name__ == "__main__":
    main()
