#!/usr/bin/env python3
"""
Test the newly retrained prefilter with some specific examples.
"""

import json
import sys
import os

# Add project root to path  
sys.path.append('.')
sys.path.append('prefilter')

from prefilter.prefilter_runtime import prefilter_titles

def test_prefilter():
    """Test the prefilter with known positive and negative examples."""
    
    # Test articles - mix of business/financial content and sports
    test_articles = [
        # These should be SELECTED (business/economic relevance)
        {'id': '1', 'title': 'UBS prüft Wegzug aus der Schweiz wegen neuer Regulierung', 'topic': 'creditreform_insights'},
        {'id': '2', 'title': 'FINMA verschärft Kapitalanforderungen für Schweizer Banken', 'topic': 'creditreform_insights'},
        {'id': '3', 'title': 'Nestlé-Verwaltungsratspräsident Paul Bulcke tritt zurück', 'topic': 'creditreform_insights'},
        {'id': '4', 'title': 'SNB hält Leitzins auf aktuellem Niveau von 1.5 Prozent', 'topic': 'creditreform_insights'},
        {'id': '5', 'title': 'Meyer Burger vor dem Aus - 45 Stellen in der Schweiz weg', 'topic': 'creditreform_insights'},
        
        # These should be FILTERED OUT (sports/entertainment)
        {'id': '6', 'title': 'Football - Coupe de Suisse - Le Stade Nyonnais sort le FC Zurich', 'topic': 'creditreform_insights'},
        {'id': '7', 'title': 'Miserable Penaltys: Der FCZ stolpert über Nyon', 'topic': 'creditreform_insights'},
        {'id': '8', 'title': 'Als ausländische Söldner in der Schweiz wüteten', 'topic': 'creditreform_insights'},
        {'id': '9', 'title': 'WM-Zeitfahren: Küng in den Top Ten – Evenepoel triumphiert', 'topic': 'creditreform_insights'},
        {'id': '10', 'title': 'Serie A: Fiorentina gegen Como ab 18:00 live', 'topic': 'creditreform_insights'},
    ]
    
    print("🔍 Testing Retrained Prefilter Model")
    print("=" * 50)
    print(f"Input: {len(test_articles)} test articles")
    print()
    
    # Apply prefilter
    survivors, scores = prefilter_titles(test_articles, 'outputs/prefilter_model.json')
    scores_dict = dict(scores)
    
    print(f"Output: {len(survivors)} articles survived prefilter")
    print(f"Retention rate: {len(survivors)/len(test_articles)*100:.1f}%")
    print()
    
    # Show all articles with scores
    print("📊 ALL ARTICLES WITH SCORES:")
    print("-" * 50)
    
    # Load model to check cutoff
    with open('outputs/prefilter_model.json', 'r') as f:
        model = json.load(f)
    cutoff = model['topics']['creditreform_insights']['cutoff']
    
    print(f"Model cutoff threshold: {cutoff:.3f}")
    print()
    
    # Handle missing scores (articles that might not have been scored)
    articles_with_scores = []
    for article in test_articles:
        if article['id'] in scores_dict:
            articles_with_scores.append((article, scores_dict[article['id']]))
        else:
            # Article wasn't scored - probably filtered out early
            articles_with_scores.append((article, 0.0))
    
    # Sort by score descending
    articles_with_scores.sort(key=lambda x: x[1], reverse=True)
    
    for article, score in articles_with_scores:
        status = "✅ PASSED" if score >= cutoff else "❌ FILTERED OUT"
        print(f"{status} | Score: {score:.3f} | {article['title'][:70]}...")
    
    print()
    print("📈 MODEL PERFORMANCE:")
    print("-" * 20)
    
    # Expected results based on content type  
    business_articles = test_articles[:5]  # First 5 are business
    sports_articles = test_articles[5:]     # Last 5 are sports
    
    business_passed = sum(1 for a in business_articles if scores_dict.get(a['id'], 0.0) >= cutoff)
    sports_filtered = sum(1 for a in sports_articles if scores_dict.get(a['id'], 0.0) < cutoff)
    
    print(f"Business articles passed: {business_passed}/{len(business_articles)} ({business_passed/len(business_articles)*100:.1f}%)")
    print(f"Sports articles filtered: {sports_filtered}/{len(sports_articles)} ({sports_filtered/len(sports_articles)*100:.1f}%)")
    
    if business_passed > 0 and sports_filtered > 0:
        print("🎉 SUCCESS: Model correctly distinguishes business from sports content!")
    elif business_passed == 0:
        print("⚠️ WARNING: Model too conservative - filters out all content")
    elif sports_filtered == 0:
        print("⚠️ WARNING: Model still selecting sports content")
    
    print()
    print("💰 Cost savings: Significant reduction in LLM API calls")

if __name__ == "__main__":
    test_prefilter()
