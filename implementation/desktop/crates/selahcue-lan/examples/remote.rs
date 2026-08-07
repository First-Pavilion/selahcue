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

use selahcue_lan::protocol::{Command, PairingInvite, ServerMessage};
use selahcue_lan::{CertPin, ControlClient};
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();

    // Pairing mode: redeem an invite URI (from the operator's QR / terminal) — the
    // same flow the mobile app uses. Prints the issued credentials for reuse.
    if args.len() >= 3 && args[1] == "pair" {
        let invite = PairingInvite::parse_uri(&args[2])
            .ok_or("bad invite (want the selahcue://pair?... URI)")?;
        let pin = CertPin::from_hex(&invite.pin_hex).ok_or("bad pin in invite")?;
        let addr: SocketAddr = format!("{}:{}", invite.host, invite.port)
            .parse()
            .map_err(|_| format!("bad host/port in invite: {}:{}", invite.host, invite.port))?;
        let name = args
            .get(3)
            .map(String::as_str)
            .unwrap_or("selahcue-remote CLI");
        println!("pairing with {addr} — waiting for the host to allow…");
        let (client, creds) = ControlClient::pair(
            addr,
            "localhost",
            pin,
            &invite.code,
            name,
            std::env::consts::OS,
        )
        .await?;
        println!("paired! role {:?}", client.role());
        println!("device : {}", creds.device_id);
        println!("token  : {}", creds.token);
        println!("reconnect later with:");
        println!(
            "  remote {addr} {} {} {} state",
            invite.pin_hex, creds.device_id, creds.token
        );
        client.close().await.ok();
        return Ok(());
    }

    if args.len() < 6 || args.len() > 7 {
        eprintln!("usage: remote <addr> <pin-hex> <device> <token> <command> [arg]");
        eprintln!("       remote pair <selahcue://pair?...uri> [device-name]");
        eprintln!(
            "commands: next  previous  go-live  blackout-on  blackout-off  clear  state  \
             timer <seconds>  stop-timer"
        );
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
        "timer" => {
            let seconds: u32 = args
                .get(6)
                .and_then(|s| s.parse().ok())
                .ok_or_else(|| "`timer` needs <seconds>, e.g. `timer 300`".to_string())?;
            Command::StartTimer { seconds }
        }
        "stop-timer" => Command::StopTimer,
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
