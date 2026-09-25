//! A durable store for the bounded autosave-SLOT history (FR-005 "last-3"; ticket 86ajy0hxg).
//!
//! Mirrors [`crate::sermon_note_store::SermonNoteStore`] / [`crate::transcript_sink::TranscriptSink`]
//! exactly, for the same reason stated on both: `selahcue-app` must not depend on
//! `selahcue-data` (the crate graph runs the other way — `selahcue-desktop` depends on both as
//! siblings), so this trait is the seam a binary crate implements against its own `Database` +
//! `autosave_repo`. [`LiveController`](crate::LiveController) holds one as
//! `Box<dyn AutosaveStore>`, defaulting to [`NullAutosaveStore`] for a caller with no store
//! configured (e.g. the operator's stand-alone in-process demo shell).

use selahcue_core::plan::ServicePlan;

use crate::controller::ControllerSnapshot;

/// One listed restore point — the wire-facing summary
/// ([`selahcue_lan::protocol::AutosaveSlotView`]'s source data), without the full snapshot
/// payload `ListAutosaveSlots` does not need to move over the wire.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AutosaveSlotSummary {
    pub slot: i64,
    pub saved_at_ms: i64,
    pub label: Option<String>,
}

/// A durable store for the autosave-slot ring. Every method takes `&mut self` — mirrors
/// `SermonNoteStore`'s own signature and reasoning: a real implementation may want interior
/// mutability it does not have to expose, and `LiveController` already serializes every call
/// behind its own `Arc<Mutex<_>>` in real wiring, so `&mut self` costs nothing extra.
pub trait AutosaveStore: Send {
    /// List slots newest-first. `Err` only for a genuine storage failure — an empty history is
    /// `Ok(Vec::new())`, never an error.
    fn list_slots(&mut self) -> Result<Vec<AutosaveSlotSummary>, String>;

    /// Load one slot's full snapshot by id, integrity-checked (FR-079) before being trusted. A
    /// real implementation checks store integrity as part of this call — a corrupt store must
    /// surface as `Err`, never as a silently wrong snapshot. Returns the slot's plan ALONGSIDE
    /// its snapshot: an autosave slot may belong to a plan that has since been replaced (a
    /// different `service_plan` row than the one currently loaded), so the caller cannot assume
    /// the plan already in memory is the right one to reposition indices against. `Ok(None)` if
    /// the slot does not exist (already pruned, or never existed).
    fn load_slot(&mut self, slot: i64)
        -> Result<Option<(ServicePlan, ControllerSnapshot)>, String>;
}

/// The default no-op store: an empty history, nothing to restore. Matches
/// [`crate::sermon_note_store::NullSermonNoteStore`]'s degradation exactly.
pub struct NullAutosaveStore;

impl AutosaveStore for NullAutosaveStore {
    fn list_slots(&mut self) -> Result<Vec<AutosaveSlotSummary>, String> {
        Ok(Vec::new())
    }

    fn load_slot(
        &mut self,
        _slot: i64,
    ) -> Result<Option<(ServicePlan, ControllerSnapshot)>, String> {
        Ok(None)
    }
}
