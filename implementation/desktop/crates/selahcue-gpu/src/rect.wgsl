// Instanced coloured rectangles — the GPU equivalent of the CPU rasterizer's
// Layer::Fill painting (painter's order via draw order; alpha src-over blend).

struct Uniforms { resolution: vec2<f32> };
@group(0) @binding(0) var<uniform> u: Uniforms;

struct VsIn {
    @location(0) rect: vec4<f32>,  // x, y, w, h in pixels (top-left origin)
    @location(1) color: vec4<f32>, // rgba 0..1
    @builtin(vertex_index) vidx: u32,
};

struct VsOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) color: vec4<f32>,
};

@vertex
fn vs(in: VsIn) -> VsOut {
    // Triangle-strip quad corners: (0,0),(1,0),(0,1),(1,1).
    let corner = vec2<f32>(f32(in.vidx & 1u), f32((in.vidx >> 1u) & 1u));
    let px = in.rect.xy + corner * in.rect.zw;
    let ndc = vec2<f32>(px.x / u.resolution.x * 2.0 - 1.0, 1.0 - px.y / u.resolution.y * 2.0);
    var out: VsOut;
    out.pos = vec4<f32>(ndc, 0.0, 1.0);
    out.color = in.color;
    return out;
}

@fragment
fn fs(in: VsOut) -> @location(0) vec4<f32> {
    return in.color;
}
