from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from . import models
from .checker import check_text
from .passport import make_seal, guidelines_version
from fastapi.staticfiles import StaticFiles

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Inkloom AI")


class RuleIn(BaseModel):
    code: str
    text: str
    category: str = "general"

class FactIn(BaseModel):
    key: str
    value: str

class FactUpdate(BaseModel):
    value: str

class AssetIn(BaseModel):
    title: str
    content: str

class AssetEdit(BaseModel):
    content: str

class ApproveIn(BaseModel):
    approved_by: str


def asset_dict(a):
    return {"id": a.id, "title": a.title, "content": a.content,
            "status": a.status, "flags": a.flags,
            "approved_by": a.approved_by}


@app.get("/api/health")
def health():
    return {"ok": True}


# ---------- Rules ----------
@app.post("/api/rules")
def add_rule(data: RuleIn, db: Session = Depends(get_db)):
    if db.query(models.Rule).filter_by(code=data.code).first():
        raise HTTPException(400, "Rule code already exists")
    rule = models.Rule(code=data.code, text=data.text, category=data.category)
    db.add(rule); db.commit(); db.refresh(rule)
    return {"id": rule.id, "code": rule.code}

@app.get("/api/rules")
def list_rules(db: Session = Depends(get_db)):
    return [{"id": r.id, "code": r.code, "text": r.text, "category": r.category}
            for r in db.query(models.Rule).all()]


# ---------- Facts ----------
@app.post("/api/facts")
def add_fact(data: FactIn, db: Session = Depends(get_db)):
    if db.query(models.Fact).filter_by(key=data.key).first():
        raise HTTPException(400, "Fact already exists. Use PUT to change it.")
    fact = models.Fact(key=data.key, value=data.value, old_values=[])
    db.add(fact); db.commit(); db.refresh(fact)
    return {"id": fact.id, "key": fact.key, "value": fact.value}

@app.get("/api/facts")
def list_facts(db: Session = Depends(get_db)):
    return [{"key": f.key, "value": f.value, "old_values": f.old_values}
            for f in db.query(models.Fact).all()]


# ---------- LIVING GUIDELINES: change a fact, re-check approved content ----------
@app.put("/api/facts/{key}")
def update_fact(key: str, data: FactUpdate, db: Session = Depends(get_db)):
    fact = db.query(models.Fact).filter_by(key=key).first()
    if not fact:
        raise HTTPException(404, "Fact not found")
    old = fact.value
    if old != data.value:
        fact.old_values = (fact.old_values or []) + [old]
        fact.value = data.value
        db.commit()

    flagged = []
    for a in db.query(models.Asset).filter_by(status="approved").all():
        flags, _ = check_text(db, a.content, use_ai=False)
        if flags:
            a.status = "flagged"
            a.flags = flags
            flagged.append({"id": a.id, "title": a.title,
                            "why": flags[0]["why"]})
    db.commit()
    return {"changed": f"{old} -> {data.value}",
            "rechecked_approved_assets": True,
            "flagged": flagged}


# ---------- Assets ----------
@app.post("/api/assets")
def add_asset(data: AssetIn, db: Session = Depends(get_db)):
    asset = models.Asset(title=data.title, content=data.content,
                         status="draft", flags=[])
    db.add(asset); db.commit(); db.refresh(asset)
    return {"id": asset.id, "title": asset.title, "status": asset.status}

@app.get("/api/assets")
def list_assets(db: Session = Depends(get_db)):
    return [asset_dict(a) for a in db.query(models.Asset).all()]

@app.put("/api/assets/{asset_id}")
def edit_asset(asset_id: int, data: AssetEdit, db: Session = Depends(get_db)):
    a = db.get(models.Asset, asset_id)
    if not a:
        raise HTTPException(404, "Asset not found")
    a.content = data.content
    if a.status != "approved":      # approved assets keep status so the seal can break
        a.status = "draft"
        a.flags = []
    db.commit()
    return asset_dict(a)


# ---------- The AI checker ----------
@app.post("/api/assets/{asset_id}/check")
def check_asset(asset_id: int, use_ai: bool = True, db: Session = Depends(get_db)):
    a = db.get(models.Asset, asset_id)
    if not a:
        raise HTTPException(404, "Asset not found")
    flags, error = check_text(db, a.content, use_ai=use_ai)
    a.flags = flags
    if flags:
        a.status = "flagged"
    elif error:
        a.status = "draft"      # AI did not run, so it cannot be called clean
    else:
        a.status = "clean"
    db.commit()
    return {"id": a.id, "status": a.status, "flags": flags, "error": error}

# ---------- Human approval + Content Passport ----------
@app.post("/api/assets/{asset_id}/approve")
def approve_asset(asset_id: int, data: ApproveIn, db: Session = Depends(get_db)):
    a = db.get(models.Asset, asset_id)
    if not a:
        raise HTTPException(404, "Asset not found")
    if a.status != "clean":
        raise HTTPException(400, "Run the check first. Only clean content can be approved.")
    version = guidelines_version(db)
    a.seal = make_seal(a.content, data.approved_by, version)
    a.approved_by = data.approved_by
    a.approved_at = datetime.now()
    a.rule_version = version
    a.status = "approved"
    db.commit()
    return {"id": a.id, "status": a.status, "seal": a.seal}

@app.get("/api/assets/{asset_id}/passport")
def passport(asset_id: int, db: Session = Depends(get_db)):
    a = db.get(models.Asset, asset_id)
    if not a or not a.seal:
        raise HTTPException(404, "No passport. This asset is not approved yet.")
    current = make_seal(a.content, a.approved_by, a.rule_version)
    intact = current == a.seal
    return {"asset": a.title, "approved_by": a.approved_by,
            "approved_at": str(a.approved_at),
            "guidelines_version": a.rule_version,
            "seal": a.seal, "seal_intact": intact,
            "message": "Seal matches. Safe to publish." if intact
                       else "CHANGED AFTER APPROVAL. Do not publish."}
app.mount("/", StaticFiles(directory="static", html=True), name="static")