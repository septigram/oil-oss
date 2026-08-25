-- 先週発生した在庫マスター設定障害（ITYP-001）のインシデント件数
-- バインドパラメータ: period_start, period_end（last_week と同義）
SELECT COUNT(*) AS cnt
FROM oil_incidents i
WHERE i.type_id = 'ITYP-001'
  AND i.occurred_at >= :period_start
  AND i.occurred_at <= :period_end
