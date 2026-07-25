//! SelahCue desktop walking skeleton: a native output window that presents the
//! **live** output on the GPU, driven by a LAN control server.
//!
//! This is the render half of the walking skeleton (native window + Rust core) with
//! the control loop wired in: a shared [`LiveController`] is driven by **both** the
//! local keyboard **and** a remote controller connected over the pinned-TLS control
//! link, so a remote command (Next / Go Live / Blackout) changes what is on screen.
//! Slides are composited on the CPU (via `selahcue-present`) and blitted to a wgpu
//! surface. The Tauri operator shell is a subsequent batch.
//!
//! Local keys follow the canonical map (UX-CANONICAL §1, `selahcue_app::keymap`):
//! `Space`/`→` stage next · `←` previous · `Enter` Go Live · `B` blackout ·
//! `Esc Esc` clear all · `Backspace` clear staged — plus host-only `P` pairing QR
//! and `Y`/`N` approve/deny. Quit via the window close button.

#![forbid(unsafe_code)]

mod guard;
#[cfg(feature = "encryption")]
mod keys;

use selahcue_app::{
    handler_for, CanonicalAction, ControllerSnapshot, KeyPress, Keymap, LiveController,
};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_data::session_repo::SessionState;
use selahcue_data::{output_repo, plan_repo, session_repo, DataError, Database};
use selahcue_engine::raster::FrameBuffer;
use selahcue_lan::protocol::{Command, DisplayView, OutputStatusView, PairingInvite};
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{generate_pairing_code, generate_token, ControlServer, Role, SelfSigned};
use selahcue_present::qr_modules;
use selahcue_present::Theme;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;
use winit::application::ApplicationHandler;
use winit::event::{ElementState, KeyEvent, StartCause, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{Key, NamedKey};
use winit::window::{Window, WindowId};

const OUTPUT_W: u32 = 1920;
const OUTPUT_H: u32 = 1080;
/// Target frame interval for the paced redraw loop (~60 Hz). Pacing with a deadline —
/// not only the Fifo present block — keeps the loop from busy-spinning when a window
/// cannot present (minimized / occluded / surface lost).
const FRAME: Duration = Duration::from_millis(16);
/// Validity window of a pairing offer (code + QR). Short-lived by design (FR-086).
const PAIRING_TTL: Duration = Duration::from_secs(120);
/// Minimum spacing between autosave writes (bounds disk I/O under command bursts).
const AUTOSAVE_MIN_INTERVAL: Duration = Duration::from_secs(1);
/// While a countdown runs, refresh its persisted elapsed at least this often — so a
/// crash loses at most this much timer progress.
const TIMER_AUTOSAVE_INTERVAL: Duration = Duration::from_secs(5);

/// GUI-launch smoke watchdog (story 86ajpevzp): in `--smoke` mode, if the main
/// window has not presented a frame within this budget, exit non-zero so CI
/// catches a genuine launch failure instead of hanging. This runs in
/// `about_to_wait`, so it only covers a stall AFTER the event loop starts — a
/// hang INSIDE window/adapter creation (before the first `about_to_wait`) is
/// bounded by the CI job's `timeout-minutes` backstop instead.
const SMOKE_TIMEOUT: Duration = Duration::from_secs(30);

/// Whether the GUI-launch smoke mode was requested (`--smoke` argument or the
/// `SELAHCUE_SMOKE` env var set). Pure over its inputs so it is unit-testable.
fn smoke_mode_requested(mut args: impl Iterator<Item = String>, env_set: bool) -> bool {
    env_set || args.any(|a| a == "--smoke")
}

/// A monitor's raw identity facts, in a plain shape the key math can be tested on.
#[derive(Debug, Clone, PartialEq, Eq)]
struct MonitorFacts {
    name: Option<String>,
    width: u32,
    height: u32,
    x: i32,
    y: i32,
}

fn monitor_facts(m: &winit::monitor::MonitorHandle) -> MonitorFacts {
    let size = m.size();
    let pos = m.position();
    MonitorFacts {
        name: m.name(),
        width: size.width,
        height: size.height,
        x: pos.x,
        y: pos.y,
    }
}

/// Stable, collision-free monitor identities for assignment persistence:
/// `name|WxH`, with a `#n` ordinal appended for DUPLICATE name+size monitors
/// (the classic two-identical-projectors venue — macOS names same-model
/// monitors identically). Ordinals are ordered by desktop position (left-to-
/// right, top-to-bottom), not enumeration order, so OS re-enumeration across
/// boots does not swap them; physically swapping the cables of two identical
/// projectors is indistinguishable to software and needs re-assignment.
/// Returns one key per input, same order. Display NAMES get the same ordinal
/// suffix so the operator picker can tell duplicates apart.
fn display_keys(facts: &[MonitorFacts]) -> Vec<(String, String)> {
    let base = |f: &MonitorFacts, i: usize| {
        (
            f.name
                .clone()
                .unwrap_or_else(|| format!("Display {}", i + 1)),
            format!(
                "{}|{}x{}",
                f.name
                    .clone()
                    .unwrap_or_else(|| format!("Display {}", i + 1)),
                f.width,
                f.height
            ),
        )
    };
    // Position-ordered ordinal among same-key monitors.
    let mut order: Vec<usize> = (0..facts.len()).collect();
    order.sort_by_key(|&i| (facts[i].x, facts[i].y));
    let mut seen: Vec<(String, u32)> = Vec::new();
    let mut ordinal = vec![0u32; facts.len()];
    for &i in &order {
        let (_, key) = base(&facts[i], i);
        match seen.iter_mut().find(|(k, _)| *k == key) {
            Some((_, n)) => {
                *n += 1;
                ordinal[i] = *n;
            }
            None => seen.push((key, 0)),
        }
    }
    let dup: Vec<bool> = (0..facts.len())
        .map(|i| {
            let (_, key) = base(&facts[i], i);
            facts
                .iter()
                .enumerate()
                .filter(|(j, f)| base(f, *j).1 == key)
                .count()
                > 1
        })
        .collect();
    (0..facts.len())
        .map(|i| {
            let (name, key) = base(&facts[i], i);
            if dup[i] {
                (
                    format!("{name} #{}", ordinal[i] + 1),
                    format!("{key}#{}", ordinal[i] + 1),
                )
            } else {
                (name, key)
            }
        })
        .collect()
}

/// Report a non-Ok disk status loudly (the storage guard is never silent).
fn report_disk(status: guard::DiskStatus) {
    match status {
        guard::DiskStatus::Ok => {}
        guard::DiskStatus::Low { available } => eprintln!(
            "SelahCue: LOW DISK at the data dir ({} MB free) — checkpoints continue, \
             but free space soon.",
            available / (1024 * 1024)
        ),
        guard::DiskStatus::Critical { available } => eprintln!(
            "SelahCue: DISK CRITICALLY FULL ({} MB free) — checkpoint writes are \
             PAUSED to protect the store; the live session continues in memory.",
            available / (1024 * 1024)
        ),
    }
}

/// The demo service plan used on a first run (no persisted session yet).
fn demo_plan() -> ServicePlan {
    let mut plan = ServicePlan::new("Sunday Service");
    plan.add_item(ItemKind::Song, "Opening Song");
    plan.add_item(ItemKind::Scripture, "Romans 8:28");
    plan.add_item(ItemKind::Section, "Sermon");
    plan.add_item(ItemKind::Song, "Closing Song");
    plan
}

/// Platform data directory for the session store (created if missing). Every
/// failure path reports itself — storage degradation must never be silent.
fn data_dir() -> Option<std::path::PathBuf> {
    // Windows resolves via APPDATA below and never reads HOME.
    #[cfg(not(target_os = "windows"))]
    let home = std::env::var_os("HOME").map(std::path::PathBuf::from);
    #[cfg(target_os = "macos")]
    let dir = home.map(|h| h.join("Library/Application Support/SelahCue"));
    #[cfg(target_os = "linux")]
    let dir = std::env::var_os("XDG_DATA_HOME")
        .map(std::path::PathBuf::from)
        // Per the XDG spec, an empty or relative XDG_DATA_HOME is treated as unset.
        .filter(|p| p.is_absolute())
        .or(home.map(|h| h.join(".local/share")))
        .map(|d| d.join("selahcue"));
    #[cfg(target_os = "windows")]
    let dir = std::env::var_os("APPDATA")
        .map(std::path::PathBuf::from)
        .map(|d| d.join("SelahCue"));
    #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
    let dir: Option<std::path::PathBuf> = home.map(|h| h.join(".selahcue"));
    let Some(dir) = dir else {
        eprintln!("SelahCue: no data directory (HOME/APPDATA unset); running in-memory.");
        return None;
    };
    if let Err(e) = std::fs::create_dir_all(&dir) {
        eprintln!(
            "SelahCue: cannot create {} ({e}); running in-memory.",
            dir.display()
        );
        return None;
    }
    Some(dir)
}

/// The desktop's session store: the SQLite database + the persisted plan's row id.
/// A storage failure degrades to in-memory (never blocks a service) with a message.
struct SessionStore {
    db: Option<Database>,
    plan_id: Option<i64>,
}

impl SessionStore {
    fn open() -> Self {
        let db = data_dir()
            .map(|dir| (dir.join("selahcue.db3"), dir))
            .and_then(|(path, dir)| match Self::open_db(&path, &dir) {
                Ok(db) => Some(db),
                Err(e) => {
                    eprintln!("SelahCue: session store unavailable ({e}); running in-memory.");
                    None
                }
            });
        SessionStore { db, plan_id: None }
    }

    /// Open the store (FR-154/86ajp5vp6). The decision is keyed on what is
    /// ACTUALLY on disk — the file header discriminates a plaintext store from
    /// an encrypted one — so a key hiccup can never mint a plaintext store next
    /// to real data, silently kill persistence, or masquerade as corruption:
    ///
    /// | on disk        | key acquired | action                                    |
    /// |----------------|--------------|-------------------------------------------|
    /// | nothing        | yes          | create ENCRYPTED                          |
    /// | nothing        | no           | create plaintext + loud warning (documented best-effort) |
    /// | plaintext      | either       | open PLAIN + warning (encryption pending a migration tool — never keyed-open a plain file) |
    /// | encrypted      | yes          | open ENCRYPTED; a key mismatch HARD-STOPS persistence with an honest message (file untouched) |
    /// | encrypted      | no           | HARD-STOP persistence: "fix the key source" (no unencrypted attempt) |
    #[cfg(feature = "encryption")]
    fn open_db(path: &std::path::Path, data_dir: &std::path::Path) -> Result<Database, DataError> {
        let acquired = keys::acquire(data_dir);
        Self::open_store(path, acquired)
    }

    /// The testable state machine behind [`open_db`] (encryption builds).
    #[cfg(feature = "encryption")]
    fn open_store(
        path: &std::path::Path,
        acquired: Option<(selahcue_data::EncryptionKey, keys::KeySource)>,
    ) -> Result<Database, DataError> {
        const SQLITE_MAGIC: &[u8; 16] = b"SQLite format 3\0";
        let on_disk: Option<bool /* plaintext */> = match std::fs::read(path) {
            Ok(bytes) if bytes.len() >= 16 => Some(&bytes[..16] == SQLITE_MAGIC),
            Ok(_) => None, // zero/short file: treat as absent
            Err(_) => None,
        };
        match (on_disk, acquired) {
            (None, Some((key, source))) => {
                println!("  Store encryption: SQLCipher (key via {source:?}).");
                Database::open_encrypted(path, &key)
            }
            (None, None) => {
                eprintln!(
                    "SelahCue: NO ENCRYPTION KEY available — creating the store \
                     UNENCRYPTED (best-effort per FR-154; set SELAHCUE_PASSPHRASE \
                     or fix the OS keychain, then migrate)."
                );
                Database::open(path)
            }
            (Some(true), key) => {
                if key.is_some() {
                    eprintln!(
                        "SelahCue: the existing store is UNENCRYPTED; opening it as-is \
                         (in-place encryption migration is a pending tool — the key was \
                         acquired and will be used once migrated)."
                    );
                }
                Database::open(path)
            }
            (Some(false), Some((key, source))) => match Database::open_encrypted(path, &key) {
                Ok(db) => {
                    println!("  Store encryption: SQLCipher (key via {source:?}).");
                    Ok(db)
                }
                Err(e) => {
                    eprintln!(
                        "SelahCue: the store is ENCRYPTED but the acquired key (via \
                         {source:?}) does not open it — a changed passphrase, a missing \
                         key.salt from a partial backup restore, or a switched key \
                         source. The file is UNTOUCHED; persistence is off until the \
                         right key is back. ({e})"
                    );
                    Err(e)
                }
            },
            (Some(false), None) => {
                eprintln!(
                    "SelahCue: the store is ENCRYPTED and no key is available — \
                     persistence is off until the keychain/passphrase is back. \
                     The file is untouched; do NOT delete it."
                );
                Err(DataError::Corrupt(
                    "encrypted store, key unavailable".into(),
                ))
            }
        }
    }

    #[cfg(not(feature = "encryption"))]
    fn open_db(path: &std::path::Path, _data_dir: &std::path::Path) -> Result<Database, DataError> {
        Database::open(path)
    }

    /// Load the persisted session: the plan + the live-state snapshot. `None` on a
    /// first run (or unusable store) — the caller seeds the demo plan.
    fn load_session(&mut self) -> Option<(ServicePlan, ControllerSnapshot)> {
        let db = self.db.as_ref()?;
        let state = match session_repo::load(db) {
            Ok(state) => state?,
            Err(e) => {
                // A corrupt snapshot is diagnosable evidence — say so before the
                // fresh start (the next autosave will overwrite the row).
                eprintln!("SelahCue: persisted session unreadable ({e}); starting fresh.");
                return None;
            }
        };
        let plan_id = state.plan_id?;
        let plan = match plan_repo::load(db, plan_id) {
            Ok(plan) => plan,
            Err(e) => {
                eprintln!("SelahCue: persisted plan unreadable ({e}); starting fresh.");
                return None;
            }
        };
        self.plan_id = Some(plan_id);
        Some((
            plan,
            ControllerSnapshot {
                live_idx: state.live_idx,
                staged_idx: state.staged_idx,
                plan_cursor: state.plan_cursor,
                blackout: state.blackout,
                timer_total_secs: state.timer_total_secs,
                timer_elapsed_secs: state.timer_elapsed_secs,
                timer_running: state.timer_running,
                live_scripture: state.live_scripture,
                live_free_text: state.live_free_text,
                staged_scripture: state.staged_scripture,
            },
        ))
    }

    /// Ensure the (demo) plan exists in the store; called before the first save.
    fn ensure_plan(&mut self, plan: &ServicePlan) {
        if self.plan_id.is_some() {
            return;
        }
        if let Some(db) = self.db.as_ref() {
            match plan_repo::insert(db, plan) {
                Ok(id) => self.plan_id = Some(id),
                Err(e) => eprintln!("SelahCue: could not persist the plan ({e})."),
            }
        }
    }

    /// Persisted output→display assignments (`(role, display_key)`), if any.
    fn load_output_assignments(&self) -> Vec<(String, String)> {
        self.db
            .as_ref()
            .and_then(|db| match output_repo::load_assignments(db) {
                Ok(rows) => Some(rows),
                Err(e) => {
                    eprintln!("SelahCue: could not read output assignments ({e}).");
                    None
                }
            })
            .unwrap_or_default()
    }

    /// Persist one output→display assignment (reported, never fatal).
    fn save_output_assignment(&self, role: &str, display_key: &str) {
        if let Some(db) = self.db.as_ref() {
            if let Err(e) = output_repo::save_assignment(db, role, display_key) {
                eprintln!("SelahCue: could not persist the {role} output assignment ({e}).");
            }
        }
    }

    /// Persist the (edited) plan: update in place, or insert on the first save.
    /// Returns whether the write succeeded (the caller re-arms the retry).
    fn save_plan(&mut self, plan: &ServicePlan) -> bool {
        let Some(db) = self.db.as_ref() else {
            return true;
        };
        let result = match self.plan_id {
            Some(id) => plan_repo::update(db, id, plan),
            None => plan_repo::insert(db, plan).map(|id| {
                self.plan_id = Some(id);
            }),
        };
        match result {
            Ok(()) => true,
            Err(e) => {
                eprintln!("SelahCue: could not persist the plan edit ({e}).");
                false
            }
        }
    }

    /// Persist the live-state snapshot. Returns whether the write succeeded (an
    /// error is reported, never fatal mid-service; the caller re-arms the retry).
    fn save_session(&mut self, snap: &ControllerSnapshot) -> bool {
        let Some(db) = self.db.as_ref() else {
            return true;
        };
        let state = SessionState {
            plan_id: self.plan_id,
            live_idx: snap.live_idx,
            staged_idx: snap.staged_idx,
            plan_cursor: snap.plan_cursor,
            blackout: snap.blackout,
            timer_total_secs: snap.timer_total_secs,
            timer_elapsed_secs: snap.timer_elapsed_secs,
            timer_running: snap.timer_running,
            live_scripture: snap.live_scripture.clone(),
            live_free_text: snap.live_free_text.clone(),
            staged_scripture: snap.staged_scripture.clone(),
        };
        match session_repo::save(db, &state) {
            Ok(()) => true,
            Err(e) => {
                eprintln!("SelahCue: autosave failed ({e}).");
                false
            }
        }
    }
}

struct Renderer {
    window: Arc<Window>,
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    pipeline: wgpu::RenderPipeline,
    bind_group_layout: wgpu::BindGroupLayout,
    sampler: wgpu::Sampler,
    frame_texture: Option<(wgpu::Texture, u32, u32)>,
}

impl Renderer {
    fn new(window: Arc<Window>) -> Self {
        let size = window.inner_size();
        let instance = wgpu::Instance::default();
        let surface = instance
            .create_surface(window.clone())
            .expect("create surface");
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            compatible_surface: Some(&surface),
            ..Default::default()
        }))
        .expect("request adapter");
        let (device, queue) =
            pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default(), None))
                .expect("request device");

        let caps = surface.get_capabilities(&adapter);
        let format = caps
            .formats
            .iter()
            .copied()
            .find(|f| f.is_srgb())
            .unwrap_or(caps.formats[0]);
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            width: size.width.max(1),
            height: size.height.max(1),
            present_mode: wgpu::PresentMode::Fifo,
            alpha_mode: caps.alpha_modes[0],
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &config);

        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("blit"),
            source: wgpu::ShaderSource::Wgsl(include_str!("blit.wgsl").into()),
        });
        let bind_group_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("blit"),
            entries: &[
                wgpu::BindGroupLayoutEntry {
                    binding: 0,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Texture {
                        sample_type: wgpu::TextureSampleType::Float { filterable: true },
                        view_dimension: wgpu::TextureViewDimension::D2,
                        multisampled: false,
                    },
                    count: None,
                },
                wgpu::BindGroupLayoutEntry {
                    binding: 1,
                    visibility: wgpu::ShaderStages::FRAGMENT,
                    ty: wgpu::BindingType::Sampler(wgpu::SamplerBindingType::Filtering),
                    count: None,
                },
            ],
        });
        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("blit"),
            bind_group_layouts: &[&bind_group_layout],
            push_constant_ranges: &[],
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("blit"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: "vs",
                buffers: &[],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: "fs",
                targets: &[Some(config.format.into())],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState::default(),
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview: None,
            cache: None,
        });
        let sampler = device.create_sampler(&wgpu::SamplerDescriptor::default());

        Renderer {
            window,
            surface,
            device,
            queue,
            config,
            pipeline,
            bind_group_layout,
            sampler,
            frame_texture: None,
        }
    }

    fn resize(&mut self, width: u32, height: u32) {
        self.config.width = width.max(1);
        self.config.height = height.max(1);
        self.surface.configure(&self.device, &self.config);
    }

    /// Composite `frame` onto this window's surface. Returns `true` when a frame
    /// was actually presented (false when the swapchain was lost/outdated and the
    /// paint is deferred to the next tick) — the smoke mode uses this to know the
    /// window really produced a visible frame before exiting.
    fn render(&mut self, frame: &FrameBuffer) -> bool {
        let (fw, fh) = (frame.width(), frame.height());
        if self.frame_texture.as_ref().map(|(_, w, h)| (*w, *h)) != Some((fw, fh)) {
            let texture = self.device.create_texture(&wgpu::TextureDescriptor {
                label: Some("frame"),
                size: wgpu::Extent3d {
                    width: fw,
                    height: fh,
                    depth_or_array_layers: 1,
                },
                mip_level_count: 1,
                sample_count: 1,
                dimension: wgpu::TextureDimension::D2,
                format: wgpu::TextureFormat::Rgba8UnormSrgb,
                usage: wgpu::TextureUsages::TEXTURE_BINDING | wgpu::TextureUsages::COPY_DST,
                view_formats: &[],
            });
            self.frame_texture = Some((texture, fw, fh));
        }
        let Some((texture, _, _)) = self.frame_texture.as_ref() else {
            return false;
        };
        self.queue.write_texture(
            wgpu::ImageCopyTexture {
                texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            frame.bytes(),
            wgpu::ImageDataLayout {
                offset: 0,
                bytes_per_row: Some(fw * 4),
                rows_per_image: Some(fh),
            },
            wgpu::Extent3d {
                width: fw,
                height: fh,
                depth_or_array_layers: 1,
            },
        );
        let tex_view = texture.create_view(&wgpu::TextureViewDescriptor::default());
        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("blit"),
            layout: &self.bind_group_layout,
            entries: &[
                wgpu::BindGroupEntry {
                    binding: 0,
                    resource: wgpu::BindingResource::TextureView(&tex_view),
                },
                wgpu::BindGroupEntry {
                    binding: 1,
                    resource: wgpu::BindingResource::Sampler(&self.sampler),
                },
            ],
        });

        let surface_frame = match self.surface.get_current_texture() {
            Ok(frame) => frame,
            Err(err) => {
                // A stale/lost swapchain (sleep, display re-negotiation) needs
                // reconfiguring. The paced frame loop (`new_events`) re-requests a paint
                // next frame, so we do NOT request one here — doing so would busy-spin
                // while the surface can't present.
                if matches!(err, wgpu::SurfaceError::Outdated | wgpu::SurfaceError::Lost) {
                    self.surface.configure(&self.device, &self.config);
                }
                return false;
            }
        };
        let target = surface_frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("blit"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &target,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &bind_group, &[]);
            pass.draw(0..3, 0..1);
        }
        self.queue.submit(Some(encoder.finish()));
        surface_frame.present();
        true
    }
}

/// A pairing request awaiting the operator's Y/N (one at a time; extras auto-deny).
struct PendingApproval {
    name: String,
    respond: tokio::sync::oneshot::Sender<bool>,
}

/// State shared between the winit thread and the control-server thread.
struct RemoteShared {
    registry: Arc<AsyncMutex<SessionRegistry>>,
    /// `(bound port, certificate pin hex)` — filled once the server is listening.
    lan: OnceLock<(u16, String)>,
    approval: Mutex<Option<PendingApproval>>,
    /// The currently offered pairing code, so cancelling pairing can withdraw it
    /// from the registry (a cancelled code must actually die, not linger to TTL).
    active_code: Mutex<Option<String>>,
}

struct App {
    /// The main audience/program output window.
    main: Option<Renderer>,
    /// The stage/confidence monitor window — the same live state composed as a speaker
    /// view (current + next line + timer + clock), FR-037.
    stage: Option<Renderer>,
    /// Shared with the control-server thread: the remote controller and the local
    /// keyboard drive the *same* live state, shown on both windows.
    controller: Arc<Mutex<LiveController>>,
    /// Pairing/registry state shared with the control-server thread.
    remote: Arc<RemoteShared>,
    /// The next frame deadline (a *fixed* schedule, advanced only when a frame fires), so
    /// continuous input can't keep pushing it forward and starve the redraw/tick loop.
    next_frame: Option<Instant>,
    /// The canonical keybinding state machine (UX-CANONICAL §1).
    keymap: Keymap,
    /// Attached physical displays, refreshed when windows are (re)created.
    displays: Vec<DisplayView>,
    /// Persisted role→display assignments (cache of the output_config table).
    assignments: Vec<(String, String)>,
    /// Launch-stability journal (crash-loop breaker, FR-169).
    launch_guard: Option<guard::LaunchGuard>,
    /// When this launch started (drives the stability mark).
    launched_at: Instant,
    /// Whether stability has been marked for this launch.
    stable_marked: bool,
    /// Last periodic disk-headroom check.
    last_disk_check: Instant,
    /// Whether checkpoint writes are currently halted (disk below the floor).
    disk_critical: bool,
    /// Breaker-tripped clean run: checkpointing fully disabled so the
    /// preserved on-disk session is never touched (review 7ad-A).
    clean_mode: bool,
    /// Cached identify frames (main = 1, stage = 2) while the overlay is active.
    identify_frames: Option<(FrameBuffer, FrameBuffer)>,
    /// The session store (SQLite) for autosave + crash recovery.
    store: SessionStore,
    last_autosave: Instant,
    /// GUI-launch smoke mode (story 86ajpevzp): present the first frame, report
    /// the time-to-first-frame (from App init — an informational figure, NOT the
    /// ≤3s cold-start NFR, which `make nfr` measures), then exit 0.
    smoke: bool,
    /// Whether the smoke exit has already fired (present can tick more than once).
    smoke_done: bool,
}

/// Apply one command to the shared controller (a poisoned lock just drops the input
/// rather than panicking the UI thread).
fn drive(controller: &Mutex<LiveController>, command: &Command) {
    if let Ok(mut c) = controller.lock() {
        let _ = c.apply(command);
    }
}

impl App {
    fn new() -> Self {
        // Open (or create) the session store; a storage failure degrades to an
        // in-memory session (the show must go on) with a clear message.
        let mut store = SessionStore::open();

        // Crash-loop breaker (FR-169): three rapid unstable launches mean
        // RECOVERY ITSELF is the failure — start clean, keep the session rows.
        let launch_guard = data_dir().map(|d| guard::LaunchGuard::new(&d));
        let crash_loop = match launch_guard.as_ref().map(guard::LaunchGuard::record_launch) {
            Some(guard::LaunchVerdict::CrashLoop { rapid_launches }) => {
                eprintln!(
                    "SelahCue: CRASH LOOP DETECTED ({rapid_launches} rapid restarts) — \
                     starting CLEAN with checkpointing DISABLED for this run, so the \
                     previous session stays untouched on disk. Once this run is stable, \
                     simply relaunch to resume the preserved session."
                );
                true
            }
            _ => false,
        };

        // Storage guard: checkpoint headroom is checked up front (and again
        // periodically in the autosave loop) — degradation is never silent, and
        // a critical startup status halts writes IMMEDIATELY (review 7ad-B).
        let startup_disk = data_dir().as_deref().and_then(guard::disk_status);
        if let Some(status) = startup_disk {
            report_disk(status);
        }
        let disk_critical = matches!(startup_disk, Some(guard::DiskStatus::Critical { .. }));

        let (plan, restored) = if crash_loop {
            (demo_plan(), None)
        } else {
            match store.load_session() {
                Some((plan, snap)) => (plan, Some(snap)),
                None => (demo_plan(), None),
            }
        };
        // Make sure the plan rows exist before the first snapshot references them —
        // except in clean mode (the preserved session must stay untouched, and no
        // orphan demo rows may accumulate across breaker trips) or on a critical
        // disk (no writes at all below the floor).
        if !crash_loop && !disk_critical {
            store.ensure_plan(&plan);
        }
        let first_run = restored.is_none() && !crash_loop;

        let controller = Arc::new(Mutex::new(LiveController::new(
            plan,
            OUTPUT_W,
            OUTPUT_H,
            Theme::dark(),
        )));

        if let Ok(mut c) = controller.lock() {
            match &restored {
                Some(snap) => {
                    // Crash/restart recovery: rebuild the exact live state.
                    c.restore(snap);
                    println!("  Session restored (crash/restart recovery).");
                }
                None => {
                    // First run: show the first item so the window isn't blank.
                    let _ = c.apply(&Command::Next);
                    let _ = c.apply(&Command::GoLive);
                }
            }
        }

        // First run: write the initial session row NOW so the seeded plan is
        // referenced immediately (a run that dies early must not orphan plan rows).
        // Skipped in clean mode / on a critical disk — no writes in either state.
        if first_run && !disk_critical {
            if let Ok(c) = controller.lock() {
                store.save_session(&c.snapshot(Instant::now()));
            }
        }

        // Start the LAN control server so remote controllers can drive this window.
        let remote = Arc::new(RemoteShared {
            registry: Arc::new(AsyncMutex::new(SessionRegistry::new())),
            lan: OnceLock::new(),
            approval: Mutex::new(None),
            active_code: Mutex::new(None),
        });
        start_remote_control(controller.clone(), remote.clone());

        App {
            main: None,
            stage: None,
            controller,
            remote,
            next_frame: None,
            keymap: Keymap::new(),
            displays: Vec::new(),
            assignments: Vec::new(),
            launch_guard,
            launched_at: Instant::now(),
            stable_marked: false,
            last_disk_check: Instant::now(),
            disk_critical,
            clean_mode: crash_loop,
            identify_frames: None,
            store,
            last_autosave: Instant::now(),
            smoke: smoke_mode_requested(
                std::env::args(),
                std::env::var_os("SELAHCUE_SMOKE").is_some(),
            ),
            smoke_done: false,
        }
    }

    /// Report the outputs (role → window/display) + attached displays to the
    /// controller so every operator surface can render the OUTPUTS panel.
    /// Re-run on window Moved/Resized: fullscreen transitions land async, so
    /// the truth arrives with those events, not with the assignment call.
    fn publish_output_status(&self) {
        let assignments = &self.assignments;
        let assigned = |role: &str| assignments.iter().any(|(r, _)| r == role);
        let assigned_key = |role: &str| {
            assignments
                .iter()
                .find(|(r, _)| r == role)
                .map(|(_, k)| k.clone())
        };
        let display_of = |renderer: &Option<Renderer>| {
            renderer
                .as_ref()
                .and_then(|r| r.window.current_monitor())
                .and_then(|m| m.name())
        };
        let size_of = |renderer: &Option<Renderer>| {
            renderer
                .as_ref()
                .map(|r| {
                    let s = r.window.inner_size();
                    (s.width, s.height)
                })
                .unwrap_or((OUTPUT_W, OUTPUT_H))
        };
        let (mw, mh) = size_of(&self.main);
        let (sw, sh) = size_of(&self.stage);
        let outputs = vec![
            OutputStatusView {
                role: "main".into(),
                display: display_of(&self.main),
                width: mw,
                height: mh,
                assigned: assigned("main"),
                assigned_key: assigned_key("main"),
            },
            OutputStatusView {
                role: "stage".into(),
                display: display_of(&self.stage),
                width: sw,
                height: sh,
                assigned: assigned("stage"),
                assigned_key: assigned_key("stage"),
            },
        ];
        if let Ok(mut c) = self.controller.lock() {
            c.set_output_status(outputs, self.displays.clone());
        }
    }

    /// Apply any remotely requested display assignments. The display must exist
    /// RIGHT NOW to be accepted: a stale key is dropped without persisting and —
    /// critically — without touching the (possibly live, fullscreen) window.
    fn apply_pending_assignments(&mut self) {
        let pending = match self.controller.lock() {
            Ok(mut c) => c.take_pending_assignments(),
            Err(_) => return,
        };
        if pending.is_empty() {
            return;
        }
        for (role, key) in &pending {
            let renderer = match role.as_str() {
                "main" => self.main.as_ref(),
                _ => self.stage.as_ref(),
            };
            let Some(r) = renderer else { continue };
            let monitors: Vec<winit::monitor::MonitorHandle> =
                r.window.available_monitors().collect();
            let facts: Vec<MonitorFacts> = monitors.iter().map(monitor_facts).collect();
            let keyed = display_keys(&facts);
            let target = monitors
                .iter()
                .zip(keyed.iter())
                .find(|(_, (_, k))| k == key)
                .map(|(m, _)| m.clone());
            match target {
                Some(monitor) => {
                    // Persist only what verifiably exists (a bad key must never
                    // overwrite a working venue profile).
                    self.store.save_output_assignment(role, key);
                    self.assignments.retain(|(r2, _)| r2 != role);
                    self.assignments.push((role.clone(), key.clone()));
                    r.window
                        .set_fullscreen(Some(winit::window::Fullscreen::Borderless(Some(monitor))));
                }
                None => {
                    eprintln!(
                        "SelahCue: display '{key}' for the {role} output is not attached; \
                         assignment ignored (window and saved profile unchanged)."
                    );
                }
            }
        }
        self.publish_output_status();
    }

    /// Autosave: persist the session when state changed (throttled to ~1/s) and
    /// periodically while a countdown runs (so its elapsed stays fresh on disk).
    fn autosave(&mut self, now: Instant) {
        // Crash-loop breaker: surviving to STABLE_AFTER forgives this launch.
        if !self.stable_marked && now.duration_since(self.launched_at) >= guard::STABLE_AFTER {
            self.stable_marked = true;
            if let Some(g) = self.launch_guard.as_ref() {
                g.mark_stable();
            }
        }
        // Storage guard: re-check headroom once a minute; halting/resuming
        // checkpoint writes is always reported.
        if now.duration_since(self.last_disk_check) >= Duration::from_secs(60) {
            self.last_disk_check = now;
            match data_dir().as_deref().and_then(guard::disk_status) {
                Some(status) => {
                    let critical = matches!(status, guard::DiskStatus::Critical { .. });
                    if critical != self.disk_critical || !matches!(status, guard::DiskStatus::Ok) {
                        report_disk(status);
                    }
                    if self.disk_critical && !critical {
                        eprintln!("SelahCue: disk headroom recovered — checkpoints resumed.");
                    }
                    self.disk_critical = critical;
                }
                None if self.disk_critical => {
                    // Free space unknowable while halted: stay safe, keep saying so.
                    eprintln!(
                        "SelahCue: cannot determine free disk space — checkpoint \
                         writes remain paused."
                    );
                }
                None => {}
            }
        }
        if self.disk_critical || self.clean_mode {
            // Critical disk: never risk corrupting a full store. Clean mode:
            // the preserved session must stay untouched. State stays in memory.
            return;
        }
        let Ok(mut c) = self.controller.lock() else {
            return;
        };
        // Plan edits persist immediately (rare, operator-driven actions) — and the
        // session snapshot goes with them, bypassing the throttle: the on-disk pair
        // (plan, indices) must never be split across a crash window.
        if c.take_plan_dirty() {
            if !self.store.save_plan(c.plan()) {
                c.mark_plan_dirty(); // failed write: retry next frame
            }
            c.take_state_dirty(); // superseded by the immediate joint save below
            if self.store.save_session(&c.snapshot(now)) {
                self.last_autosave = now;
            } else {
                c.mark_state_dirty();
            }
            return;
        }
        let dirty = c.take_state_dirty();
        let periodic =
            c.timer_active() && now.duration_since(self.last_autosave) >= TIMER_AUTOSAVE_INTERVAL;
        if (dirty || periodic) && now.duration_since(self.last_autosave) >= AUTOSAVE_MIN_INTERVAL {
            if self.store.save_session(&c.snapshot(now)) {
                self.last_autosave = now;
            } else if dirty {
                // The write failed: the change is still unpersisted — retry next frame.
                c.mark_state_dirty();
            }
        } else if dirty {
            // Too soon after the last write: keep the flag so the next frame saves.
            c.mark_state_dirty();
        }
    }

    /// `P`: toggle pairing mode — offer a fresh single-use code (2-minute TTL) and
    /// show the invite QR on the stage output + as ASCII in the terminal. Toggling
    /// off **withdraws** the code from the registry (a cancelled code must die
    /// immediately, e.g. when the operator suspects the QR was photographed).
    fn toggle_pairing(&self) {
        let Ok(mut c) = self.controller.lock() else {
            return;
        };
        if c.pairing_qr_active() {
            c.clear_pairing_qr();
            self.withdraw_active_code();
            println!("  Pairing mode off — the code is no longer redeemable.");
            return;
        }
        let Some((port, pin_hex)) = self.remote.lan.get().cloned() else {
            eprintln!("  Pairing unavailable: the control server is not running.");
            return;
        };
        let code = generate_pairing_code();
        if code.is_empty() {
            eprintln!("  Pairing unavailable: could not generate a code.");
            return;
        }
        let now = Instant::now();
        {
            let mut reg = self.remote.registry.blocking_lock();
            // Housekeeping: reclaim any expired offers so the map stays bounded.
            reg.prune_expired(now);
            reg.offer_pairing(code.clone(), Role::Producer, now, PAIRING_TTL);
        }
        if let Ok(mut slot) = self.remote.active_code.lock() {
            *slot = Some(code.clone());
        }
        let host = lan_ip();
        if host.is_loopback() {
            eprintln!(
                "  WARNING: no LAN-facing interface found — the invite uses 127.0.0.1, \
                 so only clients on THIS machine can pair."
            );
        }
        let invite = PairingInvite {
            host: host.to_string(),
            port,
            pin_hex,
            code: code.clone(),
        };
        match invite.to_uri() {
            Some(uri) => {
                print_pairing_block(&uri, &code);
                c.show_pairing_qr(uri, now + PAIRING_TTL);
            }
            None => eprintln!("  Pairing unavailable: could not encode the invite."),
        }
    }

    /// Remove the currently offered code (if any) from the registry.
    fn withdraw_active_code(&self) {
        let code = self
            .remote
            .active_code
            .lock()
            .ok()
            .and_then(|mut g| g.take());
        if let Some(code) = code {
            self.remote.registry.blocking_lock().withdraw(&code);
        }
    }

    /// `Y`/`N`: resolve a pending pairing-approval prompt. A prompt whose server
    /// side already timed out (30s) is announced as expired — it must not be
    /// mistaken for a successful approval.
    fn resolve_approval(&self, allow: bool) {
        let pending = self.remote.approval.lock().ok().and_then(|mut g| g.take());
        let Some(pending) = pending else { return };
        if pending.respond.send(allow).is_err() {
            println!(
                "  (the pairing request from '{}' had already expired — nothing granted)",
                pending.name
            );
            return;
        }
        println!(
            "  Pairing request from '{}' {}.",
            pending.name,
            if allow { "ALLOWED" } else { "denied" }
        );
        if allow {
            // The code is being consumed; dismiss the QR and forget the code.
            if let Ok(mut c) = self.controller.lock() {
                c.clear_pairing_qr();
            }
            if let Ok(mut slot) = self.remote.active_code.lock() {
                *slot = None;
            }
        }
    }

    /// The renderer whose window matches `id`, if any.
    fn renderer_for(&mut self, id: WindowId) -> Option<&mut Renderer> {
        if self.main.as_ref().is_some_and(|r| r.window.id() == id) {
            self.main.as_mut()
        } else if self.stage.as_ref().is_some_and(|r| r.window.id() == id) {
            self.stage.as_mut()
        } else {
            None
        }
    }
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        // Physical displays (FR-040): a stable, collision-free key per monitor.
        let monitors: Vec<winit::monitor::MonitorHandle> =
            event_loop.available_monitors().collect();
        let facts: Vec<MonitorFacts> = monitors.iter().map(monitor_facts).collect();
        let keyed = display_keys(&facts);
        self.displays = monitors
            .iter()
            .zip(keyed.iter())
            .map(|(m, (name, key))| {
                let size = m.size();
                DisplayView {
                    key: key.clone(),
                    name: name.clone(),
                    width: size.width,
                    height: size.height,
                }
            })
            .collect();
        self.assignments = self.store.load_output_assignments();
        let assignments = self.assignments.clone();
        let monitor_for = |role: &str| {
            assignments
                .iter()
                .find(|(r, _)| r == role)
                .and_then(|(_, key)| {
                    monitors
                        .iter()
                        .zip(keyed.iter())
                        .find(|(_, (_, k))| k == key)
                })
                .map(|(m, _)| m.clone())
        };
        if self.main.is_none() {
            let mut attrs = Window::default_attributes().with_title("SelahCue Output");
            if let Some(monitor) = monitor_for("main") {
                // Borderless fullscreen on the assigned display (spike-S4 path);
                // unassigned keeps the windowed default.
                attrs = attrs
                    .with_fullscreen(Some(winit::window::Fullscreen::Borderless(Some(monitor))));
            }
            let window = Arc::new(
                event_loop
                    .create_window(attrs)
                    .expect("create output window"),
            );
            self.main = Some(Renderer::new(window));
        }
        if self.stage.is_none() {
            let mut attrs = Window::default_attributes().with_title("SelahCue Stage / Confidence");
            if let Some(monitor) = monitor_for("stage") {
                attrs = attrs
                    .with_fullscreen(Some(winit::window::Fullscreen::Borderless(Some(monitor))));
            }
            let window = Arc::new(
                event_loop
                    .create_window(attrs)
                    .expect("create stage window"),
            );
            self.stage = Some(Renderer::new(window));
        }
        self.publish_output_status();
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, id: WindowId, event: WindowEvent) {
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
            WindowEvent::Resized(size) => {
                if let Some(renderer) = self.renderer_for(id) {
                    renderer.resize(size.width, size.height);
                    renderer.window.request_redraw();
                }
                // Fullscreen moves land async: the truthful monitor/size arrive
                // here. Stale identify frames would render at the old size.
                self.identify_frames = None;
                self.publish_output_status();
            }
            WindowEvent::Moved(_) => {
                self.publish_output_status();
            }
            WindowEvent::RedrawRequested => {
                // Identify (FR-040): while active, each window blits its number
                // INSTEAD of its scene — presentation state is untouched, so the
                // outputs resume by themselves when the overlay expires.
                let identify_active = self
                    .controller
                    .lock()
                    .ok()
                    .and_then(|c| c.identify_until())
                    .is_some_and(|t| Instant::now() < t);
                if identify_active {
                    if self.identify_frames.is_none() {
                        let theme = selahcue_present::StageTheme::dark();
                        let compose = |n: u32, r: &Renderer| {
                            let size = r.window.inner_size();
                            selahcue_engine::raster::render(&selahcue_present::compose_identify(
                                n,
                                theme.identify_bg,
                                theme.identify_marker,
                                size.width.max(1),
                                size.height.max(1),
                            ))
                        };
                        let frames = match (self.main.as_ref(), self.stage.as_ref()) {
                            (Some(m), Some(st)) => Some((compose(1, m), compose(2, st))),
                            _ => None,
                        };
                        self.identify_frames = frames;
                    }
                    if let Some((main_frame, stage_frame)) = self.identify_frames.as_ref() {
                        if self.main.as_ref().is_some_and(|r| r.window.id() == id) {
                            if let Some(r) = self.main.as_mut() {
                                r.render(main_frame);
                            }
                        } else if let Some(r) = self.stage.as_mut() {
                            r.render(stage_frame);
                        }
                        return;
                    }
                } else {
                    self.identify_frames = None;
                }
                let Ok(c) = self.controller.lock() else {
                    return;
                };
                // Each window presents its own surface from the same shared live state.
                if self.main.as_ref().is_some_and(|r| r.window.id() == id) {
                    let presented = self
                        .main
                        .as_mut()
                        .map(|r| r.render(c.presenter().live_output()))
                        .unwrap_or(false);
                    // Smoke mode (86ajpevzp): the main window produced a real frame —
                    // report time-to-first-frame (from App init) and exit cleanly (0).
                    if self.smoke && presented && !self.smoke_done {
                        self.smoke_done = true;
                        let ms = self.launched_at.elapsed().as_millis();
                        println!(
                            "SMOKE OK: main output window presented its first frame in {ms} ms (from App init)"
                        );
                        event_loop.exit();
                    }
                } else if let Some(r) = self.stage.as_mut() {
                    r.render(c.stage_output());
                }
            }
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key,
                        state: ElementState::Pressed,
                        repeat,
                        ..
                    },
                ..
            } => {
                // OS auto-repeat is never a deliberate action: a held Esc must
                // not complete the double-tap, a held B must not strobe.
                if repeat {
                    return;
                }
                // Host-local pairing keys first (not canonical live actions).
                // They still disarm a pending double-Esc — the keymap contract
                // is that ANY intervening key does (Esc, Y, Esc must never clear).
                match &logical_key {
                    Key::Character(c) if c.eq_ignore_ascii_case("p") => {
                        self.keymap.disarm();
                        self.toggle_pairing();
                        return;
                    }
                    Key::Character(c) if c.eq_ignore_ascii_case("i") => {
                        self.keymap.disarm();
                        if let Ok(mut ctl) = self.controller.lock() {
                            ctl.trigger_identify();
                        }
                        return;
                    }
                    Key::Character(c) if c.eq_ignore_ascii_case("y") => {
                        self.keymap.disarm();
                        self.resolve_approval(true);
                        return;
                    }
                    Key::Character(c) if c.eq_ignore_ascii_case("n") => {
                        self.keymap.disarm();
                        self.resolve_approval(false);
                        return;
                    }
                    _ => {}
                }
                // Canonical map (UX-CANONICAL §1). NOTE: `Esc` no longer quits —
                // double-`Esc` is Clear-all; quit via the window close button.
                let key = match logical_key {
                    Key::Named(NamedKey::Escape) => Some(KeyPress::Escape),
                    Key::Named(NamedKey::Space) => Some(KeyPress::Space),
                    Key::Named(NamedKey::Enter) => Some(KeyPress::Enter),
                    Key::Named(NamedKey::Backspace) => Some(KeyPress::Backspace),
                    Key::Named(NamedKey::ArrowLeft) => Some(KeyPress::ArrowLeft),
                    Key::Named(NamedKey::ArrowRight) => Some(KeyPress::ArrowRight),
                    Key::Character(c) => c.chars().next().map(KeyPress::Char),
                    _ => None,
                };
                let action = key.and_then(|k| self.keymap.press(k, Instant::now()));
                match action {
                    Some(CanonicalAction::Next) => drive(&self.controller, &Command::Next),
                    Some(CanonicalAction::Previous) => drive(&self.controller, &Command::Previous),
                    Some(CanonicalAction::GoLive) => drive(&self.controller, &Command::GoLive),
                    Some(CanonicalAction::ClearAll) => drive(&self.controller, &Command::Clear),
                    Some(CanonicalAction::BlackoutToggle) => {
                        let on = self
                            .controller
                            .lock()
                            .map(|g| !g.is_blackout())
                            .unwrap_or(true);
                        drive(&self.controller, &Command::Blackout { on });
                    }
                    Some(CanonicalAction::ClearLayer) => {
                        // Single-layer live output today: clearing the current
                        // layer IS the full clear (per-layer arrives with 86ajpy59e).
                        drive(&self.controller, &Command::Clear)
                    }
                    None => {}
                }
            }
            _ => {}
        }
    }

    fn new_events(&mut self, _event_loop: &ActiveEventLoop, cause: StartCause) {
        // Fire a frame when the fixed deadline is reached (or at startup): advance the
        // shared state (the countdown + confidence monitor) and repaint BOTH windows — so
        // a change made by the remote controller, which is not a winit event, appears
        // within a frame. Checking a *fixed* deadline (not now+FRAME) means continuous
        // input (repeated `WaitCancelled`) can't push it forward and starve the loop.
        let now = Instant::now();
        let due = match cause {
            StartCause::Init | StartCause::ResumeTimeReached { .. } => true,
            _ => self.next_frame.is_none_or(|deadline| now >= deadline),
        };
        if due {
            self.next_frame = Some(now + FRAME);
            if let Ok(mut c) = self.controller.lock() {
                c.tick(now);
            }
            self.autosave(now);
            self.apply_pending_assignments();
            if let Some(r) = self.main.as_ref() {
                r.window.request_redraw();
            }
            if let Some(r) = self.stage.as_ref() {
                r.window.request_redraw();
            }
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        // Smoke watchdog (86ajpevzp): a launch that never presents must FAIL, not
        // hang the CI job. If the window hasn't produced a frame within the budget,
        // exit non-zero with a clear message.
        if self.smoke && !self.smoke_done && self.launched_at.elapsed() > SMOKE_TIMEOUT {
            eprintln!(
                "SMOKE FAIL: no frame presented within {}s of launch",
                SMOKE_TIMEOUT.as_secs()
            );
            std::process::exit(1);
        }
        // Wake at the *fixed* next-frame deadline. The repaint is requested in
        // `new_events` (not here), so the loop idles until the deadline instead of
        // spinning on a self-posted redraw — a window that can't present never pegs a CPU
        // core, and the fixed deadline still fires under a stream of input events.
        let deadline = self.next_frame.unwrap_or_else(|| Instant::now() + FRAME);
        event_loop.set_control_flow(ControlFlow::WaitUntil(deadline));
    }
}

/// Spawn the pinned-TLS control server on a background thread with its own Tokio
/// runtime, driving the shared `controller`. If it can't start, the window still runs
/// under local keyboard control.
fn start_remote_control(controller: Arc<Mutex<LiveController>>, remote: Arc<RemoteShared>) {
    std::thread::spawn(move || {
        let runtime = match tokio::runtime::Builder::new_multi_thread()
            .enable_all()
            .build()
        {
            Ok(rt) => rt,
            Err(e) => {
                eprintln!("SelahCue: remote control disabled (runtime: {e})");
                return;
            }
        };
        if let Err(e) = runtime.block_on(run_server(controller, remote)) {
            eprintln!("SelahCue: remote control stopped: {e}");
        }
    });
}

async fn run_server(
    controller: Arc<Mutex<LiveController>>,
    remote: Arc<RemoteShared>,
) -> Result<(), Box<dyn std::error::Error>> {
    let identity = SelfSigned::generate(vec!["localhost".into()])
        .map_err(|e| format!("tls identity: {e:?}"))?;
    let pin = identity.pin;

    // A host-local operator session (for the operator shell on this machine): a fresh
    // random token per run — never a fixed value, since we bind beyond loopback now.
    let device = "operator-shell";
    let token = generate_token();
    if token.is_empty() {
        return Err("could not generate an operator token".into());
    }
    {
        let now = Instant::now();
        let mut reg = remote.registry.lock().await;
        reg.offer_pairing("host-local", Role::Operator, now, Duration::from_secs(60));
        reg.redeem(
            "host-local",
            DeviceId(device.to_string()),
            SessionToken::new(token.clone()),
            now,
        )
        .map_err(|e| format!("pairing: {e:?}"))?;
    }

    // Host confirmation (FR-086): raise a Y/N prompt for the winit thread; one pending
    // request at a time (extras auto-deny); an unanswered prompt times out as denied.
    // A slot whose server side already timed out (its receiver is gone) is DEAD — it
    // is reclaimed here so one ignored prompt can never wedge future pairing.
    let approval_shared = remote.clone();
    let approval: selahcue_lan::PairingApproval = Arc::new(move |name: String| {
        let (tx, rx) = tokio::sync::oneshot::channel::<bool>();
        let stored = match approval_shared.approval.lock() {
            Ok(mut slot) => {
                if slot.as_ref().is_some_and(|p| p.respond.is_closed()) {
                    *slot = None; // stale prompt from a timed-out request
                }
                if slot.is_none() {
                    *slot = Some(PendingApproval {
                        name: name.clone(),
                        respond: tx,
                    });
                    true
                } else {
                    false
                }
            }
            Err(_) => false,
        };
        if stored {
            println!();
            println!(
                "  PAIRING REQUEST from '{name}' — approving grants PRODUCER control \
                 (go-live/blackout/timers). Press Y to allow, N to deny (30s)."
            );
        }
        Box::pin(async move {
            if stored {
                rx.await.unwrap_or(false)
            } else {
                false // busy with another request
            }
        })
    });

    let server = Arc::new(
        ControlServer::new(&identity, remote.registry.clone(), handler_for(controller))
            .map_err(|e| format!("server: {e:?}"))?
            .with_pairing_approval(approval),
    );
    // Bind the LAN so a phone can reach us: joining is gated by pairing (single-use
    // TTL code + host confirmation) behind pinned TLS, so an open port grants nothing.
    let listener = TcpListener::bind("0.0.0.0:0").await?;
    let port = listener.local_addr()?.port();
    let _ = remote.lan.set((port, pin.to_hex()));
    // Advertise on mDNS so the phone can FIND us without typing an address
    // (86ajp0b0t). The TXT carries the cert pin — public data (it is printed in
    // every QR invite); joining still requires the TTL pairing code + host
    // approval, so discovery discloses presence, never access.
    let _mdns = advertise_mdns(port, device, &pin.to_hex());
    // Local clients (operator shell / CLI) connect via loopback.
    let local: SocketAddr = ([127, 0, 0, 1], port).into();
    let endpoint = write_endpoint(local, &pin.to_hex(), device, &token);
    print_connect_banner(local, &pin.to_hex(), device, &token, endpoint.as_deref());
    server
        .run(listener)
        .await
        .map_err(|e| format!("server run: {e:?}"))?;
    Ok(())
}

/// Advertise the control endpoint as `_selahcue._tcp.local.` while the server
/// runs (the returned daemon unregisters on drop). Best-effort: an mDNS-hostile
/// network only loses discovery — the QR/manual paths are unaffected.
fn advertise_mdns(port: u16, device: &str, pin_hex: &str) -> Option<mdns_sd::ServiceDaemon> {
    let daemon = match mdns_sd::ServiceDaemon::new() {
        Ok(d) => d,
        Err(e) => {
            eprintln!("SelahCue: mDNS advertising unavailable ({e}).");
            return None;
        }
    };
    // A per-run unique instance name so two hosts never collide in the phone's
    // list; the friendly name (with the pin fingerprint) rides in TXT so the
    // operator recognises the right host at a glance.
    let instance = format!("{device}-{port}");
    let friendly = format!("SelahCue {}", pin_fingerprint(pin_hex));
    let props = [("pin", pin_hex), ("name", friendly.as_str())];
    let info = mdns_sd::ServiceInfo::new(
        "_selahcue._tcp.local.",
        &instance,
        &format!("{instance}.local."),
        // Empty IP + auto-detect: mdns-sd fills in every up interface address,
        // so a multi-NIC host advertises the right one (not a single guess).
        "",
        port,
        &props[..],
    )
    .ok()?
    .enable_addr_auto();
    match daemon.register(info) {
        Ok(()) => {
            println!("  Discovery: advertising _selahcue._tcp on mDNS.");
            Some(daemon)
        }
        Err(e) => {
            eprintln!("SelahCue: mDNS registration failed ({e}).");
            None
        }
    }
}

/// This machine's LAN-facing IP (for the QR invite): a UDP "connect" selects the
/// outbound interface without sending a packet. Falls back to loopback.
fn lan_ip() -> std::net::IpAddr {
    std::net::UdpSocket::bind("0.0.0.0:0")
        .and_then(|s| {
            s.connect("8.8.8.8:80")?;
            s.local_addr()
        })
        .map(|a| a.ip())
        .unwrap_or_else(|_| std::net::IpAddr::from([127, 0, 0, 1]))
}

/// A short, human-comparable fingerprint of the certificate pin — the first 12
/// hex chars grouped in 4s (e.g. `AB12-CD34-EF56`). Shown on BOTH the host and
/// the phone so the operator can confirm a discovered host is the real one
/// before disclosing the pairing code (defeats a rogue-mDNS phish; the phone
/// mirrors this exact format). Not a secret — it derives from the public pin.
pub fn pin_fingerprint(pin_hex: &str) -> String {
    let head: String = pin_hex.chars().take(12).collect::<String>().to_uppercase();
    head.as_bytes()
        .chunks(4)
        .map(|c| std::str::from_utf8(c).unwrap_or(""))
        .collect::<Vec<_>>()
        .join("-")
}

/// Print the pairing invite: the URI, the hand-typable code, and an ASCII QR.
fn print_pairing_block(uri: &str, code: &str) {
    println!();
    println!("  PAIRING MODE (2 minutes) — scan from the SelahCue mobile app:");
    println!("  {uri}");
    println!("  or enter code: {code}");
    if let Some(pin) = uri.split("pin=").nth(1).and_then(|s| s.split('&').next()) {
        println!("  host fingerprint: {}", pin_fingerprint(pin));
        println!("  (if pairing from 'Nearby hosts', confirm the phone shows THIS fingerprint)");
    }
    if let Some((side, modules)) = qr_modules(uri) {
        println!();
        let quiet = 2usize;
        for y in 0..side + 2 * quiet {
            let mut line = String::with_capacity((side + 2 * quiet) * 2 + 2);
            line.push_str("  ");
            for x in 0..side + 2 * quiet {
                let dark = x >= quiet
                    && y >= quiet
                    && x < side + quiet
                    && y < side + quiet
                    && modules[(y - quiet) * side + (x - quiet)];
                line.push_str(if dark { "██" } else { "  " });
            }
            println!("{line}");
        }
    }
    println!("  (the QR is also on the stage/confidence window; press P again to cancel)");
    println!();
}

/// Write a local endpoint descriptor so the operator shell on this machine can
/// auto-discover + connect (a loopback-only convenience; real pairing is QR + host
/// confirmation). Values are simple ASCII (addr/hex/ids), so a hand-built JSON string is
/// safe. Returns the path written, if any.
fn endpoint_path() -> std::path::PathBuf {
    std::env::temp_dir().join("selahcue-operator-endpoint.json")
}

fn write_endpoint(
    addr: SocketAddr,
    pin_hex: &str,
    device: &str,
    token: &str,
) -> Option<std::path::PathBuf> {
    let json = format!(
        "{{\"addr\":\"{addr}\",\"pin\":\"{pin_hex}\",\"device\":\"{device}\",\"token\":\"{token}\"}}"
    );
    let path = endpoint_path();
    if let Err(e) = std::fs::write(&path, json) {
        eprintln!("SelahCue: could not write operator endpoint file: {e}");
        return None;
    }
    // The descriptor carries a bearer token. On macOS `temp_dir()` is already a per-user
    // private dir, but on Linux it is world-readable `/tmp`, so restrict to owner-only.
    // (This is a loopback-only demo convenience; real pairing is QR + host confirmation
    // and persists no token.)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600));
    }
    Some(path)
}

fn print_connect_banner(
    addr: SocketAddr,
    pin_hex: &str,
    device: &str,
    token: &str,
    endpoint: Option<&std::path::Path>,
) {
    println!();
    println!("  SelahCue — remote control ready");
    println!("  ------------------------------------------------------------");
    println!("  The output window is driven by the LAN control server.");
    println!("  address : {addr}");
    println!("  pin     : {pin_hex}");
    println!(
        "  device  : {device}   role : Operator (host shell); token: in the endpoint file (0600)"
    );
    if let Some(path) = endpoint {
        println!(
            "  endpoint: {}  (the operator shell auto-discovers this)",
            path.display()
        );
    }
    println!();
    println!("  Drive the window with the operator shell (auto-connects on this machine):");
    println!("    cargo run   # from crates/selahcue-operator");
    println!("  or from another terminal with the remote CLI:");
    println!("    cargo run -p selahcue-lan --example remote --features server -- \\");
    println!("      {addr} {pin_hex} {device} {token} next");
    println!(
        "    (commands: next · previous · go-live · blackout-on · blackout-off · clear · state)"
    );
    println!();
    println!("  Local keys: Space/\u{2192}=next  \u{2190}=prev  Enter=Go Live  B=blackout  Esc Esc=clear all  Backspace=clear staged");
    println!(
        "  Pairing:    P=show a QR invite (stage window + terminal)  Y/N=allow/deny a request"
    );
    println!();
}

fn main() {
    let event_loop = EventLoop::new().expect("event loop");
    event_loop.set_control_flow(ControlFlow::Wait);
    let mut app = App::new();
    event_loop.run_app(&mut app).expect("run app");
    // A clean exit is by definition a stable launch.
    if let Some(g) = app.launch_guard.as_ref() {
        g.mark_stable();
    }
    // Final save on clean exit (the autosave loop already covered crash paths) —
    // including a plan edit acked in the last instants before the loop exited.
    // Honours the same halts as autosave: no writes on a critical disk, and a
    // clean-mode run never touches the preserved session. A `--smoke` launch is a
    // throwaway probe — it must not persist anything (no session mutation).
    if !app.disk_critical && !app.clean_mode && !app.smoke {
        if let Ok(mut c) = app.controller.lock() {
            if c.take_plan_dirty() {
                app.store.save_plan(c.plan());
            }
            app.store.save_session(&c.snapshot(Instant::now()));
        }
    }
    // Best-effort: don't leave a stale endpoint (with a now-dead token/port) behind on a
    // clean exit, so a later operator shell doesn't try to attach to a defunct window.
    let _ = std::fs::remove_file(endpoint_path());
}

#[cfg(test)]
mod tests {
    use super::{display_keys, smoke_mode_requested, MonitorFacts};

    #[test]
    fn smoke_mode_is_detected_from_arg_or_env() {
        // Neither the flag nor the env var: normal launch.
        assert!(!smoke_mode_requested(
            ["selahcue-output".to_string()].into_iter(),
            false
        ));
        // The `--smoke` argument enables it.
        assert!(smoke_mode_requested(
            ["selahcue-output".to_string(), "--smoke".to_string()].into_iter(),
            false
        ));
        // The env var enables it even without the argument.
        assert!(smoke_mode_requested(
            ["selahcue-output".to_string()].into_iter(),
            true
        ));
        // An unrelated flag does NOT enable it.
        assert!(!smoke_mode_requested(
            ["selahcue-output".to_string(), "--verbose".to_string()].into_iter(),
            false
        ));
    }

    fn m(name: Option<&str>, w: u32, h: u32, x: i32) -> MonitorFacts {
        MonitorFacts {
            name: name.map(String::from),
            width: w,
            height: h,
            x,
            y: 0,
        }
    }

    #[test]
    fn identical_monitors_get_distinct_position_ordered_keys() {
        // The two-identical-projectors venue: same name, same size. Keys must
        // differ, ordered by desktop position regardless of enumeration order.
        let keys = display_keys(&[
            m(Some("EPSON PJ"), 1920, 1080, 1920), // enumerated first, but RIGHT
            m(Some("EPSON PJ"), 1920, 1080, 0),    // LEFT
        ]);
        assert_eq!(keys[0].1, "EPSON PJ|1920x1080#2");
        assert_eq!(keys[1].1, "EPSON PJ|1920x1080#1");
        assert_eq!(keys[0].0, "EPSON PJ #2");
        // Re-enumeration in the other order yields the SAME key per position.
        let swapped = display_keys(&[
            m(Some("EPSON PJ"), 1920, 1080, 0),
            m(Some("EPSON PJ"), 1920, 1080, 1920),
        ]);
        assert_eq!(swapped[0].1, "EPSON PJ|1920x1080#1");
        assert_eq!(swapped[1].1, "EPSON PJ|1920x1080#2");
    }

    #[test]
    fn distinct_monitors_keep_plain_keys() {
        let keys = display_keys(&[
            m(Some("Color LCD"), 2560, 1600, 0),
            m(Some("EPSON PJ"), 1920, 1080, 2560),
            m(None, 1024, 768, 5000),
        ]);
        assert_eq!(keys[0].1, "Color LCD|2560x1600");
        assert_eq!(keys[1].1, "EPSON PJ|1920x1080");
        assert_eq!(keys[2].1, "Display 3|1024x768");
        assert_eq!(keys[2].0, "Display 3");
    }
}

#[cfg(all(test, feature = "encryption"))]
#[allow(clippy::unwrap_used)]
mod encryption_tests {
    use super::*;
    use selahcue_data::EncryptionKey;

    fn tmp(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "selahcue-openstore-{}-{}",
            name,
            std::process::id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        dir.join("selahcue.db3")
    }

    #[test]
    fn fresh_store_with_a_key_is_encrypted_and_reopens() {
        let path = tmp("fresh");
        let key = EncryptionKey::from_raw([7u8; 32]);
        let db = SessionStore::open_store(&path, Some((key, keys::KeySource::SecretStore)));
        assert!(db.is_ok());
        drop(db);
        // On disk it must NOT carry the plaintext SQLite magic.
        let head = std::fs::read(&path).unwrap();
        assert_ne!(&head[..16], b"SQLite format 3\0", "file is encrypted");
        // The right key reopens it; a wrong key hard-stops WITHOUT touching it.
        let again = SessionStore::open_store(
            &path,
            Some((
                EncryptionKey::from_raw([7u8; 32]),
                keys::KeySource::SecretStore,
            )),
        );
        assert!(again.is_ok());
        drop(again);
        let before = std::fs::read(&path).unwrap();
        let wrong = SessionStore::open_store(
            &path,
            Some((
                EncryptionKey::from_raw([9u8; 32]),
                keys::KeySource::Passphrase,
            )),
        );
        assert!(
            wrong.is_err(),
            "wrong key never opens (and never falls back)"
        );
        assert_eq!(std::fs::read(&path).unwrap(), before, "file untouched");
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }

    #[test]
    fn plaintext_store_is_opened_plain_never_keyed() {
        let path = tmp("plain");
        // Mint a plaintext store (the documented no-key first-run fallback).
        let db = SessionStore::open_store(&path, None);
        assert!(db.is_ok());
        drop(db);
        let head = std::fs::read(&path).unwrap();
        assert_eq!(&head[..16], b"SQLite format 3\0", "plaintext store");
        // A later run WITH a key must keep opening it plain (no keyed open of a
        // plain file, no wedge) — the review's first-run-hiccup scenario.
        let with_key = SessionStore::open_store(
            &path,
            Some((
                EncryptionKey::from_raw([7u8; 32]),
                keys::KeySource::SecretStore,
            )),
        );
        assert!(
            with_key.is_ok(),
            "plaintext store keeps working with a key present"
        );
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }

    #[test]
    fn encrypted_store_without_a_key_hard_stops() {
        let path = tmp("nokey");
        drop(SessionStore::open_store(
            &path,
            Some((
                EncryptionKey::from_raw([7u8; 32]),
                keys::KeySource::SecretStore,
            )),
        ));
        let before = std::fs::read(&path).unwrap();
        let none = SessionStore::open_store(&path, None);
        assert!(
            none.is_err(),
            "no unencrypted attempt on an encrypted store"
        );
        assert_eq!(std::fs::read(&path).unwrap(), before, "file untouched");
        std::fs::remove_dir_all(path.parent().unwrap()).ok();
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod fingerprint_tests {
    use super::pin_fingerprint;

    #[test]
    fn fingerprint_is_the_grouped_uppercase_pin_head() {
        // Mirrored byte-for-byte by the Dart pinFingerprint (see
        // mobile test/models/discovery_test.dart) — change together.
        assert_eq!(
            pin_fingerprint("ab12cd34ef56aa99bbccddee"),
            "AB12-CD34-EF56"
        );
        // Short pins group what they have without panicking.
        assert_eq!(pin_fingerprint("abcd"), "ABCD");
        assert_eq!(pin_fingerprint(""), "");
    }
}
