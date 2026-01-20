import json

with open(r'C:\Users\elias\OneDrive - Skive College\Privat shit\Coding Project\Quote of the day\quotes_log.json', encoding='utf-8') as f:
    data = json.load(f)

print("=== QUOTES WITH ANONYM AUTHOR ===\n")
for q in data:
    if q['author'] == 'Anonym':
        print(f"QUOTE: {q['quote'][:60]}...")
        print(f"ORIG:  {q['original'][:100]}...")
        print()
