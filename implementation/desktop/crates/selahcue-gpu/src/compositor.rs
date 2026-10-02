//! The wgpu compositor (ADR-0002): renders the [`selahcue_engine`] scene model on
//! the GPU. The offscreen path here renders to a texture and reads pixels back, so
//! it can be compared against the CPU rasterizer for cross-backend parity
//! (ADR-0015).
//!
//! This pipeline renders only [`Layer::Fill`] and **silently skips [`Layer::Text`],
//! [`Layer::Image`], and [`Layer::Shape`]** (GPU-native glyphs / images / parametric
//! shapes are later batches — the CPU raster fills them today). The desktop shell today
//! does **not** use this compositor for the screen — it CPU-composites via
//! `selahcue-present` and blits the resulting framebuffer to its own surface, so
//! text renders. This pipeline must gain glyph rendering before it can drive an
//! on-screen surface (ADR-0002's intended future path).

use bytemuck::{Pod, Zeroable};
use selahcue_engine::raster::MAX_DIMENSION;
use selahcue_engine::scene::{Frame, Layer, Rgba};
use wgpu::util::DeviceExt;

/// One filled rectangle instance (pixel rect + straight-alpha colour).
#[repr(C)]
#[derive(Clone, Copy, Pod, Zeroable)]
struct Instance {
    rect: [f32; 4],
    color: [f32; 4],
}

fn to_linear(c: Rgba) -> [f32; 4] {
    [
        c.r as f32 / 255.0,
        c.g as f32 / 255.0,
        c.b as f32 / 255.0,
        c.a as f32 / 255.0,
    ]
}

/// A GPU compositor with an offscreen render path.
pub struct Compositor {
    device: wgpu::Device,
    queue: wgpu::Queue,
    pipeline: wgpu::RenderPipeline,
    uniform_layout: wgpu::BindGroupLayout,
}

impl Compositor {
    /// Create a compositor on the default adapter, or `None` if no GPU is available
    /// (so callers can skip the offscreen path in a GPU-less environment).
    pub fn new() -> Option<Self> {
        let instance = wgpu::Instance::default();
        // wgpu 30: `request_adapter` reports WHY it found nothing as a `Result`; this constructor's
        // contract is "None when there is no usable GPU", so the reason is deliberately dropped.
        let adapter =
            pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions::default()))
                .ok()?;
        let (device, queue) =
            pollster::block_on(adapter.request_device(&wgpu::DeviceDescriptor::default())).ok()?;

        let shader = device.create_shader_module(wgpu::ShaderModuleDescriptor {
            label: Some("rect"),
            source: wgpu::ShaderSource::Wgsl(include_str!("rect.wgsl").into()),
        });

        let uniform_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("uniforms"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });

        let pipeline_layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("rect"),
            bind_group_layouts: &[Some(&uniform_layout)],
            // No immediate (formerly "push constant") data: the resolution is a uniform buffer.
            immediate_size: 0,
        });

        let attrs = wgpu::vertex_attr_array![0 => Float32x4, 1 => Float32x4];
        let instance_layout = wgpu::VertexBufferLayout {
            array_stride: std::mem::size_of::<Instance>() as u64,
            step_mode: wgpu::VertexStepMode::Instance,
            attributes: &attrs,
        };

        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("rect"),
            layout: Some(&pipeline_layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs"),
                buffers: &[Some(instance_layout)],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            },
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs"),
                targets: &[Some(wgpu::ColorTargetState {
                    format: wgpu::TextureFormat::Rgba8Unorm,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
                compilation_options: wgpu::PipelineCompilationOptions::default(),
            }),
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleStrip,
                ..Default::default()
            },
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            multiview_mask: None,
            cache: None,
        });

        Some(Compositor {
            device,
            queue,
            pipeline,
            uniform_layout,
        })
    }

    /// Register a callback fired when the device is lost (NFR-024 seam: the
    /// desktop shell recreates the compositor when this fires; the CI
    /// device-loss test asserts the signal path works).
    pub fn on_device_lost(&self, callback: impl FnOnce(String) + Send + 'static) {
        // wgpu wants a reusable Fn; the loss event fires at most once per
        // device, so a take-once wrapper adapts the ergonomic FnOnce.
        let once = std::sync::Mutex::new(Some(callback));
        self.device
            .set_device_lost_callback(move |_reason, message| {
                if let Some(cb) = once.lock().unwrap_or_else(|e| e.into_inner()).take() {
                    cb(message);
                }
            });
    }

    /// Simulate a whole-device GPU loss (NFR-024 fault injection): destroys the
    /// underlying device, which fires the lost callback. Test seam — production
    /// losses come from the driver.
    pub fn simulate_device_loss(&self) {
        self.device.destroy();
        // Since wgpu follows the WebGPU spec here, `destroy()` only INVALIDATES the device: the
        // lost callback is delivered at the next poll once the queue is empty, not from inside
        // `destroy()` (wgpu 22 delivered it eagerly, which is what this seam used to rely on). A
        // genuine driver loss still invokes the callback immediately, so production recovery is
        // unaffected; this poll is what keeps the seam a faithful stand-in for it. Nothing is in
        // flight here (`render_to_pixels` waits for its own work), so this returns promptly.
        let _ = self.device.poll(wgpu::PollType::wait_indefinitely());
    }

    /// Render a frame to an offscreen texture and read the RGBA8 pixels back (the
    /// same readback ADR-0015 uses for parity/latency/flash analysis).
    pub fn render_to_pixels(&self, frame: &Frame) -> Vec<u8> {
        let width = frame.width.clamp(1, MAX_DIMENSION);
        let height = frame.height.clamp(1, MAX_DIMENSION);

        // Clear colour + fill instances (blackout = clear black, no fills).
        let (clear, instances) = if frame.blackout {
            (Rgba::BLACK, Vec::new())
        } else {
            let mut v = Vec::with_capacity(frame.layers.len());
            for layer in &frame.layers {
                // This GPU pipeline renders filled rectangles; text is CPU-rasterized
                // and presented via blit today (GPU-native glyphs are a later batch).
                if let Layer::Fill { rect, color } = layer {
                    v.push(Instance {
                        rect: [rect.x as f32, rect.y as f32, rect.w as f32, rect.h as f32],
                        color: to_linear(*color),
                    });
                }
            }
            (frame.background, v)
        };
        let clear_color = wgpu::Color {
            r: clear.r as f64 / 255.0,
            g: clear.g as f64 / 255.0,
            b: clear.b as f64 / 255.0,
            a: clear.a as f64 / 255.0,
        };

        let texture = self.device.create_texture(&wgpu::TextureDescriptor {
            label: Some("target"),
            size: wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format: wgpu::TextureFormat::Rgba8Unorm,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
            view_formats: &[],
        });
        let view = texture.create_view(&wgpu::TextureViewDescriptor::default());

        let uniforms: [f32; 2] = [width as f32, height as f32];
        let uniform_buf = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("resolution"),
                contents: bytemuck::cast_slice(&uniforms),
                usage: wgpu::BufferUsages::UNIFORM,
            });
        let bind_group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("uniforms"),
            layout: &self.uniform_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: uniform_buf.as_entire_binding(),
            }],
        });

        let instance_buf = self
            .device
            .create_buffer_init(&wgpu::util::BufferInitDescriptor {
                label: Some("instances"),
                contents: bytemuck::cast_slice(&instances),
                usage: wgpu::BufferUsages::VERTEX,
            });

        // Readback buffer with 256-byte-aligned rows.
        let unpadded_row = (width * 4) as u64;
        let align = wgpu::COPY_BYTES_PER_ROW_ALIGNMENT as u64;
        let padded_row = unpadded_row.div_ceil(align) * align;
        let readback = self.device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("readback"),
            size: padded_row * height as u64,
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });

        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor { label: None });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("composite"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(clear_color),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
                multiview_mask: None,
            });
            if !instances.is_empty() {
                pass.set_pipeline(&self.pipeline);
                pass.set_bind_group(0, &bind_group, &[]);
                pass.set_vertex_buffer(0, instance_buf.slice(..));
                pass.draw(0..4, 0..instances.len() as u32);
            }
        }
        encoder.copy_texture_to_buffer(
            wgpu::TexelCopyTextureInfo {
                texture: &texture,
                mip_level: 0,
                origin: wgpu::Origin3d::ZERO,
                aspect: wgpu::TextureAspect::All,
            },
            wgpu::TexelCopyBufferInfo {
                buffer: &readback,
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(padded_row as u32),
                    rows_per_image: Some(height),
                },
            },
            wgpu::Extent3d {
                width,
                height,
                depth_or_array_layers: 1,
            },
        );
        self.queue.submit(Some(encoder.finish()));

        // Map, strip row padding, return tightly-packed RGBA8.
        let slice = readback.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |r| {
            let _ = tx.send(r);
        });
        // Block until the copy has executed and the map callback has fired. A poll error (for
        // example a lost device) surfaces below as a failed map, which is fatal either way.
        let _ = self.device.poll(wgpu::PollType::wait_indefinitely());
        let _ = rx.recv();
        // wgpu 30 returns a `Result` here instead of panicking inside wgpu; the contract of this
        // method is unchanged (it has no error channel and has always panicked on a failed
        // readback), so the failure is still fatal — it just names itself now.
        let mapped = slice
            .get_mapped_range()
            .expect("the readback buffer is mapped once map_async has completed");
        let mut pixels = Vec::with_capacity((unpadded_row * height as u64) as usize);
        for row in 0..height as usize {
            let start = row * padded_row as usize;
            pixels.extend_from_slice(&mapped[start..start + unpadded_row as usize]);
        }
        drop(mapped);
        readback.unmap();
        pixels
    }
}
