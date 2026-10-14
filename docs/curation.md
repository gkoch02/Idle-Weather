# Curation

Every quote in `weather_quotes.jsonl` was read and accepted. `curation.json` holds the verdicts:

```json
{"accepted": ["<key>", ...], "rejected": {"<key>": "<reason>", ...}}
```

A key is `source_id:paragraph:offset`: the Gutenberg id, the index of the prose paragraph in the book body, and the character offset of the phrase in that paragraph.

## What gets accepted

A quote is kept when a reader glancing at it would feel it describes that weather happening in the scene, so it fits being shown when that is the weather outside. It must also stand on its own as an excerpt and be filed under the right condition.

Reject reasons in use:

| Reason | Example |
|---|---|
| `figurative` | "his face as gloomy as a thunderstorm" |
| `passing_mention` | the weather is incidental to the sentence |
| `hypothetical` | forecasts, "if it should rain", habitual statements |
| `weather_over` | "the rain had ceased", "the fog was gone" |
| `wrong_condition` | a moonlit night filed under sunshine |
| `expository` | encyclopedic, agricultural or ship's-log text |
| `fragment` | dangling dialogue or missing context |
| `offensive` | slurs, ethnic caricature, dialect mockery |

When it is borderline, reject: the pool is large.

## Adding more

`idle-weather bake --queue output/review-queue.jsonl --queue-depth 400` lists the best unreviewed candidates per condition, deeper than the first pass reached. Review them and add the keys to `accepted` or `rejected`.
