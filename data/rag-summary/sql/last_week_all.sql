-- 先週発生した全インシデント件数
-- バインドパラメータ:
--   period_start  先週の開始（月曜 00:00:00+09:00、含む）
--   period_end    先週の終了（日曜 23:59:59.999+09:00、含む）
SELECT COUNT(*) AS cnt
FROM oil_incidents i
WHERE i.occurred_at >= :period_start
  AND i.occurred_at <= :period_end
