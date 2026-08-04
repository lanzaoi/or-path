---
name: or-process-memory
description: Use OR-Path process memory — past solve process and key decisions via lessons retrieve/record; not standard answers; not Cognee.
---

# Process memory (≠ Skill)

- **Memory** = how we solved before + key pitfalls/decisions  
- **Skill** = general how-to playbooks (this file family)  
- **Never** treat lesson numbers as authority; always L0 solution + validate

## Auto path (product)

Retrieve node writes `notes/<slug>-lessons.json` via `orpath.process_memory`.

## CLI

```bat
orpath.bat memory-search --query "VRP capacity" --class vrp
orpath.bat memory-record --slug <slug> --class <pc> --summary "..."
```

## When researching/modeling

1. Read `notes/<slug>-lessons.md` if present.  
2. Apply **process** tips only.  
3. Do not copy past objective/tour into schema or paper as truth.
