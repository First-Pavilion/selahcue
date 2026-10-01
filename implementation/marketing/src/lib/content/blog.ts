/**
 * Blog posts. See `types.ts` for the honesty rules; every claim is backed by a file listed
 * in that post's `sources`, and each file was read against the shipped code, not just the
 * design documents (the PRD and ADRs describe intent; the operator UI and crates are what
 * runs). Where the two disagree, the post says what the build does.
 */
import { asParam, neighbours } from './lookup.ts'
import type { BlogPost, Neighbour } from './types.ts'

const OP = 'implementation/desktop/crates/selahcue-operator/dist'
const CR = 'implementation/desktop/crates'

export const blogPosts: readonly BlogPost[] = [
  {
    slug: 'why-offline-first-matters-for-sunday-morning',
    title: 'Why offline-first matters for Sunday morning',
    category: 'Product Strategy',
    published: '2026-10-01',
    featured: true,
    summary:
      'A service is not the moment to find out that your presentation software needed the internet. Here is what runs entirely on the desktop in SelahCue today, and the few things that still need a network.',
    body: [
      {
        type: 'p',
        text: 'Connections drop, and every venue is different. The practical question for a church tech team is not whether your network is good, it is whether the service can carry on when it is not. SelahCue is built so that the things you rely on during a service do not depend on a network at all.',
      },
      { type: 'h2', text: 'The rule we build to' },
      {
        type: 'p',
        text: 'SelahCue’s architecture states it plainly: slides, local scripture, media, timers, and blackout and clear must work with no network, no cloud service, no mobile controller and no AI. The desktop app owns everything that is live. Anything else is an assistant that can be missing without the service noticing.',
      },
      { type: 'h2', text: 'What runs on the desktop today' },
      {
        type: 'ul',
        items: [
          '**Scripture.** Five translations (KJV, WEB, ASV, WEBBE and Darby) are compiled into the application. Looking up and searching verses never leaves the machine.',
          '**Service plans, Preview and Live, timers, blackout and clear.** These all run in the desktop app and its output windows.',
          '**Phone control.** The controller app talks to your desktop over your local network only. The console states that nothing is exposed to the internet.',
          '**Speech-to-text.** Transcription runs on the device by default. The speech model is downloaded once, the first time you start listening, and after that it works with no connection.',
        ],
      },
      { type: 'h2', text: 'The desktop is in charge' },
      {
        type: 'p',
        text: 'A phone connected to SelahCue is a remote control, not a second copy of the show. Every command it sends is checked by the desktop against the role you gave that phone, and the desktop keeps working if the phone disconnects. If the rendering engine ever hits a fault, it holds the last good frame instead of going blank, and the console tells you it is doing so.',
      },
      { type: 'h2', text: 'Autosave, so a crash is a short interruption' },
      {
        type: 'p',
        text: 'SelahCue saves as you work, at most once a second, and the Storage settings say that at most five seconds of work can be lost. When you relaunch, it restores your plan, what was live and staged, blackout, and a running countdown. A **Session restored** notice tells you it happened. [Working offline and how autosave works](/docs/getting-started/offline-and-autosave) has the details, including what is not covered yet.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'What still needs the internet',
        text: 'The first download of the on-device speech model needs a connection once. Features that call an outside service are opt-in, and the cloud transcription option is not in release builds. Checking for updates is not available in this build yet.',
      },
    ],
    sources: [
      { path: 'docs/architecture/ARCHITECTURE.md', supports: 'Principles: desktop-authoritative, offline-first core (slides, scripture, timers, blackout work with no network), mobile holds no authoritative state, output-failure isolation.' },
      { path: 'docs/product/prds/SelahCue-PRD.md', supports: 'Core live functions must work with zero network (line 54, NFR-015).' },
      { path: `${CR}/selahcue-scripture/src/lib.rs`, supports: 'Five bundled translations compiled in; "Everything works offline".' },
      { path: `${OP}/index.html`, supports: 'Console copy: nothing exposed to the internet; autosave saves within 5 s; update checking unavailable; "holding its last good frame".' },
      { path: `${OP}/app.js`, supports: 'Session restored notice; on-device model downloads once on first Start listening; OUTPUT HELD message.' },
      { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'Autosave throttled to at most once per second; running countdown re-saved every 5 s.' },
      { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Restore on launch re-presents live/staged items, blackout and countdown; commands are RBAC-checked on the host.' },
      { path: `${CR}/selahcue-engine/src/engine.rs`, supports: 'Engine holds the last good frame on a fault (never-blank guarantee).' },
      { path: `${CR}/selahcue-operator/src/transcription_route.rs`, supports: 'Release builds fall back to on-device transcription when cloud is selected.' },
    ],
  },
  {
    slug: 'what-your-stage-team-sees-on-the-stage-display',
    title: 'What your stage team sees on the stage display',
    category: 'Worship Tech',
    published: '2026-10-01',
    summary:
      'The stage display is a separate screen for the people on the platform: what is on now, what is next, the time, a countdown and messages from production. Here is what it shows, and what it does not do yet.',
    body: [
      {
        type: 'p',
        text: 'The audience screen shows what the congregation should see. The people leading from the platform need more than that, and they need it without it ever appearing behind them on the wall. That is the stage display, also called the confidence display.',
      },
      { type: 'h2', text: 'What it shows' },
      {
        type: 'ul',
        items: [
          'The line that is live now, and a **NEXT** line so the band or speaker knows what is coming.',
          'The wall-clock date and time.',
          'The service countdown, with a clear **TIME UP** state, and an **OVER** count that keeps running after zero.',
          'A **Message from production** overlay when someone on the team sends one.',
        ],
      },
      {
        type: 'p',
        text: 'The audience never sees the next line, the countdown or stage messages. Those exist only on the stage output.',
      },
      { type: 'h2', text: 'Three layouts' },
      {
        type: 'p',
        text: 'Pick a stage theme from the console: **Worship** for songs, **Scripture** for readings with a time-left panel, or **Timer-only** for a large countdown. TIME UP is shown differently in each: it tints the timer bar in Worship, the time panel in Scripture, and the whole screen in Timer-only.',
      },
      { type: 'h2', text: 'Messages to the stage' },
      {
        type: 'p',
        text: 'The console has one-tap messages for the moments that come up every week (**Wrap up, 2 min left**, **Slow down**, **Wrap up now** and **Great job**) and a free-text field limited to 120 characters. Send it, and it appears on the stage display; clear it when it has done its job.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'What is not configurable yet',
        text: 'Stage text size, and which items appear on the stage display, are fixed in this build; those controls are shown disabled in Settings. There is one countdown at a time, and the stage display is the only screen that shows it. The audience screen never shows a timer.',
      },
      {
        type: 'p',
        text: 'To set it up step by step, read [Stage display](/docs/display-outputs/stage-display) and [Assign displays to outputs](/docs/display-outputs/assign-displays-to-outputs).',
      },
    ],
    sources: [
      { path: 'implementation/desktop/crates/selahcue-present/src/stage.rs', supports: 'Stage content: current/NEXT, TIME UP tint per template, OVER m:ss, Message from production overlay, templates.' },
      { path: `${OP}/index.html`, supports: 'Stage theme choices, message presets and 120-character custom message, "Shown on the stage output only", disabled text-size and layer controls.' },
      { path: `${OP}/settings-outputs.js`, supports: 'Stage defaults toggles are always-on and disabled: "Not configurable yet".' },
      { path: `${CR}/selahcue-desktop/src/main.rs`, supports: 'Wall clock rendered on the stage output.' },
      { path: `${CR}/selahcue-app/src/controller.rs`, supports: 'Timer is shown on stage only; audience never receives it.' },
    ],
  },
  {
    slug: 'which-bible-translations-ship-with-selahcue',
    title: 'Which Bible translations ship with SelahCue',
    category: 'Scripture',
    published: '2026-10-01',
    summary:
      'Five translations are built into the app and work offline. Licensed translations such as NIV and ESV are not available in this build. Here is exactly where things stand.',
    body: [
      {
        type: 'p',
        text: 'Scripture is the part of a service where an error is most visible, and where copyright questions are most real. So this post is deliberately plain about what is in the app today and what is not.',
      },
      { type: 'h2', text: 'What is included' },
      {
        type: 'ul',
        items: [
          '**KJV**, the King James Version. This is the translation the console opens on.',
          '**WEB**, the World English Bible.',
          '**ASV**, the American Standard Version.',
          '**WEBBE**, the World English Bible, British Edition.',
          '**DBY**, the Darby translation.',
        ],
      },
      {
        type: 'p',
        text: 'They are compiled into the application, so they are there with no download and no connection. SelahCue lists each of them as public domain on the About page, and the canon is the 66 books of the Protestant Bible.',
      },
      { type: 'h2', text: 'What is not included' },
      {
        type: 'p',
        text: 'Licensed translations such as NIV, ESV and NLT are not available in this build. The Scripture settings say so directly: importing a licensed module or connecting a licensed Bible service is **Not available in this build yet**. Nothing in the app downloads or unlocks a copyrighted translation today, and we will not describe a mechanism for that until one exists.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'Adding text yourself',
        text: 'SelahCue does not supply a licence for any translation. If you put text from a translation that is not public domain on a slide yourself, make sure you have permission to use it.',
      },
      { type: 'h2', text: 'Using what is there' },
      {
        type: 'p',
        text: 'Switch translation from the picker in the Scriptures tab; it lists the five by code. To find and put a verse on screen, see [Find and stage a verse](/docs/scripture-bibles/find-and-stage-a-verse).',
      },
    ],
    sources: [
      { path: 'implementation/desktop/crates/selahcue-scripture/src/lib.rs', supports: 'Bundled translations KJV (default), WEB, ASV, WEBBE, DBY compiled in; public-domain wording; works offline.' },
      { path: 'implementation/desktop/crates/selahcue-core/src/scripture.rs', supports: '66-book canon.' },
      { path: `${OP}/settings-about.js`, supports: 'About page lists bundled translations as "Public Domain — no attribution required".' },
      { path: `${OP}/index.html`, supports: '"Not available in this build yet" for licensed modules/APIs; "Licensed translations (a future release)".' },
      { path: `${OP}/app.js`, supports: 'Translation picker shows codes; console opens on KJV.' },
    ],
  },
  {
    slug: 'controlling-selahcue-from-a-phone-how-pairing-works',
    title: 'Controlling SelahCue from a phone: how pairing works',
    category: 'Mobile',
    published: '2026-10-01',
    summary:
      'A paired phone can advance slides, blackout the screen or run the timer from anywhere in the room, over your local network. Here is how a phone is paired and what each role is allowed to do.',
    body: [
      {
        type: 'p',
        text: 'The person running the service is not always standing at the desk. The SelahCue controller app lets a paired phone or tablet drive the show from the room, over the same local network as the desktop. This post explains how a device is trusted, in plain language.',
      },
      {
        type: 'callout',
        variant: 'info',
        title: 'Where the controller app stands',
        text: 'The controller app is not in the app stores yet; it is built from the project today. Everything below describes how pairing works in the current build.',
      },
      { type: 'h2', text: 'Pairing in three steps' },
      {
        type: 'ol',
        items: [
          'On the desktop, open the Remote Control page. It shows a QR code that is valid for two minutes and can be used once.',
          'On the phone, scan the code with the controller app. (The app can also list hosts it finds on the network, but if your network blocks that discovery, scanning the QR is the way in.)',
          'Back on the desktop, a pending request appears. You choose the device’s role and press **Approve**, or **Deny**.',
        ],
      },
      {
        type: 'p',
        text: 'The phone only trusts a host whose certificate matches the fingerprint in the QR code, and the connection is encrypted. Nothing is exposed to the internet and no internet connection is needed.',
      },
      { type: 'h2', text: 'Roles decide what a phone can do' },
      {
        type: 'ul',
        items: [
          '**Producer** can go live, step forward and back, clear, blackout, run the timer, search and stage scripture, and approve detected verses.',
          '**Assistant** can step through the plan and stage items and scripture, but only to Preview. It cannot go live, clear, blackout or run the timer.',
          '**Viewer** can watch the live state and transcript, and nothing else.',
        ],
      },
      {
        type: 'p',
        text: 'No phone can edit the plan, send stage messages, change themes or outputs, or manage devices. The desktop operator keeps those. Each command is checked by the desktop before it runs, and the desktop operator can remove a device at any time from the Paired devices list.',
      },
      {
        type: 'p',
        text: 'Step-by-step instructions are in [Pair a phone](/docs/mobile-control/pair-a-phone), and if something does not connect, start with [My phone will not pair](/support/mobile-control/phone-wont-pair).',
      },
    ],
    sources: [
      { path: 'implementation/desktop/crates/selahcue-lan/src/rbac.rs', supports: 'Producer / Assistant / Viewer permissions; plan edits, stage messages and device management not available to phones.' },
      { path: 'implementation/desktop/crates/selahcue-lan/src/server.rs', supports: 'Pairing code valid 120 s and single use; operator approval and role; revoke; per-connection tasks.' },
      { path: 'implementation/desktop/crates/selahcue-lan/src/pinning.rs', supports: 'Phone trusts only the certificate whose SHA-256 matches the invite.' },
      { path: `${OP}/remote.js`, supports: 'Pending request card with role dropdown, Approve and Deny; paired devices list with Revoke.' },
      { path: `${OP}/index.html`, supports: 'Pair a device panel; multicast-blocked guidance (scan the QR); nothing exposed to the internet.' },
      { path: 'implementation/mobile/selahcue_controller/lib/views/pairing_view.dart', supports: 'Phone pairing screen: scan QR, waiting for host approval.' },
      { path: 'docs/release/mobile/RELEASE-CHECKLIST.md', supports: 'Mobile app not yet released to stores (checklist unchecked).' },
    ],
  },
  {
    slug: 'ndi-output-in-selahcue-what-works-today',
    title: 'NDI output in SelahCue: what works today',
    category: 'Livestreaming',
    published: '2026-10-01',
    summary:
      'SelahCue can send an output to other software on your network as an NDI source. Here is how it is set up, which builds include it, and the limits you should know before planning a stream around it.',
    body: [
      {
        type: 'p',
        text: 'NDI lets one computer send video to another over the local network without a capture card. SelahCue can publish the audience-facing outputs as NDI sources so that a streaming computer can pick them up. This post is a straight account of how far that goes today.',
      },
      { type: 'h2', text: 'How it works' },
      {
        type: 'p',
        text: 'In **Screens & Outputs**, select an audience-class output (Audience Main, Lower Third or Livestream Program). The inspector has an **NDI Output** section with a **Source name** field and a **Broadcast as NDI** toggle. The source name is whatever you type, and two outputs cannot broadcast under the same name. Frames are sent at 1920 by 1080, at a frame rate you choose from 24, 30, 48, 50 or 60.',
      },
      { type: 'h2', text: 'Blackout reaches the stream too' },
      {
        type: 'p',
        text: 'When you blackout, every NDI feed goes black along with the audience screen, so the stream and the room agree. The stage display is separate and is not sent over NDI.',
      },
      { type: 'h2', text: 'Which builds include it' },
      {
        type: 'p',
        text: 'NDI is a build option. The Windows installer is built with it and carries the NDI runtime. A build without it shows the same settings but transmits nothing, and the inspector says **NDI runtime unavailable** and disables the toggle.',
      },
      {
        type: 'callout',
        variant: 'warning',
        title: 'Not shipped: transparency',
        text: 'Every frame SelahCue sends is opaque. The Lower Third output is a normal opaque picture, not a keyed overlay with an alpha channel, so it will not composite over your camera as a transparent layer. That is a later piece of work, and we would rather say so than let you find out mid-setup.',
      },
      { type: 'h2', text: 'On the receiving side' },
      {
        type: 'p',
        text: 'SelahCue’s own interface says the feed can be picked up by software such as OBS and vMix, or by another SelahCue. What those programs need installed on their side is documented by their makers, not by us. We publish no latency figures for NDI.',
      },
      {
        type: 'p',
        text: 'The how-to is in [NDI output](/docs/display-outputs/ndi-output), and if the toggle is greyed out, see [The NDI toggle is greyed out](/support/display-outputs/ndi-toggle-greyed-out).',
      },
    ],
    sources: [
      { path: `${OP}/app.js`, supports: 'NDI Output inspector: Source name, Broadcast as NDI, runtime-unavailable message, duplicate-name refusal, frame-rate choices, receivable by OBS / vMix / another SelahCue.' },
      { path: 'implementation/desktop/crates/selahcue-desktop/src/video_sink.rs', supports: 'NDI sink; 1920x1080 RGBA frames.' },
      { path: 'implementation/desktop/crates/selahcue-desktop/Cargo.toml', supports: '`ndi` Cargo feature is off by default.' },
      { path: '.github/workflows/windows-installer.yml', supports: 'Windows installer built with --features ndi and bundles the NDI runtime.' },
      { path: 'implementation/desktop/crates/selahcue-app/src/controller.rs', supports: 'Blackout returns black frames for all outputs including NDI; duplicate NDI source names refused.' },
      { path: 'implementation/desktop/crates/selahcue-engine/src/raster.rs', supports: 'Output is opaque; no alpha.' },
      { path: 'implementation/desktop/crates/selahcue-present/src/theme.rs', supports: 'Lower-third uses opaque backdrop; true NDI alpha-keying is a later slice.' },
    ],
  },
]

export function blogPath(slug: string): string {
  return `/blog/${slug}`
}

export function findBlogPost(slug: unknown): BlogPost | undefined {
  const wanted = asParam(slug)
  return blogPosts.find((p) => p.slug === wanted)
}

export const featuredPost: BlogPost | undefined = blogPosts.find((p) => p.featured)

export function blogNeighbours(post: BlogPost): { prev: Neighbour | null; next: Neighbour | null } {
  return neighbours(blogPosts, blogPosts.indexOf(post), (p) => ({ title: p.title, to: blogPath(p.slug) }))
}

/** Up to `limit` other posts, same category first, then the rest in index order. */
export function relatedPosts(post: BlogPost, limit = 3): BlogPost[] {
  const others = blogPosts.filter((p) => p !== post)
  const same = others.filter((p) => p.category === post.category)
  const rest = others.filter((p) => p.category !== post.category)
  return [...same, ...rest].slice(0, limit)
}
