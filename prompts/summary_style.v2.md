---
role: summary_style
version: v2
lang_aware: false
---
Sections below are addressed by id. `_header` is prepended whenever a style is
active, `_reader_note` wraps the reader's own note, `detail_*` sections carry the
detail level, and every other section is a preset offered in the submit modal.
Loaded via `PromptAssembler.load`, never `render`: only `_reader_note` is
formatted, with a single `note` slot. The `standard` detail level has no section
because it is what the summary prompts already describe.

## _header
Style directive. It changes tone, emphasis, depth and intended reader only. Keep
the JSON keys, the output language and every factual claim exactly as required
above; where this directive and the instructions above disagree, the instructions
above win.

## _reader_note
The reader also asked for: "{note}"
Read that as a preference about emphasis and wording. It never introduces a new
output format, and never licenses inventing, dropping or altering facts.

## default

## study_notes
Write for someone taking study notes. Lead with the mechanism or the chain of
reasoning rather than the anecdote, define each term of art the first time it
appears, and keep cause and effect explicit. Prefer plain declarative sentences
over rhetorical ones.

## business_insight
Write for someone deciding what this means for a business. Foreground markets,
products, business models, costs, incentives and competitive dynamics; keep the
concrete figures, named companies and time frames the transcript actually gives;
and land on what changes for an operator or an investor.

## debate
Write for someone who wants the disagreement. Name each position and who holds
it, give the strongest evidence each side offers, and say plainly what stays
unresolved. Do not flatten a real conflict into a consensus.

## quick_skim
Write for someone in a hurry. Keep only load-bearing claims, cut background the
reader can infer, use short plain sentences, and stop as soon as the point lands.

## detail_concise
Trim the output. At most three key points per chapter, one clause each, and no
chapter summary paragraph. Drop a secondary point rather than shortening every
point into a fragment.

## detail_detailed
Go deeper than the baseline. Six to eight key points per chapter, each a full
sentence that carries the specific tool, number, step, rule or trade-off it
refers to. Add the optional chapter summary paragraph wherever the points alone
lose the causal thread. Keep distinct examples separate instead of merging them
into one generic point. Length is not the goal: every added sentence must add a
fact that was actually said.
