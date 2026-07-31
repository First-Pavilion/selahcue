//! Repository for [`ServicePlan`] persistence (FR-001/002).
//!
//! Maps the pure domain model to the `service_plan` / `plan_item` tables and back,
//! preserving item order and the id counter. Writes are transactional.

use crate::{DataError, Database, Result};
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
        // Stanza content serialized as the plain-text format; NULL = title-only
        // (identical to every pre-v6 row).
        let content = if item.stanzas.is_empty() {
            None
        } else {
            Some(selahcue_core::plan::stanzas_to_text(&item.stanzas))
        };
        tx.execute(
            "INSERT INTO plan_item (plan_id, item_id, ord, kind, title, planned_secs, owner, content, theme)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![
                plan_id,
                item.id.0 as i64,
                ord as i64,
                item.kind.as_tag(),
                item.title,
                item.planned_secs.map(|s| s as i64),
                item.owner,
                content,
                item.theme,
            ],
        )?;
    }
    tx.commit()?;
    Ok(plan_id)
}

/// Replace a persisted plan's name + items atomically (the plan-edit save path).
pub fn update(db: &Database, plan_id: i64, plan: &ServicePlan) -> Result<()> {
    let tx = db.conn().unchecked_transaction()?;
    let n = tx.execute(
        "UPDATE service_plan SET name = ?2, next_id = ?3 WHERE id = ?1",
        params![plan_id, plan.name, plan.next_id() as i64],
    )?;
    if n == 0 {
        return Err(DataError::NotFound);
    }
    tx.execute("DELETE FROM plan_item WHERE plan_id = ?1", params![plan_id])?;
    for (ord, item) in plan.items().iter().enumerate() {
        // Stanza content serialized as the plain-text format; NULL = title-only
        // (identical to every pre-v6 row).
        let content = if item.stanzas.is_empty() {
            None
        } else {
            Some(selahcue_core::plan::stanzas_to_text(&item.stanzas))
        };
        tx.execute(
            "INSERT INTO plan_item (plan_id, item_id, ord, kind, title, planned_secs, owner, content, theme)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
            params![
                plan_id,
                item.id.0 as i64,
                ord as i64,
                item.kind.as_tag(),
                item.title,
                item.planned_secs.map(|s| s as i64),
                item.owner,
                content,
                item.theme,
            ],
        )?;
    }
    tx.commit()?;
    Ok(())
}

/// Substring search over plan names (the library view; ASCII-case-insensitive per
/// SQLite LIKE semantics). `%`/`_` in the query are treated as LITERALS (escaped),
/// not wildcards. <300ms at 5k plans (perf-tested).
pub fn search(db: &Database, query: &str) -> Result<Vec<PlanSummary>> {
    let escaped = query
        .replace('\\', "\\\\")
        .replace('%', "\\%")
        .replace('_', "\\_");
    let conn = db.conn();
    let mut stmt = conn.prepare(
        "SELECT id, name FROM service_plan WHERE name LIKE '%' || ?1 || '%' ESCAPE '\\' ORDER BY id",
    )?;
    let rows = stmt.query_map(params![escaped], |r| {
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

/// Duplicate a stored plan under a new name (FR-005); returns the new row id.
pub fn duplicate(db: &Database, plan_id: i64, new_name: &str) -> Result<i64> {
    let plan = load(db, plan_id)?;
    insert(db, &plan.duplicate(new_name))
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
        "SELECT item_id, kind, title, planned_secs, owner, content, theme
         FROM plan_item WHERE plan_id = ?1 ORDER BY ord, item_id",
    )?;
    let rows = stmt.query_map(params![plan_id], |r| {
        Ok((
            r.get::<_, i64>(0)?,
            r.get::<_, String>(1)?,
            r.get::<_, String>(2)?,
            r.get::<_, Option<i64>>(3)?,
            r.get::<_, Option<String>>(4)?,
            r.get::<_, Option<String>>(5)?,
            r.get::<_, Option<String>>(6)?,
        ))
    })?;

    let mut items = Vec::new();
    for row in rows {
        // Bound the reload (audit M2 no-leak rule): never materialize more than
        // MAX_PLAN_ITEMS rows into memory, even if a corrupt/oversized row set was
        // persisted — mirrors the controller's remote-AddItem cap. `query_map` is lazy,
        // so breaking stops fetching the rest.
        if items.len() >= selahcue_core::plan::MAX_PLAN_ITEMS {
            break;
        }
        let (item_id, kind_tag, title, planned, owner, content, theme) = row?;
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
            // The parser is total, so any stored text loads (NULL = title-only).
            stanzas: content
                .map(|t| selahcue_core::plan::stanzas_from_text(&t))
                .unwrap_or_default(),
            // Per-item theme override (S8-3d); NULL = the global theme.
            theme,
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
    let n = db
        .conn()
        .execute("DELETE FROM service_plan WHERE id = ?1", params![plan_id])?;
    if n == 0 {
        Err(DataError::NotFound)
    } else {
        Ok(())
    }
}
