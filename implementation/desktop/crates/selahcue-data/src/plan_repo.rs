//! Repository for [`ServicePlan`] persistence (FR-001/002).
//!
//! Maps the pure domain model to the `service_plan` / `plan_item` tables and back,
//! preserving item order and the id counter. Writes are transactional.

use crate::{Database, DataError, Result};
use rusqlite::params;
use selahcue_core::plan::{ItemId, ItemKind, PlanItem, ServicePlan};

/// A lightweight plan listing (id + name), for the library view.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PlanSummary {
    pub id: i64,
    pub name: String,
}

/// Insert a new plan and its items atomically; returns the new plan's row id.
pub fn insert(db: &Database, plan: &ServicePlan) -> Result<i64> {
    let tx = db.conn().unchecked_transaction()?;
    tx.execute(
        "INSERT INTO service_plan (name, next_id) VALUES (?1, ?2)",
        params![plan.name, plan.next_id() as i64],
    )?;
    let plan_id = tx.last_insert_rowid();
    for (ord, item) in plan.items().iter().enumerate() {
        tx.execute(
            "INSERT INTO plan_item (plan_id, item_id, ord, kind, title, planned_secs, owner)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
            params![
                plan_id,
                item.id.0 as i64,
                ord as i64,
                item.kind.as_tag(),
                item.title,
                item.planned_secs.map(|s| s as i64),
                item.owner,
            ],
        )?;
    }
    tx.commit()?;
    Ok(plan_id)
}

/// Load a plan (with ordered items) by row id.
pub fn load(db: &Database, plan_id: i64) -> Result<ServicePlan> {
    let conn = db.conn();
    let (name, next_id): (String, i64) = conn
        .query_row(
            "SELECT name, next_id FROM service_plan WHERE id = ?1",
            params![plan_id],
            |r| Ok((r.get(0)?, r.get(1)?)),
        )
        .map_err(|e| match e {
            rusqlite::Error::QueryReturnedNoRows => DataError::NotFound,
            other => DataError::from(other),
        })?;

    // `ord` is UNIQUE per plan; the `item_id` tie-breaker makes the order
    // deterministic even if a future writer ever duplicated an ord.
    let mut stmt = conn.prepare(
        "SELECT item_id, kind, title, planned_secs, owner
         FROM plan_item WHERE plan_id = ?1 ORDER BY ord, item_id",
    )?;
    let rows = stmt.query_map(params![plan_id], |r| {
        Ok((
            r.get::<_, i64>(0)?,
            r.get::<_, String>(1)?,
            r.get::<_, String>(2)?,
            r.get::<_, Option<i64>>(3)?,
            r.get::<_, Option<String>>(4)?,
        ))
    })?;

    let mut items = Vec::new();
    for row in rows {
        let (item_id, kind_tag, title, planned, owner) = row?;
        let kind = ItemKind::from_tag(&kind_tag)
            .ok_or_else(|| DataError::Corrupt(format!("unknown item kind '{kind_tag}'")))?;
        // Report out-of-range stored integers as corruption rather than silently
        // truncating (consistent with the unknown-kind handling above).
        let id = u64::try_from(item_id)
            .map_err(|_| DataError::Corrupt(format!("negative item_id {item_id}")))?;
        let planned_secs = match planned {
            Some(s) => Some(
                u32::try_from(s)
                    .map_err(|_| DataError::Corrupt(format!("planned_secs {s} out of range")))?,
            ),
            None => None,
        };
        items.push(PlanItem {
            id: ItemId(id),
            kind,
            title,
            planned_secs,
            owner,
        });
    }

    Ok(ServicePlan::from_parts(name, items, next_id as u64))
}

/// List all plans (id + name), ordered by id.
pub fn list(db: &Database) -> Result<Vec<PlanSummary>> {
    let conn = db.conn();
    let mut stmt = conn.prepare("SELECT id, name FROM service_plan ORDER BY id")?;
    let rows = stmt.query_map([], |r| {
        Ok(PlanSummary {
            id: r.get(0)?,
            name: r.get(1)?,
        })
    })?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r?);
    }
    Ok(out)
}

/// Delete a plan (items cascade). Errors `NotFound` if no such plan.
pub fn delete(db: &Database, plan_id: i64) -> Result<()> {
    let n = db.conn().execute(
        "DELETE FROM service_plan WHERE id = ?1",
        params![plan_id],
    )?;
    if n == 0 {
        Err(DataError::NotFound)
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_plan() -> ServicePlan {
        let mut p = ServicePlan::new("Sunday Service");
        let a = p.add_item(ItemKind::Announcement, "Welcome");
        let b = p.add_item(ItemKind::Song, "Great Are You Lord");
        p.add_item(ItemKind::Scripture, "Romans 8:28-30");
        p.get_mut(a).unwrap().planned_secs = Some(120);
        p.get_mut(b).unwrap().owner = Some("Worship".into());
        p
    }

    #[test]
    fn round_trips_a_plan_faithfully() {
        let db = Database::open_in_memory().unwrap();
        let original = sample_plan();
        let id = insert(&db, &original).unwrap();
        let loaded = load(&db, id).unwrap();
        // Equality covers name, every item (id/kind/title/planned/owner), order, and next_id.
        assert_eq!(loaded, original);
        // The rehydrated plan keeps the no-reuse invariant.
        let mut loaded = loaded;
        assert_eq!(loaded.add_item(ItemKind::Section, "X"), ItemId(4));
    }

    #[test]
    fn preserves_item_order() {
        let db = Database::open_in_memory().unwrap();
        let mut p = ServicePlan::new("Order");
        for t in ["A", "B", "C", "D"] {
            p.add_item(ItemKind::Song, t);
        }
        p.reorder(3, 0).unwrap(); // D to front
        let id = insert(&db, &p).unwrap();
        let loaded = load(&db, id).unwrap();
        let titles: Vec<_> = loaded.items().iter().map(|i| i.title.as_str()).collect();
        assert_eq!(titles, ["D", "A", "B", "C"]);
    }

    #[test]
    fn list_and_delete() {
        let db = Database::open_in_memory().unwrap();
        let id1 = insert(&db, &ServicePlan::new("First")).unwrap();
        let _id2 = insert(&db, &ServicePlan::new("Second")).unwrap();
        let listed = list(&db).unwrap();
        assert_eq!(listed.len(), 2);
        assert_eq!(listed[0].name, "First");

        delete(&db, id1).unwrap();
        let remaining = list(&db).unwrap();
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0].name, "Second");
        // Deleting the same plan again errors NotFound.
        assert!(matches!(delete(&db, id1), Err(DataError::NotFound)));
    }

    #[test]
    fn delete_missing_errors() {
        let db = Database::open_in_memory().unwrap();
        assert!(matches!(delete(&db, 999), Err(DataError::NotFound)));
    }

    #[test]
    fn deleting_plan_cascades_items() {
        let db = Database::open_in_memory().unwrap();
        let id = insert(&db, &sample_plan()).unwrap();
        delete(&db, id).unwrap();
        // Items are gone (cascade); loading errors NotFound.
        assert!(matches!(load(&db, id), Err(DataError::NotFound)));
        let orphan_items: i64 = db
            .conn()
            .query_row("SELECT COUNT(*) FROM plan_item", [], |r| r.get(0))
            .unwrap();
        assert_eq!(orphan_items, 0);
    }

    #[test]
    fn corrupt_kind_tag_is_reported() {
        let db = Database::open_in_memory().unwrap();
        let id = insert(&db, &ServicePlan::new("Bad")).unwrap();
        db.conn()
            .execute(
                "INSERT INTO plan_item (plan_id, item_id, ord, kind, title) VALUES (?1, 1, 0, 'gibberish', 'X')",
                params![id],
            )
            .unwrap();
        assert!(matches!(load(&db, id), Err(DataError::Corrupt(_))));
    }

    #[test]
    fn out_of_range_planned_secs_is_reported_not_truncated() {
        let db = Database::open_in_memory().unwrap();
        let id = insert(&db, &ServicePlan::new("Bad")).unwrap();
        // A stored planned_secs beyond u32 must surface as corruption, not wrap.
        db.conn()
            .execute(
                "INSERT INTO plan_item (plan_id, item_id, ord, kind, title, planned_secs)
                 VALUES (?1, 1, 0, 'song', 'X', ?2)",
                params![id, i64::from(u32::MAX) + 1],
            )
            .unwrap();
        assert!(matches!(load(&db, id), Err(DataError::Corrupt(_))));
    }

    #[test]
    fn backup_produces_a_loadable_copy() {
        let db = Database::open_in_memory().unwrap();
        let id = insert(&db, &sample_plan()).unwrap();
        let dst = tempfile::NamedTempFile::new().unwrap();
        db.backup_to(dst.path()).unwrap();

        let restored = Database::open(dst.path()).unwrap();
        restored.integrity_check().unwrap();
        let loaded = load(&restored, id).unwrap();
        assert_eq!(loaded.name, "Sunday Service");
        assert_eq!(loaded.len(), 3);
    }
}
