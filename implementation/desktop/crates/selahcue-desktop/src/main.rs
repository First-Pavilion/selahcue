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
//! Local keys: `Space` stage next · `Enter` Go Live · `B` blackout · `C` clear · `Esc` quit.

#![forbid(unsafe_code)]

use selahcue_app::{handler_for, LiveController};
use selahcue_core::plan::{ItemKind, ServicePlan};
use selahcue_engine::raster::FrameBuffer;
use selahcue_lan::protocol::Command;
use selahcue_lan::session::{DeviceId, SessionRegistry, SessionToken};
use selahcue_lan::{ControlServer, Role, SelfSigned};
use selahcue_present::Theme;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tokio::net::TcpListener;
use tokio::sync::Mutex as AsyncMutex;
use winit::application::ApplicationHandler;
use winit::event::{ElementState, KeyEvent, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{Key, NamedKey};
use winit::window::{Window, WindowId};

const OUTPUT_W: u32 = 1920;
const OUTPUT_H: u32 = 1080;

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

    fn render(&mut self, frame: &FrameBuffer) {
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
            return;
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
                // reconfiguring; either way, reschedule a paint so the recovered
                // surface repaints under ControlFlow::Wait rather than freezing on
                // black until the next input event.
                if matches!(
                    err,
                    wgpu::SurfaceError::Outdated | wgpu::SurfaceError::Lost
                ) {
                    self.surface.configure(&self.device, &self.config);
                }
                self.window.request_redraw();
                return;
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
    }
}

struct App {
    renderer: Option<Renderer>,
    /// Shared with the control-server thread: the remote controller and the local
    /// keyboard drive the *same* live output.
    controller: Arc<Mutex<LiveController>>,
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
        let mut plan = ServicePlan::new("Sunday Service");
        plan.add_item(ItemKind::Song, "Opening Song");
        plan.add_item(ItemKind::Scripture, "Romans 8:28");
        plan.add_item(ItemKind::Section, "Sermon");
        plan.add_item(ItemKind::Song, "Closing Song");

        let controller = Arc::new(Mutex::new(LiveController::new(
            plan,
            OUTPUT_W,
            OUTPUT_H,
            Theme::dark(),
        )));

        // Show the first item immediately so the window isn't blank at launch.
        if let Ok(mut c) = controller.lock() {
            let _ = c.apply(&Command::Next); // stage item 0 in Preview
            let _ = c.apply(&Command::GoLive); // commit it to Live
        }

        // Start the LAN control server so a remote controller can drive this window.
        start_remote_control(controller.clone());

        App {
            renderer: None,
            controller,
        }
    }
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.renderer.is_none() {
            let attrs = Window::default_attributes().with_title("SelahCue Output");
            let window = Arc::new(event_loop.create_window(attrs).expect("create window"));
            self.renderer = Some(Renderer::new(window));
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let App {
            renderer,
            controller,
        } = self;
        let Some(renderer) = renderer.as_mut() else {
            return;
        };
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
            WindowEvent::Resized(size) => {
                renderer.resize(size.width, size.height);
                renderer.window.request_redraw();
            }
            WindowEvent::RedrawRequested => {
                if let Ok(c) = controller.lock() {
                    renderer.render(c.presenter().live_output());
                }
            }
            WindowEvent::KeyboardInput {
                event:
                    KeyEvent {
                        logical_key,
                        state: ElementState::Pressed,
                        ..
                    },
                ..
            } => {
                match logical_key {
                    Key::Named(NamedKey::Escape) => event_loop.exit(),
                    Key::Named(NamedKey::Space) => drive(controller, &Command::Next),
                    Key::Named(NamedKey::Enter) => drive(controller, &Command::GoLive),
                    Key::Character(c) if c.eq_ignore_ascii_case("b") => {
                        let on = controller.lock().map(|g| !g.is_blackout()).unwrap_or(true);
                        drive(controller, &Command::Blackout { on });
                    }
                    Key::Character(c) if c.eq_ignore_ascii_case("c") => {
                        drive(controller, &Command::Clear)
                    }
                    _ => {}
                }
                renderer.window.request_redraw();
            }
            _ => {}
        }
    }

    fn about_to_wait(&mut self, _event_loop: &ActiveEventLoop) {
        // Repaint continuously (vsync-paced by the Fifo present mode) so a change made
        // by the *remote* controller — which is not a winit event — appears on screen
        // within a frame rather than waiting for the next local input.
        if let Some(renderer) = self.renderer.as_ref() {
            renderer.window.request_redraw();
        }
    }
}

/// Spawn the pinned-TLS control server on a background thread with its own Tokio
/// runtime, driving the shared `controller`. If it can't start, the window still runs
/// under local keyboard control.
fn start_remote_control(controller: Arc<Mutex<LiveController>>) {
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
        if let Err(e) = runtime.block_on(run_server(controller)) {
            eprintln!("SelahCue: remote control stopped: {e}");
        }
    });
}

async fn run_server(controller: Arc<Mutex<LiveController>>) -> Result<(), Box<dyn std::error::Error>> {
    let identity =
        SelfSigned::generate(vec!["localhost".into()]).map_err(|e| format!("tls identity: {e:?}"))?;
    let pin = identity.pin;

    // Demo shortcut: pre-pair one Producer device with a fixed token. Real pairing —
    // a single-use QR code confirmed on the host — is the mobile-client batch.
    let device = "producer";
    let token = "demo-producer-token";
    let registry = Arc::new(AsyncMutex::new(SessionRegistry::new()));
    {
        let now = Instant::now();
        let mut reg = registry.lock().await;
        reg.offer_pairing("demo", Role::Producer, now, Duration::from_secs(3600));
        reg.redeem(
            "demo",
            DeviceId(device.to_string()),
            SessionToken::new(token),
            now,
        )
        .map_err(|e| format!("pairing: {e:?}"))?;
    }

    let server = Arc::new(
        ControlServer::new(&identity, registry, handler_for(controller))
            .map_err(|e| format!("server: {e:?}"))?,
    );
    // Loopback only: the remote CLI runs on this machine. LAN binding travels with the
    // mobile client + QR pairing batch (so we don't expose an unpaired port by default).
    let listener = TcpListener::bind("127.0.0.1:0").await?;
    let addr = listener.local_addr()?;
    print_connect_banner(addr, &pin.to_hex(), device, token);
    server.run(listener).await.map_err(|e| format!("server run: {e:?}"))?;
    Ok(())
}

fn print_connect_banner(addr: SocketAddr, pin_hex: &str, device: &str, token: &str) {
    println!();
    println!("  SelahCue — remote control ready");
    println!("  ------------------------------------------------------------");
    println!("  The output window is driven by the LAN control server.");
    println!("  address : {addr}");
    println!("  pin     : {pin_hex}");
    println!("  device  : {device}   token : {token}   role : Producer");
    println!();
    println!("  Drive the window from another terminal on this machine:");
    println!("    cargo run -p selahcue-lan --example remote --features server -- \\");
    println!("      {addr} {pin_hex} {device} {token} next");
    println!("    (commands: next · previous · go-live · blackout-on · blackout-off · clear · state)");
    println!();
    println!("  Local keys also work: Space=next  Enter=Go Live  B=blackout  C=clear  Esc=quit");
    println!();
}

fn main() {
    let event_loop = EventLoop::new().expect("event loop");
    event_loop.set_control_flow(ControlFlow::Wait);
    let mut app = App::new();
    event_loop.run_app(&mut app).expect("run app");
}
