# Branch rulesets

`main-branch.json` is the protection applied to `main`, modelled on Idle Hours':

- `main` can't be deleted or force-pushed.
- The `test` CI job (lint and pytest) must pass.

GitHub doesn't read this file. After editing it, push the change yourself:

```bash
RULESET_ID=$(gh api /repos/gkoch02/Idle-Weather/rulesets --jq '.[] | select(.name=="Protect main") | .id')
gh api --method PUT "/repos/gkoch02/Idle-Weather/rulesets/$RULESET_ID" --input .github/rulesets/main-branch.json
```

If you add a CI job, add it to `required_status_checks` too. A required check must report on every PR, so CI has no paths filter.
