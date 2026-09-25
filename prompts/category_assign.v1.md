---
role: category_assign
version: v1
lang_aware: true
---
Put each episode below into the one category from the list that fits it best.
Return JSON with exactly one key, `assignments`: a list with one object per
episode, each with `episode` (the episode label, such as "e1") and `category`
(the category label, such as "c2", or null).

Categories (label, name):
{categories}

Rules:

- Answer for every episode label exactly once.
- Use only the category labels listed above. Do not invent categories.
- Judge by what the episode is mainly about, not by a passing mention.
- If no category fits, answer null. Do not force an episode into a poor fit.
- The episodes are written in {lang}; that does not change the labels you
  return.

Episodes:
{episodes}
