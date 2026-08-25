-- 先週発生した顧客ネットワーク障害（ITYP-004）のインシデント件数
-- バインドパラメータ: period_start, period_end（last_week と同義）
SELECT COUNT(*) AS cnt
FROM oil_incidents i
WHERE i.type_id = 'ITYP-004'
  AND i.occurred_at >= :period_start
  AND i.occurred_at <= :period_end
