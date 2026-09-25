---
role: category_taxonomy
version: v1
lang_aware: true
---
You are organising a personal library of summarised videos and podcasts into
folders. Decide which NEW folders (categories) the library needs. Return JSON
with exactly one key, `new_categories`: a list of objects, each with `name`
and `reason`.

Existing categories (the user made or approved these; they all stay exactly as
they are — never rename, merge, repeat or remove them):
{existing}

Rules:

- Propose between {min_new} and {max_new} new categories. Propose none if the
  existing categories already fit every episode well.
- Prefer the existing categories. Add a new one only for a group of episodes
  that none of them fits.
- The categories must split THIS library in a useful way. If most episodes
  share one broad theme (for example they are all about AI or programming), do
  not propose that broad theme as a single category; split it by what the
  episodes are actually about (a tool, a practice, an audience, a kind of
  content). Avoid a category that would hold more than half of the library
  unless the library really has only one subject.
- A category should fit at least two episodes. Do not create a category for a
  single episode.
- `name` is a short folder name in {lang}: at most 12 characters, no numbering,
  no emoji, no quotes, no trailing punctuation.
- `reason` is one short sentence in {lang} naming which episodes it collects
  and why.

Episodes (label, title — one-line summary):
{episodes}
