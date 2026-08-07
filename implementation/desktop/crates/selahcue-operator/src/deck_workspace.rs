//! The operator-local **Presentation & Media** workspace (Design 2.0, Figma node 329:124).
//!
//! Owns the authored [`SlideDeck`] + [`MediaLibrary`] the console edits, plus the editor cursors
//! (selected slide / element, the live slide) and a **bounded** undo/redo snapshot stack. Every
//! mutation returns a [`DeckWorkspace::view`] JSON snapshot (a `DeckView`) the webview re-renders
//! from — the same one-round-trip pattern as `OperatorView`, but a **separate** operator-local
//! shape so the LAN-shared `OperatorView` (and its byte-pinned cross-language fixtures) is never
//! touched.
//!
//! The compositor stays native wgpu: the webview never lays a slide out itself — it draws the
//! base64 pixels [`DeckWorkspace::render_slide`] composes through `compose_authored_slide`
//! (ADR-0002/0003), exactly like the Theme Designer's `preview_theme`.

use std::collections::{HashMap, HashSet};
use std::path::Path;

use selahcue_core::media::{MediaId, MediaKind, MediaLibrary};
use selahcue_present::{
    media_usage, render_authored_slide, AuthoredSlide, Background, Element, Fit, FrameBuffer,
    ImageBackground, ImageFit, MediaRef, Rgba, ShapeKind, SlideDeck, SlideId, TextAlign, Theme,
    Transition, VAlign,
};
use serde_json::{json, Value};

/// Upper bound on the undo/redo history (no-leak): far above the ≥20 steps FR-016 requires, and
/// each entry is one bounded `SlideDeck` clone.
const MAX_UNDO: usize = 60;

/// The authored-deck editing workspace behind the Presentation surface.
pub struct DeckWorkspace {
    deck: SlideDeck,
    media: MediaLibrary,
    /// Audience theme used to compose slide previews (the fallback background + default styling).
    theme: Theme,
    selected: Option<SlideId>,
    /// Index into the selected slide's `elements` of the selected element, if any.
    selected_element: Option<usize>,
    /// The slide currently "presented" (Preview→Live: only `go_live` sets it — editing never does).
    live: Option<SlideId>,
    undo: Vec<SlideDeck>,
    redo: Vec<SlideDeck>,
}

impl DeckWorkspace {
    /// A demo workspace so the stand-alone console opens on a populated surface (mirrors
    /// `demo_shell`): the "Grace That Feeds" deck + a small media library (one asset deliberately
    /// missing, a few unused) matching the 329:124 mock.
    pub fn demo() -> Self {
        let mut deck = SlideDeck::new("Sermon: Grace That Feeds");
        // 1 — sermon title
        if let Some(id) = deck.add_slide() {
            if let Some(s) = deck.get_mut(id) {
                s.elements
                    .push(text_element("SERMON TITLE", 80, 300, 840, 90, 34));
                s.elements
                    .push(text_element("Grace That Feeds", 80, 400, 840, 220, 120));
            }
        }
        // 2 — scripture (the mock's selected slide)
        if let Some(id) = deck.add_slide() {
            if let Some(s) = deck.get_mut(id) {
                s.elements
                    .push(text_element("ISAIAH 61:5 · KJV", 80, 240, 700, 90, 34));
                s.elements.push(text_element(
                    "And strangers shall stand and feed your flocks, and the sons of the alien shall be your plowmen and your vinedressers.",
                    80, 360, 700, 420, 90,
                ));
                s.notes = "read slowly, pause after 'vinedressers'".to_string();
                s.transition = Transition::Fade;
            }
        }
        // 3 — testimony clip (video → a placeholder shape this pass; video render is deferred)
        if let Some(id) = deck.add_slide() {
            if let Some(s) = deck.get_mut(id) {
                s.elements
                    .push(shape_element(Rgba::rgb(30, 30, 44), 120, 200, 760, 500));
                s.elements
                    .push(text_element("▶ Testimony clip", 120, 720, 760, 90, 40));
            }
        }
        // 4 — sermon points
        if let Some(id) = deck.add_slide() {
            if let Some(s) = deck.get_mut(id) {
                s.elements
                    .push(text_element("3 Points", 80, 180, 840, 120, 90));
                s.elements.push(text_element(
                    "• Provision\n• Restoration\n• Purpose",
                    80,
                    340,
                    840,
                    480,
                    70,
                ));
            }
        }
        // 5 — a slide that USES a library image (so usage/unused counts are real)
        if let Some(id) = deck.add_slide() {
            if let Some(s) = deck.get_mut(id) {
                if let Some(source) = MediaRef::new("demo://harvest field.jpg") {
                    s.background = Some(Background::Image(ImageBackground { source }));
                }
                s.elements
                    .push(text_element("🖼 Harvest field", 80, 760, 840, 90, 44));
            }
        }
        // 6 — closing prayer
        if let Some(id) = deck.add_slide() {
            if let Some(s) = deck.get_mut(id) {
                s.elements
                    .push(text_element("Closing Prayer", 80, 420, 840, 180, 96));
            }
        }

        let mut media = MediaLibrary::new();
        // demo:// scheme → the missing-probe treats these as present except the one designated
        // missing, so the stand-alone surface shows a realistic "1 missing" without real files.
        media.import(
            "demo://harvest field.jpg",
            MediaKind::Image,
            2_400_000,
            Some(1920),
            Some(1080),
            None,
            0,
        );
        media.import(
            "demo://sunrise worship.jpg",
            MediaKind::Image,
            3_100_000,
            Some(1920),
            Some(1080),
            None,
            0,
        );
        media.import(
            "demo://testimony.mp4",
            MediaKind::Video,
            48_000_000,
            Some(1920),
            Some(1080),
            Some(134_000),
            0,
        );
        media.import(
            "demo://cross bokeh.jpg",
            MediaKind::Image,
            1_800_000,
            Some(1920),
            Some(1080),
            None,
            0,
        );
        media.import(
            "demo://particles.mov",
            MediaKind::Video,
            12_000_000,
            Some(1920),
            Some(1080),
            Some(30_000),
            0,
        );
        media.import(
            "demo://baptism.jpg",
            MediaKind::Image,
            2_000_000,
            Some(1920),
            Some(1080),
            None,
            0,
        );
        media.import(
            "demo://ambient pad.wav",
            MediaKind::Audio,
            33_000_000,
            None,
            None,
            Some(200_000),
            0,
        );
        media.import(
            "demo://offering bed.mp3",
            MediaKind::Audio,
            5_000_000,
            None,
            None,
            Some(245_000),
            0,
        );

        let selected = deck.slides().get(1).map(|s| s.id); // the scripture slide, as in the mock
        DeckWorkspace {
            deck,
            media,
            theme: Theme::dark(),
            selected,
            selected_element: None,
            live: None,
            undo: Vec::new(),
            redo: Vec::new(),
        }
    }

    // --- library open/switch -----------------------------------------------------------------

    /// The deck currently open for editing (the Library persists/lists a snapshot of this).
    pub fn open_deck(&self) -> &SlideDeck {
        &self.deck
    }

    /// Open `deck` for editing — the deck-switch path (Library "open"/"new"). Replaces the deck and
    /// resets the editing session: first slide selected, no element selected, Live cleared (the old
    /// deck's live slide is meaningless in a new deck — FR-012: switching is not "go live"), and the
    /// bounded undo/redo history dropped (a fresh document). The media library is unchanged (a
    /// shared asset library this pass; per-deck media is a follow-up).
    pub fn load_deck(&mut self, deck: SlideDeck) {
        self.selected = deck.slides().first().map(|s| s.id);
        self.deck = deck;
        self.selected_element = None;
        self.live = None;
        self.undo.clear();
        self.redo.clear();
    }

    /// Rename the open deck in place (the Library "rename" applied to the live editor).
    pub fn set_open_name(&mut self, name: String) {
        self.deck.name = name;
    }

    // --- snapshotting -----------------------------------------------------------------------

    /// Run an edit `f` and record an undo snapshot **only if it actually changed the deck**.
    /// `f` returns whether it edited; a no-op (e.g. the Image tool with no library image, an
    /// out-of-range index, or an at-cap add) records NOTHING — so a dead/blocked control can
    /// never push a phantom undo entry or silently wipe the redo stack. Bounded (`MAX_UNDO`).
    fn commit(&mut self, f: impl FnOnce(&mut Self) -> bool) {
        let before = self.deck.clone();
        if f(self) {
            self.undo.push(before);
            if self.undo.len() > MAX_UNDO {
                self.undo.remove(0);
            }
            self.redo.clear();
        }
    }

    /// The `MediaRef` of the first non-missing library image (the Image tool's default source).
    fn first_image_source(&self) -> Option<MediaRef> {
        let missing: HashSet<u64> = self
            .media
            .missing(missing_probe)
            .iter()
            .map(|m| m.0)
            .collect();
        self.media
            .assets()
            .iter()
            .find(|a| a.kind == MediaKind::Image && !missing.contains(&a.id.0))
            .and_then(|a| MediaRef::new(&a.path))
    }

    /// After a deck swap (undo/redo/restore), keep the cursors valid.
    fn fix_cursors(&mut self) {
        if let Some(id) = self.selected {
            if self.deck.index_of(id).is_none() {
                self.selected = self.deck.slides().first().map(|s| s.id);
            }
        } else {
            self.selected = self.deck.slides().first().map(|s| s.id);
        }
        let n = self
            .selected
            .and_then(|id| self.deck.get(id))
            .map_or(0, |s| s.elements.len());
        if self.selected_element.is_some_and(|i| i >= n) {
            self.selected_element = None;
        }
        if let Some(id) = self.live {
            if self.deck.index_of(id).is_none() {
                self.live = None;
            }
        }
    }

    fn effective_selected(&self) -> Option<SlideId> {
        self.selected
            .or_else(|| self.deck.slides().first().map(|s| s.id))
    }

    // --- slide list edits -------------------------------------------------------------------

    pub fn add_slide(&mut self) {
        self.commit(|w| {
            if let Some(id) = w.deck.add_slide() {
                w.selected = Some(id);
                w.selected_element = None;
                true
            } else {
                false
            }
        });
    }

    pub fn remove_slide(&mut self, id: u64) {
        self.commit(|w| {
            let removed = w.deck.remove(SlideId(id));
            if removed {
                w.fix_cursors();
            }
            removed
        });
    }

    pub fn duplicate_slide(&mut self, id: u64) {
        self.commit(|w| {
            if let Some(new_id) = w.deck.duplicate(SlideId(id)) {
                w.selected = Some(new_id);
                w.selected_element = None;
                true
            } else {
                false
            }
        });
    }

    pub fn reorder_slide(&mut self, from: usize, to: usize) {
        self.commit(|w| w.deck.reorder(from, to));
    }

    pub fn select_slide(&mut self, id: u64) {
        // Navigation, not an edit → no snapshot, Live untouched (FR-012).
        if self.deck.get(SlideId(id)).is_some() {
            self.selected = Some(SlideId(id));
            self.selected_element = None;
        }
    }

    // --- element edits ----------------------------------------------------------------------

    fn with_selected<R>(&mut self, f: impl FnOnce(&mut AuthoredSlide) -> R) -> Option<R> {
        let id = self.effective_selected()?;
        self.deck.get_mut(id).map(f)
    }

    pub fn add_element(&mut self, kind: &str) {
        self.commit(|w| {
            let el = match kind {
                "shape" => Some(shape_element(Rgba::rgb(124, 92, 255), 350, 380, 300, 240)),
                // "Background" adds a full-frame shape behind the content (a real background
                // placeholder until gradient/image background editing lands) — not the small
                // centred Shape box.
                "background" => Some(background_shape()),
                // "Image" adds the first non-missing library image as its source (swap via the
                // media panel); a no-op — recording nothing — when the library has no image.
                "image" => w
                    .first_image_source()
                    .map(|source| image_element(source, 200, 250, 600, 460)),
                _ => Some(text_element("Text", 200, 430, 600, 160, 90)),
            };
            match el {
                Some(el) => {
                    let idx = w.with_selected(|s| {
                        s.elements.push(el);
                        s.elements.len() - 1
                    });
                    w.selected_element = idx;
                    idx.is_some()
                }
                None => false,
            }
        });
    }

    pub fn add_image_element(&mut self, media_id: u64) {
        self.commit(|w| {
            let source = w
                .media
                .get(MediaId(media_id))
                .map(|a| a.path.clone())
                .and_then(|p| MediaRef::new(&p));
            match source {
                Some(source) => {
                    let idx = w.with_selected(|s| {
                        s.elements.push(image_element(source, 200, 250, 600, 460));
                        s.elements.len() - 1
                    });
                    w.selected_element = idx;
                    idx.is_some()
                }
                None => false,
            }
        });
    }

    pub fn remove_element(&mut self, index: usize) {
        self.commit(|w| {
            let removed = w
                .with_selected(|s| {
                    if index < s.elements.len() {
                        s.elements.remove(index);
                        true
                    } else {
                        false
                    }
                })
                .unwrap_or(false);
            if removed {
                w.selected_element = None;
            }
            removed
        });
    }

    pub fn select_element(&mut self, index: Option<usize>) {
        let n = self
            .effective_selected()
            .and_then(|id| self.deck.get(id))
            .map_or(0, |s| s.elements.len());
        self.selected_element = index.filter(|&i| i < n);
    }

    pub fn move_element(&mut self, index: usize, x: u16, y: u16, w: u16, h: u16) {
        self.commit(|ws| {
            let edited = ws
                .with_selected(|s| {
                    if let Some(el) = s.elements.get_mut(index) {
                        set_element_rect(
                            el,
                            x.min(1000),
                            y.min(1000),
                            w.clamp(1, 1000),
                            h.clamp(1, 1000),
                        );
                        true
                    } else {
                        false
                    }
                })
                .unwrap_or(false);
            if edited {
                ws.selected_element = Some(index);
            }
            edited
        });
    }

    pub fn set_element_z(&mut self, index: usize, z: i16) {
        self.commit(|w| {
            w.with_selected(|s| match s.elements.get_mut(index) {
                Some(el) => {
                    set_element_z(el, z);
                    true
                }
                None => false,
            })
            .unwrap_or(false)
        });
    }

    /// Reassign element z-order to match a FRONT→BACK `order` (the Layers panel drag/keyboard
    /// reorder). `order` must be a permutation of `0..len`; a malformed order is a **no-op** (never
    /// a panic). Distinct z-values are assigned so the compose paint order (z asc, then index) is
    /// exactly `order` — `order[0]` (frontmost) gets the highest z. One undo entry for the reorder.
    pub fn reorder_elements(&mut self, order: Vec<usize>) {
        self.commit(|w| {
            w.with_selected(|s| {
                let n = s.elements.len();
                if order.len() != n {
                    return false;
                }
                let mut seen = vec![false; n];
                for &i in &order {
                    if i >= n || seen[i] {
                        return false; // not a permutation of 0..n
                    }
                    seen[i] = true;
                }
                let mut changed = false;
                for (k, &i) in order.iter().enumerate() {
                    let new_z = (n - 1 - k) as i16; // front (k=0) → highest z
                    if let Some(el) = s.elements.get_mut(i) {
                        if el.z() != new_z {
                            set_element_z(el, new_z);
                            changed = true;
                        }
                    }
                }
                changed
            })
            .unwrap_or(false)
        });
    }

    pub fn toggle_element_visible(&mut self, index: usize) {
        self.commit(|w| {
            w.with_selected(|s| match s.elements.get_mut(index) {
                Some(el) => {
                    set_element_visible(el, !el.visible());
                    true
                }
                None => false,
            })
            .unwrap_or(false)
        });
    }

    pub fn set_element_text(&mut self, index: usize, text: String) {
        // Bounded by the element model (MAX_TEXT_ELEMENT_LEN); clamp defensively here too.
        let text: String = text
            .chars()
            .take(selahcue_present::MAX_TEXT_ELEMENT_LEN)
            .collect();
        self.commit(|w| {
            w.with_selected(|s| {
                if let Some(Element::Text { text: t, .. }) = s.elements.get_mut(index) {
                    *t = text;
                    true
                } else {
                    false
                }
            })
            .unwrap_or(false)
        });
    }

    /// Apply a partial JSON `patch` to the selected slide's element at `index` (the Inspector's
    /// edit path): the element is serialised, the patch keys overlaid, and the result deserialised
    /// back — so any serde field (geometry, colour, align, variant, weight, fit, …) can be set in
    /// one call, type-checked by serde. A malformed patch that won't deserialise is a **no-op**
    /// (never a panic). Records an undo entry only on a real change; clamps text + geometry.
    pub fn update_element(&mut self, index: usize, patch: Value) {
        self.commit(|w| {
            let Some(sid) = w.effective_selected() else {
                return false;
            };
            let Some(slide) = w.deck.get_mut(sid) else {
                return false;
            };
            let Some(el) = slide.elements.get_mut(index) else {
                return false;
            };
            let mut base = match serde_json::to_value(&*el) {
                Ok(v) => v,
                Err(_) => return false,
            };
            if let (Value::Object(bm), Value::Object(pm)) = (&mut base, &patch) {
                for (k, val) in pm {
                    bm.insert(k.clone(), val.clone());
                }
            } else {
                return false;
            }
            let mut next: Element = match serde_json::from_value(base) {
                Ok(e) => e,
                Err(_) => return false,
            };
            clamp_element(&mut next);
            if &next == el {
                return false;
            }
            *el = next;
            true
        });
    }

    /// Point the selected slide's image element at `index` at the library asset `media_id` (the
    /// Inspector's **Replace…**). No-op if `index` is not an image or the asset path is invalid.
    pub fn replace_element_image(&mut self, index: usize, media_id: u64) {
        self.commit(|w| {
            let source = w
                .media
                .get(MediaId(media_id))
                .map(|a| a.path.clone())
                .and_then(|p| MediaRef::new(&p));
            let Some(source) = source else {
                return false;
            };
            let Some(sid) = w.effective_selected() else {
                return false;
            };
            let Some(slide) = w.deck.get_mut(sid) else {
                return false;
            };
            match slide.elements.get_mut(index) {
                Some(Element::Image { source: s, .. }) => {
                    *s = source;
                    true
                }
                _ => false,
            }
        });
    }

    // --- per-slide props --------------------------------------------------------------------

    pub fn set_notes(&mut self, notes: String) {
        let notes: String = notes
            .chars()
            .take(selahcue_present::MAX_NOTES_LEN)
            .collect();
        self.commit(|w| w.with_selected(|s| s.notes = notes).is_some());
    }

    pub fn set_transition(&mut self, transition: &str) {
        let t = if transition == "fade" {
            Transition::Fade
        } else {
            Transition::Cut
        };
        self.commit(|w| w.with_selected(|s| s.transition = t).is_some());
    }

    pub fn set_auto_advance(&mut self, secs: Option<u32>) {
        self.commit(|w| {
            w.with_selected(|s| s.auto_advance_secs = secs.filter(|&v| v > 0))
                .is_some()
        });
    }

    // --- undo / redo / present --------------------------------------------------------------

    pub fn undo(&mut self) {
        if let Some(prev) = self.undo.pop() {
            self.redo.push(std::mem::replace(&mut self.deck, prev));
            if self.redo.len() > MAX_UNDO {
                self.redo.remove(0);
            }
            self.fix_cursors();
        }
    }

    pub fn redo(&mut self) {
        if let Some(next) = self.redo.pop() {
            self.undo.push(std::mem::replace(&mut self.deck, next));
            if self.undo.len() > MAX_UNDO {
                self.undo.remove(0);
            }
            self.fix_cursors();
        }
    }

    /// Mark the selected slide "live" (Present). Preview→Live: this is the ONLY action that sets
    /// `live` — editing/selecting never does (FR-012).
    pub fn go_live(&mut self) {
        self.live = self.effective_selected();
    }

    /// Advance the LIVE slide pointer by `delta` (−1 previous / +1 next), clamped to the deck ends,
    /// then select AND mark it live. Steps from the current live slide (or the selected slide when
    /// nothing is live). Returns whether a slide is now live (`false` only on an empty deck).
    /// Navigation of what is on air — the grid transport (◀ ▶ / arrow keys while presenting).
    pub fn go_live_delta(&mut self, delta: i32) -> bool {
        let Some(base) = self.live.or_else(|| self.effective_selected()) else {
            return false;
        };
        let Some(idx) = self.deck.index_of(base) else {
            return false;
        };
        let last = self.deck.len().saturating_sub(1) as i64;
        let next = (idx as i64 + delta as i64).clamp(0, last) as usize;
        let Some(slide) = self.deck.get_index(next) else {
            return false;
        };
        let sid = slide.id;
        self.selected = Some(sid);
        self.selected_element = None;
        self.live = Some(sid);
        true
    }

    /// The `(slide_json, theme_json)` for the currently-selected slide — the SAME slide + theme
    /// the canvas preview composes ([`render_slide`](Self::render_slide)) — so the physical
    /// audience output is byte-identical to the editor. `None` when nothing is selected (an empty
    /// deck) or serialization fails. The shell's `deck_go_live` sends this over the LAN control
    /// link so "Present" reaches the native output window (the `AuthoredSlide` is composed on the
    /// host with the same compositor as scripture/plan content).
    pub fn present_payload(&self) -> Option<(String, String)> {
        let sid = self.effective_selected()?;
        let slide = self.deck.get(sid)?;
        let slide_json = serde_json::to_string(slide).ok()?;
        let theme_json = serde_json::to_string(&self.theme).ok()?;
        Some((slide_json, theme_json))
    }

    // --- media ------------------------------------------------------------------------------

    /// Register an imported media file (its metadata). Real disk import of the file bytes uses the
    /// native picker on the shell side; this records the asset in the library.
    pub fn import_media(
        &mut self,
        path: String,
        kind: &str,
        size_bytes: u64,
        width: Option<u32>,
        height: Option<u32>,
        duration_ms: Option<u32>,
    ) {
        let kind = MediaKind::from_tag(kind).unwrap_or(MediaKind::Image);
        self.media
            .import(path, kind, size_bytes, width, height, duration_ms, 0);
    }

    pub fn remove_media(&mut self, id: u64) {
        self.media.remove(MediaId(id));
    }

    // --- preview compose --------------------------------------------------------------------

    /// Compose one slide (the selected one, or `id` when given) to a bounded RGBA framebuffer for
    /// the canvas preview — the SAME native compositor as the audience output (never blank).
    pub fn render_slide(&self, id: Option<u64>, max_w: u32, max_h: u32) -> Option<FrameBuffer> {
        let sid = id.map(SlideId).or_else(|| self.effective_selected())?;
        let slide = self.deck.get(sid)?;
        let w = max_w.clamp(1, 960);
        let h = max_h.clamp(1, 540);
        Some(render_authored_slide(slide, &self.theme, w, h))
    }

    // --- view -------------------------------------------------------------------------------

    /// The `DeckView` JSON the webview renders from.
    pub fn view(&self) -> Value {
        let usage = media_usage(&self.media, &[&self.deck]);
        let unused: HashSet<u64> = usage.unused.iter().map(|m| m.0).collect();
        let missing_ids = self.media.missing(missing_probe);
        let missing: HashSet<u64> = missing_ids.iter().map(|m| m.0).collect();
        let selected = self.effective_selected();

        let slides: Vec<Value> = self
            .deck
            .slides()
            .iter()
            .enumerate()
            .map(|(i, s)| {
                json!({
                    "id": s.id.0,
                    "n": i + 1,
                    "lines": thumb_lines(s),
                    "kind": slide_kind(s),
                })
            })
            .collect();

        let slide = selected.and_then(|id| self.deck.get(id)).map(|s| {
            json!({
                "id": s.id.0,
                "elements": s
                    .elements
                    .iter()
                    .enumerate()
                    .map(|(i, e)| element_json(i, e))
                    .collect::<Vec<_>>(),
                "selected_element": self.selected_element,
                "notes": s.notes,
                "transition": transition_tag(s.transition),
                "auto_advance_secs": s.auto_advance_secs,
                "has_background": s.background.is_some(),
            })
        });

        // How many slides reference each asset path (by image element OR image background) — the
        // "Used on k slides" warning on the remove-media confirm (C-002). Bounded by the deck size.
        let mut uses: HashMap<&str, usize> = HashMap::new();
        for s in self.deck.slides() {
            let mut seen: HashSet<&str> = HashSet::new();
            for el in &s.elements {
                if let Element::Image { source, .. } = el {
                    seen.insert(source.as_str());
                }
            }
            if let Some(Background::Image(bg)) = &s.background {
                seen.insert(bg.source.as_str());
            }
            for path in seen {
                *uses.entry(path).or_insert(0) += 1;
            }
        }

        let assets: Vec<Value> = self
            .media
            .assets()
            .iter()
            .map(|a| {
                json!({
                    "id": a.id.0,
                    "name": file_name(&a.path),
                    "path": a.path,
                    "kind": a.kind.as_tag(),
                    "size_label": size_label(a.size_bytes),
                    "width": a.width,
                    "height": a.height,
                    "duration_label": a.duration_ms.map(dur_label),
                    "missing": missing.contains(&a.id.0),
                    "unused": unused.contains(&a.id.0),
                    "uses": uses.get(a.path.as_str()).copied().unwrap_or(0),
                })
            })
            .collect();

        json!({
            "name": self.deck.name,
            "count": self.deck.len(),
            "slides": slides,
            "selected": selected.map(|s| s.0),
            "live": self.live.map(|s| s.0),
            "slide": slide,
            "media": {
                "assets": assets,
                "total_label": size_label(self.media.total_bytes()),
                "missing_count": missing_ids.len(),
                "unused_count": usage.unused.len(),
            },
            "can_undo": !self.undo.is_empty(),
            "can_redo": !self.redo.is_empty(),
        })
    }
}

// --- element constructors -------------------------------------------------------------------

fn text_element(text: &str, x: u16, y: u16, w: u16, h: u16, size_permille: u16) -> Element {
    Element::Text {
        x_permille: x,
        y_permille: y,
        w_permille: w,
        h_permille: h,
        text: text.to_string(),
        color: Rgba::rgb(240, 240, 245),
        size_permille,
        line_height_permille: 1100,
        align_h: TextAlign::Left,
        align_v: VAlign::Top,
        fit: Fit::ShrinkToFit,
        opacity: 255,
        z: 0,
        font: None,
        weight: 400,
        letter_spacing_permille: 0,
        visible: true,
    }
}

fn shape_element(fill: Rgba, x: u16, y: u16, w: u16, h: u16) -> Element {
    Element::Shape {
        x_permille: x,
        y_permille: y,
        w_permille: w,
        h_permille: h,
        fill,
        border: Rgba::new(0, 0, 0, 0),
        border_permille: 0,
        opacity: 255,
        z: 0,
        variant: ShapeKind::Rect,
        corner_permille: 16,
        visible: true,
    }
}

/// A full-frame background shape sitting BEHIND the slide content (`z < 0`) — the "Background"
/// tool's placeholder until gradient/image background editing lands.
fn background_shape() -> Element {
    Element::Shape {
        x_permille: 0,
        y_permille: 0,
        w_permille: 1000,
        h_permille: 1000,
        fill: Rgba::rgb(26, 24, 51),
        border: Rgba::new(0, 0, 0, 0),
        border_permille: 0,
        opacity: 255,
        z: -1,
        variant: ShapeKind::Rect,
        corner_permille: 0,
        visible: true,
    }
}

/// An image element from a resolved [`MediaRef`] at a per-mille rect (default `Stretch` fit).
fn image_element(source: MediaRef, x: u16, y: u16, w: u16, h: u16) -> Element {
    Element::Image {
        x_permille: x,
        y_permille: y,
        w_permille: w,
        h_permille: h,
        source,
        opacity: 255,
        z: 0,
        visible: true,
        fit: ImageFit::default(),
    }
}

fn set_element_rect(el: &mut Element, x: u16, y: u16, w: u16, h: u16) {
    match el {
        Element::Shape {
            x_permille,
            y_permille,
            w_permille,
            h_permille,
            ..
        }
        | Element::Image {
            x_permille,
            y_permille,
            w_permille,
            h_permille,
            ..
        }
        | Element::Text {
            x_permille,
            y_permille,
            w_permille,
            h_permille,
            ..
        } => {
            *x_permille = x;
            *y_permille = y;
            *w_permille = w;
            *h_permille = h;
        }
    }
}

/// Defensive bounds on a patched element (the Inspector patch is host-validated by serde, but a
/// crafted value could still be out of range): clamp geometry into 0..=1000 (w/h ≥ 1) and cap a
/// text box's length at [`MAX_TEXT_ELEMENT_LEN`] (no-leak).
fn clamp_element(el: &mut Element) {
    let (x, y, w, h, _) = element_geometry(el);
    set_element_rect(
        el,
        x.min(1000),
        y.min(1000),
        w.clamp(1, 1000),
        h.clamp(1, 1000),
    );
    if let Element::Text { text, .. } = el {
        if text.chars().count() > selahcue_present::MAX_TEXT_ELEMENT_LEN {
            *text = text
                .chars()
                .take(selahcue_present::MAX_TEXT_ELEMENT_LEN)
                .collect();
        }
    }
}

fn set_element_z(el: &mut Element, new_z: i16) {
    match el {
        Element::Shape { z, .. } | Element::Image { z, .. } | Element::Text { z, .. } => *z = new_z,
    }
}

fn set_element_visible(el: &mut Element, v: bool) {
    match el {
        Element::Shape { visible, .. }
        | Element::Image { visible, .. }
        | Element::Text { visible, .. } => *visible = v,
    }
}

// --- view helpers ---------------------------------------------------------------------------

/// The missing-file probe: real (imported) paths are checked on disk; the demo `demo://` scheme is
/// treated as present except the one designated-missing asset, so the stand-alone surface shows a
/// realistic missing state without real files.
fn missing_probe(path: &str) -> bool {
    match path.strip_prefix("demo://") {
        Some(rest) => rest != "baptism.jpg",
        None => Path::new(path).exists(),
    }
}

/// Per-mille geometry + opacity common to every kind.
fn element_geometry(el: &Element) -> (u16, u16, u16, u16, u8) {
    match el {
        Element::Shape {
            x_permille,
            y_permille,
            w_permille,
            h_permille,
            opacity,
            ..
        }
        | Element::Image {
            x_permille,
            y_permille,
            w_permille,
            h_permille,
            opacity,
            ..
        }
        | Element::Text {
            x_permille,
            y_permille,
            w_permille,
            h_permille,
            opacity,
            ..
        } => (*x_permille, *y_permille, *w_permille, *h_permille, *opacity),
    }
}

/// The DeckView JSON for one element: the **full serde props** (so the Inspector can bind every
/// field — `x_permille`, `color`/`fill` `{r,g,b,a}`, `align_h`, `variant`, … all snake_case) PLUS
/// the short `x/y/w/h/z/visible/opacity` aliases the on-canvas selection + keyboard already read,
/// and the computed `label` / `name` / `missing`. The Inspector patches back via
/// [`DeckWorkspace::update_element`] using the full serde keys.
fn element_json(index: usize, el: &Element) -> Value {
    let mut v = serde_json::to_value(el).unwrap_or_else(|_| json!({}));
    let (x, y, w, h, opacity) = element_geometry(el);
    let label = match el {
        Element::Text { text, .. } => {
            let first = text.lines().next().unwrap_or("").trim();
            if first.is_empty() {
                "Text".to_string()
            } else {
                first.chars().take(28).collect()
            }
        }
        Element::Image { source, .. } => file_name(source.as_str()),
        Element::Shape { .. } => "Shape".to_string(),
    };
    if let Value::Object(m) = &mut v {
        m.insert("index".into(), json!(index));
        m.insert("label".into(), json!(label));
        // short aliases (canvas hit-test / drag / keyboard read these)
        m.insert("x".into(), json!(x));
        m.insert("y".into(), json!(y));
        m.insert("w".into(), json!(w));
        m.insert("h".into(), json!(h));
        m.insert("z".into(), json!(el.z()));
        m.insert("visible".into(), json!(el.visible()));
        m.insert("opacity".into(), json!(opacity));
        if let Element::Image { source, fit, .. } = el {
            m.insert("name".into(), json!(file_name(source.as_str())));
            m.insert("missing".into(), json!(!missing_probe(source.as_str())));
            // `fit` is skipped from serde JSON when it is the default `Stretch`; expose it
            // ALWAYS (snake_case string) so the inspector's Fit control shows the right option.
            m.insert(
                "fit".into(),
                serde_json::to_value(fit).unwrap_or_else(|_| json!("stretch")),
            );
        }
    }
    v
}

/// A few text lines for a SLIDES-list thumbnail (front text of the slide, bounded).
fn thumb_lines(s: &AuthoredSlide) -> Vec<String> {
    s.elements
        .iter()
        .filter_map(|e| match e {
            Element::Text { text, visible, .. } if *visible => {
                let line = text.lines().next().unwrap_or("").trim();
                if line.is_empty() {
                    None
                } else {
                    Some(line.chars().take(40).collect::<String>())
                }
            }
            _ => None,
        })
        .take(3)
        .collect()
}

/// A coarse kind hint for the thumbnail (drives its icon): image/shape/text.
fn slide_kind(s: &AuthoredSlide) -> &'static str {
    if matches!(s.background, Some(Background::Image(_)))
        || s.elements
            .iter()
            .any(|e| matches!(e, Element::Image { .. }))
    {
        "image"
    } else if s.elements.iter().any(|e| matches!(e, Element::Text { .. })) {
        "text"
    } else {
        "shape"
    }
}

fn transition_tag(t: Transition) -> &'static str {
    match t {
        Transition::Cut => "cut",
        Transition::Fade => "fade",
    }
}

/// The file name from a path (strips the `demo://` scheme and any directory).
fn file_name(path: &str) -> String {
    let p = path.strip_prefix("demo://").unwrap_or(path);
    p.rsplit(['/', '\\']).next().unwrap_or(p).to_string()
}

/// Human byte size ("2.4 MB", "1.2 GB") — bounded, deterministic.
fn size_label(bytes: u64) -> String {
    const KB: u64 = 1024;
    const MB: u64 = KB * 1024;
    const GB: u64 = MB * 1024;
    if bytes >= GB {
        format!("{:.1} GB", bytes as f64 / GB as f64)
    } else if bytes >= MB {
        format!("{:.1} MB", bytes as f64 / MB as f64)
    } else if bytes >= KB {
        format!("{:.0} KB", bytes as f64 / KB as f64)
    } else {
        format!("{bytes} B")
    }
}

/// "m:ss" for a duration in ms.
fn dur_label(ms: u32) -> String {
    let secs = ms / 1000;
    format!("{}:{:02}", secs / 60, secs % 60)
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used)]
    use super::*;

    #[test]
    fn go_live_delta_steps_and_clamps_at_both_ends() {
        let mut ws = DeckWorkspace::new_empty_for_test();
        ws.add_slide();
        ws.add_slide();
        ws.add_slide();
        let ids: Vec<SlideId> = ws.deck.slides().iter().map(|s| s.id).collect();
        assert_eq!(ids.len(), 3, "three slides added");

        // Start live on the first slide.
        ws.select_slide(ids[0].0);
        ws.go_live();
        assert_eq!(ws.live, Some(ids[0]));

        // +1 → slide 2, +1 → slide 3, +1 → clamped at slide 3.
        assert!(ws.go_live_delta(1));
        assert_eq!(ws.live, Some(ids[1]));
        assert!(ws.go_live_delta(1));
        assert_eq!(ws.live, Some(ids[2]));
        assert!(ws.go_live_delta(1));
        assert_eq!(ws.live, Some(ids[2]), "clamped at the last slide");

        // Back to the first, clamped at 0.
        assert!(ws.go_live_delta(-1));
        assert_eq!(ws.live, Some(ids[1]));
        assert!(ws.go_live_delta(-1));
        assert_eq!(ws.live, Some(ids[0]));
        assert!(ws.go_live_delta(-1));
        assert_eq!(ws.live, Some(ids[0]), "clamped at the first slide");
    }

    #[test]
    fn go_live_delta_on_an_empty_deck_is_a_noop() {
        let mut ws = DeckWorkspace::new_empty_for_test();
        assert!(!ws.go_live_delta(1));
    }

    #[test]
    fn undo_history_is_bounded_and_recovers_at_least_twenty_steps() {
        // No-leak: many edits never grow the undo stack past MAX_UNDO, and ≥20 steps are
        // recoverable (FR-016). Each add_slide is a real edit → one undo entry.
        let mut ws = DeckWorkspace::demo();
        let base = ws.deck.len();
        for _ in 0..(MAX_UNDO + 40) {
            ws.add_slide();
        }
        assert!(
            ws.undo.len() <= MAX_UNDO,
            "undo stack stays bounded (no unbounded growth)"
        );
        // Recover 20 steps.
        let before = ws.deck.len();
        for _ in 0..20 {
            ws.undo();
        }
        assert_eq!(ws.deck.len(), before - 20, "≥20 undo steps are recoverable");
        assert!(
            ws.deck.len() >= base,
            "undo never goes below the starting deck"
        );
    }

    #[test]
    fn a_blocked_control_never_pushes_a_phantom_undo_or_wipes_redo() {
        // The review's #1 regression: a no-op edit (Image tool with no usable image, or an
        // out-of-range element op) must record NOTHING — no phantom undo entry, redo preserved.
        let mut ws = DeckWorkspace::new_empty_for_test();
        ws.add_slide(); // one real edit
        ws.undo(); // now redo has one entry
        assert!(!ws.redo.is_empty(), "precondition: redo is populated");
        let undo_before = ws.undo.len();
        ws.add_element("image"); // no library image → no-op
        ws.remove_element(999); // out-of-range → no-op
        ws.set_element_z(999, 5); // out-of-range → no-op
        assert_eq!(ws.undo.len(), undo_before, "a no-op records no undo entry");
        assert!(!ws.redo.is_empty(), "a no-op never wipes the redo stack");
    }

    #[test]
    fn editing_and_navigation_never_change_live_only_present_does() {
        // FR-012 Preview→Live isolation at the workspace level.
        let mut ws = DeckWorkspace::demo();
        let first = ws.deck.slides()[0].id.0;
        assert_eq!(ws.live, None, "nothing is live at first");
        ws.add_slide();
        ws.add_element("text");
        ws.select_slide(first);
        ws.set_notes("x".into());
        assert_eq!(ws.live, None, "editing/navigation never sets Live");
        ws.go_live();
        assert!(ws.live.is_some(), "only Present sets Live");
    }

    #[test]
    fn load_deck_switches_the_open_deck_and_resets_the_session() {
        // The Library open/switch path: load_deck replaces the deck, selects its first slide, and
        // resets Live + the undo history (a fresh document — switching is not "go live", FR-012).
        let mut ws = DeckWorkspace::demo();
        ws.add_slide(); // give the outgoing deck some undo history
        ws.go_live(); // and a live slide
        assert!(ws.live.is_some());
        let mut fresh = selahcue_present::SlideDeck::new("Fresh");
        fresh.set_id(selahcue_present::DeckId(99));
        fresh.add_slide();
        let first = fresh.slides()[0].id;
        ws.load_deck(fresh);
        assert_eq!(
            ws.open_deck().id(),
            selahcue_present::DeckId(99),
            "the open deck switched"
        );
        assert_eq!(ws.open_deck().name, "Fresh");
        assert_eq!(
            ws.selected,
            Some(first),
            "the first slide of the new deck is selected"
        );
        assert_eq!(ws.live, None, "switching decks clears Live (FR-012)");
        // A freshly-loaded deck has no undo history: undo is a no-op, the deck is unchanged.
        let before = ws.open_deck().clone();
        ws.undo();
        assert_eq!(
            ws.open_deck(),
            &before,
            "no undo history after a deck switch"
        );
    }

    #[test]
    fn update_element_applies_a_valid_patch_and_snapshots_only_on_change() {
        let mut ws = DeckWorkspace::demo();
        ws.add_element("text"); // a fresh text element on the selected slide, auto-selected
        let idx = ws.selected_element.unwrap();
        let undo_before = ws.undo.len();
        ws.update_element(idx, serde_json::json!({ "size_permille": 120 }));
        // the edit changed the element → one undo entry
        assert_eq!(
            ws.undo.len(),
            undo_before + 1,
            "a real edit records one undo entry"
        );
        let el = &ws.deck.get(ws.selected.unwrap()).unwrap().elements[idx];
        assert!(matches!(el, Element::Text { size_permille, .. } if *size_permille == 120));
        // applying the SAME value is a no-op → no new undo entry
        let after = ws.undo.len();
        ws.update_element(idx, serde_json::json!({ "size_permille": 120 }));
        assert_eq!(ws.undo.len(), after, "a no-op patch records nothing");
    }

    #[test]
    fn update_element_ignores_a_malformed_patch_without_panicking() {
        let mut ws = DeckWorkspace::demo();
        ws.add_element("text");
        let idx = ws.selected_element.unwrap();
        let undo_before = ws.undo.len();
        // a wrong-typed value cannot deserialise back into Element → no-op, no panic
        ws.update_element(idx, serde_json::json!({ "size_permille": "huge" }));
        assert_eq!(ws.undo.len(), undo_before, "a malformed patch is a no-op");
    }

    #[test]
    fn update_element_clamps_geometry_and_text_length() {
        let mut ws = DeckWorkspace::demo();
        ws.add_element("text");
        let idx = ws.selected_element.unwrap();
        let long = "x".repeat(selahcue_present::MAX_TEXT_ELEMENT_LEN + 50);
        ws.update_element(
            idx,
            serde_json::json!({ "x_permille": 5000, "w_permille": 0, "text": long }),
        );
        let el = &ws.deck.get(ws.selected.unwrap()).unwrap().elements[idx];
        match el {
            Element::Text {
                x_permille,
                w_permille,
                text,
                ..
            } => {
                assert!(*x_permille <= 1000, "x clamped into 0..=1000");
                assert!(*w_permille >= 1, "w floored to >= 1");
                assert_eq!(
                    text.chars().count(),
                    selahcue_present::MAX_TEXT_ELEMENT_LEN,
                    "text truncated to the cap"
                );
            }
            _ => panic!("expected a text element"),
        }
    }

    #[test]
    fn view_reports_per_asset_usage_count() {
        // demo() slide 5 uses "demo://harvest field.jpg" as a background → that asset's `uses` is
        // >= 1 (the "Used on k slides" source for the remove-media warning, C-002); an asset no
        // slide references reports 0.
        let ws = DeckWorkspace::demo();
        let v = ws.view();
        let assets = v["media"]["assets"].as_array().unwrap();
        let harvest = assets
            .iter()
            .find(|a| a["path"] == "demo://harvest field.jpg")
            .unwrap();
        assert!(
            harvest["uses"].as_u64().unwrap() >= 1,
            "a referenced asset reports its slide usage count"
        );
        let unused = assets.iter().find(|a| a["unused"] == true).unwrap();
        assert_eq!(
            unused["uses"].as_u64().unwrap(),
            0,
            "an unused asset reports 0 uses"
        );
    }

    #[test]
    fn update_element_sets_image_fit_and_element_json_exposes_it() {
        // The Inspector Fit control (C-008) patches `{fit}`; the raster honours it, and element_json
        // ALWAYS exposes `fit` (even the default) so the control renders the right option selected.
        let mut ws = DeckWorkspace::demo();
        ws.add_element("image"); // first library image → auto-selected
        let idx = ws
            .selected_element
            .expect("the image element is auto-selected");
        ws.update_element(idx, serde_json::json!({ "fit": "fill" }));
        let el = &ws.deck.get(ws.selected.unwrap()).unwrap().elements[idx];
        assert!(
            matches!(el, Element::Image { fit, .. } if *fit == ImageFit::Fill),
            "the fit patch applies to the image element"
        );
        assert_eq!(
            element_json(idx, el)["fit"],
            "fill",
            "element_json exposes the image fit as a snake_case string"
        );
    }

    #[test]
    fn reorder_elements_reassigns_z_to_the_front_to_back_order() {
        // The Layers-panel drag (C: deck_reorder_elements) reassigns DISTINCT z so the compose
        // paint order (z asc, then index) matches the requested FRONT→BACK order: order[0] (front)
        // gets the highest z. A malformed order is a no-op (never a panic), preserving undo.
        let mut ws = DeckWorkspace::demo();
        ws.add_element("text"); // slide now has ≥2 elements
        ws.add_element("shape");
        let sid = ws.selected.unwrap();
        let n = ws.deck.get(sid).unwrap().elements.len();
        assert!(n >= 2);
        // Put element 0 at the FRONT (highest z) and the last at the BACK (z 0).
        let order: Vec<usize> = (0..n).collect(); // front→back = [0, 1, .., n-1]
        let undo_before = ws.undo.len();
        ws.reorder_elements(order.clone());
        assert_eq!(
            ws.undo.len(),
            undo_before + 1,
            "a real reorder records one undo entry"
        );
        let els = &ws.deck.get(sid).unwrap().elements;
        assert_eq!(
            els[0].z(),
            (n - 1) as i16,
            "order[0] (front) gets the highest z"
        );
        assert_eq!(els[n - 1].z(), 0, "order[n-1] (back) gets z 0");
        // Distinct, strictly-decreasing z down the front→back order.
        for k in 1..n {
            assert!(
                els[order[k - 1]].z() > els[order[k]].z(),
                "front→back z strictly decreases"
            );
        }
        // Malformed orders are no-ops (no panic, no undo entry).
        let after = ws.undo.len();
        ws.reorder_elements(vec![0, 0]); // not a permutation
        ws.reorder_elements(vec![0]); // wrong length
        ws.reorder_elements((0..n + 5).collect()); // out of range / wrong length
        assert_eq!(ws.undo.len(), after, "malformed reorders are no-ops");
    }

    #[test]
    fn update_element_sets_and_clears_the_text_font() {
        // The Font-family picker (C-006) patches `{font}`; "System default" sends null → the
        // bundled default. Both round-trip through the serde merge-patch without panicking.
        let mut ws = DeckWorkspace::demo();
        ws.add_element("text");
        let idx = ws.selected_element.unwrap();
        let sid = ws.selected.unwrap();
        ws.update_element(idx, serde_json::json!({ "font": "Georgia" }));
        match &ws.deck.get(sid).unwrap().elements[idx] {
            Element::Text { font, .. } => {
                assert_eq!(font.as_ref().map(|f| f.as_str()), Some("Georgia"))
            }
            _ => panic!("expected a text element"),
        }
        ws.update_element(idx, serde_json::json!({ "font": null }));
        match &ws.deck.get(sid).unwrap().elements[idx] {
            Element::Text { font, .. } => {
                assert!(
                    font.is_none(),
                    "null clears the font to the bundled default"
                )
            }
            _ => panic!("expected a text element"),
        }
    }

    #[test]
    fn present_payload_is_the_selected_slide_and_theme_or_none_when_empty() {
        // A populated workspace yields a (slide, theme) pair that round-trips to the SAME types
        // the host composes — so "Present" reaches the output byte-identically to the canvas.
        let ws = DeckWorkspace::demo();
        let (slide_json, theme_json) = ws.present_payload().expect("demo has a selectable slide");
        serde_json::from_str::<selahcue_present::AuthoredSlide>(&slide_json)
            .expect("slide_json is a valid AuthoredSlide");
        serde_json::from_str::<Theme>(&theme_json).expect("theme_json is a valid Theme");

        // An empty workspace (no slides) has nothing to present.
        let empty = DeckWorkspace::new_empty_for_test();
        assert!(
            empty.present_payload().is_none(),
            "an empty deck has nothing to present"
        );
    }

    impl DeckWorkspace {
        /// A minimal empty workspace (no demo content) for the no-op/undo tests.
        fn new_empty_for_test() -> Self {
            DeckWorkspace {
                deck: SlideDeck::new("t"),
                media: MediaLibrary::new(),
                theme: Theme::dark(),
                selected: None,
                selected_element: None,
                live: None,
                undo: Vec::new(),
                redo: Vec::new(),
            }
        }
    }
}
