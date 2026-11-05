from app.database import SessionLocal, Base, engine
from app import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Wipe old data
db.query(models.Asset).delete()
db.query(models.Fact).delete()
db.query(models.Rule).delete()
db.commit()

rules = [
    ("1.1", "tone", "Use a friendly, simple tone. Avoid heavy jargon."),
    ("1.2", "tone", "Do not use ALL CAPS for whole sentences."),
    ("2.1", "claims", "Never promise guaranteed results or guaranteed jobs."),
    ("2.2", "claims", "Do not use words like 'best in the world' or '100% success'."),
    ("3.1", "legal", "Every offer post must mention that terms and conditions apply."),
    ("4.1", "pricing", "Only show the current offer price in any post."),
    ("4.2", "pricing", "Never show old prices. Always use the current offer price."),
    ("5.1", "accessibility", "Do not use more than three emojis in one post."),
]
for code, cat, text in rules:
    db.add(models.Rule(code=code, category=cat, text=text))

db.add(models.Fact(key="diwali_price", value="999", old_values=[]))

posts = [
    ("Instagram post - Diwali offer",
     "Diwali sale! Get our course for only Rs 999. Limited time. T&C apply."),
    ("Facebook ad - Festive discount",
     "Light up your career this Diwali. Join now for just Rs 999. T&C apply."),
    ("LinkedIn post - Early bird",
     "Early bird offer: enroll today at Rs 999 and start learning. T&C apply."),
]
for title, content in posts:
    db.add(models.Asset(title=title, content=content, status="draft", flags=[]))

db.commit()
db.close()
print("Demo data loaded: 8 rules, 1 fact, 3 posts")