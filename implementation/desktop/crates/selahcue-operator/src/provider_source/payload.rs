//! Frozen, bounded payload framing shared by native build generation and consumption.
pub(crate) const MAGIC: &[u8] = b"\0SCUE-PILOT-PAYLOAD-V1\0";
pub(crate) const TRAILER: &[u8] = b"\0SCUE-PILOT-END-V1\0";
pub(crate) const MAX_PAYLOAD: usize = 16_384;

pub(crate) fn frame_json(raw: &[u8]) -> Option<Vec<u8>> {
    if raw.is_empty() || raw.len() > MAX_PAYLOAD || std::str::from_utf8(raw).is_err() {
        return None;
    }
    let mut frame = Vec::with_capacity(MAGIC.len() + 4 + raw.len() + TRAILER.len());
    frame.extend_from_slice(MAGIC);
    frame.extend_from_slice(&(raw.len() as u32).to_le_bytes());
    frame.extend_from_slice(raw);
    frame.extend_from_slice(TRAILER);
    Some(frame)
}

pub(crate) fn json_from_frame(frame: &[u8]) -> Option<&str> {
    if !frame.starts_with(MAGIC) {
        return None;
    }
    let body_start = MAGIC.len().checked_add(4)?;
    let length = u32::from_le_bytes(frame.get(MAGIC.len()..body_start)?.try_into().ok()?);
    let length = usize::try_from(length).ok()?;
    if length == 0 || length > MAX_PAYLOAD {
        return None;
    }
    let body_end = body_start.checked_add(length)?;
    let frame_end = body_end.checked_add(TRAILER.len())?;
    if frame.len() != frame_end || frame.get(body_end..frame_end)? != TRAILER {
        return None;
    }
    std::str::from_utf8(frame.get(body_start..body_end)?).ok()
}
