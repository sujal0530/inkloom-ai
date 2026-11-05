import hashlib
from . import models


def make_seal(content, approver, rule_version):
    raw = f"{content}|{approver}|{rule_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def guidelines_version(db):
    rules = db.query(models.Rule).all()
    facts = db.query(models.Fact).all()
    return (1
            + sum((r.version or 1) - 1 for r in rules)
            + sum(len(f.old_values or []) for f in facts))