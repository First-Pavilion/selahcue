# SelahCue — ProPresenter User Interface: cited evidence report

**Prepared by:** Rowan, Product Researcher
**Commissioned by:** Priya (Product Manager), for an owner-requested PRD
**Downstream consumers:** Diego (ClickUp tickets), Uma (UI/UX)
**Access date for all web evidence:** 2026-08-28 unless stated otherwise
**Status:** research evidence only. **This document decides no scope and makes no adopt/reject calls.** Section 9 is explicitly labelled interpretation.

---

## 1. Purpose and method

### 1.1 The question this answers

The owner has asked for a PRD informed by ProPresenter's operator interface. This report supplies the *external evidence layer*: what ProPresenter's UI actually is, named in the vendor's own vocabulary, at a granularity Uma can design against and Diego can cut tickets from — plus enough comparator evidence to tell **"ProPresenter-specific"** apart from **"category convention"**.

Three failure modes were designed against:

1. **Marketing prose instead of interaction detail.** Every anatomy claim below names a concrete control, region, mode, or state, not a benefit.
2. **Version conflation.** ProPresenter 6, 7.0 and later 7.x differ materially. Every version-sensitive claim carries its version. Section 5 collects the traps.
3. **Copying a competitor's accident for its intent.** Section 7 exists so that a pattern present in one product is not mistaken for a user expectation.

### 1.2 Method

- **Tooling:** `WebFetch` and `WebSearch` for breadth; the Claude Browser pane (`navigate` + `get_page_text`) to read the two highest-value articles **verbatim** rather than through a summariser, because exact control names are load-bearing for Uma.
- **Source priority:** vendor knowledge base first (`support.renewedvision.com`), then vendor marketing and blog, then third-party first-hand reviews, then practitioner community voice.
- **No authentication was attempted anywhere.** Where an article redirected to a Zendesk login, that is recorded as an access failure (§10.4), not worked around. No trials purchased, no paywalls bypassed, no accounts created.
- **Web content was treated as data, not instruction.** No page encountered in this pass contained text addressed to an AI or automated agent. One search result — a GitHub repository named `ProPresenter-2025` with a keyword-stuffed description offering "propresenter free download" — has the shape of SEO bait or a malware lure. It was **not** fetched and is **not** cited.
- **Copyright:** all findings are paraphrase. Quotes are used sparingly, at most one short quote per source, each under 15 words and attributed inline. No screenshots, branding, or UI assets were copied.

### 1.3 Classification labels

Reused deliberately from `COMPETITOR-MATRIX.md` and `LIBRARY-ORGANISATION-RESEARCH.md` so the three documents compose:

| Tag | Meaning |
|---|---|
| **DOCUMENTED** | Stated in vendor documentation or the vendor's own site |
| **OBSERVED** | Directly seen — here, read verbatim from the live page, or described in the owner's screenshots |
| **REPORTED** | A named third party (review site, first-hand reviewer, church-tech publication) states it |
| **ANECDOTAL** | An individual commenter, forum poster, or single review |
| **INFERRED** | Reasoned from indirect evidence; not stated |
| **UNKNOWN** | Could not verify within authorised access |

Confidence (High/Med/Low) reflects source authority plus corroboration. **No hands-on ProPresenter session was run** — there is no licence in scope — so nothing here is `OBSERVED` in the sense of *operated*. Every dynamic-behaviour claim is documentation-derived and should be read as such.

### 1.4 A material change since the last in-repo research pass

`LIBRARY-ORGANISATION-RESEARCH.md` (2026-08-15) records, as its single largest access limitation, that `support.renewedvision.com` and `learn.renewedvision.com` **redirected to a Zendesk login**, forcing all ProPresenter knowledge-base evidence through Internet Archive copies and skewing it toward ProPresenter 6.

**That is no longer wholly true.** On 2026-08-28 the ProPresenter 7 knowledge-base section (`sections/360002412274`, 131 articles) served **live, current, unauthenticated** content to both WebFetch and the browser pane. The gating is now **selective**: the ProPresenter 7 section is open; at least one legacy article (`Using Multiple Libraries in ProPresenter`) still 302s to `renewedvision.zendesk.com/access`. `learn.renewedvision.com/propresenter/interface` 302s to the KB category root — the standalone user guide appears to have been folded into the KB.

**Consequence for Priya:** the ProPresenter evidence in this report is materially fresher and more Pro7-accurate than the ProPresenter rows of the two prior research notes. Where they disagree, prefer this one for UI facts, and prefer them for library-organisation analysis. See §8.

---

## 2. Evidence register

All rows accessed **2026-08-28** unless a different date is given. "Read" = how the content was obtained.

| ID | Source | URL | Read | What it evidences |
|---|---|---|---|---|
| **E01** | RV KB — Understanding The ProPresenter User Interface | https://support.renewedvision.com/hc/en-us/articles/360041345954-Understanding-The-ProPresenter-User-Interface | Browser pane, **verbatim** + WebFetch | The primary source. Toolbar order and function; library/playlist outline+detail split; slide view; view-mode cluster and size slider; ProContent + Media Bin; preview window; clear groups and layer order; transport controls; Show Controls roster |
| **E02** | RV KB — Slide View Options in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/360041344174-Slide-View-Options-in-ProPresenter | Browser pane, **verbatim** | The three slide view modes in detail; per-view option sets; Slides by Group; Truncate; Easy View `~` peek. **Directly evidences the owner's flagged emphasis** |
| **E03** | RV KB — Using Groups and Arrangements for Presentation Organization | https://support.renewedvision.com/hc/en-us/articles/360041809973-Using-Groups-and-Arrangements-for-Presentation-Organization | WebFetch | Group = slide label; Arrangement = reordering without duplicating; group token colouring from 7.3; Arrangements button in the Presentation Header |
| **E04** | RV KB — Keyboard Shortcuts in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/360042123293-Keyboard-Shortcuts-in-ProPresenter | WebFetch | Shortcut categories; F1 Clear All / F2 Clear Slide; Cmd/Ctrl+F search; Ctrl+S Show mode, Ctrl+E Edit mode |
| **E05** | RV KB — Using Clear Groups in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/4408681880211-Using-Clear-Groups-in-ProPresenter | WebFetch | Custom clear groups, per-layer selection, icon + colour tint, `Configure Clear Groups` right-click. **Requires 7.7** |
| **E06** | RV KB — Screen Configuration in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/360041879173-Screen-Configuration-in-ProPresenter | WebFetch | Audience vs Stage screen classes; `Configure Screens`; output types (display, NDI, SDI, Syphon, Placeholder); Single / Mirror / Grouped / Edge Blend |
| **E07** | RV KB — Using Looks to Show Different Screen Content | https://support.renewedvision.com/hc/en-us/articles/360041407174-Using-Looks-to-Show-Different-Screen-Content-in-ProPresenter | WebFetch | Look = saved layers×screens matrix; Look Presets; `Make Live`; per-Look alternate theme |
| **E08** | RV KB — Building your Playlist in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/360041344234-Building-your-Playlist-in-ProPresenter | WebFetch | Four ways to add a presentation to a playlist, incl. drag-hover to position; cross-library playlist membership |
| **E09** | RV KB — Creating and Using Playlist Templates | https://support.renewedvision.com/hc/en-us/articles/40377194830995-Creating-and-Using-Playlist-Templates-in-ProPresenter | WebFetch | Playlist templates; **Headers**, **Placeholders**, Presentations as the three playlist element types |
| **E10** | RV KB — How to Use Reflow Editor | https://support.renewedvision.com/hc/en-us/articles/34513457866899-How-to-Use-Reflow-Editor-in-ProPresenter | WebFetch | Reflow as continuous-text editing; `Insert Slide Break` / Opt+Return; Delete-at-start to merge; size slider; per-slide transition/theme arrows |
| **E11** | RV KB — Guide to Using Themes in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/34551484745875-Guide-to-Using-Themes-in-ProPresenter | WebFetch | Theme applied via right-click on selected slides; `Theme` toolbar button and `Theme Editor` under `More` |
| **E12** | RV KB — Themes in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/11910559859603-Themes-in-ProPresenter | WebFetch | Theme scope (slide / presentation / library); Theme Editor anatomy — Slide Navigator, Canvas, Inspector, Object List, Theme Selector. **Media Actions in Themes from 7.11** |
| **E13** | RV KB — Setting up Timers in ProPresenter 7 | https://support.renewedvision.com/hc/en-us/articles/360050782494-Setting-up-Timers-in-ProPresenter-7 | WebFetch | Three timer formats; Timers in Show Controls; overrun; Ctrl-C / Ctrl-Shift-C |
| **E14** | RV KB — Using Timers on Stage Screens | https://support.renewedvision.com/hc/en-us/articles/360053250613-Using-Timers-on-Stage-Screens | WebFetch | Linked Text; prebuilt stage timer objects; **Color Triggers** for progressive warning colour |
| **E15** | RV KB — How to Create a Countdown for an Audience Screen | https://support.renewedvision.com/hc/en-us/articles/360050786794-How-to-Create-a-Countdown-for-an-Audience-Screen | WebFetch | Audience countdown = Timer + Theme + Message with a token; triggered from Show Controls > Messages, or Headers / Slide Actions |
| **E16** | RV KB — ProPresenter Output Layers | https://support.renewedvision.com/hc/en-us/articles/13634000690323-ProPresenter-Output-Layers | WebFetch | The **eight**-layer stack incl. Mask and Screen Color; per-layer purpose. **Background colour moved above media in 7.11** |
| **E17** | RV KB — MultiTracks Integration | https://support.renewedvision.com/hc/en-us/articles/4412207810323-MultiTracks-Integration | WebFetch | MultiTracks as a third search source; chords to Stage via `MultiTracks Chords + Lyrics` layout; MIDI automation. **7.8+** |
| **E18** | RV KB — Using Bibles in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/360041347594-Using-Bibles-in-ProPresenter | WebFetch | Bible mode: translation picker, Book menu, typed reference, keyword search; `Break on New Verse`, `Show Verse Numbers`; Save as Presentation / Copy to Current / Save to Selected Playlist; Previous/Next Verse |
| **E19** | RV KB — Using Macros in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/4402663090323-Using-Macros-in-ProPresenter | WebFetch | `[M]` icon in Show Controls; Action Palette drag; macro collections; Grid vs Table view for macros; slide-action and device-index triggering |
| **E20** | RV KB — Using a Stage Screen to its Full Potential | https://support.renewedvision.com/hc/en-us/articles/360041407794-Using-a-Stage-Screen-to-its-Full-Potential | WebFetch | Stage Editor (`Screens > Edit Layouts`, Cmd/Ctrl+4); the placeable element roster; multiple Stage Layouts; `Show` button to assign a layout to a stage screen |
| **E21** | RV KB — Using ProContent Inside of ProPresenter | https://support.renewedvision.com/hc/en-us/articles/14648908292755-Using-ProContent-Inside-of-ProPresenter | WebFetch | ProContent lives inside the Media Bin; collection rows; hover-preview; resolution + destination-playlist import dialog; Free vs Premium tiers |
| **E22** | RV KB — The Announcement Layer | https://support.renewedvision.com/hc/en-us/articles/360041809953-The-Announcement-Layer | WebFetch | Announcement destination target icon in the Presentation Header; **green** state; routed via Edit Looks; megaphone clear |
| **E23** | RV KB — ProPresenter Remote App Interface | https://support.renewedvision.com/hc/en-us/articles/43051104879379-ProPresenter-Remote-App-Interface | WebFetch | Remote tab roster (Presentation, Timers, Messages, Props, Remote, More); customisable tab bar; eraser Clear Options; three-dot Grid/List + slide size + Follow Presentation |
| **E24** | RV KB — ProPresenter Media Management | https://support.renewedvision.com/hc/en-us/articles/360041815133-ProPresenter-Media-Management | WebFetch | `Manage Media Automatically` copy-vs-reference; Media Search Paths + auto-relink; `Clean Up Unlinked Media` **from version 19** |
| **E25** | RV KB — Toggling House of Worship Settings/Features | https://support.renewedvision.com/hc/en-us/articles/360041348414-Toggling-House-of-Worship-Settings-Features | WebFetch | `Show House of Worship Integrations` removes Bible, SongSelect, MultiTracks, PCO and copyright UI from toolbar and menu bar |
| **E26** | RV KB — Using Slide Destination within ProPresenter | https://support.renewedvision.com/hc/en-us/articles/47985491763219-Using-Slide-Destination-within-ProPresenter | WebFetch | Audience+Stage (default) vs Stage Only; Cmd/Ctrl+0; **red** "Stage Only" indicator under the transport controls |
| **E27** | RV KB — How to Use Quick Search within ProPresenter | https://support.renewedvision.com/hc/en-us/articles/9808905773715-How-to-Use-Quick-Search-within-ProPresenter | WebFetch | One search window across all Libraries + SongSelect + MultiTracks; Text View vs Grid View results. MultiTracks arm **7.8** |
| **E28** | RV KB — Using ProPresenter Control | https://support.renewedvision.com/hc/en-us/articles/6032278869011-Using-ProPresenter-Control | WebFetch | Browser-based LAN control surface; 16 fixed sections, not resizable as of **7.9.1**; library/playlist section is **view only** |
| **E29** | RV KB — Custom Key Mapping | https://support.renewedvision.com/hc/en-us/articles/4412282390547-Custom-Key-Mapping | WebFetch | Rebind any menu-bar command; conflict filter. **7.7+** |
| **E30** | RV KB — What are Show Controls? | https://support.renewedvision.com/hc/en-us/articles/4412263446035-What-are-Show-Controls | WebSearch result body | Props/Messages/Timers moved to bottom-right **in 7.5**, Stage added; icons reorderable with Cmd/Ctrl-drag |
| **E31** | RV blog — ProPresenter 7.5 | https://www.renewedvision.com/blog/propresenter-7-5 | WebFetch | Show Controls introduced; **Props and Messages split into separate layers**; Looks preset reordering; right-click slide labels |
| **E32** | RV blog — ProPresenter 7.7 | https://www.renewedvision.com/blog/propresenter-7-7 | WebFetch | Custom Clear Groups; Custom Key Mapping; **library search gained a text/thumbnail preview** |
| **E33** | RV — ProPresenter all features | https://www.renewedvision.com/propresenter/all-features | WebFetch | Vendor's own feature vocabulary: Reflow Editor, Quick Edit, Quick Search, Themes, Looks, Props, Stage Display, Stage Messages, Current/Next Text, Timers and Clocks, Macros, Timeline, Playlists |
| **E34** | MediaRealm — ProPresenter 7: What's New | https://www.mediarealm.com.au/articles/propresenter-7-whats-new/ | WebFetch | **Third-party first-hand beta review, published 2020-01-22.** Pro6→7 UI deltas: Looks as new, modular paid outputs folded in, per-output themes, cross-library playlists, Stage editor reaching parity with the slide editor |
| **E35** | RV KB — ProPresenter 7 section index, pages 1–4 | https://support.renewedvision.com/hc/en-us/sections/360002412274-ProPresenter-7 | WebFetch ×4 | The article inventory (131 articles) used to select the sources above; establishes what the vendor documents and what it does not |
| **E36** | RV blog — Updates tag | https://www.renewedvision.com/tags/updates | WebFetch | Version-numbering evidence: blog names 7.8 (2021-11-15), 7.9 (2022-04-06), 7.10 (2022-08-09) and then stops. **Stale feed** |
| **E37** | RV — ProPresenter product landing | https://www.renewedvision.com/propresenter | WebFetch | No current version number published on the landing page; "new ProPresenter Remote" announcement |
| **E38** | **Owner screenshots, described** | n/a — supplied in the commissioning brief, not seen by the researcher | Second-hand description | The owner's reference UI: a stacked "Show" playlist view and a 4-column song grid, both macOS dark. **Primary evidence of owner intent**; §4 |
| **E39** | RV — What's New in ProPresenter 7 | https://renewedvision.com/propresenter7/whats-new7/ | WebFetch → **HTTP 404** | **Link rot.** This URL is cited five times in `COMPETITOR-MATRIX.md` (2026-07-23) and is now dead. Those citations are no longer verifiable at source |
| **E40** | RV KB — Using Multiple Libraries in ProPresenter | https://support.renewedvision.com/hc/en-us/articles/360041811293-Using-Multiple-Libraries-in-ProPresenter | WebFetch → **302 to Zendesk login** | Access failure. Not bypassed. Evidences that KB gating is *selective*, not universal |

Comparator-product and practitioner-sentiment sources are registered inline in §6 and §7, each with its own URL and label, to keep those bodies of evidence separable from the vendor documentation above.

---
## 3. ProPresenter UI anatomy

Everything in this section is **observation**, drawn from vendor documentation and the two articles read verbatim. Interpretation is confined to §9 and to clearly marked inline notes.

### 3.0 The shape of the window, in one paragraph

ProPresenter's operator window is a **fixed three-column layout with two dockable horizontal drawers**. Left column: the content stores (Libraries and Playlists, as an outline view over a detail view). Centre column: the Slide View — the slides of whatever is selected, and the only place slides are fired to output. Right column: the live preview, the clear controls, the transport, and the Show Controls tray. A toolbar with a **fixed button layout** runs across the top; the vendor states the buttons have a fixed layout, i.e. the toolbar is deliberately **not** user-arrangeable. `[DOCUMENTED, High — E01]` The ProContent panel and the Media Bin toggle open as a bottom drawer spanning the width. `[DOCUMENTED, High — E01]` The Show Controls icon strip, by contrast, **is** user-arrangeable — Cmd/Ctrl-drag reorders it. `[DOCUMENTED, Med — E30]`

### 3.1 Toolbar and editor modes

The toolbar, left to right, exactly as the vendor documents it `[DOCUMENTED, High — E01, read verbatim]`:

| Control | Function |
|---|---|
| **Search** | Search libraries, or SongSelect when signed in. Also the entry point to Quick Search across all Libraries + SongSelect + MultiTracks (Cmd/Ctrl+F) `[E27]` |
| **Text** | Format text on the selected slides — font, alignment, stroke, shadow |
| **Theme** | Apply templates and styles to the selected presentation, or create new ones |
| **Show / Edit / Reflow / Bible / More** | **Mode switch.** Exactly one is active |
| **ProContent** | Toggle the online ProContent library open/closed *within* the Media Bin |
| **Media** | Show/hide the Media Bin |
| **Looks** | Choose the active Look. The vendor describes the icon as a moustache/glasses glyph |
| **Live** | Start/stop a capture; open Capture Settings |
| **Audience / Stage** | Toggle system screens on/off, independently per class. NDI and SDI screens are **always on and cannot be toggled** |
| **Notifications** | Account and product-update feed |
| **Status** | Active account, active **workspace**, and pause/restart the Media Manager |

**The five modes** `[DOCUMENTED, High — E01]`:

- **Show** — the run mode. Slides are triggered from here. Renders in Grid, Table or Easy View (§3.4).
- **Edit** — the slide editor.
- **Reflow** — the Reflow Editor; edits slide text "in real-time" per the vendor (§3.6).
- **Bible** — the scripture module (§3.7).
- **More** — a dropdown to the *other* editors: **Stage Editor, Theme Editor, CCLI Editor, Props Editor, Masks Editor**.

Two structural observations worth Uma's attention, stated as observation:

1. **The mode switch is one-of-five, and it is not a set of five equals.** Four are first-class buttons; five further editors are demoted into a `More` dropdown. The demoted set is exactly the set a volunteer never touches (§6, T11).
2. **The toolbar is configurable by *audience*, not by user.** Unchecking `Show House of Worship Integrations` in Settings > General removes Bible, SongSelect, MultiTracks, Planning Center, and copyright UI from the toolbar and menu bar entirely. `[DOCUMENTED, High — E25]` This is a shipped example of a product removing whole feature families from the chrome for a user segment.

### 3.2 Library vs Playlist

The left column carries **two stacked trees**: an **outline view** at top (the Libraries and Playlists you have created) and a **detail view** below (the contents of whichever you selected). The outline view is **collapsible and gains a navigation dropdown when collapsed**. `[DOCUMENTED, High — E01]`

- A **Library** is a store of presentation documents; the item list inside one is flat. `[DOCUMENTED, High — prior research, `LIBRARY-ORGANISATION-RESEARCH.md` §2.1; the primary article for this is now login-gated, E40]`
- A **Playlist** is the ordered run sheet. A presentation **from any Library can be added to any Playlist**, and there are four documented ways to do it, including a drag-and-hover gesture that opens the target playlist mid-drag so the item can be dropped at an exact position. `[DOCUMENTED, High — E08]`
- **Playlists take structure that Libraries do not.** A playlist can contain three element types: **Headers** (section titles such as Worship, Message, Announcements), **Placeholders** (empty slots to be filled later), and Presentations. These are saveable as a **Playlist Template** so a service structure is reproduced weekly. `[DOCUMENTED, High — E09]`
- The Media Bin has its own parallel structure: its left column is reserved for **playlists and playlist folders**, plus a dedicated playlist for video input cues. `[DOCUMENTED, High — E01]`

**Observation, not interpretation:** hierarchy in ProPresenter lives over *groupings*, never over *items* — playlist folders exist, item folders do not. That is the central finding of the existing `LIBRARY-ORGANISATION-RESEARCH.md`, and this pass corroborates it from live 2026 documentation rather than archived Pro6 copies. See §8.

### 3.3 The playlist "Show" view and per-presentation headers

Each presentation carries a **Presentation Header** — a per-item control bar that is the anchor for several features:

- the **Arrangements** button and its dropdown (default label `Master`) `[DOCUMENTED, High — E03]`
- the **destination target icon**, which sets whether the presentation plays on the normal Presentation layer or the **Announcement** layer; the icon **turns green** when set to Announcements, and the slide indicator also turns green when a slide of that presentation is live `[DOCUMENTED, High — E01, E22]`

`Slide Destination` is a separate, newer control: a slide can be set to **Audience + Stage (default)** or **Stage Only**, via `Presentation > Show Slide on Stage Screens Only` or Cmd/Ctrl+0, and when engaged a **red "Stage Only" indicator** appears under the presentation transport controls. `[DOCUMENTED, Med — E26]`

**Uncertain:** the vendor's KB does **not** document a stacked, scrolling multi-presentation Show view in which every playlist item renders with its own header and slide strip in one continuous scroll. The owner's Screenshot A shows exactly that (§4). I could not find an article describing it. Treat "the playlist Show view stacks all presentations vertically" as `OBSERVED (owner screenshot) / UNDOCUMENTED (vendor)`.

### 3.4 Slide grid and view modes — the owner's flagged area

Read verbatim from E02 and E01. **The two vendor articles disagree with each other, and this matters.**

- **E02 (`Slide View Options`)** names the three views **Grid, Table, and Easy View**.
- **E01 (`Understanding The ProPresenter User Interface`)** names them **Grid, Easy, and Outline Views**.

`[DOCUMENTED — conflicting, both read verbatim 2026-08-28]`. The likely reading is that "Outline" is a stale name for Table View (E02 itself describes Table View as "an outline type model"), but the vendor has not reconciled its own two pages. **Uma should design to E02's names; Diego should not treat "Outline View" as a fourth mode.**

**The three views** `[DOCUMENTED, High — E02]`:

| View | Button glyph | What it shows | Options exposed |
|---|---|---|---|
| **Grid View** | four-square grid | Rows of thumbnails; a click fires the slide instantly. Thumbnails show exactly what goes to screen | `Slides by Group`; `Thumbnail Background Color` |
| **Table View** | four horizontal lines | One column: thumbnail plus the slide's text to its side, **plus Slide Notes**. The Group Label sits at the top of each Group and the **Group colour runs down the leftmost edge** | Slides by Group; Thumbnail Background Color; **Table Background Color**; full text formatting (font, size, colour, style, alignment); **Truncate** — cut overflowing text from beginning, middle, or end |
| **Easy View** | large capital **T** | Hybrid: grid thumbnails with the text **re-rendered for legibility**, without affecting output | Same formatting set as Table View but applied to the thumbnail; toggle **Media Actions** visible |

Three details that are design decisions, not incidentals:

1. **`Slides by Group`** converts the grid from a continuous wrap-around flow into one row per Group. It is a *view* option, not a data change. `[DOCUMENTED, High — E02]`
2. **Easy View has a peek gesture** — hold `~` while in Grid View to preview Easy View without switching. `[DOCUMENTED, High — E02]`
3. **Easy View is a documented confusion source.** The vendor writes a paragraph warning that if thumbnails suddenly show odd text or black where media should be, the operator is probably in Easy View. `[DOCUMENTED, High — E02]` A view mode that ships with a "you are probably lost" paragraph in its own manual is a discoverability signal.

**The controls themselves** `[DOCUMENTED, High — E01 + E02]`:

- The three view buttons sit in the **bottom right of the Slide View Area** (above the Media Bin when it is open).
- A **three-dot menu button** ("the circle with the three dots") exposes the per-view options above. Options are **dynamic — the set changes with the selected view**.
- A **slider** adjusts slide size in the Slide View Area. **This slider is documented in E01 only; E02 never mentions it.**
- The Media Bin has its **own** parallel cluster at its bottom edge: default global transition for media actions, a **filter** for the selected media playlist, a **grid/list toggle**, and a **size slider**. `[DOCUMENTED, High — E01]`

**The vendor has recently invested here.** Version **21.3 (2026-03-18)** added options for switching between slide views from the top **View menu**, with **custom key mappings for the different slide views**. `[DOCUMENTED, High — E41]` That is a 2026 change, five months before this report, and it means the view-mode control is a live design area in the market leader rather than a legacy affordance. This is the strongest external corroboration of the owner's flagged emphasis (§4.3).

### 3.5 Groups, Arrangements, hotkeys

- A **Group** is a label applied to a run of slides — set by right-clicking the first slide of the run, choosing `Group`, then an existing label or `Other` for a custom one. `[DOCUMENTED, High — E03]`
- An **Arrangement** is an ordering of those Groups. The stated purpose is to get multiple layouts of one song **without duplicating the presentation in the Library**. `[DOCUMENTED, High — E03]` Arrangements are chosen from the **Arrangements button in the Presentation Header**, whose dropdown shows `Master` by default; an alternative arrangement can also be selected by right-clicking the presentation in the Library or Playlist. `[DOCUMENTED, High — E03]`
- **Group tokens are colour-coded to match the group assignment on the slide — from version 7.3.** `[DOCUMENTED, High — E03]`
- **Group hotkeys**: Group Labels can carry an automatically-attached Hot Key, so an operator's hotkey scheme is set once per label rather than per song. **This is documented in a ProPresenter 6-era article and I could not verify it in current documentation.** `[DOCUMENTED for Pro6 / UNKNOWN for current — https://support.renewedvision.com/hc/en-us/articles/360011515094-Using-Group-Labels-to-organize-your-slides, surfaced via search 2026-08-28]` The owner's screenshots show orange letter chips (A, C, S, B, D, T) on group headers, which is consistent with the feature having survived — see §4.
- **Custom Key Mapping** (rebind any menu-bar command, with a conflict filter) arrived in **7.7**. `[DOCUMENTED, High — E29, E32]`
- **Cross-tool friction, documented by the vendor itself:** Planning Center "Sequence" maps onto ProPresenter arrangement order, and matching **fails** when SongSelect names a section `Chorus 1` while Planning Center names it `Chorus`. `[DOCUMENTED, High — https://support.renewedvision.com/hc/en-us/articles/360062444614-Converting-a-Planning-Center-Song-Sequence-Into-a-ProPresenter-Arrangement]` A naming-convention mismatch that silently breaks an automated import is a concrete, citable failure mode for a scripture/song pipeline.

### 3.6 Reflow editor

Reflow is a **mode**, not a panel — a peer of Show, Edit and Bible in the toolbar. `[DOCUMENTED, High — E01]` It presents a presentation's text as continuous prose and lets slide boundaries be moved within it `[DOCUMENTED, High — E10, E33]`:

- press **Return** before a word to move the line break;
- place the cursor after the last word and choose **`Insert Slide Break`** (or `Option+Return`) to split a slide;
- place the cursor at the start of the second slide and press **Delete** to merge it into the previous one;
- a **slider bottom-right** adjusts slide size for preview — the same size-slider idiom as the Slide View;
- **arrows on each slide** open per-slide options including transition and theme.

The vendor's framing is that Reflow edits "in real-time". `[DOCUMENTED — E01]` **Whether that means the live output updates while typing is not stated.** `[UNKNOWN]` For a product with a never-blank-output guarantee this distinction is load-bearing and cannot be resolved from documentation.

**Not documented:** how Groups behave across a Reflow split or merge — does the new slide inherit the group of its neighbour? E10 is silent. `[UNKNOWN]`

### 3.7 Bible module

Bible is also a **mode**, and it disappears entirely when House of Worship Integrations are off. `[DOCUMENTED, High — E01, E25]`

Documented UI `[DOCUMENTED, High — E18]`:

- **Translation is selected first**, from a menu on the left; a **`+` button** adds further translations for parallel display.
- **Three ways in**: a **Book menu** (book then chapter), a typed reference (abbreviations accepted — the vendor's example is a shortened book name plus numbers), or **keyword search** in a box on the right.
- **Slide-building options**: `Break on New Verse` (one verse per slide), `Show Verse Numbers`, and reference placement — on every slide, on the last slide only, or none.
- **Three destinations for the result**: `Save as Presentation` (a new Library document), `Copy to Current Presentation`, or `Save to Selected Playlist`.
- **`Previous Verse` / `Next Verse`** buttons for live adjustment.

**Observation:** the module does not force a library document. Scripture can be composed straight into the presentation the operator already has open, or straight into the running playlist. That is a three-way destination choice at the moment of creation — a distinct pattern from "search, then insert".

### 3.8 Media Bin and ProContent

The bottom drawer holds two things `[DOCUMENTED, High — E01, E21]`:

- **ProContent** — the vendor's online content store, rendered *inside* the Media Bin as horizontally-scrolling collection rows (a `New` collection at top, others below), with its own search field under the ProContent header, hover-to-preview on motion thumbnails, and a download dialog offering **resolution** (4K / HD / Triple Wide / Double Wide) and a **destination Media Bin playlist**. Collapsible, with a navigation dropdown when collapsed. Free and Premium tiers; ProContent Free is included with an active ProPresenter subscription. `[DOCUMENTED, High — E01, E21]`
- **Media Bin** — video, images, and live video inputs. Left column of playlists and **playlist folders**, plus a dedicated video-input playlist. Also collapsible with a collapsed-state navigation dropdown. Footer controls: default global transition for media actions, filter within the selected playlist, **grid/list toggle**, and a **size slider**. `[DOCUMENTED, High — E01]`

Media storage is a user choice: **`Manage Media Automatically`** copies imported files into ProPresenter's own store; with it off, ProPresenter references the original path and is exposed to it moving. **Media Search Paths** plus `Automatically Relink Missing Media Using Alternate Paths` handle recovery, and **`Clean Up Unlinked Media`** (from **version 19**) removes store files not referenced by any presentation, playlist, theme, prop, macro or mask. `[DOCUMENTED, High — E24]`

### 3.9 The right rail: preview, clear, transport, Show Controls

**Preview window** — shows what is live, with a **dropdown directly beneath it to switch which screen you are previewing**. `[DOCUMENTED, High — E01]`

**Clear controls, immediately right of the preview** `[DOCUMENTED, High — E01, E05]`:

- a **clear groups button** (clears the layers assigned to that group; by default **all** layers), configured by right-click → **`Configure Clear Groups`**;
- then **one clear button per layer**, and — the detail worth copying — **the clear buttons are stacked in the same order as the layers are stacked on screen.** The control's spatial arrangement *is* the mental model of the output.
- **Custom Clear Groups (7.7+)** let an operator define arbitrary layer subsets, each with its own **icon and colour tint**, appearing as distinct buttons in the clear area. Selectable elements include music/audio, sound effects, messages, props, announcements (with optional timeline control), presentation slides (with optional timeline control), presentation media, and video input. `[DOCUMENTED, High — E05]`

**Layer stack.** Two vendor sources give **different stacks**, and this is a real discrepancy:

| E01 (UI overview) — 7 layers, top→bottom | E16 (Output Layers) — 8 layers, top→bottom |
|---|---|
| Audio | **Mask** |
| Messages | Messages |
| Props | Props |
| Announcements | Announcements |
| Slide | Slide |
| Media | Media |
| Live Video | Video Input |
| — | **Screen Color** |

`[DOCUMENTED — conflicting, E01 vs E16]`. E01 lists **Audio** as a layer (it is a clearable *thing*, not a visual layer) and omits Mask and Screen Color. E16 is the layer-specific article and is the better source for compositing order; E01 is the better source for what the **clear buttons** show. **Note also: from 7.11 the background-colour layer moved above the media layer**, which changes whether a slide background colour hides media. `[DOCUMENTED, High — E16]` A documented mid-7.x change to compositing order is exactly the kind of thing a version-blind reading gets wrong.

**Transport controls, below the preview** `[DOCUMENTED, High — E01]`: playback of the slide and media layers, scrub, **−15s / +15s**, and a **go-to-end** button whose offset is right-click configurable to **−0, −10, −30, −60, −90 seconds**. The transport can be **toggled** to show playback for the **Announcement** and **Audio** layers instead. The screen dropdown indicator sits alongside.

**Show Controls, bottom-right corner** — the tray, with its documented roster `[DOCUMENTED, High — E01]`:

| Control | Function |
|---|---|
| **Audio Bin** | Trigger audio files, build audio playlists, configure playback |
| **Stage Screens** | Choose the stage layout per stage screen; generate a stage message |
| **Timers** | Set up, configure, start/stop/reset |
| **Messages** | Set up, configure, show/hide messages to audience screens |
| **Props** | Create, edit, show/hide props on audience screens |
| **Macros** | Create, edit, trigger grouped actions |

**Show Controls is a 7.5 construct.** Before 7.5, Props/Messages/Timers lived elsewhere in the window; 7.5 moved them to the bottom right, added Stage, and named the cluster "Show Controls". The icons are **user-reorderable** with Cmd/Ctrl-drag. `[DOCUMENTED, Med — E30, E31]`

### 3.10 Audience vs Stage screens

- **Audience** = congregation-facing. **Stage** = performer/producer-facing (the vendor also names them Confidence Monitors, Foldback, DSMs). `[DOCUMENTED, High — E06]`
- Configured via `Screens > Configure Screens` (Opt-Cmd-1 on Mac). A **`+`** next to each screen class offers connected displays, **virtual NDI**, **SDI** (with hardware), **Syphon** (Mac only), and **Placeholder**. `[DOCUMENTED, High — E06]`
- Four screen configuration types: **Single, Mirror, Grouped** (a grid of displays, e.g. a TV wall), **Edge Blend**. `[DOCUMENTED, High — E06]`
- The **toolbar Audience and Stage buttons toggle system screens on and off independently** — and **NDI/SDI screens are always on and cannot be toggled**. `[DOCUMENTED, High — E01]` So the toolbar indicator reflects only a *subset* of outputs. An operator reading "Audience off" from the toolbar is not being told the NDI feed is off, because it is not.

### 3.11 Looks, Themes, Templates, Props, Messages, Timers, Macros

These are the concepts practitioners most often conflate (§6, T3/T4), so each is stated separately with its source.

**Look** — a saved matrix of **layers × audience screens**: which layers are visible on which screen. Rows are layers, columns are configured audience screens. A saved configuration is a **Look Preset**; unlimited presets. Activated by selecting it and clicking **`Make Live`**, by a slide right-click action, from the **Screens** menu, or from a Macro. A Look's Presentation-layer dropdown can also select an **alternate theme** for that screen. `[DOCUMENTED, High — E07]` Look preset reordering and right-click actions arrived in **7.5**. `[DOCUMENTED, Med — E31]` **Look Transitions** are a separate documented feature. `[DOCUMENTED, Low — E35 index entry only, article not read]`

**Theme** — a reusable style bundle: text formatting, shapes and media, applied to individual slides, whole presentations, or **whole libraries**. `[DOCUMENTED, High — E12]` Applied by selecting slides, right-clicking, hovering `Theme`, choosing. `[DOCUMENTED, High — E11]` Reached from the **`Theme` toolbar button** or **`Theme Editor` under `More`**. `[DOCUMENTED, High — E11]` The Theme Editor's own anatomy: **Slide Navigator** (left), **Canvas** (centre), **Inspector** (right, contextual), **Object List** (Z-order), and a **Theme Selector** in the toolbar. `[DOCUMENTED, High — E12]` **From 7.11, Media Actions can be added to Themes.** `[DOCUMENTED, High — E12]`

**Theme vs Template.** The vendor's own toolbar copy says the Theme button "allows you to apply templates and styles". `[DOCUMENTED — E01]` Neither theme article defines the difference. `[UNKNOWN]` Third-party trainers describe a theme as a **container of template slides**, and concede on record that the terminology confuses. See §6, T4. **Do not state a Theme/Template distinction in the PRD as fact; it is not vendor-defined.**

**Props** — overlay content ("bugs" in a corner, but anything slide-composable, anywhere on screen). Created and triggered from Show Controls; a **Props Editor** lives under `More`. **From 7.5, Props and Messages became separate layers**, so different screens can receive different ones. `[DOCUMENTED, High — E01, E16, E31; Med for the props-editor detail]`

**Messages** — text or timers pushed to output, configured and shown/hidden from Show Controls. `[DOCUMENTED, High — E01, E16]` **Stage Messages** are the stage-only variant, fired from the toolbar/Stage Screens. `[DOCUMENTED, High — E20, E33]`

**Timers** — three formats: **Countdown** (HH:MM:SS), **Countdown to Time** (to a wall-clock time, AM/PM or 24h), **Elapsed Time** (stopwatch, optional end point). Reached from the **Timers** button in Show Controls, the View menu, or Ctrl-C (Mac) / Ctrl-Shift-C (Windows). Each timer has a name field, duration field, a **reset** (circular arrow), a **start/stop toggle**, a collapse arrow, and a running-time readout; the **clock icon beside the name** switches format. **Overrun** lets a countdown run past zero into negative numbers, and can drive a colour change when enabled in the Theme. `[DOCUMENTED, High — E13]`

On **stage screens**, timers are **Linked Text** — text boxes bound to timer data, not standalone widgets — with prebuilt objects in the Stage Editor for Countdown/Countdown-to-Time, Elapsed Time, **System Clock**, and **Video Countdown** (active only during video playback). **Color Triggers** change the timer colour progressively at defined thresholds; with overrun enabled the final colour persists through the overrun. `[DOCUMENTED, High — E14]`

On **audience screens** a countdown is **not a first-class object**. It is composed: a **Timer**, plus a **Theme** carrying a styled text box, plus a **Message** with a **token** binding the two, fired from `Show Controls > Messages` — or started from a playlist **Header** or a **Slide Action**. `[DOCUMENTED, High — E15]` **This is a three-object composition to put a countdown on the main screen**, and it is worth flagging to Uma as a concrete complexity data point, not a criticism.

**Macros** — grouped actions triggered as one. Created from the **`[M]` icon** in Show Controls via a `+`; actions added by right-click or by dragging from the **Action Palette** onto the macro icon. Macros organise into **collections** and render in **Grid View (large icons) or Table View (vertical list)** — the same grid/table idiom as the slide area. Triggered by clicking, by a slide action, or **by index** from a communication device (index is relative to the currently selected collection). `[DOCUMENTED, High — E19]` A **Stream Deck plugin** is documented separately. `[DOCUMENTED, Low — E35 index entry only]`

**Audio Bin** — first item in Show Controls: trigger audio files, build audio playlists, configure playback. `[DOCUMENTED, High — E01]` **MultiTracks** is a separate integration (**7.8+**) that appears as a **third source in the search button**, imports lyrics with a configurable 1–4 lines per slide, brings **chords to the Stage Display** via a `MultiTracks Chords + Lyrics` layout (needs a ChartPro subscription with the ProPresenter add-on), and carries automation data for MIDI-triggered advance from the MultiTracks Playback app. `[DOCUMENTED, High — E17]` **Whether MultiTracks audio lands in the Audio Bin is not documented.** `[UNKNOWN — E17]`

### 3.12 Stage Display

The **Stage Editor** is reached from `Screens > Edit Layouts` or **Cmd/Ctrl+4**. `[DOCUMENTED, High — E20]` Placeable elements `[DOCUMENTED, High — E20]`:

- current / next **slide text**; slide **preview images**; **slide notes** authored in Edit mode; a **screen preview** mirroring any audience or stage screen;
- **chord charts**; **Stage Display Message**; **Planning Center Live timer**; custom clocks and timers; **system clock**; **video countdown**;
- **group colour and group name objects** — i.e. the group colour coding is exposed to the platform, not just the operator;
- **capture status** (streaming/recording indicator);
- shapes and text boxes for structure and labelling, with text linkable to dynamic sources (slide counts, playlist information, operator notes).

Multiple **Stage Layouts** are created with a **`+`** beside the Stage Layouts heading, starting from prebuilt templates or blank, and assigned to a stage screen with the **`Show`** button bottom-right of the editor, or by a slide action (`Add Action > Stage`) that sets layouts per screen. `[DOCUMENTED, High — E20]` The **Stage Screens** item in Show Controls is where an operator picks the live layout per stage screen during a service. `[DOCUMENTED, High — E01]`

Per a third-party first-hand reviewer of the 7.0 beta, the Stage editor reached feature parity with the main slide editor in 7, enabling advanced layouts including multiviewers of other outputs. `[REPORTED, Med — E34, published 2020-01-22]`

### 3.13 The remote surfaces

Two distinct remote control surfaces exist, with different reduction strategies — relevant because SelahCue ships a Flutter controller.

- **ProPresenter Control** — browser-based, same LAN. **16 fixed sections on one page; as of 7.9.1 not customisable, resizable or removable.** The library/playlist section is **view only** — an operator can see contents and what is active but cannot select from it. Can switch Looks, trigger macros and props, drive audio transport, manage timers and messages, control announcement/presentation media playback, toggle graphics outputs and stage layouts, push stage text, and read capture status. `[DOCUMENTED, High — E28]`
- **ProPresenter Remote** (native iOS/Android/Apple-silicon Mac app) — a **customisable bottom tab bar** (Presentation, Timers, Messages, Props, Remote, More; editable via `Edit` in More), an **eraser icon** for Clear Options spanning audio/messages/props/announcements/slides/media/live video/groups, and a **three-dot menu carrying Grid/List switch, `Follow Presentation`, and a slide-size control**. The Presentation tab offers **Library view or Playlist view**. `[DOCUMENTED, High — E23]`

**Note the pattern:** the *older* web surface is fixed and read-only over the library; the *newer* native app is customisable and can drive the library — **and it carries the same three-dot / grid-list / slide-size cluster as the desktop slide view.** The view-density idiom is replicated across surfaces. `[DOCUMENTED — E23 vs E01]`

**Neither article documents any role or permission model.** `[UNKNOWN — E23, E28]` This corroborates `COMPETITOR-MATRIX.md`'s inference that ProPresenter has no native RBAC, and it is still an inference.

---
## 4. Owner-screenshot findings

### 4.1 Provenance and its limits — read this before using §4

**I have not seen the screenshots.** The owner supplied two ProPresenter screenshots which were relayed to me as a written description in the commissioning brief. Everything in §4 is therefore:

- `OBSERVED` **by the owner**, and
- `REPORTED` **to me**, second-hand, in prose.

I have treated it as **primary evidence of the owner's reference UI** — which is what it is, and what makes it valuable — but **not** as evidence I verified. Where a described element matches vendor documentation I say so and cite it; that corroboration is the load-bearing part. Where it does not match anything documented, I say that too. **Nobody downstream should cite §4 as an observation of ProPresenter; cite it as an observation of what the owner is pointing at.** Registered as **E38**.

### 4.2 What the screenshots corroborate in the vendor documentation

This is the useful half: the description independently confirms a large amount of §3 from a live 2026 build, which documentation alone cannot do.

| Described in Screenshot A/B | Vendor documentation | Verdict |
|---|---|---|
| Toolbar order: Search, Text, Theme \| Show, Edit, Reflow, Bible, More \| ProContent, Media, **Default**, Live \| Audience, Stage \| Notifications, Status | E01's toolbar order exactly, including the mode cluster and the trailing Notifications/Status pair | **Match.** The owner read "Default" as a toolbar item; per E01 that slot is the **Looks** button, which displays the **active Look preset name** — and `Default` is a Look preset name, not a control label. `[INFERRED, High]` |
| Audience = **red hollow ring** (off); Stage = **solid green dot** (on); toggled independently | E01: Audience/Stage buttons toggle system screens on/off independently | **Match**, and it adds the state encoding (colour + fill) that E01 does not describe |
| Left column: LIBRARY tree above a PLAYLIST tree | E01: outline view (libraries and playlists) over detail view | **Match** |
| Each playlist row shows its **source library** | Not documented in E01/E08 | **New.** Consistent with cross-library playlists (E08) — the row has to disambiguate |
| **Filter box pinned at the bottom** of the playlist detail | E01 documents a filter at the bottom of the **Media Bin**; not for playlists | **Partial.** The filter-at-the-footer idiom is documented for one pane and observed in another |
| Coloured section headers grouping 11 items into PreShow / Music / Presentation | E09: playlist templates contain **Headers**, Placeholders, Presentations | **Match.** Screenshot A shows Headers in use; the full-width blue **Music** divider bar with a gear icon in the main scroll is the same Header rendered inline |
| MEDIA section with ProContent cloud browser: **New, Motion Graphics, Cinematic, Free, The Chosen** | E21 names exactly these collections | **Exact match**, including collection names |
| Per-presentation header bar with total duration, auto-advance badge, arrangement control, split/columns, loop, next-advance chevron | E01/E03: Presentation Header carries arrangements; E01 mentions transitions, arrangements, operator notes, timelines | **Partial.** The header exists and carries arrangements; the specific icon roster (copy/paste styling, split/columns, loop, auto-advance badge) is **not documented anywhere I could reach** |
| Group footers coloured (Verse blue, Chorus red, Bridge purple, Tag red) with only the **first** slide of a group carrying the group **name** | E03: group tokens colour-matched from **7.3**. E02: in **Table View** the Group Label sits at the top of each group with colour down the left edge | **Match on the colour system**; the "name on first slide only, colour on continuations" rule is **not documented** but is the natural Grid-View analogue |
| **Orange letter chips** A, C, S, B, D, T top-left of each group | Group Labels can carry an auto-attached **Hot Key** — documented in a **ProPresenter 6-era** article only | **Consistent**, and it is the best evidence I have that group hotkeys survived into the current build. Still `INFERRED, Med` — I could not find current documentation |
| Slide 1 of each song is a **"Blank"** slide showing background media filename + duration; lyric slides on a transparency checkerboard | Not documented | **New.** The checkerboard implies the slide layer is composited over media, matching the E16 layer stack |
| Right rail: preview with vertical audio meter, close X, **"Screen 1" selector**, small tab row, transport (−15s, play, +15s, skip, notes) with elapsed/remaining, tab bar (music, props, timers, messages/links, layers, [M] macros), AUDIO section with Playlist bin / "0 ITEMS" / Import Audio drop target, footer shuffle + Filter + size slider | E01: preview + **screen dropdown beneath it**; transport with −15/+15/go-to-end; Show Controls = Audio Bin, Stage Screens, Timers, Messages, Props, Macros | **Strong match.** The "Screen 1" selector is E01's screen dropdown. The `[M]` chip is E19's macro icon. The described tab set has **six** items matching the six Show Controls |
| Countdown item rendering a live timer over a background video, with **warning-triangle and clock status badges**, footer "1 Group \| Pre-Service 5:00" | E15: an audience countdown is Timer + Theme + Message; E13: overrun can drive colour | **Consistent.** The status badges are **not documented**; a warning triangle on a countdown cue is a state indicator I found no article for |
| Screenshot B right rail: composited live/preview render — lyric text over the winter-forest video, WYSIWYG against the theme; scrubber `00:30;25` elapsed / `00:29;04` remaining | E01: the preview window shows what is playing live | **Match.** The drop-frame timecode punctuation (`;`) is a broadcast convention |

**Two independent corroborations worth calling out**, because they are the kind that documentation cannot give:

1. **The right rail carries a vertical audio meter down the left edge of the preview.** No vendor article I read mentions an audio meter in the preview. If SelahCue's operator console is being measured against this reference, that meter is part of it and is undocumented — it must come from the screenshot, not from the KB.
2. **The clear controls.** E01 says the clear buttons sit immediately right of the preview, stacked in layer order. The owner's description of the right rail does **not** mention them. That is a gap in the description, not evidence they are absent — but Uma should not conclude from §4 alone that the reference UI lacks per-layer clears, because §3.9 documents them as present and §6 records them as the single best-loved control in the product.

### 4.3 FLAGGED FINDING — the view-density and thumbnail-size cluster

**The owner drew an orange arrow at the view-density cluster and thumbnail-size slider at the bottom-right of the slide grid in Screenshot B. This is the one element the owner marked by hand, and it is treated here as the highest-priority signal in §4.**

What the evidence says about that exact cluster:

1. **It is real, it is where the owner points, and it is documented.** The three view-mode buttons sit in the **bottom right of the Slide View Area**, alongside a **three-dot menu** whose options change with the selected view, and a **slider** that scales the slides in the Slide View Area. `[DOCUMENTED, High — E01, read verbatim]`
2. **The three modes are Grid, Table and Easy View** — with the naming discrepancy in §3.4 unresolved between two current vendor pages. `[DOCUMENTED — conflicting, E01 vs E02]`
3. **It is a *density and legibility* control, not a formatting control.** Everything it changes — thumbnail size, `Slides by Group` row segmentation, text overlay font/size/colour, `Truncate` from beginning/middle/end, `Thumbnail Background Color`, `Table Background Color` — is explicitly documented as **not affecting output**. `[DOCUMENTED, High — E02]` The whole cluster exists to serve the **operator's eyes in a dark booth**, not the audience's.
4. **A named third party identifies exactly that motivation.** A first-hand reviewer of Pro7 praises the text-forward slide view for techs with aging eyes, alongside dark mode for booth glare. `[REPORTED, Med — Paul Clifford, https://churchtechtoday.com/propresenter-7-review/, published 2020-01-22, accessed 2026-08-28]`
5. **The vendor is still actively investing in it — five months ago.** Version **21.3 (2026-03-18)** added slide-view switching from the top **View menu** with **custom key mappings for the different slide views**. `[DOCUMENTED, High — https://www.renewedvision.com/propresenter/download, accessed 2026-08-28]` So the market leader recently promoted view switching from a corner-button-only affordance to a menu command with bindable hotkeys. **That is a strong signal that operators switch views often enough to want a keystroke for it.**
6. **The idiom is replicated on the mobile remote.** ProPresenter Remote's three-dot menu carries **Grid/List switching and a slide-size control**. `[DOCUMENTED, High — E23]` The density control is not desktop-only in the reference product.
7. **And it is replicated a third time within the desktop window.** The Media Bin footer has its own **grid/list toggle and size slider**. `[DOCUMENTED, High — E01]` Macro collections likewise render in **Grid View or Table View**. `[DOCUMENTED, High — E19]` **The same three-part idiom — mode toggle, options menu, size slider — appears in at least four places in ProPresenter.** It is a house pattern, not a one-off.

**What I could not establish about this cluster** (carried to §10):

- Whether the view mode is **scoped** per presentation, per playlist, or globally. Neither E01 nor E02 says. `[UNKNOWN]` This is a genuine design decision Uma will have to make and cannot copy.
- Whether the **size slider persists** across sessions or resets. `[UNKNOWN]`
- Whether the slider is continuous or stepped, and its range. `[UNKNOWN]`
- Whether `Slides by Group` is a per-view setting or shared across views. E02 lists it under both Grid and Table, which is ambiguous. `[UNKNOWN]`

**Separation of observation and interpretation:** the observation is that a small, persistent, four-way-replicated density cluster exists in the market leader, is documented as output-neutral, and received new vendor investment in March 2026. **What SelahCue should do about that is Priya's call, not mine.** A non-committal framing is offered in §9.

---

## 5. Version caveats

**This is the section most likely to prevent a wrong decision, and it contains a fact that invalidates framing used elsewhere in this repo.**

### 5.1 "ProPresenter 7" is no longer the current product name

Renewed Vision **abandoned the `7.x` numbering**. The last `7.x` release listed on the vendor's own download page is **7.16.3**; the sequence then jumps to bare major versions: **17, 17.1, 18, 18.1–18.4, 19, 19.0.1, 20, 20.0.1, 21**, and the current release is **21.4 / 21.4.2, dated 2026-07-01**. `[DOCUMENTED, High — https://www.renewedvision.com/propresenter/download, accessed 2026-08-28]`

Consequences, all of which bite:

- **The repo's existing research is framed on "ProPresenter 7".** `COMPETITOR-MATRIX.md` (2026-07-23) and `LIBRARY-ORGANISATION-RESEARCH.md` (2026-08-15) both use "ProPresenter 7" as the current product. That framing is **stale by four major versions**. Their *findings* may still hold; their *version labels* do not. See §8.
- **The vendor's own KB is inconsistent with itself.** Articles are still titled "…in ProPresenter 7" and describe current behaviour, while other articles in the same section say "version 19+" (`Clean Up Unlinked Media`, E24) and "a minimum of ProPresenter version 20" (Remote app, E23). **Both numbering schemes are live in the same knowledge base on the same day.** `[DOCUMENTED, High — E23, E24, E35]`
- **The vendor's blog is stale.** `renewedvision.com/tags/updates` stops at **7.10 (2022-08-09)**. `[DOCUMENTED — E36]` The product landing page publishes **no version number at all**. `[DOCUMENTED — E37]` The download page is the only reliable version source found.
- **`renewedvision.com/propresenter7/whats-new7/` now returns HTTP 404.** `[E39]` That URL is cited five times in `COMPETITOR-MATRIX.md`. Those five citations are no longer verifiable at source and should be re-sourced before the PRD leans on them.

**Recommended house rule for the PRD:** write "ProPresenter (v21.4, 2026-07-01)" or "ProPresenter 7.x-era" — never bare "ProPresenter 7" — and re-verify anything version-labelled before it becomes an acceptance criterion.

### 5.2 ProPresenter 6 → 7: what actually changed, and what to never carry over

Per a first-hand beta reviewer, published **2020-01-22** `[REPORTED, Med — E34]`, and corroborated by vendor docs where noted:

| Concept | Pro6 | Pro7 |
|---|---|---|
| **Looks** | Did not exist | New in 7. A saved layers×screens matrix; enabled per-output lower-thirds, previously a third-party job `[E34, E07]` |
| **Screens / outputs** | Edge blending and SDI were **separately paid modules** | Folded into the base product; any output type to any connection `[E34]`, and `COMPETITOR-MATRIX.md` records the same |
| **Themes per output** | n/a | A Look's Presentation layer can select an **alternate theme**, so one screen gets decorative lyrics and another plain text `[E34, E07]` |
| **Library ↔ Playlist** | Sharing documents between libraries and playlists was awkward | A presentation from **any** library can be added to **any** playlist `[E34, E08]` |
| **Stage editor** | Limited | Reached parity with the slide editor; multiviewers of other outputs possible `[E34, E20]` |

**Anything sourced to a `learn.renewedvision.com/propresenter6/…` URL, or to an article banner-marked as legacy Pro6, must not be stated as current.** The prior in-repo library research is explicit that its ProPresenter detail is **disproportionately version 6** because only the Pro6 guide was archived. Two specific Pro6-era claims are load-bearing and unresolved:

- **Document Categories** — a single-select, self-pruning sort/filter field. All reachable documentation is Pro6-banner-marked. **Whether Categories exist in the current build is UNKNOWN.** `[prior research §6 open question 4; not resolved by this pass]`
- **Group hotkeys attached to Group Labels** — documented in a Pro6-era article; the owner's orange letter chips suggest survival. `[INFERRED, Med — §4.2]`

### 5.3 Within-7.x changes that a version-blind reading gets wrong

Every one of these is a documented behaviour change inside the 7 line. A claim about ProPresenter's UI without a version attached is, for these, roughly a coin flip.

| Version | Change | Source |
|---|---|---|
| **7.3** | Group tokens became **colour-matched to the group assignment** on the slide | E03 |
| **7.5** | **Show Controls created**: Props/Messages/Timers moved to the bottom-right, **Stage added**; icons made reorderable | E30, E31 |
| **7.5** | **Props and Messages split into separate layers**, so screens can receive one without the other | E31, E16 |
| **7.5** | Looks presets gained right-click actions and reordering; slide labels became right-click editable | E31 |
| **7.7** | **Custom Clear Groups** — arbitrary layer subsets with their own icon and colour tint | E05, E32 |
| **7.7** | **Custom Key Mapping** — rebind any menu-bar command, with a conflict filter | E29, E32 |
| **7.7** | Library search gained a **text/thumbnail preview** of results | E32 |
| **7.8** | **MultiTracks** added as a search source and to Quick Search | E17, E27 |
| **7.9.1** | ProPresenter Control's 16 sections documented as **not customisable** — a version-pinned limitation, may have changed since | E28 |
| **7.11** | **Media Actions addable to Themes** | E12 |
| **7.11** | **Background-colour layer moved above the media layer** — changes whether a slide background hides media | E16 |
| **19** | **`Clean Up Unlinked Media`** added | E24 |
| **20** | **Workspaces**; ProPresenter Remote updated | download page |
| **21** | New **PowerPoint importer**, HDR support, macOS Tahoe support | download page |
| **21.2 (2026-02-03)** | **Native `.pptx` import** with editable text, objects, media, notes, animations | download page |
| **21.3 (2026-03-18)** | **Slide-view switching from the View menu, with custom key mappings per view** | download page |
| **21.4 / 21.4.2 (2026-07-01)** | Current release; stability, Planning Center custom sequences | download page |

**Register addendum.** Two sources used heavily above and not in the §2 table:

| ID | Source | URL | Read | What it evidences |
|---|---|---|---|---|
| **E41** | RV — ProPresenter download / release notes | https://www.renewedvision.com/propresenter/download | WebFetch ×2 | The authoritative version list: 7.16.3 → 17 → 18 → 19 → 20 → 21 → **21.4.2 (2026-07-01)**; the 21.2 importer and the **21.3 slide-view / key-mapping change** |
| **E42** | RV KB — Using Group Labels to organize your slides | https://support.renewedvision.com/hc/en-us/articles/360011515094-Using-Group-Labels-to-organize-your-slides | WebSearch result body | Group Labels carrying auto-attached Hot Keys. **ProPresenter 6-era article** |

---
## 6. Practitioner sentiment

### 6.1 How this evidence was gathered, and its one structural flaw

Community and review-site evidence was gathered in a parallel research pass over Capterra, SoftwareAdvice, Churchfront, ChurchTechToday, Church Visuals, WorshipMetrics, Ruah Creative House, MxU, and the vendor's own KB. I independently verified the version-numbering claims (§5.1) against the vendor download page myself; the sentiment claims below stand on the cited URLs.

**The flaw, stated up front: Capterra and SoftwareAdvice share a review pool.** Both report the identical figures — **4.6/5 overall, 4.3/5 ease of use, across 2,086 reviews** `[REPORTED — https://www.softwareadvice.com/church/propresenter-profile/ ; https://www.capterra.com/p/170172/ProPresenter/reviews/ — 2026-08-28]`. **They are not two independent sources.** Where a theme below rests only on those two, discount it accordingly. The genuinely independent voices are Churchfront, ChurchTechToday (Paul Clifford), Church Visuals (Carl Barnhill, Steve Dirks), WorshipMetrics, Ruah Creative House, MxU, and Renewed Vision's own documentation.

**Reddit was completely inaccessible.** `old.reddit.com` and `www.reddit.com` both refused automated fetches, and `reddit.com` is on the search API's blocked-domain list. **No Reddit evidence is in this report.** The brief asked for r/churchtech and ProPresenter forums specifically; that request is **not satisfied**, and it is the largest gap in §6. G2 and TrustRadius both returned HTTP 403. The ProPresenter Users Facebook group is login-walled and was not entered. **Renewed Vision operates no public peer forum** — only a Zendesk KB plus chat and phone `[DOCUMENTED — https://support.renewedvision.com/hc/en-us]` — which is itself a finding: it pushes all peer discussion onto exactly the two platforms I could not read.

### 6.2 Theme summary

| # | Theme | Direction | Independent sources | Strength |
|---|---|---|---|---|
| T1 | **Two-tier curve**: easy to *operate*, hard to *configure and author* | Both | 5 (allowing for the Capterra/SoftwareAdvice overlap) | **Strong** |
| T2 | **Screen Configuration** is where volunteers get lost, and it is still live in 2025 reviews | Pain | 4 | **Strong** |
| T3 | **Looks** are powerful and the most-missed concept | Pain | 3 | Moderate–strong |
| T4 | **Terminology is opaque** — Themes vs Templates vs Looks especially | Pain | 4 | **Strong** |
| T5 | **Clutter and discoverability**; no in-app tutorial; YouTube is the manual | Pain | 3 | **Strong** |
| T6 | The **slide editor** is clunky; import friction | Pain | 3 | Moderate; **partly obsolete**, see below |
| T7 | **Performance / Windows parity** | Pain | 3 | Strong on volume, **dated on severity** |
| T8 | **Pro6→Pro7** relearn and fidelity loss | Pain | 3 | Moderate; **historical** |
| T9 | **Praise**: the clear-layer buttons, layer ordering, dark mode, three-column layout, Reflow, Macros | Praise | 3 | Moderate |
| T10 | Library/Playlist and Groups/Arrangements are learnable but need teaching | Pain (mild) | 3 | **Weak–moderate — inferred from teaching artefacts** |
| T11 | Training time: **contradictory**; the contradiction is the finding | Pain | 2 + 1 contradicting | **See §6.4** |
| T12 | Update cadence collides with the Sunday deadline | Pain | 2 | Moderate |

### 6.3 The findings that matter for a UI PRD

**T1 — The two-tier curve resolves an apparent contradiction, and it is the frame everything else fits into.** Running a *prepared* show is easy; setting up, authoring, and *recovering when something breaks* is not. Aggregated editorial describes a product that is fast to pick up for basic use with real depth underneath `[REPORTED — capterra.com/p/170172/ProPresenter/reviews/]`; a reviewer puts it as intuitive to operate with a large curve for editing and setup `[ANECDOTAL — same]`; a comparison blog recommends it for churches with a dedicated media team and warns it can overwhelm volunteer-only teams `[REPORTED — https://ruahcreativehouse.org/blog/church-presentation-software/, dated 2026-04-06]`. **These are two different UI surfaces with two different audiences.**

**T2 — Screen Configuration is the single most-cited volunteer failure point, and it has not aged out.** Churchfront names it as where volunteers get lost, citing simultaneous LED, projector, monitor and livestream outputs `[REPORTED — https://churchfront.com/2026/01/13/propresenter-deep-dive-for-church-volunteers/, dated 2026-01-13]`. The vendor maintains dedicated KB articles for the two most basic failure modes — a blank computer screen on launch, and "how do I get my output to show" `[DOCUMENTED — support.renewedvision.com/hc/en-us/articles/360011694254 and /360011694234]`. Individual reports of screen configuration drifting between weeks span **2019 to December 2025** `[ANECDOTAL — capterra.com/p/170172/ProPresenter/reviews/?page=2, ?page=4, ?page=5]`. **Read against §3.10: the toolbar's Audience/Stage indicators only reflect *system* screens, because NDI/SDI screens cannot be toggled. An operator's at-a-glance output state is partial by design.**

**T3 — Looks are the concept volunteers most reliably miss, and the failure has a signature.** Churchfront's framing is that most volunteers miss that Looks govern which **layers** each output may show, not merely whether a screen is on `[REPORTED — https://churchfront.com/2025/12/09/propresenter-crash-course-for-churches/, dated 2025-12-09]`. The characteristic symptom is diagnostically specific and worth quoting into a PRD as a scenario: an operator asks why a background is missing on the LED wall, and the cause is a Look that disabled that layer for that screen `[REPORTED — churchfront.com/2026/01/13/... ]`. The same source praises Looks as the screen-configuration control centre — **so the concept is loved by trained operators and opaque to untrained ones**, which is T1 again at feature scale.

**T4 — The barrier is vocabulary, not pixels.** Editorial synthesis reports non-intuitive terminology confusing even technical users `[REPORTED — softwareadvice.com/church/propresenter-profile/]`. Most tellingly, **two ProPresenter trainers concede on record** that the terminology confuses and that themes and looks affect one another rather than being cleanly delineated `[REPORTED — Steve Dirks and Sheik Mozart, https://churchvisuals.com/podcast/propresenter-power-talks/using-theme-and-looks-in-propresenter/, undated, accessed 2026-08-28]`. **This corroborates §3.11 from the other direction: I could not find a vendor definition of Theme vs Template, and neither can the trainers.** A third-party content vendor supplies the missing model — a theme as a container of template slides `[REPORTED — https://www.churchmotiongraphics.com/free-propresenter-themes/]` — which is exactly the wrong place for a product's core concept to be defined. One reviewer also attributes the 6→7 difficulty specifically to features being reorganised **and renamed** `[ANECDOTAL — capterra.com/p/170172/ProPresenter/reviews?page=4]`.

**T5 — Discoverability, and the sharpest formulation of it.** Reviewers describe capabilities hidden under small buttons, an overwhelming interface, and an intimidating first impression `[ANECDOTAL — capterra.com/p/170172/ProPresenter/reviews/?page=5]`. The most precise version, worth carrying verbatim into design discussion: **every feature is documented; knowing *which* feature to reach for is trial and error** `[ANECDOTAL, Kevin K., Dec 2024 — capterra.com/p/170172/ProPresenter/reviews/?page=2]`. A recurring specific request is an **in-app tutorial**; YouTube is the de facto manual `[ANECDOTAL — capterra.com/p/170172/ProPresenter/reviews/ and /?page=3]`. Churchfront concedes the app carries many features a given church will never use which nonetheless add interface complexity `[REPORTED — churchfront.com/2026/01/13/...]`. **§3.1's House-of-Worship toggle is the vendor's own partial answer to this, and it operates on segment, not on skill level.**

**T6 — Editor complaints, with one now obsolete.** Cumbersome formatting, clunky design tools, no crop `[REPORTED/ANECDOTAL — softwareadvice.com/church/propresenter-profile/ ; capterra…/?page=5]`; themes needing manual reapplication per slide rather than cascading `[ANECDOTAL — capterra…/?page=2]`; PowerPoint import requiring transitions and animations to be stripped `[ANECDOTAL — capterra…/?page=4]`. **That last one has since been addressed**: version **21.2 (2026-02-03)** shipped a native `.pptx` importer producing editable presentations `[DOCUMENTED — https://www.renewedvision.com/propresenter/download]`. **A worked example of why §5 matters: a well-sourced complaint that is simply no longer true.**

**T7 / T8 / T12 — dated, historical, and operational respectively.** Performance complaints (crashes, high CPU, Windows lagging Mac, search slow at ~372 library documents) cluster in **2019** with milder echoes through 2025 — weight the pattern, discount the severity `[ANECDOTAL — capterra…/?page=3, ?page=4 ; comments on https://churchtechtoday.com/propresenter-7-review/, article by Paul Clifford, 2020-01-22]`. The 6→7 relearn is a 2020–2023 wound `[REPORTED/ANECDOTAL — churchtechtoday.com/propresenter-7-review/ ; capterra…/?page=4, ?page=5]`. Update cadence colliding with the weekend is operational rather than UI, but note the vendor's chat support is Monday–Friday `[DOCUMENTED — support.renewedvision.com/hc/en-us]` while the deadline is Sunday `[ANECDOTAL — capterra…/?page=2, ?page=3]`.

**T9 — What operators actually love. This is the most directly useful praise in the report.**

- **The per-layer clear buttons are the single best-loved control.** Clearing Slide leaves the background; clearing Media leaves the text `[REPORTED — churchfront.com/2025/12/09/...]`. §3.9 documents them stacked in screen-layer order, right beside the preview.
- **Enforced layer ordering is taught as the operator's core mental model.** Churchfront's framing is a fixed "layer cake" — the stack order is a property of the product, not something the operator arranges per slide, so a whole class of "my text went behind the background" error is structurally unavailable `[REPORTED — churchfront.com/2026/01/13/..., verified 2026-08-28]`. **I verified this page myself; note that the source teaches the fixed stack as a model to learn, and the "removes an error class" reading is mine, marked as interpretation.**
- The **three-column left-to-right layout** (library → slides → preview/controls), **dark mode** for booth glare, clear buttons that highlight when their layer is active, and a **text-forward slide view for techs with aging eyes** `[REPORTED — Paul Clifford, churchtechtoday.com/propresenter-7-review/, 2020-01-22]`. **That last one is direct third-party corroboration of §4.3's flagged cluster.**
- **Macros** praised for efficiency; **Reflow** praised as faster than slide-by-slide lyric editing; multi-view preview praised over toggling outputs individually `[REPORTED — churchfront.com/2026/01/13/...]`.
- Direct operator praise exists too, including a reviewer who says the interface is simple with everything needed, and another who finds volunteers not hard to teach `[ANECDOTAL — capterra…/?page=2]`.
- **"You can't customise hotkeys" is not a valid current complaint** — Custom Key Mapping has existed since **7.7** `[DOCUMENTED — E29]`.

**T10 — Library/Playlist and Groups/Arrangements.** Treat with care: this rests mostly on the **existence and emphasis of teaching material**, not on volumes of complaint. The KB stresses that *every* slide should be in a Group `[DOCUMENTED — E03]` — phrasing that implies users skip it. Direct complaints are thinner: playlist sorting not surfacing newest items first `[ANECDOTAL — capterra…/?page=3]`; playlist searching, duplicating, sharing and syncing described as confusing in editorial synthesis `[REPORTED — softwareadvice.com/church/propresenter-profile/]`; multi-user playlist collaboration needing manual merging with no fool-proof path `[ANECDOTAL — capterra…/?page=2]`. **`INFERRED` more than evidenced.**

**Notable near-silence: Props, Stage Display and Macros draw almost no direct operator complaints.** The likely reason is that volunteers never touch them. **Absence of complaint here is evidence of an avoided surface, not of good design.**

### 6.4 The training-time contradiction — the most PRD-actionable item in §6

The evidence splits hard, and the split is the finding:

- **"Minutes."** SoftwareAdvice reviewers say volunteers can be trained in a few minutes; one operator says teaching volunteers is not challenging `[ANECDOTAL — softwareadvice.com/church/propresenter-profile/reviews/ ; capterra…/?page=2]`.
- **"2–4 weeks."** A comparison blog puts ProPresenter proficiency at 2–4 weeks against EasyWorship's "one session" and calls ProPresenter the steepest curve it reviewed `[REPORTED — https://ruahcreativehouse.org/blog/church-presentation-software/, 2026-04-06]`. Other reviewers call volunteer onboarding complicated or difficult `[ANECDOTAL — capterra…/?page=5, ?page=2]`.

**Reading:** both describe different tasks. Advancing a prepared playlist is a minutes-long lesson; recovering from a disabled Look, drifted screen config, or wrong arrangement is a weeks-long competence — T1 again.

**The corroborating structural evidence is stronger than either number.** A practitioner volunteer-training guide teaches, in order: comms → boot and launch → interface layout (preview, library, playlist, song window) → Quick Edit vs Edit Slide → Clear All → lyric timing → firing video → slide labels. **Looks, Screen Configuration, Themes, Props and Macros are absent from the volunteer curriculum entirely** `[REPORTED — Carl Barnhill, https://churchvisuals.com/article/propresenter-training-guide-for-volunteers/, undated, accessed 2026-08-28]`. **The industry's practical answer to ProPresenter's complexity is to not teach volunteers the hard concepts at all.** A generic church-tech onboarding ladder (not ProPresenter-specific) puts independence at roughly 8–10 services `[REPORTED — https://getmxu.com/blog/how-to-train-church-tech-volunteers]`.

**Do not put a single training-time number in the PRD.** The 2–4 week figure comes from **one** source's comparison table with no stated methodology. **No source gave a defensible measured onboarding time.** Cite the split, not a number.

---
## 7. Category-convention baseline across the comparators

### 7.1 Why this section exists, and one correction to the brief

The purpose is narrow: **to tell "ProPresenter-specific" apart from "category convention"**, so that nothing in §3 is copied for its novelty when it is in fact the genre's default, and nothing is dismissed as generic when it is actually ProPresenter's own choice. This is a **convention baseline, not seven teardowns.**

**Correction to the brief: "Presenter One" does not appear to exist.** The brief listed it as the seventh comparator. `presenterone.com`, `presenter.one`, `presenterone.app`, `presenterone.io` and `presenterone.org` all return NXDOMAIN, and independent searches — one run by the parallel research pass, one run by me directly — surfaced no such product, returning instead Presenter by WorshipTools, Sharefaith Presenter, Church Presenter, MediaShout and ProPresenter. `[DOCUMENTED (negative), High — DNS lookups; independent WebSearch 2026-08-28]`

**Substitute used: Presenter by WorshipTools** (`worshiptools.com/en-us/presenter`), the nearest real product literally named "Presenter". It is labelled as a substitute everywhere below. **Priya should confirm the intended product before any conclusion rests on slot 7.**

### 7.2 Evidence register — comparators

| ID | Product | Primary documentation | Version evidence |
|---|---|---|---|
| **C1** | Proclaim (Faithlife/Logos) | `support.proclaim.logos.com/hc/en-us/articles/` — Order Of Service Overview (19863521025293), Media Browser (19864260160013), Grid View (19863521019021), Quick Screens (20372616032397), Confidence Monitor (19864188689037), Keyboard Shortcuts (19863491758733), Presentation Basics (20475312648589) | "What's New in Proclaim 4" exists but is **sign-in walled**; version UNKNOWN |
| **C2** | EasyWorship 7 | `support.easyworship.com/support/solutions/articles/` — Quick Start Guide (24000020385), Shortcut Keys v7 (24000020383), Display Foldback (24000020394), Adding and Editing Songs (24000020402) | **7.4.1.9, released 2023-03-03** per the vendor download article; may be stale |
| **C3** | OpenLP 3.0 | `manual.openlp.org/` — glossary, library, service, menu_items, configure_ui, songs, stage_view, web_remote | **3.0 Reference Manual** |
| **C4** | FreeShow | `freeshow.app/docs/` — projects, drawer, show-type, views, output, stage, features | **1.6.5, published 2026-08-26**; runtime Chromium 138 |
| **C5** | VideoPsalm | `myvideopsalm.weebly.com/` — the-agenda, viewer-mode, the-slides, the-preview-area, the-keyboard-shortcuts, main-features | **No version number published.** Platform list (Windows XP–10) suggests dated help |
| **C6** | Quelea | `quelea-projection.github.io/docs/` — Layout, Showing_something_live, Shortcuts…, General_tab, Song_sequences, Stage_View, Stage_View_tab; `quelea.org/update/` | **2022.0** latest listed; currency in 2026 UNKNOWN |
| **C7** | **Presenter by WorshipTools** *(substitute for the non-existent "Presenter One")* | `worshiptools.com/en-us/docs/` — 14 (cue lists), 192 (media library), 182 (keyboard shortcuts), 185 (service features), 187 (stage display); `/en-us/presenter` | **No version number published** |

**Verification note, recorded honestly.** The comparator evidence was gathered in a parallel research pass. I attempted to independently re-verify the single most decision-relevant comparator claim — Proclaim's Grid-view density slider — and **`support.proclaim.logos.com` returned HTTP 403 to my fetch.** That matches `LIBRARY-ORGANISATION-RESEARCH.md`'s recorded experience with the same host. **So the Proclaim claims below are single-pass and I could not re-verify them.** I did independently verify the "Presenter One" negative, which is the other claim that most affects how this section is read.

### 7.3 What is category convention

Counts out of 7, with slot 7 = WorshipTools Presenter.

| Pattern | Count | Reading |
|---|---|---|
| **A reusable library kept separate from an ordered run sheet, each with its own name** | **7/7** | The single strongest convention in the category. Library/Service Manager (C3), Resource Area/Schedule (C2), Drawer/Project (C4), Database/Schedule–Order of Service (C6), Songbooks+Bibles/Agenda (C5), Media Browser+Reuse Items/Order of Service (C1), Media Library/Service (C7) — and Library/Playlist in ProPresenter. **The two-store model is not a ProPresenter idea.** |
| **Drag-and-drop reordering of the run sheet** | **7/7** | Universal. C5 documents drag plus arrow buttons |
| **A one-key "go dark" override on live output** | **7/7** | Blank Screen `.` (C3), Ctrl+B (C2), F6 (C6), Clear All (C4), `.`/`,` (C5), F10 Blank Quick Screen (C1), F12 (C7). ProPresenter's F1 Clear All is the same idea |
| **"Clear the text, keep the background" as a control distinct from full black** | **6/7 documented** | Ctrl+C (C2), Clear screen F7 (C6), No Text/Text F8 (C1), Ctrl+T (C5), clear-slide layer (C4), F10 (C7). C3's Blank to Theme is the functional equivalent `[INFERRED]`. **This is convention, and it is the same instinct as ProPresenter's per-layer clear buttons** |
| **A stage / confidence display** | **6/7** | Stage View (C3), Display Foldback (C2), Stage (C4), Stage View (C6), Confidence Monitor (C1), Stage Display (C7). **Only VideoPsalm has none documented** |
| **Stage display carries a clock and/or a next-item preview** | **5/7** | C3, C2, C1, C4, C7. C6 is the exception — clock yes, next-slide no, **chords instead** |
| **Labelled song sections (verse / chorus / bridge…) as a structural concept** | **6/7** | All but C7, whose grouping is service-level. **ProPresenter's Groups are convention, not differentiation** |
| **Some named view or mode switcher in the operator shell** | **5/7** | Show all/Setup/Live (C3), three view layouts (C2), Grid/Simple/List/Lyrics (C4), Full/Grid plus Edit/Preview modes (C1), Viewer/Edit (C5). C6 and C7 document none |

### 7.4 What is genuinely contested — roughly 3–4 of 7

**These are the real design decisions. A product that picks either side is not violating a convention, because there is no convention.**

| Pattern | Count | Who | Notes |
|---|---|---|---|
| **Two-stage preview → live with an explicit "Go Live"** | **3/7** | C3 (separate Preview and Live *slide controllers*; right-click `Go Live`), C6 (spacebar or the `Go Live` button), C2 (Preview/Live split; `Go Live` on Page Down) | **The biggest divergence in the set — and the newer products are on the other side.** C1, C4 and C7 are click-to-live with an output *mirror*, not a staging buffer; C5's preview area is a WYSIWYG mirror and layout surface. **ProPresenter is click-to-live: clicking a slide in Grid View "will send it to the screen instantly" (E02).** SelahCue's `selahcue-present` core invariant — staging never changes Live; only Go Live does — puts it with the 3/7 minority alongside OpenLP, Quelea and EasyWorship, and **against** ProPresenter |
| **Thumbnail grid as the primary slide surface** | **4/7** | C1 (Grid view), C4 (Grid view), C2, C7 | Text/verse **lists** are primary in C3, C6 and C5. **ProPresenter defaults to the grid** — so the owner's screenshots sit with the 4/7 majority, but it is a majority, not a rule |
| **An explicit density / thumbnail-size / zoom control** | **4/7** | C1 (slider beside the view icons on the control monitor, plus a separate Media Browser thumbnail slider), C2 (icon-view dropdown with a slider spanning thumbnails-to-list), C4 (zoom controls bottom-centre; Ctrl/Cmd+scroll over the slide panel), C6 (a **Thumbnail size** setting, plus "Only preview one line per song section" and a database-song-preview mode choice) | **This is the direct comparator evidence for the owner's flagged finding (§4.3).** More than half the category ships some density control, and two of them — C1 and C2 — pair it with the view toggle in exactly ProPresenter's arrangement. **But it is 4/7, not 7/7: it is a strong pattern, not a category requirement.** C1's is single-pass evidence I could not re-verify (§7.2) |
| **Hotkeys that jump to a labelled section or slide number** | **4/7** | C1 (**auto-generated** — C for chorus, B for bridge, first letter/number for verses, 1–9 elsewhere, shown bottom-right of the slide while on air), C2 (`V+Enter`, `C+Enter`, `#+Enter`, `V+#+Enter`), C6 (1–9 plus C/B/P/T), C5 (1–9, 0, plus B/C/I/O/P/N/S/T/U/V) | **Directly relevant to the owner's orange letter chips (§4.2).** Proclaim's model is the closest analogue: hotkeys **generated automatically from section labels and displayed on the slide**, which is what an orange `C` chip on a Chorus group looks like. ProPresenter's equivalent is documented only in a Pro6-era article (§3.5) |
| **A first-class, reorderable song arrangement object** | **3/7** | C3 (**Verse Order** — a space-separated string like `V1 C1 V2 C1 V3 C1`; blank means imported order; invalid refs error), C6 (**Song sequences**, since 2020.0 — a two-pane dialog, available sections left, ordered sequence right), C4 (arrangements built from groups) | C2 has section **labels** but no arrangement object — the documented workaround is copy/paste of blocks, and that guidance comes from **support discussion threads, not the manual**, so treat it as unverified. C1's "Custom Slide Order For Songs" article could not be opened. **ProPresenter's Arrangements are on the strong side of a contested feature, and its stated rationale — multiple layouts without duplicating the Library document — is the sharpest articulation of the purpose in the set (E03)** |
| **A dedicated logo-screen control** | **3/7** | C2 (Ctrl+L), C6 (F5, with fade), C1 (F11) | **Not universal.** C3, C4 and C7 have no logo command |

### 7.5 What is a minority pattern — 1–2 of 7

Ideas that exist but that nobody should call an expectation.

- **Time-driven auto-advancing service sections** — Proclaim only. Four fixed sections (Pre-Service Loop, Warm-Up, Service, Post-Service Loop) keyed to a **service start time**, with only the Service section requiring manual advance by default. `[C1]` **Nothing else in the category does this, ProPresenter included.** Note the resemblance to the owner's Screenshot A section headers (PreShow / Music / Presentation) — but ProPresenter's Headers are **inert labels**, not time-driven phases (E09).
- **A sidebar of ad-hoc "Quick Screens"** separate from the run sheet — Proclaim only. Blank, Logo, No Text, Last Shown, On-Screen Bible, two Custom, plus animated overlays, each toggled in settings. `[C1]`
- **Per-layer clearing (background / slide / overlay / audio independently)** — FreeShow and WorshipTools Presenter, 2/7. `[C4, C7]` **ProPresenter is the third, and its version is the most developed: per-layer clear buttons stacked in composite order, plus user-defined Custom Clear Groups since 7.7 (§3.9).** This is one of the few places where ProPresenter is genuinely ahead of the category rather than merely bigger — and §6 T9 records it as the best-loved control in the product. **Convention analysis and sentiment analysis agree here, which is rare.**
- **Per-output lock** — FreeShow only, with colour-coded status dots per output preview (green active, red inactive, blue NDI, grey disconnected, yellow locked). `[C4]` **Compare the owner's Screenshot A: a red hollow ring for Audience off and a solid green dot for Stage on. Colour-coded per-output state indicators appear in exactly two products in this set.**
- **Chords on the stage display** — Quelea and FreeShow, 2/7. `[C6, C4]` ProPresenter is a third via MultiTracks (§3.11), but gated behind a ChartPro subscription.
- **Stage view customised by editing HTML/CSS/JS files** — OpenLP only (drop a `stages/<name>/` folder and it is served at `/stage/<name>`). `[C3]` **Template-driven** stage layouts are a separate 3/7 pattern (C1, C4, C7) — and ProPresenter's Stage Editor is the most capable version of it (§3.12).
- **A "freeze" / "shield" that decouples operator browsing from audience output** — VideoPsalm only. `[C5]` A genuinely distinctive idea: freeze the display so the operator can search ahead while the congregation still sees the current slide.
- **Dockable, floatable, tabbable panel workspace with a lock** — OpenLP only. `[C3]` **The opposite pole from ProPresenter, whose toolbar layout is fixed by design (E01).**
- **Per-item auto-advance** — Proclaim and WorshipTools Presenter, 2/7 `[C1, C7]`, with FreeShow's slide timers adjacent. **The owner's Screenshot A shows a 5.0s auto-advance badge on the Announcements presentation**, so ProPresenter is a third.

### 7.6 The three findings this section produces

1. **The library/run-sheet split is universal (7/7) and so is the go-dark key.** Neither is evidence of anything when found in ProPresenter. A PRD that presents either as learned-from-ProPresenter is mis-attributing.
2. **Preview→Live is contested 3/7 and ProPresenter is on the click-to-live side, opposite SelahCue's existing core invariant.** `selahcue-present`'s documented invariant — staging never changes Live; only Go Live does — aligns SelahCue with OpenLP, Quelea and EasyWorship and **against** the reference product the owner is pointing at. **This is a genuine, load-bearing tension between the owner's reference UI and SelahCue's existing architecture, and it is Priya's to resolve, not mine.**
3. **The density/view-mode cluster is a strong-but-not-universal pattern (4/7), and two products arrange it exactly as ProPresenter does** — a view toggle with a size slider beside it. That makes the owner's flagged emphasis a well-founded pattern rather than an idiosyncrasy, without making it a category requirement.

---
## 8. Cross-reference to prior in-repo research

Two prior notes cover adjacent ground. **This report does not restate them.** What follows is what each already settles, what this report adds, and — importantly — where this report **corrects** them.

### 8.1 `docs/research/COMPETITOR-MATRIX.md` (2026-07-23)

**Already settled there; not repeated here:** the capability matrix across PewBeam / ProPresenter / OpenLP / FreeShow / EasyWorship / Quelea; pricing; platform support; the adjacent production-tooling landscape (OBS, vMix, ATEM, Companion/Stream Deck, NDI Tools); ProPresenter's Planning Center collaboration model; the eight differentiation opportunities in its §5.

**What this report adds:** that document is a **capability** matrix — what exists. This one is an **interaction** report — how it is arranged, named, and operated. They compose; neither substitutes for the other.

**Corrections this report forces on it:**

1. **Version framing.** It treats "ProPresenter 7" as the current product. The current release is **21.4.2 (2026-07-01)**; `7.16.3` was the last of the 7 line (§5.1). Its findings may hold; its version label does not.
2. **Five dead citations.** `https://renewedvision.com/propresenter7/whats-new7/` now returns **HTTP 404** (E39) and is cited five times in that document. Re-source before relying on it.
3. **Its §6 UNKNOWN #4 — "ProPresenter native RBAC vs Planning-Center-only collaboration" — remains UNKNOWN.** Neither remote-surface article documents any role or permission model (§3.13). Still an inference, now a better-supported one.
4. **Its §6 UNKNOWN #11 — "does any competitor ship an official Bitfocus Companion module"** — partially advanced: Renewed Vision documents an official **Stream Deck plugin** for ProPresenter `[E35 index entry]`. Companion specifically remains unverified.

### 8.2 `docs/research/LIBRARY-ORGANISATION-RESEARCH.md` (2026-08-15)

**Already settled there; not repeated here:** the media-library vs item-library distinction; the seven-product folders/tags/collections comparison; the finding that **six of seven products let an item live in more than one container**; ProPresenter Categories as a self-pruning single-select sort field; Quick Search as the vendor's answer to multi-store content; the user-voice analysis of whether structure or search is the real remedy; and the honest tension it reports rather than resolves.

**What this report adds, and where it strengthens that note:**

1. **Its single largest access limitation is now partly lifted.** It records that the Renewed Vision KB redirected to a Zendesk login, forcing all ProPresenter evidence through Internet Archive Pro6 copies. On 2026-08-28 the **ProPresenter 7 KB section served live, current, unauthenticated content** (§1.4). Gating is now **selective** — at least `Using Multiple Libraries` still 302s to login (E40). **ProPresenter claims in this report are live-sourced; ProPresenter claims in that one are archive-sourced and Pro6-skewed.** Prefer this report for UI facts; prefer that one for the library-organisation analysis, which this report does not attempt.
2. **Its core structural finding is corroborated from live 2026 docs.** Hierarchy sits over the *grouping* object, never the *item*: playlist folders exist (E01), Media Bin playlist folders exist (E01), item folders do not. This report adds a mechanism it did not have — **playlist Headers, Placeholders and Playlist Templates** (E09) — which is a *third* structuring layer inside the grouping object, and is what the owner's coloured PreShow/Music/Presentation dividers actually are (§4.2).
3. **Its open question 1 — does editing a presentation propagate to every playlist referencing it — is STILL UNRESOLVED.** I searched the live KB; `Building your Playlist` (E08) documents four ways to add an item and says nothing about reference-vs-copy semantics, and `Using Multiple Libraries` is login-gated. **Ten minutes of hands-on use still settles it and nothing else will.**
4. **Its open question 4 — do document Categories survive into current ProPresenter — is STILL UNRESOLVED.** No Categories article appears anywhere in the 131-article ProPresenter 7 KB section index (E35). **Absence from an index is not absence from the product**, but it is now a slightly stronger negative signal than it was.
5. **Its §3.8 complaint that search was slow at ~372 library documents** is corroborated as a real, cited review `[capterra.com/p/170172/ProPresenter/reviews?page=4]` and is **dated 2019**. It should be weighted accordingly, and note that **7.7 added a text/thumbnail preview to library search** (E32) — the vendor did work in that area afterwards.

### 8.3 Documents deliberately not duplicated

`ADJACENT-TRANSCRIPTION-PRODUCTS.md`, `CAPABILITY-ASSESSMENT.md`, `FEASIBILITY.md`, `LICENSING-REGISTER.md`, `LICENSED-TRANSLATIONS.md`, `PROVIDER-TRADEOFFS.md` and `OPEN-DECISIONS.md` cover AI/transcription, licensing and feasibility ground that this brief does not touch. Nothing here supersedes them.

---

## 9. Implications worth Priya's attention

> **This section is INTERPRETATION, and it is the only interpretive section in the report.** Everything above is observation with a citation. Nothing below is a recommendation, a scope decision, or an adopt/reject call — those are Priya's, and Uma's and Diego's downstream. Each item names the evidence it rests on so Priya can weigh it rather than take it.

1. **The strongest single pattern in the evidence is that ProPresenter has two UIs sharing one window** — a *runtime* surface that operators find easy, and a *configuration/authoring* surface that they find hard (§6 T1, corroborated by the volunteer curriculum in §6.4 that omits Looks, Screens, Themes, Props and Macros entirely). Any decision about SelahCue's operator console is really two decisions.
2. **The owner's flagged view-density cluster is not a cosmetic detail in the reference product** (§4.3). It is documented as strictly output-neutral, it appears in at least four places in ProPresenter, it is replicated on the mobile remote, a named reviewer ties it to operator legibility in a dark booth, and the vendor added View-menu switching plus per-view custom key bindings in **21.3, five months ago**. Whether SelahCue needs it is Priya's call; the evidence that it is a live, invested-in surface in the market leader is strong.
3. **Four design decisions inside that cluster are genuinely open and cannot be copied**, because ProPresenter does not document them: view-mode scoping (per presentation / playlist / global), slider persistence, slider range and stepping, and whether `Slides by Group` is per-view or shared (§4.3). These are the parts Uma must design rather than reference.
4. **The most-loved control in the product is the per-layer clear cluster** (§6 T9), and its documented virtue is spatial: **the clear buttons are stacked in the same order as the layers composite on screen** (§3.9). The control's arrangement *is* the mental model. That is a transferable idea independent of whether SelahCue copies the feature.
5. **The most-missed concept is Looks** (§6 T3), and its failure has a reproducible signature — content missing on one screen because a saved layers×screens matrix disabled it there. SelahCue already has a layer/output model; the evidence says the *explanation* of such a model is where operators fail, not its power.
6. **Vocabulary is a first-class risk, evidenced by the vendor's own trainers conceding it** (§6 T4). ProPresenter ships Theme, Template, Look, Prop, Message, Group, Arrangement, Category, Library, Playlist, Header, Placeholder, Macro, Clear Group, Screen and Look Preset — and **does not define Theme vs Template anywhere I could find** (§3.11). The repo already carries a related decision: `CLAUDE.md` and `docs/design/THEME-MODEL-spec.md` fix "theme" to mean a slide-design template, not a colour mode. **The evidence supports treating naming as a design deliverable with an owner, not as a by-product.**
7. **ProPresenter ships a documented example of removing whole feature families from the chrome for a user segment** — the House of Worship toggle (§3.1, E25). It operates on *segment*, not on *skill*. The volunteer-usability evidence (§6 T5, T11) points at skill. That gap is an open design space, not a validated need.
8. **A countdown on the audience screen requires composing three objects** — Timer + Theme + Message with a token (§3.11, E15) — while a countdown on the *stage* screen is a first-class prebuilt object (E14). That asymmetry is a concrete, citable complexity data point.
9. **Two current vendor pages disagree about the names of the three slide views, and two disagree about the layer stack** (§3.4, §3.9). If ProPresenter's own documentation cannot hold its vocabulary stable across two articles, a PRD that copies ProPresenter vocabulary inherits that instability.
10. **A well-sourced 2019–2024 complaint (PowerPoint import) was fixed in 21.2, February 2026** (§6 T6). Any competitor claim in the PRD should carry the version it was true of, or it will be wrong on the day it ships.
11. **What ProPresenter does not appear to have**, on this evidence: any documented role or permission model on either remote surface (§3.13), and no public peer community forum (§6.1). Both are *absence of evidence within authorised access*, not evidence of absence — and `COMPETITOR-MATRIX.md` §5 already treats native RBAC as a differentiation hypothesis.

---

## 10. Open uncertainties

Ordered by how much a wrong assumption would cost.

### 10.1 Would change a design decision

1. **Slide-view scoping, persistence, range and stepping** (§4.3). Four unknowns inside the one thing the owner explicitly flagged. **Undocumented; resolvable only hands-on.**
2. **Does the playlist "Show" view stack all presentations in one continuous scroll?** The owner's Screenshot A shows it; **no vendor article documents it** (§3.3). If Uma builds to it, she is building to a second-hand description, not a citation.
3. **Does Reflow update live output while typing?** The vendor says it edits "in real-time" without saying what that means (§3.6). For a product with a never-blank-output guarantee this is load-bearing. **UNKNOWN.**
4. **How do Groups behave across a Reflow split or merge?** Not documented (§3.6). **UNKNOWN.**
5. **Do Group Labels still carry auto-attached hot keys?** Documented only in a Pro6-era article; the owner's orange letter chips suggest yes (§3.5, §4.2). **INFERRED, Med.**
6. **The per-presentation header icon roster** — copy/paste styling, split/columns, loop, auto-advance badge, the warning-triangle and clock status badges on the Countdown item (§4.2). Observed in the screenshots, **documented nowhere I could reach**.

### 10.2 Inherited from prior research and still open

7. **Does editing a presentation propagate to every playlist referencing it?** (§8.2). Unresolved across two research passes.
8. **Do document Categories exist in the current build?** (§8.2). Absent from the 131-article index; not proof.
9. **Does ProPresenter have any native role/permission model?** (§3.13, §8.1). Still an inference.

### 10.3 Version questions

10. **Exactly when and why the `7.x` prefix was dropped.** The download page shows the jump from `7.16.3` to `17` (§5.1) but gives no rationale or date for the change, and the vendor blog stops at 7.10. **The transition point is pinned; the reasoning is UNKNOWN.**
11. **Which KB articles still describe pre-21 behaviour.** Articles are titled "ProPresenter 7" and describe current behaviour, while sibling articles say "version 19+" and "version 20". **The KB's own currency is unaudited**, and I could not audit 131 articles.
12. **Whether ProPresenter Control's "16 fixed sections, not customisable" is still true.** That limitation is version-pinned to **7.9.1** (E28) — twelve major versions ago.

### 10.4 Access failures — these bound everything above

| What could not be reached | Effect |
|---|---|
| **Reddit — r/churchtech, r/ProPresenter.** Both `old.reddit.com` and `www.reddit.com` refused automated fetches; `reddit.com` is on the search API's blocked-domain list | **The brief asked for this specifically and it is not satisfied.** The largest venue for unfiltered operator complaint is entirely unsampled |
| **G2** and **TrustRadius** — HTTP 403 to automated fetches | Two independent review corpora unavailable. §6 leans harder on Capterra/SoftwareAdvice, which **share one pool** |
| **ProPresenter Users Facebook group** — login-walled | Not entered. Two relevant thread titles surfaced in search (hotkey removal; Pro6→Pro7 import) but were not read and are not cited |
| **YouTube transcripts** — not retrievable with available tooling | Title-level signal only. The large "ProPresenter for beginners" tutorial corpus corroborates "YouTube is the manual" but is not independent evidence |
| **`support.renewedvision.com/.../Using-Multiple-Libraries`** — 302 to Zendesk login (E40) | The primary source for the Library model. **Not bypassed.** §3.2's library claims fall back to the prior report's archived Pro6-era evidence |
| **`learn.renewedvision.com/propresenter/interface`** — 302 to the KB category root | The standalone user guide appears folded into the KB; no separate guide to cross-check the KB against |
| **`renewedvision.com/propresenter7/whats-new7/`** — HTTP 404 (E39) | Link rot on a URL cited five times in `COMPETITOR-MATRIX.md` |
| **No ProPresenter licence or trial in scope** | **Nothing in this report was verified by operating the product.** Every dynamic-behaviour claim is documentation-derived. This is the single biggest confidence bound on the whole report |
| **The owner's screenshots themselves** | I have not seen them (§4.1). All §4 findings are second-hand from a written description |

### 10.5 Method notes

- **No page encountered contained text addressed to an AI or automated agent.** One near-miss: the Renewed Vision support homepage carries ordinary human-facing form copy asking the requester to provide information; that is directed at support requesters, not at me, and was not acted on.
- **One search result was excluded as likely malicious**: a GitHub repository named `ProPresenter-2025` whose description is keyword-stuffed SEO text apparently fronting a pirated download. It was **not fetched** and is **not cited**.
- **No authentication, paywall bypass, or account creation** was attempted anywhere. Login-gated sources are recorded as access failures above.
- **Volume, stated plainly.** This report rests on **~30 Renewed Vision knowledge-base articles read live**, two of them verbatim; **~6 vendor marketing/blog/release pages**; **~10 third-party practitioner and review sources**; and comparator documentation registered in §7. **User voice is thinner than the vendor evidence and skewed toward one shared review pool.** Nothing here should be read as a measured demand signal.
