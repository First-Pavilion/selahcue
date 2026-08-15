# SelahCue — Research note: how comparable products organise and find items in a large library

**Work item:** commissioned by `docs/product/SIZING-library-grouping.md` §3.1 ("Hands-on competitor check")
**Goal Contract:** `docs/delivery/goals/GOAL-research-library-organisation.md`
**Prepared by:** Product Researcher, SelahCue
**Access date for all findings:** 2026-08-15 (where a source carries its own date, that date is given inline)
**ClickUp:** none — no ClickUp item covers library grouping; creating one would pre-empt the Product Manager's scope call.

## What this note is, and what it is not

`COMPETITOR-MATRIX.md` documents **service scheduling** (playlists, run sheets, schedules) for six products and records **nothing** about how any of them organise a *content library*. This note fills only that hole. **It does not modify the matrix** — every existing row there is untouched (verified by `git diff`).

This note reports evidence. **It makes no recommendation and takes no scope decision.** Priya owns scope. Where evidence is thin it is labelled thin, and the counts are deliberately unflattering — the commissioning note is explicit that thin evidence must not be dressed up as a verdict.

### Classification legend (reused from `COMPETITOR-MATRIX.md`)

| Tag | Meaning |
|-----|---------|
| **OBSERVED** | Directly seen — a user's own post, a vendor screenshot, or the product's actual source/schema |
| **DOCUMENTED** | Stated in official docs, KB, changelog, or the vendor's own site |
| **INFERRED** | Reasoned from indirect evidence; not explicitly confirmed |
| **UNKNOWN** | Could not verify with available (non-paywalled, non-login) access |

Confidence (High/Med/Low) reflects source authority plus corroboration. As in the existing matrix, **no product was operated hands-on** — no trials purchased, no accounts created, no login or paywall bypassed. `OBSERVED` here therefore means public source code, public schemas, public forum posts and dated reviews, not a running application. §6 lists every access failure.

---

## 0. The distinction that governs every finding below

These products keep **two different libraries** and organise them **differently**. Conflating them would corrupt any conclusion:

- The **media library** — images, videos, motion backgrounds, audio. Large, bought in bundles, browsed by look, and usually backed by the file system.
- The **item library** — songs, sermon decks, announcement sets, scripture slides. Smaller, retrieved by name, usually backed by a database.

SelahCue's `deck` is an **item**, not media. Findings about media organisation are the weaker analogy and are marked as such throughout. The distinction matters because the two consistently get *different* treatment inside the same product: **the media library gets the folder tree; the item library gets search and labels.**

---

## 1. Comparison table

`?` = UNKNOWN. Evidence for every cell is in §2.

| | ProPresenter 7 | Proclaim | EasyWorship 7/8 | MediaShout 7 | OpenLP 3.x | FreeShow 1.5.x | Quelea |
|---|---|---|---|---|---|---|---|
| **Folders over items** | **No** — flat inside a Library | **No** | **Yes** — nested, but every leaf must be a *Collection*; resources cannot attach to a folder | Lyrics: **flat** (All + Custom) | **No** — explicitly by design | **No** — flat categories | **No** |
| **Folders over media** | Playlist folders in Media Bin | Boards (facets) | Nested; mirrors Windows dirs by exact-string rule | **Nested since v7.6.2** (Mar 2024); *is* the disk | Groups for images only | OS folders | Image groups |
| **Folders over groupings** | **Yes** — Group Folders over playlists | n/a | n/a | n/a | n/a | **Yes — nested** folders over projects | No |
| **Item in >1 container?** | **Yes** via playlists; **No** across Libraries | **Yes** — "can be on multiple boards" | **Yes** — "the same media item may can appear in multiple collections" | **Yes** — "you can have the same lyric in many different folders" | **Yes** — topics & song books | **No** — `category` is a scalar | n/a |
| **Many-to-many mechanism** | Playlists | **Boards *and* tags** | **Collections *and* media tags** | Custom folders (tag-like) | **Topics, Song Books, Authors** | **Tags** (`quickAccess.tags`) | **None found** |
| **Single-select classification** | Category (Pro6) | — | — | — | Theme | Category | Theme |
| **Division of labour explained?** | n/a — different objects | **Yes** — tags→search, boards→shared shelves | **Yes** — "tags are a field, collections are a saved query over fields" | n/a — no separate tag concept | **No** — manual defines none | **No** — docs never mention tags | n/a |
| **Smart / dynamic groups** | Smart Playlist mirrors a disk folder | Suggested Media; trending | **Yes** — Match All/Any rules over Title, Author, Copyright, Words, Any Field, Directory | **No** (fixed 3-value type filter) | No | No | No |
| **Search** | Title **and** slide text, ranked; Pro7 Quick Search spans all Libraries | Search bar; tags feed it | Title **or** keyword — behind an icon toggle; scope sticky and invisible | Title + Stanzas + Author, **exact match**, scoped to folder | **9 modes, mutually exclusive** | Title (+ cached content, unconfirmed) | Title + lyrics + author, **unified** |
| **Recency** | **Yes** — Last Used Date sort, on every row | **Yes** — Recent Media facet; Duplicate Recent | **None found** | **None found** | None found | **Yes** — modified/created/used sort | None found |
| **Favourites** | Not found | **Yes** — default Favorites board | **None found** | Star = save to Cues Library (a store, not a flag) | Not found | **Media only** | Not found |
| **Declutter** | "Clean Up Unlinked Media" | — | — | — | "Find Duplicate Songs" | **Archive a category** | — |

**The single most striking row is "item in >1 container".** Six of seven products answer **yes**. Only FreeShow ships a true single-home container for items — and it is flat, not a tree.

---

## 2. Per-product findings

### 2.1 ProPresenter 7 (Renewed Vision)

**The headline: the item library is flat. The hierarchy is one level up, over playlists.**

**Folders / hierarchy**

- **DOCUMENTED (High):** multiple Libraries exist and the vendor's stated purpose is *separation*, not thematic grouping: "The main reason would be if you had groups of Presentations you want to keep separate from each other… Another option would be to keep a certain type of presentation, such as songs, separate from other presentations like speaking notes and Scripture slides." — https://support.renewedvision.com/hc/en-us/articles/360041811293-Using-Multiple-Libraries-in-ProPresenter (dated 2020-01-20)
- **DOCUMENTED (High):** a Library is a **folder on disk** — "click on the plus (+) button and browse to the new folder you want to add as a Library. This needs to be an empty folder, or a folder that only contains ProPresenter Library files in it." — https://support.renewedvision.com/hc/en-us/articles/360011693974-How-do-I-add-multiple-Libraries-to-ProPresenter
- **INFERRED (High):** therefore a document is **single-home across Libraries** and **Libraries do not nest**. Follows from the add-a-folder mechanism; not stated in so many words. Worth ten minutes of hands-on confirmation.
- **DOCUMENTED (High):** inside a Library, documents are a **flat list** — the Library "is composed of two main pieces: the search bar and the documents list." — https://learn.renewedvision.com/propresenter6/introduction-to-propresenter/the-library
- **DOCUMENTED (High):** hierarchy exists over **playlists**: "Group Folders are used to organize your Playlists. For example, you might have a Group Folder for 'Liturgies', 'Sunday AM', or 'Wednesday PM'." — https://learn.renewedvision.com/propresenter6/introduction-to-propresenter/playlists. Same pattern in Pro7's Media Bin: "The left column of the media bin is reserved for playlists and playlist folders." — https://support.renewedvision.com/hc/en-us/articles/360041345954-Understanding-The-ProPresenter-User-Interface

**Classification and many-to-many**

- **DOCUMENTED (High):** no tag mechanism on documents in any source checked. Instead, **Categories — used only for sorting and filtering**: "Categories are simply used for sorting. They don't have any impact on the document other than letting you sort by Category in the Library." — https://support.renewedvision.com/hc/en-us/articles/360011514894-Using-Categories-for-Library-documents-in-ProPresenter-6
- **DOCUMENTED (Med):** Categories are **self-pruning**, explicitly modelled on iTunes genres: "Once you remove the last document assigned to a category, that category is removed… If you use iTunes, this works similar to how genres work for music." The Categories list was **removed from Preferences** — the vendor deliberately stopped making the taxonomy a thing users maintain. — same URL
- **INFERRED (High):** Categories are **single-select** — every documented assignment route is a dropdown, and filtering is single-value ("When you select a category, for example, 'Hymns', only documents with that category would be shown").
- **DOCUMENTED (High):** the real many-to-many axis is the **playlist**: "ProPresenter now allows you to add a Presentation from any Library into any Playlist." — https://support.renewedvision.com/hc/en-us/articles/360041811293-Using-Multiple-Libraries-in-ProPresenter
- **UNKNOWN:** whether editing a presentation propagates to every playlist referencing it. A search synthesis asserted it does; **no primary source was retrievable** (the current guide is login-gated and the user-guide PDF host returned HTTP 521 on every attempt). This is the divergence question, and it stays open — see §6.
- **UNKNOWN:** whether document Categories survive into ProPresenter 7. Every Category article reachable is banner-marked "This article deals with our legacy product, ProPresenter 6." **Absence of evidence is not evidence of absence.**

**Findability besides structure**

- **DOCUMENTED (High):** search covers **titles and slide text**, ranked — https://support.renewedvision.com/hc/en-us/articles/360011610593-Why-do-so-many-songs-show-up-when-I-search
- **DOCUMENTED (High):** sort by "Title, Category, **Last Used Date**, or Search Rank", and the row itself shows "the song name, category, and the last used date." — https://learn.renewedvision.com/propresenter6/introduction-to-propresenter/the-library
- **DOCUMENTED (High):** Pro7 **Quick Search** — one shortcut across *every* Library plus external catalogues: "search in all Libraries, SongSelect, and MultiTracks all from one unified window… Command+F on Mac or Control+F on Windows." — https://support.renewedvision.com/hc/en-us/articles/9808905773715-How-to-Use-Quick-Search-within-ProPresenter
  - *Interpretation (mine):* Quick Search deliberately ignores the Library boundary. The product's answer to "my content is in several places" is a global search box, not navigation.
- **DOCUMENTED (Med):** Smart Playlists (ex-"Hot Folders") are dynamic but **derived from the file system, not user rules** — they mirror a disk folder. Media only.

**The vendor documents its own scale problem**

- **DOCUMENTED (High):** "if you are searching for a specific song and you have a large library, **this may result in your desired Document far down in the search results**." Both remedies offered are non-structural — switch the sort to Search Rank, or restrict search to titles. — https://support.renewedvision.com/hc/en-us/articles/360011610593-Why-do-so-many-songs-show-up-when-I-search

### 2.2 Proclaim (Faithlife / Logos)

**The headline: ships boards and tags together — and made the "folder" many-to-many on purpose.**

- **DOCUMENTED (High):** boards are explicitly **not** containers: "**Adding media to a board does not remove it from the main browser pane. A piece of media can be on multiple boards.**" — https://support.faithlife.com/hc/en-us/articles/360007126952-Organize-your-media-with-boards
  - *Interpretation (mine):* that sentence is written defensively. It pre-empts the containment model a user brings from file folders and corrects it.
- **DOCUMENTED (High):** boards are team-shared with useful defaults: "Boards you create in Proclaim are shared with your entire team… **A Favorites board exists to get you started.**" Managed in "the facet view" — i.e. rendered as filters, not a tree. — same URL
- **DOCUMENTED (High):** tags are many-per-item, **system-suggested**, and framed purely as a search aid: "As you type, Proclaim suggests tags, which you can accept or reject. (**Reference tags allow users to locate the media item through a search. The more tags you add, the easier the item will be locate in the future.**)" — https://support.faithlife.com/hc/en-us/articles/360007128472-Media-Browser
- **DOCUMENTED (High):** the same import dialog offers rename + tags + add-to-Board together — the two mechanisms sit side by side at the moment of filing. — same URL
- **The division of labour (DOCUMENTED, Med):** **tags feed search; boards are thematic, shared shelves you browse.** Neither is a single-home folder, so the classic "I filed it in the wrong place" error cannot occur.
- **DOCUMENTED (High):** sorts are **usage-derived** — "popularity (all-time usage), relevance…, or by what's trending (popular media in the last seven days)"; **Suggested Media** is computed from the current presentation; Proclaim 4.0 added a "**Recent Media facet**… See the media you've recently added to your presentations." — Media Browser article + https://faithlife.github.io/ProclaimReleaseNotes/4.0/ReleaseNotes.html
- **UNKNOWN:** whether boards nest. No nesting language found either way.

**Items and service items — no structure at all**

- **DOCUMENTED (High):** finding a past item is a search modal plus a type filter: "expand the Add Item menu and select Reuse item… **Enter the name of the previously used item in the search box. If necessary, filter by service item type.**" — https://support.proclaim.logos.com/hc/en-us/articles/19863521020941-How-Do-I-Reuse-Items (dated 2024-08-13)
- **DOCUMENTED (High):** the vendor's findability advice is **naming**, not filing: "**If you add custom names to your service items** … **it's easier to reuse them later.** In the example above, the addition of 'bilingual' makes it easy to find that exact item." — same URL
- **DOCUMENTED (Med):** recency is the primary route back: "**Duplicate Recent expands a list of recent presentations by date.**"

### 2.3 EasyWorship 7/8

**The headline: the most sophisticated model in the set — a "Collection" is a saved query, not a bucket — and it is the most reported as hard to work.**

**Folders / hierarchy**

- **DOCUMENTED (High):** the library is five tabbed sub-libraries in a Resource Area: "Songs, Scriptures, Media, Presentations, and Themes." — https://support.easyworship.com/support/solutions/articles/24000020385-quick-start-guide
- **DOCUMENTED (High) — nesting is real, but folders cannot hold items:** "Within Collections and My Collections you can create Folders which are just containers for your collections… **Under each of those folders, you can create other folders and collections.**" and "You don't have to create folders to create collections, but you do have to have a collection to add resources to it. **You cannot add resources to a folder.**" — EasyWorship 7 Manual (official zip: https://supportresources.easyworship.com/PDF_Manual/EasyWorship7Manual.zip, via https://support.easyworship.com/support/solutions/articles/24000020510-easyworship-7-manual)
- **DOCUMENTED (High) — multi-home:** "**The same media item may can appear in multiple collections.**" *(the "may can" typo is in the source)* — https://support.easyworship.com/support/solutions/articles/24000020385-quick-start-guide
- **DOCUMENTED (High) — references, not copies, with a sharp edge:** "Adding items to a Collection does not copy them to a folder. **If you delete the source, it will be deleted permanently** and will no longer be in your EasyWorship Library or Collection." — EW7 Manual
- **DOCUMENTED (Med) — the hierarchy is invisible from the main view:** vendor staff: "while it will allow you to organize the files like you want, **you will only see that while in the Collections portion of the Media Tab**… When you go to the main section of the Resource Area ALL of the files of the specific type… will be visible." — https://support.easyworship.com/support/discussions/topics/24000015141
- **DOCUMENTED (Med):** media collections bind to Windows directories by **exact string match**, under a fixed resources path — https://support.easyworship.com/support/discussions/topics/24000022724
- **DOCUMENTED (Med):** two scopes exist — shared *Collections* and private *My Collections*, and the private ones are a backup hazard: "**If you ever backup your database, My Collections will not be backed up with it.**" — https://easyworship.com/blog/creating-and-using-collections (vendor Head of Training, 2019-02-11)
- **Contradiction retained:** whether Scripture supports collections. Vendor sources disagree — the Collections blog and EW7 Manual both list "Songs, Scripture, Media Presentations, or Themes", while https://easyworship.com/blog/7-easyworship-basics (2019-03-26) says "**With the exception of scriptures**, they each have the option of organizing them by collections." Both vendor-authored, same year. **Unresolved.**
- **UNKNOWN:** whether the media scan traverses nested *disk* folders. Snippet-only reports (login-gated threads) say it does not. Note this is a *different* hierarchy from the Collections sidebar, which does nest — conflating them is easy.

**Tags — and an unusually clear division of labour**

- **DOCUMENTED (High):** tags exist **on media** as a real field — "**Tags: This drop down allows you to enter tags for the clip.**" — https://support.easyworship.com/support/solutions/articles/24000020404-videos
- **OBSERVED (Med):** tags do **not** exist on songs; the request is marked **Deferred** with 2 supporters and no vendor reply: "I would like to be able to add Tags… such as 'Christmas, Easter, Holy Spirit'… to songs, within EasyWorship, to be able to create Collections automatically." — https://support.easyworship.com/support/discussions/topics/24000016808
- **DOCUMENTED (High) — the division of labour, and it is the clearest of any product here: a Collection is a *saved query*; tags are one of the *fields* it queries.** "Use the folder (directory) that media items are stored for criteria in a collection… **Use tagging, title or file name** of the media item to create easily accessible lists of media items based on the criteria you provide." — Quick Start Guide
- **DOCUMENTED (High) — real smart groups:** "Check the box next to Match and use the drop-down to choose **All** or **Any** of the following rules", over "**Title, Author, Copyright, Administrator, Words, or Any Field**" (media adds **Directory**), with an Add icon for more filters. Membership is **hybrid — static drag-and-drop *and* dynamic rule evaluation.** — https://easyworship.com/blog/creating-and-using-collections + EW7 Manual

**Findability besides structure**

- **DOCUMENTED (High):** two search modes — title/reference, or keyword over song words — "**Toggle between search modes by clicking the icon on the left side of the search box.**" — Quick Start Guide
- **OBSERVED (High) — the toggle is the single biggest reported findability failure.** A user reported autocomplete "no longer working" and **uninstalled and reinstalled EasyWorship**; staff replied "You have the copyright field selected. You need to click on the Title file and then it will work." The search scope is **sticky and invisible**. — https://support.easyworship.com/support/discussions/topics/24000022268
  - A related feature request ("Seperate Search Box") is marked **Not Taken**: "If I want to switch from my normal title only search (the default) to get to a search for only words, **it takes 3 clicks**." The vendor disputed the click count — **both sides retained.** — https://support.easyworship.com/support/discussions/topics/24000002237
- **DOCUMENTED (Med):** scripture sort ascending/descending; thumbnail/list view slider. — https://support.easyworship.com/support/solutions/articles/24000020401-scriptures
- **Recency / favourites: none found** across the Quick Start Guide, EW7 Manual, Collections blog and KB, Scriptures KB, Videos KB, Songs KB, and the Full Features KB folder. Nearest proxy is a **song activity report** with use counts. **Not found — not proven absent.**
- **INFERRED (Med) — a telling asymmetry:** the vendor's *cloud* catalogue (Premium Media) offers category / still-vs-motion / holiday **facets** that the user's own local library does not get. — https://support.easyworship.com/support/discussions/topics/24000024018

### 2.4 MediaShout 7

**The headline: "folders" that are explicitly not folders — and a deletion asymmetry that punishes the folder mental model.**

- **DOCUMENTED (High) — the strongest multi-membership statement any product in this set makes:** "There is an All Folder which is the master folder containing all of your lyrics. You can create any number of Custom Folders… (they will always remain in the All Folder, too)" and "**The separate folders are simply pointing back to the All Folder, so you can have the same lyric in many different folders.**" — https://mediashout.com/docs/mediashout-7-user-guide/index-of-all-functions/e-f-g/ and .../m-n-o/
- **DOCUMENTED (High) — and here is the trap:** "Deleting a lyric from a custom-created folder will only remove that Lyric from that folder… **Deleting a lyric from the All Folder will delete the lyric permanently** from the All Folder and any Custom Folders that lyric is in." Compounded by one trash-can icon meaning different things depending on focus. — https://mediashout.com/docs/mediashout-7-user-guide/index-of-all-functions/c-d/ and .../t-u-v-w-x-y-z/
- **UNKNOWN (leaning one level):** lyric folders nesting. Not found across ~15 user-guide pages; no source positively denies it.
- **DOCUMENTED (High) — the media library gained nesting in 2024, and it *is* the disk:** "**We have had many requests to show additional subfolders within the main folder** which the user assigns for the Media Library, so now you have your wish!" (v7.6.2, 2024-03-21) — https://support.mediashout.com/991981-What-has-changed-in-v762. Media hierarchy is therefore **strictly single-home**, in direct contrast to the multi-home lyric folders in the same product.
- **No tag mechanism found** across ~20 official sources (the T-Z function index has entries for Timer, Tip of the Day, Training Videos, Transition Plug-In, Trash Can… and **no "Tags"**). **No source positively states tags are absent.** The custom folders are functionally tag-like; MediaShout simply calls them folders.
- **DOCUMENTED (Med) — a naming-history clue:** MediaShout 6 called them "**lyric groups — special categories that you assign songs to**". MS7 renamed the same semantics to "folders". *(snippet-only; the MS6 guide URL now redirects and the archive was unreachable)* — that rename is the plausible root of the deletion confusion.
- **DOCUMENTED (High) — search is exact-match and folder-scoped:** within My Library it matches "those words in the exact order as they are listed in the **Title, Stanzas, and Author** field"; "**search is exact match**". Better field coverage than EasyWorship's default, but no fuzzy or stemmed matching. — https://mediashout.com/docs/mediashout-7-user-guide/index-of-all-functions/s/ and .../creating-your-first-script/
- **DOCUMENTED (High) — three search boxes, three behaviours, and the vendor admits it:** the v7.7.0 changelog lists "**Modify Search boxes to behave in more similar ways**" plus "Enhanced the Search function in a few places"; v7.6.6 says the Cues Library search "used to require extra clicks and it was **too cumbersome**." — https://support.mediashout.com/257018-What-has-changed-in-v770, https://support.mediashout.com/458048-What-has-changed-in-v766
- **DOCUMENTED (Med) — the vendor's own advice creates two competing song stores:** it recommends saving lyrics to the **Cues Library** ("we recommend saving Lyrics here as your ongoing database of edited lyrics for future use") — which has **no folders**, title-only search, and a fixed three-value type filter. So a user ends up with My Library (folders + 3-field search) *and* the Cues Library (no folders + title search). — https://mediashout.com/docs/mediashout-7-user-guide/index-of-all-functions/c-d/ and .../advanced-tools/cues-library/
- **No recency, no sort options, no favourites flag found.** The star icon saves to the Cues Library — a store, not a flag.
- **UNKNOWN:** "MediaShout Cloud" — **no evidence it exists.** Checked the vendor site, FAQ, full MS7 guide TOC and KB category list. "MediaShout LE" is a price tier. A third-party directory claiming "cloud-based access" is contradicted by the vendor's own desktop-installer pages and is judged unreliable.

### 2.5 OpenLP 3.x

**The headline: the richest many-to-many labelling in the whole set — and its users still cannot find things, because the search cannot combine them.**

Evidence here is unusually strong because the schema is public. The two load-bearing forum quotes were **independently re-verified by me** against the OpenLP forum's public JSON API.

- **DOCUMENTED (High) — no folders, and the maintainer says why:** "OpenLP doesn't have a concept of folders because OpenLP doesn't store songs as files, it stores all your songs in a database. I see two ways to work around this, one is to use topics, and the other is to use song books." (`raoul`, OpenLP team, 2017-03-30) — https://discuss.openlp.org/d/3470-song-folder
- **DOCUMENTED (High) — not even a browsable grouping:** "there isn't currently a grouping of songs, but you can do a search by songbook." (2017-12-20) — https://discuss.openlp.org/d/3726-multiple-song-books
- **OBSERVED (High):** one SQLite database; `song_books` is `id, name, publisher` with no self-reference, so Song Books are **flat**. — https://gitlab.com/openlp/openlp/-/raw/master/openlp/plugins/songs/lib/db.py

**Four coexisting mechanisms** (`OBSERVED`, from the schema and the editor form):

| Mechanism | Cardinality | Evidence |
|---|---|---|
| **Topics** | **many-to-many** | `songs_topics(song_id, topic_id)`; `topics` is just `id, name` |
| **Song Books** | **many-to-many with a payload** | `SongBookEntry(songbook_id, song_id, entry)` — same song, different hymn number per book |
| **Authors** | **many-to-many with a role** | `AuthorSong(author_id, song_id, author_type)` |
| **Themes** | **single-valued** | `theme_name = Column(Unicode(128))` |

> Terminology trap, matching SelahCue's own convention: an OpenLP "Theme" is a **slide-design template**, not a subject label.

- **OBSERVED (High) — the manual never explains which to use.** The song-editor section is headed "Authors, Topics & Song Book" but documents **only authors**; the labels `Topic:`, `Book:` and `Number:` do not appear on the page. — https://manual.openlp.org/songs.html
- **DOCUMENTED (High) — the manual teaches a string hack instead:** "You could use an alternate title of 'hymn' on all your hymn song titles for grouping. When you search 'hymn' it will show all the hymns…" — https://manual.openlp.org/_sources/songs.rst.txt
- **DOCUMENTED (High):** nine search modes — Entire Song, Titles, Lyrics, Authors, Topics, Songbooks, Themes, Copyright, CCLI number. — https://manual.openlp.org/library.html
- **INFERRED (High) — and this is pivotal: the modes are mutually exclusive.** There is no "songbook = X AND lyrics contain Y". Inferred from `set_search_types` / `on_search_text_button_clicked` in https://gitlab.com/openlp/openlp/-/raw/master/openlp/plugins/songs/lib/mediaitem.py, and corroborated by the user complaint in §3.
- **OBSERVED (Med):** the Tools menu ships "**Find Duplicate Songs**" — a built-in de-duplicator is itself evidence that duplicate accumulation is a known, recurring problem.
- **Favourites, recency, sort controls, smart groups: none found** in the sources checked. **Not found — not proven absent.**

### 2.6 FreeShow 1.5.x (ChurchApps)

**The headline: nested folders and many-to-many tags ship in the same product — and the docs teach only one of them.**

- **DOCUMENTED (High) — projects nest:** "To add a folder click 'New folder'… **You can also have folders inside folders.**" Recommended pattern is event-then-year. — https://freeshow.app/docs/projects. Note the shape: a project is "a playlist with all the songs, videos, presentations and other elements for your meeting" — so, as in ProPresenter, **the nesting is over the grouping object, not the item.**
- **DOCUMENTED (High) — shows get flat, single-home categories:** "On the left you can organize them into categories by dragging any show over the category." — https://freeshow.app/docs/drawer
- **OBSERVED (High) — single-home, verified at source *by me*:** `category: null | ID` — a scalar, not an array; and `tags?: string[]` — an array. — https://raw.githubusercontent.com/ChurchApps/FreeShow/main/src/types/Show.ts. Categories also have **no parent field** (https://raw.githubusercontent.com/ChurchApps/FreeShow/main/src/types/Tabs.ts), so they do not nest.
- **OBSERVED (High):** the drawer has a live tag filter storing tags per show under `quickAccess.tags`, and it **AND**s multiple selected tags. — https://raw.githubusercontent.com/ChurchApps/FreeShow/main/src/frontend/components/drawer/pages/Shows.svelte
- **OBSERVED (Med) — the division of labour is not explained.** The word "tags" does not appear on https://freeshow.app/docs/drawer — the page that teaches categories. Checked `/docs/drawer`, `/projects`, `/media`, `/format-show`, `/format-project`, `/show`. **Not found on those pages** — not proven absent from all FreeShow docs.
- **OBSERVED (High) — the only genuine item-level recency sort in the open-source set:** sort headers are name, number, and `modified`, over `timestamps: { created, modified, used }`.
- **DOCUMENTED (High) — a declutter affordance no other product here has:** "You can right click a category to mark it as 'Archive'. Doing this will **hide it from the 'All' tab and searches**." — https://freeshow.app/docs/drawer
- **DOCUMENTED (High):** favourites exist **for media only**.
- **PARTIALLY VERIFIED, flagged deliberately:** a sentence stating search also covers cached text content appeared in a search-engine extract of the drawer page but **not on direct fetch**. Recorded as unconfirmed rather than quoted as fact.

### 2.7 Quelea

**The headline: no library organisation at all — and its community is not complaining. Both halves are weak evidence.**

- **OBSERVED (High):** the song entity has **no organisational field whatsoever** — `id, title, author, lyrics, ccli, copyright, year, publisher, key, capo, info, translations, songsequence`. No category, folder, group, songbook or tags column; no join table. — https://raw.githubusercontent.com/quelea-projection/Quelea/master/Quelea/src/main/java/org/quelea/data/db/model/Song.java
- **DOCUMENTED (High):** what the docs call "organising" is the *schedule*, not the library. — https://raw.githubusercontent.com/quelea-projection/quelea-projection.github.io/master/docs/Layout.md
- **DOCUMENTED (High) — the entire browse story is scrolling:** "You could either search by title, phrase or author… You could also **scroll through the database** to find the desired song." — https://quelea.org/manuals/Quelea%20manual-en.pdf (manual v2016.2)
- **OBSERVED (Med):** unlike OpenLP, search is **unified, not modal** — title, body and author run together and merge.
- **Contradictory evidence, retained rather than resolved:** the shipped translation file contains `tags.button=Manage tags...`, `filter.tag=Filter tags`, `tags.label=Tags` — but **no implementing code path was found** (no tags column, no `getTags()`, no tag field in the Lucene index, no `FilterType.TAG`, no tag control in the library panel, no mention in the manual). Part of the noise is explained by "Tag" also being a *lyric section type*, but that does not explain `Manage tags...` or `Filter tags`. **Most plausibly vestigial. Whether song tags ever shipped: UNKNOWN.**
- **Honest note on the quiet forum:** a Discourse search for `folders OR categories songs library` returned **literally zero results**. That is *not* evidence of satisfaction — Quelea's community is far smaller, so low volume plausibly reflects community size (**INFERRED**, Low).

---

## 3. User-voice evidence

### 3.0 Three biases — read before using any count below

1. **OpenLP is massively over-represented.** Its forum is public and machine-readable; the commercial products' are not. Its song module also genuinely lacks folders, so it structurally over-produces "users demanding folders". **Do not generalise OpenLP's folder demand to ProPresenter.**
2. **The ProPresenter complaints cluster in June–July 2019** on Capterra — a review-solicitation drive, not a spike in pain. They sit in the "Cons" field of otherwise 4–5 star reviews. Some predate Pro7's Quick Search.
3. **Reddit was completely unreachable** and the largest ProPresenter and MediaShout communities are login-walled Facebook groups. The biggest venues are simply unsampled.

### 3.1 What practitioners actually teach

Two third-party workflow guides were reachable. Both teach **file-system folder hierarchy plus naming conventions** — and both concern **media**.

- **DOCUMENTED (Med):** folders by content type for backgrounds, and **a folder for every Sunday** for foreground video. Teaches organising the file system *outside* ProPresenter; says nothing about playlists, categories, tags or search. — https://churchvisuals.com/article/propresenter-masterclass-part-two-organizing-your-video-image-library/
- **DOCUMENTED (Med):** "create a hierarchy of folders" mirrored into the software, plus "Rename media using logical naming conventions" and `YYYY-MM-DD` service folders. — https://www.churchmotiongraphics.com/blog/how-to-organize-your-church-media-library/

Three things in that second guide cut **against** the approach it recommends:

1. **Curation decays** — the "New" folder "can easily get unorganized if not maintained on a regular basis."
2. **It is a standing cost** — the scheme "will require time, commitment and **teaching everyone involved** how to follow your media library guidelines."
3. **Single-home forces a compromise** — for thematic bundles the guide advises keeping the pack intact rather than distributing items to where they thematically belong. (**INFERRED**, Med — my reading of the stated advice.)

An EasyWorship-specific guide by the same publisher falls back to the same place: "Using clear and descriptive file names will save you time when searching", e.g. `Blue_Abstract_Worship_Background.mp4`. — https://www.churchmotiongraphics.com/blog/tips-and-tricks-for-managing-your-easyworship-media-library/

### 3.2 Sustained demand for folders — 17 years of it, at low volume

Six OpenLP threads asking explicitly for folders, spanning **2008 to November 2025**. The span is the signal; the rate is roughly one thread every 2–3 years.

- **OBSERVED (High), 2008-07-22:** "I would like to see… an option of organization of the music with folders and sub-folders… we use more than 400 song of hymn and is better separat in other folder." — https://discuss.openlp.org/d/514-diferent-folders-for-songs
- **OBSERVED (High), 2020-02-25:** "Please allow also Folders in Media!… **otherwise we cannot use the Software. All the Media in One Folder is just too much.**" — https://discuss.openlp.org/d/5014-folders-in-all-categories
- **OBSERVED (High), 2022-01-06 (migrant from EasyWorship):** "looking for a way to sort them, **rather than scanning all of the files listed**." — https://discuss.openlp.org/d/5656-folders
- **OBSERVED (Med), 2023-05-08:** "We have books like our classic hymnbook (500 hymns), praise songs, kids camp songs, Christmas songs… **if they were all mixed up it would be a painful list to pull from**." — https://discuss.openlp.org/d/3726-multiple-song-books
- **OBSERVED (Med), 2015-08-26:** a user asks for "a tree-like representation with the ability for nested folders"; maintainer: "We've added this to images. I'll add a feature request… for the rest of the items." — https://discuss.openlp.org/d/2711-featreq-organize-library-items-in-folders
- **OBSERVED (Med), 2025-11-11, unanswered when read:** "I want to create some folders for songs in diferent languages." — https://discuss.openlp.org/d/7281-diferent-folders-for-songs

And the vendor-confirmed version, from MediaShout's own changelog: "**We have had many requests** to show additional subfolders within the main folder" — shipped March 2024 (§2.4).

### 3.3 Users at real scale

- **OBSERVED (High) — FreeShow, 3,500 songs:** "We have over 3500 songs in our database, and sometimes, **searching by name is not the most efficient way** - some songs are duplicated in different song books, etc." … "it would be nice if we could **search for metadata** too. Even better, if the song list was actually a **table, that we could sort** by name, but also by CCLI number, author etc." — https://github.com/ChurchApps/FreeShow/issues/1025
  - Note what this user asks for: **not folders and not tags — better search keys and a sortable table.**
- **OBSERVED (High) — OpenLP:** "we use several complete song books that contains each one several hundred of songs… it miss the functionnality to **search for a song that is in a song book and contains a keyword**." (2013-10-17) — https://discuss.openlp.org/d/2215-opensong-folders-like *(re-verified by me via the forum API)*
- **OBSERVED (Med) — OpenLP, ~4000 songs** when running duplicate detection — https://discuss.openlp.org/d/5745-how-does-duplicate-song-detection-work
- **OBSERVED (Med) — EasyWorship, current:** "**navigating the digital repository can lag a little as the repository grows**" (Technology Committee, Aug 2026) — https://www.capterra.com/p/101489/EasyWorship/
- **OBSERVED (Med) — EasyWorship, title collisions:** a request for custom columns "**especially if there are several hymns/songs with the same or very similar titles**" — https://support.easyworship.com/support/discussions/topics/24000022231

### 3.4 Users mixing up which mechanism is which — the direct evidence for question 1

- **OBSERVED (High) — the strongest single citation in this note. An OpenLP *developer* confused his own product's two mechanisms and corrected himself four minutes later.** At 22:49 on 2021-03-12: "When editing a song, there is a place for songbooks and a place for **category**. Think of songbooks as what hymnal and **categories** as Lent and Easter." At 22:53: "Sorry i said the wrong thing….**replace category with Topics** in my previous message! **Sorry about the confusion.**" — https://discuss.openlp.org/d/3726-multiple-song-books *(I re-verified this exchange and its four-minute gap directly against the forum's JSON API.)*
- **OBSERVED (High) — two tag-like mechanisms already shipped, and the user asked for folders anyway.** In 2023 a user posts a mockup requesting folders; another replies that the capability exists twice over: "OpenLP already provides the **Songbooks** functionality… and the **Topics** functionalities (to group songs by tags/themes/arbitrary sentences)." — https://discuss.openlp.org/d/5941-recommendation-adding-seperate-folders-to-the-songs-library-view
  - **This is the most decision-relevant datum for the owner's instinct.** Folders have a mental-model pull that an equivalent tag mechanism did not satisfy — even when the tags were already there and someone pointed them out.
- **OBSERVED (High) — the same substitution offered in 2008:** a user asks for folders and is answered with tags: "A request to 'tag' songs with multiple categories has already been made, which will hopefully **fulfil your request**." — https://discuss.openlp.org/d/514-diferent-folders-for-songs. Offered in 2008; users were still asking for folders in 2025.
- **OBSERVED (Med) — a tag mechanism shipped that search could not reach:** "I can see where I can designate a song topics but **I can't see where I can search by topic**… The drop down menu offers entire songs, title, lyrics, authors, songbooks and themes but **not topics**." Team: "This is currently not possible, but we have added this functionality…" — https://discuss.openlp.org/d/3044-search-for-songs-by-topics
- **OBSERVED (Med) — user reaches for tags to emulate folders, refused:** "**It seems like Topics are a way to get the categories I use**, but can the listings be restricted to a particular Topic?" Maintainer: "No, not at the moment." — https://discuss.openlp.org/d/2346-restrict-song-lists-to-specific-topics
- **OBSERVED (Med) — ProPresenter, a commercial product with a category mechanism:** "**Particularly organizing and tagging videos. It's simply not intuitive to use.**… If you use the file menu to import a clip, you can't select where it goes… **As a result we got a lot of videos loaded into the wrong categories and I have to do some sorting.**" (Worship Pastor, 2019-06-26) — https://www.capterra.com/p/170172/ProPresenter/reviews/?page=6
- **OBSERVED (Med) — category maintenance is itself a cost:** "The inability to delete or rename a library category without first changing every library item in that category to some other category" (2019-06-27) — https://www.capterra.com/p/170172/ProPresenter/reviews/?page=5
- **OBSERVED (Med) — MediaShout's two song stores confuse people.** Publicly-readable Facebook post titles (bodies login-walled): "Can someone explain the difference between the **Lyric library and the Cue library**"; "When I have a lyric loaded… **how do I save it to the 'Lyric Library'**"; and one whose own phrasing fuses the two: "songs you have created in **the MS 7 library cue**". — facebook.com/groups/MediaShoutUsers/posts/2473895609425676/, /3317738565041372/, /2546661352149101/
- **OBSERVED (Med) — EasyWorship, the thread title exists literally: "Folders vs. Collections?"** *(login-gated; snippet only)* — "Collections are preferred because you can set up collections that are searchable which you were not able to do in EW 2009", while "**some users still find the traditional folder approach easier**." — https://support.easyworship.com/support/discussions/topics/24000013548

**Honest negative on ProPresenter Library-vs-Playlist:** I looked specifically for users confused between Libraries and Playlists and **found no direct complaint**. A large corpus of explainer tutorials exists, but tutorials exist for everything. **Not evidence of confusion; do not cite it as such.**

**A discoverability failure worth separating from a confusion failure:** an EasyWorship user with "probably a hundred motion backgrounds" wrote "**I don't find anyway to add sub-groups in EW.** Do I really just have to scroll through hundreds of files dumped into one location?" — and later, after being shown Collections, "**I just didn't know where to look.**" The feature existed. — https://support.easyworship.com/support/discussions/topics/24000015141

**Counter-evidence — people using multiple mechanisms happily**

- **OBSERVED (Med):** one church runs song books *plus* title-prefix codes *plus* parallel Dropbox folders: "All this does make for a very full Songs folder! **But it is easy to navigate**." — https://discuss.openlp.org/d/3726-multiple-song-books
- **OBSERVED (Med) — ProPresenter users praising the library/playlist split:** "The BEST part of this product is the building of libraries and how easy it is to build a service or presentation from your libraries" (2021-10-15); "I love having a library of many, many songs and the ability to easily and quickly create a playlist" (2019-06-27) — https://www.capterra.com/p/170172/ProPresenter/reviews/
- **OBSERVED (Med) — MediaShout:** "I love the built in libraries and the ease of creating and updating the libraries to fit our needs." (2019-01-06); GetApp aggregate scores media library 3.9/5, content library 3.0/5.

### 3.5 Duplication and divergence — what the commissioning note asked for specifically

- **OBSERVED (High) — the single best thread found anywhere, and it cuts BOTH ways.** OpenLP users argue about whether editing a song inside a service should propagate to the library:
  - wants isolation: "there are times when a song may need to be edited… **only (one time) for a specific service**… I note however that this results in the song being edited (again) **directly in the song database**."
  - states the mental model: "when we select a song from the database and add it to service, **we are not COPYING**… It is only a **LINK or shortcut**."
  - wants the coupling: "I would **not** like to see this change as the default… I often make corrections to the songs. **I want those changes reflected in the song database as well.**"
  - proposes the resolution: "the Song Editor dialog should have **two Save buttons**, perhaps labelled 'Save' and 'Save (this service only)'."
  — https://discuss.openlp.org/d/2726-editing-song-in-service-file-always-changes-song-in-database (2015–2016)
  - **Users disagree about whether propagation is a bug or a feature. That disagreement *is* the finding** — it is not evidence that users want isolation.
  - Multi-user amplification (2011): "it saves the verse order in the database… could lead to problems **if you share one database with several team-members**… I don't want to check the song database for errors each month, because someone might have changed songs." — https://discuss.openlp.org/d/1390-working-with-songs-the-right-way
- **OBSERVED (High) — duplicates accumulate, and cleaning them is dangerous:** "Every time I set up a new service… **This results in numerous duplicate songs**… **It is time consuming to delete the duplicates, plus sometimes the wrong duplicated song is removed. It is aggravating.**" (2022) — https://discuss.openlp.org/d/5767-duplicate-songs. The built-in de-duplicator itself destroyed both copies: "I end up not having either of the songs left!" (2018), still "being worked" in 2019 — https://discuss.openlp.org/d/4097-deleting-duplicate-songs-deletes-all-copies-of-song
- **OBSERVED (Med) — ProPresenter sync breeds duplicate files:** "Library/Shared Folders/Cloud/Pro sync creates **multiple duplicate files… it's a nightmare**… I have iterations of the original creation, then an iteration with - '*filename*-Media Laptop Pro'…" (2020-01-12) — https://www.capterra.com/p/170172/ProPresenter/reviews/?page=7
- **OBSERVED (Med) + DOCUMENTED (High) — orphaned media accumulation spawned both a third-party tool and a vendor feature.** The tool author: "**ProPresenter makes it VERY easy to accumulate lots of media files that are no longer used or needed.**" — https://github.com/arlinsandbulte/Pro7-Media-Sweeper. Renewed Vision ships "Clean Up Unlinked Media" — https://support.renewedvision.com/hc/en-us/articles/360041815133-ProPresenter-Media-Management
- **OBSERVED (Med) — EasyWorship's *sanctioned* variant workflow mints a second library record.** The vendor-endorsed way to make a song arrangement is drag to schedule, edit, rename, then "Add to Resource"; staff confirmed a proper arrangement feature is "**not a feature in EW yet**". — https://support.easyworship.com/support/discussions/topics/24000019117. Snippet-only corroboration: users naming songs "Version 2"/"V2", and a request for a duplicate-song command.
  - **This is the real duplication-and-divergence vector in EasyWorship — and note it is *not* caused by multi-folder membership.**
- **Explicit non-finding on the commissioning note's hypothesis:** I looked for reports of *an item placed in two folders drifting out of sync* and **found none, in any product**. The reference-based models documented in §2 predict it cannot happen: EasyWorship collections hold references, MediaShout folders "point back to the All Folder", Proclaim boards do not remove the item from the browser. **UNKNOWN rather than disproven** — but the mechanism the note worried about is not the mechanism the evidence shows failing.
  - The nearest real trap is the opposite one, and it is about *perception*: EasyWorship snippet-only — "With a folder you can move an item to a subfolder, with a collection **it remains in the main collection when moved to the sub collection**." That is what makes users *believe* they have duplicates.

### 3.6 Organisational metadata being lost — a distinct risk class

- **OBSERVED (Med) — FreeShow, twice, independently:** "the tags, folders etc **didn't come with the songs**" (https://github.com/ChurchApps/FreeShow/issues/1112); and categories plus their actions and templates lost on **both** machines after a first cloud sync, unrecoverable from backup, the user "uncertain about where the program stores show category data" (https://github.com/ChurchApps/FreeShow/issues/2621).
- **OBSERVED (Med) — EasyWorship migration destroyed organising work:** a request that EW2009 image folders convert to EW6 collections on import — **7 supporters, closed, unactioned**. — https://support.easyworship.com/support/discussions/topics/6000033922. Also: collections are not portable between churches (6 supporters, closed) — .../6000035238. And "My Collections" are silently excluded from database backups (§2.3).
- **OBSERVED (Med) — MediaShout:** "Our church just updated media shout and **we've lost everything that we had**" (post title; body login-walled); and a 1.0-rated review: "you cannot import older MediaShout files without losing all changes. **Years of past work is lost.**" — https://www.capterra.com/p/140318/MediaShout/reviews/?page=2
- Applies equally to folders and to tags — **not a folders-vs-tags argument.**

### 3.7 How people actually cope — and it is not the product's structure

Four independent churches converged on the same technique: **encode structure into the item's title, then search for the prefix.**

- **OBSERVED (High) — an OpenLP developer officially recommends it:** "I agree it would be great to have folders in all the media libraries, but until that is implemented remember you can **group items in a library by adding a prefix to the titles**… try `<Lent>` and `<Scripture>`… By enclosing the **tag** in `<>` they should not show up in the Footers." (2020-02-26) — https://discuss.openlp.org/d/5014-folders-in-all-categories. He calls the title prefix a "tag": users are hand-rolling a tag system inside a filename.
- **OBSERVED (High) — deployed church practice:** "use a **prefix for each song book and use that in the title**… '1 God Can Make It Right' becomes '**RMU-1** God Can Make It Right'. **Filtering for a specific songbook is done by searching for the prefix only. At least that's how we do it at our church.**" (2024-07-16) — https://discuss.openlp.org/d/5724-possible-to-collapse-song-books
- **OBSERVED (Med):** numbering schemes ("I start the song number with 1001… Then you can search by name or number"); three-letter hymnbook codes ("TIS675", "CAH023"); liturgy codes ("Lit_01_Gathering_Lent") — plus **separate Dropbox folders per hymn book**, structure built *outside* the app. — https://discuss.openlp.org/d/3726-multiple-song-books
- **OBSERVED (Med) — EasyWorship users rename files to game the collection rules:** "instead of adding it to EW and then either dragging and dropping it to the collection **or renaming it so it will filter to the collection**" (10 likes, comments closed) — https://support.easyworship.com/support/discussions/topics/6000023488
- **OBSERVED (Med) — a church's internal wiki instructs search-first for ProPresenter 7:** "**Finding Content: Use the search bar within the Library.**" (modified 2025-08-29) — https://wiki.necommunity.church/xwiki/bin/view/Tech/Media/ProPresenter%207/
- Proclaim's vendor advice matches: rename your items so you can find them later (§2.2).

**Technique tally in the reachable corpus:** naming conventions ×5 · search ×2 · structure built *outside* the app ×1 · **successfully organising a large library using the product's own structural features ×0.**

Read that last count with bias #1: the corpus is dominated by OpenLP, whose song module *has* no structural feature to succeed with. But note it is corroborated in EasyWorship, which *does* have one.

### 3.8 Is search actually good enough? Both directions, honestly

**Direction A — search substitutes for structure. Real, but thin.** Three user statements, all of them workarounds forced by *missing* structure (the prefix-searchers above), plus a maintainer offering search in place of grouping: "**there isn't currently a grouping of songs, but you can do a search by songbook.** It may not be what you're looking for, but maybe it's enough for now?"

**I found no user saying anything like "I never use folders, I just type the name."** That pattern did not surface. Reporting its absence rather than stretching weaker quotes to fill it.

**Direction B — search is inadequate and people want structure. Better sourced.**

- **OBSERVED (High), and note the library size:** "**The search function is very slow. We have only 372 documents in our library, but the latency is very noticeable**… queries should add priority to exact title matches… **the song that I want, which exactly matches the query will be all the way at the bottom of the results because it begins with a Y.**" (2019-06-27) — https://www.capterra.com/p/170172/ProPresenter/reviews/?page=4
  - **372 documents is a small library.** This is a *ranking* failure, not a scale failure — the problem does not wait for a big library to appear.
- **OBSERVED (High):** "documents that may have those key words in them, but not in their titles show up before the actual song… **It typically makes us fill in most, if not all of a song name before the song itself shows up**." (2019-06-27) — same URL
- **OBSERVED (High) — EasyWorship's hidden mode toggle** (§2.3): a user uninstalled and reinstalled the product over a search-scope setting.
- Plus the six folder-demand threads and the vendor's own "Why do so many songs show up when I search?" article.

**Direction C — recency. One user finding, and it is a complaint about its absence.**

- **OBSERVED (Med):** "I don't like how **you can't organise the playlist bins**. Many times, you'll have to **scroll to the very end of your background slides to get the newest ones instead of them coming up first**." (2024-12-19) — https://www.capterra.com/p/170172/ProPresenter/reviews/
- A search of the OpenLP forum for recency / "last used" concepts found **nothing relevant.**
- **This is one data point. Do not build on it.** It is worth flagging precisely because §2 shows three products *ship* recency affordances that no user in this corpus is observed praising or requesting. **Shipped ≠ used.**

### 3.9 The vendor as user-proxy

Some of the strongest "users struggle at scale" evidence is vendors conceding the problem in their own materials — high-quality, because a vendor documents what generates tickets:

- Renewed Vision: "if you are searching for a specific song and you have a large library, this may result in your desired Document far down in the search results."
- MediaShout: "**We have had many requests** to show additional subfolders" (shipped 2024); and "Modify Search boxes to behave in more similar ways" (2025).
- EasyWorship: repeated release-note fixes for "collections not limiting results correctly when you have rules for individual fields".
- EasyWorship's Head of Training on why the organisation requests sit closed: "**we have been neglecting this. I think It's gotten so overwhelming, nobody wants to take it on.**" — https://support.easyworship.com/support/discussions/topics/24000016895

---

## 4. The two decision-relevant questions

### Question 1 — Do folders and tags coexisting actually work, or do users find it confusing?

**Answer, in three parts.**

**(a) The market has largely stopped shipping true single-home folders — the distinction the question assumes has already collapsed.**

Six of the seven products let one item live in many containers (§1). And in the products that call that mechanism a "folder", the vendor documentation goes out of its way to say it is not one:

- MediaShout: "**The separate folders are simply pointing back to the All Folder, so you can have the same lyric in many different folders.**"
- EasyWorship: "**The same media item may can appear in multiple collections.**"
- Proclaim: "**Adding media to a board does not remove it from the main browser pane. A piece of media can be on multiple boards.**"

Only FreeShow ships a true single-home item container (`category: null | ID`) — and it is flat, not a tree. **Where real hierarchy exists, it consistently sits over the *grouping* object, not the item** (ProPresenter's Group Folders over playlists; FreeShow's nested folders over projects; EasyWorship's folders, which can hold only collections and *never* resources).

**(b) There IS observable confusion — six instances found — and it tracks the metaphor, not the coexistence.**

The clearest finding in this note is that **calling a many-to-many mechanism a "folder" is what confuses people**, and the failure modes are concrete:

- An **OpenLP developer** publicly mixed up Song Books and Topics and corrected himself four minutes later (§3.4).
- **MediaShout's** delete semantics punish the folder model directly: deleting from a custom folder removes one membership; deleting from the All Folder **destroys the lyric everywhere** — via the same trash-can icon.
- **EasyWorship's** "move to sub-collection leaves it in the parent" makes users *believe* they have duplicates.
- **ProPresenter** users load "a lot of videos into the wrong categories".

Both products that ship two mechanisms **without** explaining the division of labour (OpenLP's four; FreeShow's category-plus-undocumented-tags) show users struggling. The two that **do** explain it — Proclaim ("tags feed search, boards are shared shelves") and EasyWorship ("tags are a field, collections are a saved query over fields") — produced no comparable confusion evidence in my sweep, though for Proclaim that null is weak because its forum is unreachable.

**(c) The uncomfortable counter-finding, which I want to state plainly because it cuts against the tidy conclusion: users asked for folders anyway.**

In OpenLP, a tag mechanism was offered as the answer to a folder request in **2008**, and again in **2023** — and users were still filing folder requests in **November 2025**. In the 2023 thread the user was told, correctly, that two tag-like mechanisms already shipped. He had asked for folders regardless. **Folders have a mental-model pull that an equivalent labelling mechanism did not satisfy.**

**Evidence strength: good for the mechanics, moderate for the confusion, and I cannot give you a rate.** The mechanism claims are `OBSERVED` at schema and source level or quoted verbatim from vendor docs. The confusion claims rest on six citable instances — real and independently re-verified for OpenLP, but six. Whether these represent widespread struggle or a few unlucky users is **UNKNOWN**, and the venues that would tell us (Reddit, Facebook groups, vendor forums) are unreachable.

**Counter-evidence retained:** the practitioner guides teach plain single-home hierarchies and find them teachable; one church happily runs song books *plus* title codes *plus* Dropbox folders together and calls it "easy to navigate"; several ProPresenter reviewers name the library/playlist split as the product's best feature.

### Question 1a — the finding I did not go looking for

**A labelling mechanism is worth only what the query language can combine.**

OpenLP has by some distance the richest many-to-many labelling in this set — topics, multi-book membership with per-book hymn numbers, roled authors. It is the strongest "tags work" case available. Its users still hack song titles with three-letter codes and reserved numeric ranges. The reason is stated precisely by a user in 2013:

> "it miss the functionnality to **search for a song that is in a song book and contains a keyword**."

Because OpenLP's nine search modes are **mutually exclusive**, a Topic can never narrow a lyric search. The labels are applied, stored correctly, and query-visible one at a time — and are therefore nearly useless for the actual retrieval job. One product in the set solves exactly this: **EasyWorship's Collections are saved queries with Match All/Any over multiple fields**, which is the compound query OpenLP's users are asking for.

Compare, too, the FreeShow user with 3,500 songs, who asked not for folders or tags but for **more searchable keys and a sortable table**.

(Evidence: `OBSERVED` at code level for the exclusivity; `OBSERVED` for the complaint and the title hacks; `DOCUMENTED` for EasyWorship's rule builder. The causal link between them is my **INFERRED** reading — high confidence, and the most useful thing in this note.)

### Question 2 — Is the pain the owner describes usually solved by STRUCTURE at all?

**Answer: the evidence does not support a clean "no", and I am not going to give you one. It splits by source type, and the split is itself the finding.**

**What the products do points away from structure:**

1. **No product in the set puts a folder tree over items.** Where hierarchy exists it is over the grouping object. OpenLP rejected folders explicitly; Quelea has nothing; ProPresenter's item library has been flat in both documented versions. (`DOCUMENTED`, High)
2. **When ProPresenter addressed "content in too many places", it shipped a global search box** — Quick Search deliberately spans every Library from one shortcut. (`DOCUMENTED`, High)
3. **When vendors document the large-library failure, the remedies are non-structural** — change the sort, restrict the search scope. (`DOCUMENTED`, High)
4. **Proclaim's item library — the closest analogue to SelahCue's decks — has no folders, no tags and no boards.** Retrieval is a search modal, a type filter, and a dated recent list; the vendor's own advice is **naming**. (`DOCUMENTED`, High)
5. **ProPresenter deliberately de-maintained its one taxonomy** (self-pruning Categories, list removed from Preferences, explicitly modelled on iTunes genres). (`DOCUMENTED`, Med)
6. **The coping tally is naming ×5, search ×2, product structure ×0.** (§3.7)

**What users say points toward structure, and it is better-sourced than I expected:**

1. **Direction B outweighs Direction A** (§3.8). Evidence that search *substitutes* for structure is thin — three statements, all workarounds forced by missing structure, and **not one user said "I just search for it"**. Evidence that search is *inadequate* is stronger and more specific.
2. **The most precise complaint is about ranking at 372 documents** — a *small* library. If that generalises, better ranking beats more structure, and the problem arrives early rather than at scale.
3. **Folder demand is sustained over 17 years** and vendor-confirmed ("many requests" — MediaShout, shipped 2024).
4. **Every product does ship *some* grouping.** Nobody ships bare search alone.
5. **Recency is shipped by three products and requested by essentially nobody** in this corpus — the single recency data point is a complaint about its *absence* in a media bin. My earlier reading over-weighted recency on vendor-documentation evidence; the user voice does not corroborate it. **Shipped ≠ used.**

**Honest reading.** The products that handle large libraries best solve *retrieval* with search, ranking and query composition, and use grouping for *composition and sharing* rather than for storage. That pattern is consistent across all seven and is the strongest claim I can support. But **it is a pattern in what vendors built, and the user voice does not straightforwardly endorse it** — users keep asking for structure, and the sharpest complaints are about search quality rather than about missing folders. Those two facts are in tension. **I am reporting the tension rather than resolving it**, because resolving it on this evidence would be exactly the dressed-up verdict the commissioning note warned against.

**What would actually settle it** is in §6 — and note that the commissioning note's own proposed card-sort would answer the multi-home question, but *not* this one.

---

## 5. Implications (not recommendations)

Stated as implications for the decision Priya owns. **None of this is a recommendation about what SelahCue should build.**

- The owner's pain — "it's a pain to search for one item in many places" — is close to what **Quick Search** (one search across all stores) was built for in the market leader. But the sharpest user complaints in this corpus are about **search ranking**, not about search coverage, and they appear at ~372 items.
- If a folder tree is considered: comparable products put hierarchy over the **grouping** object, not the item. SelahCue already has that object — `ServicePlan`.
- If a many-to-many mechanism is considered: **the naming is load-bearing.** Every documented confusion and data-loss trap in §4(b) comes from a many-to-many mechanism wearing a folder's name.
- If both are considered: the two products that explain the division of labour give each mechanism a *different job* (index vs shelf; field vs saved query) rather than two ways to file the same thing.
- Question 1a suggests a labelling mechanism without compound query may not repay its curation cost. EasyWorship is the one product here that has compound query.
- §3.6 is a risk that applies to any grouping design: organisational metadata that lives apart from the item gets destroyed by sync, migration and backup — reported in three products.

---

## 6. Limitations, access failures, and open questions

**Method:** WebSearch + WebFetch against public vendor documentation, support KBs, release notes, public source repositories and schemas, community forums and third-party guides; plus `curl` retrieval of **publicly-archived** copies via the Internet Archive where a formerly-public page is now gated, and the OpenLP forum's public JSON API. **No trials purchased, no accounts created, no login or paywall bypassed.** No proprietary code, branding or UI was copied.

**Access failures — these bound the confidence of everything above:**

| What could not be reached | Effect |
|---|---|
| **Reddit — entirely blocked** across every attempt | The single biggest gap. Almost certainly the largest venue for this conversation, wholly unsampled |
| **Facebook groups** (ProPresenter, MediaShout users) — login-walled | Only post *titles* readable. The largest communities for two products are effectively unquotable |
| `support.renewedvision.com` and `learn.renewedvision.com` now redirect to a **Zendesk login** | All ProPresenter KB evidence is from **publicly archived copies**; reflects the article as archived, not necessarily as it reads today |
| Only the **ProPresenter 6** guide is archived | ProPresenter item-library detail is disproportionately **version 6**; per-version claims are flagged individually |
| `files.renewedvision.com/.../Pro7UserGuide.pdf` — **HTTP 521 on every attempt**, confirmed repeatedly | The authoritative Pro7 reference was unavailable |
| `support.proclaim.logos.com` — **HTTP 403** to automated fetches | Proclaim evidence is from archived copies and older `support.faithlife.com` URLs |
| EasyWorship `[v6]`/`[v7]` archive threads — login-gated | Nine EasyWorship claims are **snippet-only** and flagged as such inline |
| EasyWorship's KB search and Collections articles are **video-only with no transcript** | Their contents are UNKNOWN |
| MediaShout has **no public user forum**; MS5/MS6 guides are dead and unarchived | MediaShout user voice is post-titles and review sites only |
| Capterra returns an empty body to automated fetches from my session | Review quotes here came via a research pass that reached the rendered pages; I could not re-verify them myself |

**Top open questions, in the order they would change a decision:**

1. **Does editing a ProPresenter presentation propagate to every playlist referencing it?** The divergence question the commissioning note asked for directly, and no primary source was retrievable. Ten minutes of hands-on use settles it.
2. **What is the *rate* of folders-vs-tags confusion?** Six instances is enough to prove the failure mode exists, not enough to size it. An hour in the ProPresenters Facebook group would be worth more than any further doc reading.
3. **Is the owner's pain a ranking problem or a structure problem?** The 372-document complaint suggests ranking. This is testable against SelahCue's own search before any structural work is scoped.
4. **Do document Categories still exist in ProPresenter 7?** All reachable Category documentation is legacy Pro6.
5. **Do Proclaim Boards nest? Do MediaShout lyric folders nest?** No nesting language found either way for either.
6. **EasyWorship Scripture collections** — two vendor sources from the same year contradict each other (§2.3).

**Volume note, stated plainly.** This note rests substantially on **vendor documentation and public source code**, supplemented by a **modest and lopsided** body of user voice: roughly 15 OpenLP threads, ~9 ProPresenter reviews, ~12 EasyWorship threads, a handful of MediaShout review lines and post titles, and a few GitHub issues. **OpenLP is over-represented by a wide margin.** The commissioning note asked specifically for evidence of users duplicating items across folders and complaining about divergence — **I did not find that, in any product**, and §3.5 explains why the documented reference-based models predict it cannot happen. What I found instead is a *different* duplication vector (variant workflows minting second records) and a *perception* trap (multi-membership mistaken for duplication). **Nothing here should be read as a measured user-demand signal.**

---

## 7. Evidence index

| # | Claim | Label | Source |
|---|---|---|---|
| 1 | ProPresenter: multiple Libraries; purpose is separation | DOCUMENTED-High | https://support.renewedvision.com/hc/en-us/articles/360041811293-Using-Multiple-Libraries-in-ProPresenter |
| 2 | A Library is a disk folder you browse to and link | DOCUMENTED-High | https://support.renewedvision.com/hc/en-us/articles/360011693974-How-do-I-add-multiple-Libraries-to-ProPresenter |
| 3 | Documents single-home across Libraries; Libraries don't nest | INFERRED-High | follows from #2; not stated |
| 4 | Documents inside a Library are a flat list | DOCUMENTED-High | https://learn.renewedvision.com/propresenter6/introduction-to-propresenter/the-library |
| 5 | Group Folders organise **playlists**, not documents | DOCUMENTED-High | https://learn.renewedvision.com/propresenter6/introduction-to-propresenter/playlists |
| 6 | Pro7 Media Bin has playlists and playlist folders | DOCUMENTED-High | https://support.renewedvision.com/hc/en-us/articles/360041345954-Understanding-The-ProPresenter-User-Interface |
| 7 | Categories sort only; dynamic/self-pruning; removed from Preferences | DOCUMENTED-High | https://support.renewedvision.com/hc/en-us/articles/360011514894-Using-Categories-for-Library-documents-in-ProPresenter-6 |
| 8 | Categories single-select | INFERRED-High | dropdown assignment + single-value filter, same URL |
| 9 | Any presentation from any Library into any Playlist | DOCUMENTED-High | see #1 |
| 10 | Edits propagate to all referencing playlists | **UNKNOWN** | no primary source retrievable |
| 11 | Whether Categories persist in Pro7 | **UNKNOWN** | all reachable docs Pro6-banner-marked |
| 12 | Search covers titles **and** slide text, ranked | DOCUMENTED-High | https://support.renewedvision.com/hc/en-us/articles/360011610593-Why-do-so-many-songs-show-up-when-I-search |
| 13 | Vendor concedes large-library search failure; remedies non-structural | DOCUMENTED-High | same URL |
| 14 | Sort by Title / Category / **Last Used Date** / Search Rank | DOCUMENTED-High | see #4 |
| 15 | Quick Search spans all Libraries + SongSelect + MultiTracks | DOCUMENTED-High | https://support.renewedvision.com/hc/en-us/articles/9808905773715-How-to-Use-Quick-Search-within-ProPresenter |
| 16 | Smart Playlists mirror a disk folder; media only | DOCUMENTED-Med | search corpus + https://www.youtube.com/watch?v=HLUCChgqQTE |
| 17 | Proclaim: media can be on **multiple** boards; board add is non-destructive | DOCUMENTED-High | https://support.faithlife.com/hc/en-us/articles/360007126952-Organize-your-media-with-boards |
| 18 | Boards team-shared; default Favorites board; managed in "facet view" | DOCUMENTED-High | same URL |
| 19 | Tags many-per-item, system-suggested, framed as a search aid | DOCUMENTED-High | https://support.faithlife.com/hc/en-us/articles/360007128472-Media-Browser |
| 20 | Sorts usage-derived (popularity/relevance/trending); colour facets | DOCUMENTED-High | same URL |
| 21 | Suggested Media derived from the current presentation | DOCUMENTED-High | same URL |
| 22 | Recent Media facet added in Proclaim 4.0 | DOCUMENTED-High | https://faithlife.github.io/ProclaimReleaseNotes/4.0/ReleaseNotes.html |
| 23 | Reuse = search box + service-item-type filter; no folders, no tags | DOCUMENTED-High | https://support.proclaim.logos.com/hc/en-us/articles/19863521020941-How-Do-I-Reuse-Items |
| 24 | Proclaim's findability advice for items is **naming** | DOCUMENTED-High | same URL |
| 25 | EasyWorship folders nest but **cannot hold resources**; leaves are Collections | DOCUMENTED-High | EW7 Manual, https://support.easyworship.com/support/solutions/articles/24000020510-easyworship-7-manual |
| 26 | "The same media item may can appear in multiple collections" | DOCUMENTED-High | https://support.easyworship.com/support/solutions/articles/24000020385-quick-start-guide |
| 27 | Collections hold references; deleting the source deletes it everywhere | DOCUMENTED-High | EW7 Manual |
| 28 | Collections are **saved queries** — Match All/Any over Title, Author, Copyright, Administrator, Words, Any Field, Directory | DOCUMENTED-High | https://easyworship.com/blog/creating-and-using-collections + EW7 Manual |
| 29 | Division of labour: tags are a field, collections query fields | DOCUMENTED-High | Quick Start Guide |
| 30 | Tags exist on media; **not** on songs (request Deferred) | DOCUMENTED-High / OBSERVED-Med | https://support.easyworship.com/support/solutions/articles/24000020404-videos ; https://support.easyworship.com/support/discussions/topics/24000016808 |
| 31 | Search mode hidden behind an icon toggle; scope sticky and invisible | DOCUMENTED-High + OBSERVED-High | Quick Start Guide ; https://support.easyworship.com/support/discussions/topics/24000022268 |
| 32 | EasyWorship Scripture collections — vendor sources contradict | **CONTRADICTORY** | https://easyworship.com/blog/creating-and-using-collections vs https://easyworship.com/blog/7-easyworship-basics |
| 33 | Sanctioned EasyWorship variant workflow mints a second library record | OBSERVED-Med | https://support.easyworship.com/support/discussions/topics/24000019117 |
| 34 | MediaShout: "same lyric in many different folders" | DOCUMENTED-High | https://mediashout.com/docs/mediashout-7-user-guide/index-of-all-functions/m-n-o/ |
| 35 | Delete from custom folder ≠ delete from All Folder (destroys everywhere) | DOCUMENTED-High | https://mediashout.com/docs/mediashout-7-user-guide/index-of-all-functions/c-d/ |
| 36 | Media subfolders added v7.6.2 after "many requests"; media is single-home | DOCUMENTED-High | https://support.mediashout.com/991981-What-has-changed-in-v762 |
| 37 | MediaShout lyric search is **exact match**, folder-scoped | DOCUMENTED-High | https://mediashout.com/docs/mediashout-7-user-guide/index-of-all-functions/s/ |
| 38 | Three search boxes behave differently; vendor is fixing it | DOCUMENTED-High | https://support.mediashout.com/257018-What-has-changed-in-v770 |
| 39 | Vendor advice creates two competing song stores (My Library vs Cues Library) | DOCUMENTED-Med | https://mediashout.com/docs/mediashout-7-user-guide/advanced-tools/cues-library/ |
| 40 | No MediaShout tag mechanism found in ~20 official sources | not found (not disproven) | MS7 guide index pages, KB, changelogs |
| 41 | OpenLP has no folders, by design | DOCUMENTED-High | https://discuss.openlp.org/d/3470-song-folder *(re-verified by me)* |
| 42 | Topics / Song Books / Authors all many-to-many; Theme single-valued | OBSERVED-High | https://gitlab.com/openlp/openlp/-/raw/master/openlp/plugins/songs/lib/db.py |
| 43 | Nine search modes, **mutually exclusive** | DOCUMENTED-High / INFERRED-High | https://manual.openlp.org/library.html ; `mediaitem.py` |
| 44 | The manual explains none of Topics/Song Books/Themes at assignment | OBSERVED-High | https://manual.openlp.org/songs.html |
| 45 | The manual teaches an alternate-title string hack for grouping | DOCUMENTED-High | https://manual.openlp.org/_sources/songs.rst.txt |
| 46 | OpenLP developer confused Song Books with Topics, corrected 4 min later | OBSERVED-High | https://discuss.openlp.org/d/3726-multiple-song-books *(re-verified by me)* |
| 47 | Tags offered as the answer to folder requests in 2008 and 2023; folders still requested 2025 | OBSERVED-High | d/514, d/5941, d/7281 |
| 48 | Link-vs-copy divergence debate; users disagree on whether propagation is a bug | OBSERVED-High | https://discuss.openlp.org/d/2726-editing-song-in-service-file-always-changes-song-in-database |
| 49 | FreeShow: `category: null \| ID` (single-home), `tags?: string[]` (many) | OBSERVED-High | https://raw.githubusercontent.com/ChurchApps/FreeShow/main/src/types/Show.ts *(verified by me)* |
| 50 | FreeShow projects nest; categories do not | DOCUMENTED-High / OBSERVED-High | https://freeshow.app/docs/projects ; `Tabs.ts` |
| 51 | FreeShow docs teach categories, never tags | OBSERVED-Med | https://freeshow.app/docs/drawer |
| 52 | FreeShow sorts by name / number / modified; Archive hides a category | OBSERVED-High / DOCUMENTED-High | `Shows.svelte` ; https://freeshow.app/docs/drawer |
| 53 | FreeShow user with 3,500 songs asks for search keys + sortable table | OBSERVED-High | https://github.com/ChurchApps/FreeShow/issues/1025 |
| 54 | Quelea song entity has no organisational field at all | OBSERVED-High | `Song.java` |
| 55 | Quelea tag strings exist with no implementing code path | **CONTRADICTORY / UNKNOWN** | `gb.lang` vs `SongSearchIndex.java`, `LibrarySongList.java` |
| 56 | ProPresenter search ranking fails at **372 documents** | OBSERVED-High | https://www.capterra.com/p/170172/ProPresenter/reviews/?page=4 |
| 57 | ProPresenter users load videos into the wrong categories | OBSERVED-Med | https://www.capterra.com/p/170172/ProPresenter/reviews/?page=6 |
| 58 | ProPresenter sync creates duplicate files | OBSERVED-Med | https://www.capterra.com/p/170172/ProPresenter/reviews/?page=7 |
| 59 | Orphaned media accumulation: third-party tool + vendor "Clean Up Unlinked Media" | OBSERVED-Med / DOCUMENTED-High | https://github.com/arlinsandbulte/Pro7-Media-Sweeper ; https://support.renewedvision.com/hc/en-us/articles/360041815133-ProPresenter-Media-Management |
| 60 | Practitioner guides teach folder hierarchy + naming; warn of decay and training cost | DOCUMENTED-Med | churchvisuals.com ; churchmotiongraphics.com |
| 61 | Coping tally: naming ×5, search ×2, product structure ×0 | OBSERVED-Med | §3.7 sources |
| 62 | Organisational metadata destroyed by sync / migration / backup, in 3 products | OBSERVED-Med | FreeShow #1112, #2621 ; EW 6000033922 ; MediaShout reviews |
| 63 | No report found, in any product, of an item in two folders drifting out of sync | **UNKNOWN** | §3.5 — reference-based models predict it cannot |
| 64 | Rate of folders-vs-tags confusion | **UNKNOWN** | Reddit blocked, Facebook login-walled, vendor forums gated |
