//! A minimal remote controller CLI (foundation demo).
//!
//! Connects to a running SelahCue output window over the pinned-TLS control link and
//! sends **one** command, so you can watch a remote command drive the on-screen output.
//! The window prints the exact address / pin / device / token to use on startup.
//!
//! ```text
//! cargo run -p selahcue-lan --example remote --features server -- \
//!   127.0.0.1:54321 <pin-hex> producer demo-producer-token go-live
//! ```
//!
//! The real mobile controller is a Flutter client speaking this same protocol; this
//! CLI exercises the identical server path (pinned TLS → device auth → RBAC → handler).

use selahcue_lan::protocol::{Command, ServerMessage};
use selahcue_lan::{CertPin, ControlClient};
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 6 {
        eprintln!("usage: remote <addr> <pin-hex> <device> <token> <command>");
        eprintln!("commands: next  previous  go-live  blackout-on  blackout-off  clear  state");
        std::process::exit(2);
    }

    let addr: SocketAddr = args[1]
        .parse()
        .map_err(|_| format!("bad address (want host:port): {}", args[1]))?;
    let pin = CertPin::from_hex(&args[2])
        .ok_or_else(|| format!("bad pin (want 64 hex chars): {}", args[2]))?;
    let device = &args[3];
    let token = &args[4];
    let command = match args[5].as_str() {
        "next" => Command::Next,
        "previous" => Command::Previous,
        "go-live" => Command::GoLive,
        "blackout-on" => Command::Blackout { on: true },
        "blackout-off" => Command::Blackout { on: false },
        "clear" => Command::Clear,
        "state" => Command::GetState,
        other => return Err(format!("unknown command: {other}").into()),
    };

    let mut client = ControlClient::connect(addr, "localhost", pin, device, token).await?;
    println!("connected — granted role {:?}", client.role());

    let reply = client.command(command).await?;
    match reply {
        ServerMessage::Ack { .. } => println!("Ack — the output window updated."),
        ServerMessage::Denied { reason, .. } => println!("Denied: {reason:?}"),
        other => println!("{other:?}"),
    }

    client.close().await.ok();
    Ok(())
}
