# Retrieval Profile — legacy O(N) scan (baseline)

- scale: **10,000 facts** · searches profiled: 40
- wall-clock per search (warm): **144.4 ms**
- store: SQLite (WAL)

## Cost decomposition (self-time by phase, from cProfile `tottime`)

| phase | self-time share |
|-------|-----------------|
| search total | 25.4% |
| scoring (lexical/exact/recency/temporal) | 18.2% |
| serialization + explainability metadata | 14.5% |
| temporal parsing | 11.1% |
| temporal filtering | 10.1% |
| explainability metadata | 8.4% |
| tokenization | 4.1% |
| normalization (build doc text) | 3.7% |
| row deserialization (json) | 2.2% |
| candidate scan (+ row deserialization) | 2.1% |

## Measured hotspots

1. **search total** dominates (25% self-time). This is the O(N) candidate scan: every scoped object is deserialized, tokenized, and its IDF corpus rebuilt on **every** query.
2. The scan + per-object tokenization/normalization is inherently O(corpus) and grows linearly with scale — the root cause of 116ms→722ms→7.4s (1k→10k→100k).
3. Temporal filtering, source-trust lookup, and explainability metadata are **per-candidate**, so they also scale with the candidate set, not the result set.

## Conclusion

The fix is to **shrink the candidate set before scoring**: an inverted (FTS) index returns only the objects that match the query terms (O(matches)), and the existing explainable scorer runs over that small set — preserving temporal/authority/exact components while removing the full-corpus scan. See ADR-016/017.

<details><summary>Top cProfile frames (cumulative)</summary>

```
         49602541 function calls in 15.038 seconds

   Ordered by: cumulative time
   List reduced from 57 to 40 due to restriction <40>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
       40    0.323    0.008   15.038    0.376 /Users/AI/Projects/epistemos/src/epistemos/core/__init__.py:1086(search)
       40    1.367    0.034   14.714    0.368 /Users/AI/Projects/epistemos/src/epistemos/retrieval/__init__.py:85(search)
   400000    1.207    0.000    5.140    0.000 /Users/AI/Projects/epistemos/src/epistemos/retrieval/__init__.py:157(_score_one)
   400000    0.966    0.000    2.947    0.000 /Users/AI/Projects/epistemos/src/epistemos/retrieval/__init__.py:220(_build)
   400040    0.141    0.000    2.458    0.000 /Users/AI/Projects/epistemos/src/epistemos/storage/sqlite.py:201(objects)
   400000    0.148    0.000    1.954    0.000 /opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/lib/python3.14/json/__init__.py:304(loads)
   400000    0.263    0.000    1.751    0.000 /opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/lib/python3.14/json/decoder.py:340(decode)
 13200040    1.499    0.000    1.499    0.000 {method 'get' of 'dict' objects}
   800000    0.629    0.000    1.309    0.000 {built-in method builtins.sum}
  2000000    0.741    0.000    1.305    0.000 /Users/AI/Projects/epistemos/src/epistemos/_util.py:68(parse_instant)
   400000    1.284    0.000    1.284    0.000 /opt/homebrew/Cellar/python@3.14/3.14.5/Frameworks/Python.framework/Versions/3.14/lib/python3.14/json/decoder.py:351(raw_decode)
   400000    0.209    0.000    1.211    0.000 /Users/AI/Projects/epistemos/src/epistemos/temporal/__init__.py:50(believed_at)
   800000    0.261    0.000    0.928    0.000 /Users/AI/Projects/epistemos/src/epistemos/temporal/__init__.py:32(instant_in_interval)
   400000    0.557    0.000    0.892    0.000 /Users/AI/Projects/epistemos/src/epistemos/retrieval/__init__.py:250(_why)
   400000    0.248    0.000    0.861    0.000 /Users/AI/Projects/epistemos/src/epistemos/retrieval/__init__.py:41(_object_text)
   400000    0.201    0.000    0.676    0.000 /Users/AI/Projects/epistemos/src/epistemos/temporal/__init__.py:43(valid_at)
   400040    0.274    0.000    0.635    0.000 /Users/AI/Projects/epistemos/src/epistemos/retrieval/__init__.py:35(_tokens)
   800000    0.299    0.000    0.434    0.000 {method 'join' of 'str' objects}
  1600000    0.404    0.000    0.404    0.000 {built-in method builtins.round}
       40    0.360    0.009    0.360    0.009 {method 'fetchall' of 'sqlite3.Cursor' objects}
  1600000    0.253    0.000    0.351    0.000 /Users/AI/Projects/epistemos/src/epistemos/retrieval/__init__.py:183(<genexpr>)
   400000    0.345    0.000    0.345    0.000 <string>:2(__init__)
  1600000    0.231    0.000    0.329    0.000 /Users/AI/Projects/epistemos/src/epistemos/retrieval/__init__.py:148(<genexpr>)
   800040    0.152    0.000    0.314    0.000 /Users/AI/Projects/epistemos/src/epistemos/_util.py:57(now_utc)
       40    0.241    0.006    0.271    0.007 {method 'sort' of 'list' objects}
   400040    0.208    0.000    0.208    0.000 {method 'findall' of 're.Pattern' objects}
  2000040    0.181    0.000    0.181    0.000 {built-in method math.log}
  2000000    0.178    0.000    0.178    0.000 {method 'append' of 'list' objects}
  1200000    0.177    0.000    0.177    0.000 {method 'count' of 'list' objects}
  2000080    0.168    0.000    0.168    0.000 {built-in method builtins.isinstance}
   800040    0.162    0.000    0.162    0.000 {built-in method now}
  2000120    0.153    0.000    0.153    0.000 {method 'lower' of 'str' objects}
```
</details>
