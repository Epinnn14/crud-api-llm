# EXPLAIN ANALYZE: before and after the index (stretch)

Run on Postgres 16 against a table seeded with **200,000 tasks**, 1% of them done (`done = (g % 100 = 0)`). The query is the `?done=true` filter.

```text
--- WITHOUT index
                                                QUERY PLAN                                                
----------------------------------------------------------------------------------------------------------
 Seq Scan on tasks  (cost=0.00..3870.04 rows=1927 width=43) (actual time=0.008..10.039 rows=2001 loops=1)
   Filter: done
   Rows Removed by Filter: 198003
 Planning Time: 0.151 ms
 Execution Time: 10.125 ms
(5 rows)

--- WITH idx_tasks_done
                                                          QUERY PLAN                                                           
-------------------------------------------------------------------------------------------------------------------------------
 Index Scan using idx_tasks_done on tasks  (cost=0.29..283.21 rows=2000 width=43) (actual time=0.019..1.210 rows=2001 loops=1)
   Index Cond: (done = true)
 Planning Time: 0.192 ms
 Execution Time: 1.295 ms
(4 rows)

```

**Result:** the sequential scan read and discarded 198,003 rows in **10.1 ms**. With `idx_tasks_done`, Postgres jumps straight to the 2,001 matching rows in **1.3 ms**, about 8x faster. On a boolean column, an index only pays off when the value being searched for is rare. If half the rows were done, the planner would ignore the index and scan anyway.
