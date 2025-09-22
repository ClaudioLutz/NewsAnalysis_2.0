# pip install trafilatura phonenumbers spacy
# python -m spacy download en_core_web_sm  # or de_core_news_sm / xx_ent_wiki_sm

import trafilatura, phonenumbers, spacy

URL = "https://egeli-informatik.ch/"
REGION = "CH"  # use "CH" for Switzerland, or None to parse internationally

from trafilatura import fetch_url, extract

downloaded = fetch_url(URL)
if downloaded:
    text = extract(downloaded, output_format="txt")
else:
    text = ""


# 2) Phone numbers
phones = []
if text:
    for match in phonenumbers.PhoneNumberMatcher(text, REGION):
        num = match.number
        phones.append(phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164))

# 3) Names via NER (English model shown; swap to your site’s language)
nlp = spacy.load("en_core_web_sm")
names = []
if text:
    doc = nlp(text)
    names = [ent.text for ent in doc.ents if ent.label_ in ("PERSON",)]

print("Phones:", sorted(set(phones)))
print("Names:", sorted(set(names)))
