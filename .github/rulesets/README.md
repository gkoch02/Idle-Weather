# Branch rulesets

`main-branch.json` is the protection applied to `main`, modelled on Idle Hours' and HomeDashboard's:

- `main` can't be deleted or force-pushed.
- Changes go through a pull request, with no approval needed. Review threads must be resolved before merging.
- The `test` CI job (lint and pytest) must pass.

GitHub doesn't read this file. After editing it, push the change yourself:

```bash
RULESET_ID=$(gh api /repos/gkoch02/IdleWeather/rulesets --jq '.[] | select(.name=="Protect main") | .id')
gh api --method PUT "/repos/gkoch02/IdleWeather/rulesets/$RULESET_ID" --input .github/rulesets/main-branch.json
```

If you add a CI job, add it to `required_status_checks` too, unless it is advisory. `idle-hours-main` is: it tests against Idle Hours' `main`, which can break without any change here, so it must not block merges. A required check must report on every PR, so CI has no paths filter.
