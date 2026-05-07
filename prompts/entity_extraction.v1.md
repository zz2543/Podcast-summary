---
role: entity_extraction
version: v1
lang_aware: true
---
Extract named entities from this podcast transcript in {lang}. Return JSON with
an `entities` array. Each item must include `name`, `kind`, and advisory `count`.

Allowed kinds are `person`, `book`, and `product`.

Transcript:
{transcript}
